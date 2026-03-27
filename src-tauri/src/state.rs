use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tokio::sync::{Mutex as TokioMutex, RwLock, Semaphore, mpsc};
use dashmap::DashMap;

use crate::commands::transcription::SegmentPayload;
use crate::config::{AppConfig, PartialAppConfig, apply_partial, default_models_path, normalized_app_config};
use crate::error::AppError;
use crate::models::{DownloadCommand, ModelsToml};
use crate::models::registry::{model_file_path, parse_variant_id};
use crate::storage::db::Database;
use crate::timeline::manager::TimelineManager;
use crate::transcription::batch::{BatchCommand, BatchQueue};
use crate::transcription::engine::WhisperEngine;
use crate::transcription::pipeline::TranscriptionCommand;
use crate::workspace::manager::WorkspaceManager;
use crate::llm::{
    engine::LlmEngine,
    tasks::PromptTemplates,
    worker::{LlmTaskControl, LlmTaskMessage},
    LlmEngineStatus,
};

#[derive(Debug, Clone)]
pub struct RecordingSessionMeta {
    pub session_id: String,
    pub started_at_ms: i64,
    pub is_paused: bool,
}

pub struct AppState {
    // M1–M3 fields
    pub app_data_dir: Arc<PathBuf>,
    pub db: Arc<Database>,
    pub workspace_manager: Arc<WorkspaceManager>,
    pub timeline: TimelineManager,
    pub config: Arc<RwLock<AppConfig>>,
    pub model_config: Arc<ModelsToml>,
    pub download_tx: mpsc::Sender<DownloadCommand>,

    // M4: realtime transcription pipeline
    /// SyncSender 满足 Send，可从 std::thread 和 tokio 任务中发送
    pub transcription_tx: std::sync::mpsc::SyncSender<TranscriptionCommand>,

    /// Whisper 引擎（std Mutex：只在 spawn_blocking / 同步上下文中访问，不跨 await）
    pub whisper_engine: Arc<Mutex<Option<WhisperEngine>>>,

    /// 发送 () 可停止正在运行的 cpal 采集线程（stream 保留在其创建线程，不跨线程）
    pub capture_stop_tx: Arc<std::sync::Mutex<Option<std::sync::mpsc::SyncSender<()>>>>,

    /// 实时 segment 缓存（session_id → segments），供 stop_realtime 读取写 DB
    /// std Mutex：TranscriptionWorker（非 async）写，stop_realtime 读（不跨 await 持锁）
    pub segments_cache: Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,

    /// 实时 PCM 缓存（session_id → 16kHz f32 samples），用于 WAV 写入
    /// std Mutex：resampler std::thread 写，stop_realtime 读（不跨 await 持锁）
    pub pcm_cache: Arc<Mutex<HashMap<String, Vec<f32>>>>,

    /// 当前录音会话元数据：录音控制、轮询状态、resampler 闸门都以此为唯一真相
    pub recording_meta: Arc<Mutex<Option<RecordingSessionMeta>>>,

    /// resampler 线程完成信号（stop_realtime 等待此信号后再发 Stop 给 pipeline）
    /// 用于解决停止竞态条件：确保所有 AudioChunk 发送完毕后再执行最终 flush
    pub resampler_done_rx: Arc<TokioMutex<Option<tokio::sync::oneshot::Receiver<()>>>>,

    /// 原子停止标志：stop_realtime 设为 true，resampler 线程轮询并退出
    /// 比依赖 raw_rx disconnect 更可靠：macOS CoreAudio 不立即停止回调
    pub resampler_stop: Arc<std::sync::atomic::AtomicBool>,

    /// 最新音频 RMS 电平（f32 bits 存储于 AtomicU32）
    /// 由 VAD resampler 线程写入，get_audio_level 命令读出供前端轮询
    pub audio_level: Arc<std::sync::atomic::AtomicU32>,

    /// M7: 批量转写队列命令发送端
    pub batch_tx: mpsc::Sender<BatchCommand>,

    /// M7: 批量转写队列共享状态，只读查询直接访问这里
    pub batch_queue: Arc<BatchQueue>,

    // M5: LLM Worker fields

    /// LLM Worker 消息发送端
    pub llm_tx: mpsc::Sender<LlmTaskMessage>,

    /// LLM 引擎实例（Option：模型未加载时为 None）
    pub llm_engine: Arc<TokioMutex<Option<Arc<LlmEngine>>>>,

    /// LLM 任务控制表（task_id → 控制对象）
    pub llm_task_controls: Arc<DashMap<String, Arc<LlmTaskControl>>>,

