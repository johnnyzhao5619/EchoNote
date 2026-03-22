use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::sync::atomic::AtomicBool;
use tokio::sync::{Mutex as TokioMutex, RwLock, mpsc};
use dashmap::DashMap;

use crate::commands::transcription::SegmentPayload;
use crate::config::AppConfig;
use crate::models::{DownloadCommand, ModelsToml};
use crate::models::registry::{model_file_path, parse_variant_id};
use crate::storage::db::Db;
use crate::transcription::engine::WhisperEngine;
use crate::transcription::pipeline::TranscriptionCommand;
use crate::llm::{
    engine::LlmEngine,
    tasks::PromptTemplates,
    worker::LlmTaskMessage,
    LlmEngineStatus,
};

pub struct AppState {
    // M1–M3 fields
    pub db: Arc<Db>,
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

    /// 当前录音会话 ID
    pub current_session_id: Arc<TokioMutex<Option<String>>>,

    /// resampler 线程完成信号（stop_realtime 等待此信号后再发 Stop 给 pipeline）
    /// 用于解决停止竞态条件：确保所有 AudioChunk 发送完毕后再执行最终 flush
    pub resampler_done_rx: Arc<TokioMutex<Option<tokio::sync::oneshot::Receiver<()>>>>,

    /// 原子停止标志：stop_realtime 设为 true，resampler 线程轮询并退出
    /// 比依赖 raw_rx disconnect 更可靠：macOS CoreAudio 不立即停止回调
    pub resampler_stop: Arc<std::sync::atomic::AtomicBool>,

    /// 最新音频 RMS 电平（f32 bits 存储于 AtomicU32）
    /// 由 VAD resampler 线程写入，get_audio_level 命令读出供前端轮询
    pub audio_level: Arc<std::sync::atomic::AtomicU32>,

    // M5: LLM Worker fields

    /// LLM Worker 消息发送端
    pub llm_tx: mpsc::Sender<LlmTaskMessage>,

    /// LLM 引擎实例（Option：模型未加载时为 None）
    pub llm_engine: Arc<TokioMutex<Option<Arc<LlmEngine>>>>,

    /// 活跃任务取消标志表（task_id → AtomicBool）
    pub active_llm_cancels: Arc<DashMap<String, Arc<AtomicBool>>>,

    /// Prompt 模板（启动时一次性加载，只读）
    pub prompt_templates: Arc<PromptTemplates>,

    /// LLM 引擎状态
    pub llm_engine_status: Arc<TokioMutex<LlmEngineStatus>>,
}

impl AppState {
    /// 根据当前 AppConfig 尝试热加载 WhisperEngine。
    /// 调用时机：模型下载完成、切换激活模型。
    /// 返回 true = 加载成功；false = 文件不存在或加载失败。
    pub async fn try_load_whisper(&self) -> bool {
        let (model_dir, active_model) = {
            let cfg = self.config.read().await;
            let model_dir = std::path::Path::new(&cfg.vault_path)
                .parent()
                .unwrap_or(std::path::Path::new(&cfg.vault_path))
                .join("models");
            (model_dir, cfg.active_whisper_model.clone())
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
}