    /// 单 permit 串行化真正的 LLM 推理，避免多任务并发占满内存
    pub llm_generation_permit: Arc<Semaphore>,

    /// Prompt 模板（启动时一次性加载，只读）
    pub prompt_templates: Arc<PromptTemplates>,

    /// LLM 引擎状态
    pub llm_engine_status: Arc<TokioMutex<LlmEngineStatus>>,
}

impl AppState {
    pub fn models_dir(&self) -> PathBuf {
        default_models_path(self.app_data_dir.as_ref())
    }

    pub fn default_config(&self) -> AppConfig {
        normalized_app_config(AppConfig::default(), self.app_data_dir.as_ref())
    }

    pub fn normalize_config(&self, config: AppConfig) -> AppConfig {
        normalized_app_config(config, self.app_data_dir.as_ref())
    }

    pub async fn persist_config(&self, config: AppConfig) -> Result<AppConfig, AppError> {
        let normalized = self.normalize_config(config);
        let serialized = serde_json::to_string(&normalized)
            .map_err(|e| AppError::Storage(format!("serialize config: {e}")))?;

        self.db.save_setting("app_config", &serialized).await?;

        let mut guard = self.config.write().await;
        *guard = normalized.clone();
        Ok(normalized)
    }

    pub async fn update_config(&self, partial: PartialAppConfig) -> Result<AppConfig, AppError> {
        let mut next = {
            let guard = self.config.read().await;
            guard.clone()
        };
        apply_partial(&mut next, partial);
        self.persist_config(next).await
    }

    /// 根据当前 AppConfig 尝试热加载 WhisperEngine。
    /// 调用时机：模型下载完成、切换激活模型。
    /// 返回 true = 加载成功；false = 文件不存在或加载失败。
    pub async fn try_load_whisper(&self) -> bool {
        let (model_dir, active_model) = {
            let cfg = self.config.read().await;
            (self.models_dir(), cfg.active_whisper_model.clone())
        };

        let Some((model_type, variant_name)) = parse_variant_id(&active_model) else {
            return false;
        };
        let Some(variant_cfg) = self.model_config.whisper.variants.get(variant_name) else {
            return false;
        };
        let model_path = model_file_path(&model_dir, model_type, variant_name, &variant_cfg.url);
        if !model_path.exists() {
            log::debug!("[whisper] model file not found: {}", model_path.display());
            return false;
        }

        let engine_arc = Arc::clone(&self.whisper_engine);
        match tokio::task::spawn_blocking(move || WhisperEngine::new(&model_path)).await {
            Ok(Ok(engine)) => {
                *engine_arc.lock().unwrap() = Some(engine);
                log::info!("[whisper] engine loaded: {active_model}");
                true
            }
            Ok(Err(e)) => {
                log::warn!("[whisper] load failed: {e}");
                false
            }
            Err(e) => {
                log::warn!("[whisper] spawn_blocking panicked: {e}");
                false
            }
        }
    }

    /// 根据当前 AppConfig 尝试热加载 LlmEngine。
    /// 调用时机：模型下载完成、切换激活模型、应用启动。
    /// 返回 true = 加载成功；false = 文件不存在或加载失败。
    pub async fn try_load_llm(&self) -> bool {
        let (model_dir, active_model, llm_context_size) = {
            let cfg = self.config.read().await;
            (self.models_dir(), cfg.active_llm_model.clone(), cfg.llm_context_size)
        };

        let Some((model_type, variant_name)) = parse_variant_id(&active_model) else {
            return false;
        };
        let Some(variant_cfg) = self.model_config.llm.variants.get(variant_name) else {
            return false;
        };
        let model_path = model_file_path(&model_dir, model_type, variant_name, &variant_cfg.url);
        if !model_path.exists() {
            log::debug!("[llm] model file not found: {}", model_path.display());
            return false;
        }

        // Check-and-set Loading status under lock to prevent concurrent double-load.
        {
            let mut status = self.llm_engine_status.lock().await;
            if matches!(*status, LlmEngineStatus::Loading { .. }) {
                log::debug!("[llm] already loading, skipping duplicate load");
                return false;
            }
            *status = LlmEngineStatus::Loading {
                model_id: active_model.clone(),
            };
        }

        let engine_arc = Arc::clone(&self.llm_engine);
        let status_arc = Arc::clone(&self.llm_engine_status);
        let model_id = active_model.clone();
        let path = model_path;

        match tokio::task::spawn_blocking(move || {
            LlmEngine::new(
                &path,
                crate::llm::engine::ContextParams {
                    ctx_size: llm_context_size,
                    ..crate::llm::engine::ContextParams::default()
                },
            )
        }).await {
            Ok(Ok(engine)) => {
                *engine_arc.lock().await = Some(Arc::new(engine));
                *status_arc.lock().await = LlmEngineStatus::Ready {
                    model_id,
                    loaded_at: chrono::Utc::now().timestamp(),
                };
                log::info!("[llm] engine loaded: {active_model}");
                true
            }
            Ok(Err(e)) => {
                *status_arc.lock().await = LlmEngineStatus::Error {
                    message: e.to_string(),
                };
                log::warn!("[llm] load failed: {e}");
                false
            }
            Err(e) => {
                *status_arc.lock().await = LlmEngineStatus::Error {
                    message: format!("spawn_blocking panicked: {e}"),
                };
                log::warn!("[llm] spawn_blocking panicked: {e}");
                false
            }
        }
    }
}

#[cfg(test)]
pub(crate) async fn make_test_state(app_data_dir: PathBuf) -> AppState {
    use crate::config::{normalized_app_config, AppConfig};
    use crate::models::{DownloadCommand, ModelsToml};
    use crate::storage::db::Database;

    let app_data_dir = Arc::new(app_data_dir);
    let db = Arc::new(Database::open("sqlite::memory:").await.unwrap());
    let workspace_manager = Arc::new(WorkspaceManager::new(db.pool.clone()));
    let timeline = TimelineManager::new(db.pool.clone());
    let config = Arc::new(RwLock::new(normalized_app_config(
        AppConfig::default(),
        app_data_dir.as_ref(),
    )));
    let model_config = Arc::new(ModelsToml {
        whisper: crate::models::ModelGroup {
            default_variant: "base".to_string(),
            variants: HashMap::new(),
        },
        llm: crate::models::ModelGroup {
            default_variant: "qwen2.5-3b-q4".to_string(),
            variants: HashMap::new(),
        },
    });
    let (download_tx, _rx) = mpsc::channel::<DownloadCommand>(1);
    let (transcription_tx, _trx) = std::sync::mpsc::sync_channel(1);
    let (batch_tx, _batch_rx) = mpsc::channel::<BatchCommand>(1);
    let batch_queue = Arc::new(BatchQueue::new());

    AppState {
        app_data_dir,
        db,
        workspace_manager,
        timeline,
        config,
        model_config,
        download_tx,
        transcription_tx,
        whisper_engine: Arc::new(Mutex::new(None)),
        capture_stop_tx: Arc::new(Mutex::new(None)),
        segments_cache: Arc::new(Mutex::new(HashMap::new())),
        pcm_cache: Arc::new(Mutex::new(HashMap::new())),
        recording_meta: Arc::new(Mutex::new(None)),
        resampler_done_rx: Arc::new(TokioMutex::new(None)),
        resampler_stop: Arc::new(std::sync::atomic::AtomicBool::new(false)),
        audio_level: Arc::new(std::sync::atomic::AtomicU32::new(0)),
        batch_tx,
        batch_queue,
        llm_tx: {
            let (tx, _) = mpsc::channel(1);
            tx
        },
        llm_engine: Arc::new(TokioMutex::new(None)),
        llm_task_controls: Arc::new(DashMap::new()),
        llm_generation_permit: Arc::new(Semaphore::new(1)),
        prompt_templates: Arc::new(crate::llm::tasks::PromptTemplates {
            summary: crate::llm::tasks::TaskTemplate {
                system: String::new(),
                user: String::new(),
                max_tokens: 512,
            },
            meeting_brief: crate::llm::tasks::TaskTemplate {
                system: String::new(),
                user: String::new(),
                max_tokens: 1024,
            },
            translation: crate::llm::tasks::TaskTemplate {
                system: String::new(),
                user: String::new(),
                max_tokens: 2048,
            },
            qa: crate::llm::tasks::TaskTemplate {
                system: String::new(),
                user: String::new(),
                max_tokens: 512,
            },
        }),
        llm_engine_status: Arc::new(TokioMutex::new(crate::llm::LlmEngineStatus::NotLoaded)),
    }
}

#[cfg(test)]
mod tests {
    use super::make_test_state;

    #[tokio::test]
    async fn test_make_test_state_initializes_workspace_manager() {
        let tmp = tempfile::tempdir().unwrap();
        let state = make_test_state(tmp.path().to_path_buf()).await;

        let folders = state.workspace_manager.list_folders().await.unwrap();
        assert!(folders.is_empty());
    }
}
