// src-tauri/src/commands/transcription.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use std::sync::atomic::Ordering;
use std::time::Duration;
use tauri::{AppHandle, Emitter, State};
use uuid::Uuid;

use crate::audio;
use crate::error::AppError;
use crate::state::{AppState, RecordingSessionMeta};
use crate::transcription::batch::{BatchCommand, BatchJobView};
use crate::transcription::ffmpeg::{detect_ffmpeg, is_supported_format};
use crate::transcription::pipeline::TranscriptionCommand;

const CAPTURE_STARTUP_TIMEOUT: Duration = Duration::from_secs(15);

// ── Public types (also used by pipeline.rs) ──────────────────────────────────

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct SegmentPayload {
    pub id: u32,
    pub recording_session_id: String,
    pub start_ms: u32,
    pub end_ms: u32,
    pub text: String,
    pub language: String,
    pub is_partial: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum RecordingStatus {
    Idle,
    Recording { session_id: String, started_at: i64 },
    Paused   { session_id: String },
    Stopped  { session_id: String, recording_id: String },
}

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(rename_all = "snake_case")]
pub enum RecordingMode {
    RecordOnly,
    TranscribeOnly,
    TranscribeAndTranslate { target_language: String },
}

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct RealtimeConfig {
    pub device_id: Option<String>,
    pub language: Option<String>,
    pub mode: RecordingMode,
    pub vad_threshold: f32,
}

fn build_recording_status(meta: Option<&RecordingSessionMeta>) -> RecordingStatus {
    match meta {
        None => RecordingStatus::Idle,
        Some(meta) if meta.is_paused => RecordingStatus::Paused {
            session_id: meta.session_id.clone(),
        },
        Some(meta) => RecordingStatus::Recording {
            session_id: meta.session_id.clone(),
            started_at: meta.started_at_ms,
        },
    }
}

fn resolve_input_config(
    config: Result<(u32, usize), AppError>,
) -> Result<(u32, usize), AppError> {
    config
}

fn should_process_live_audio(
    meta: Option<&RecordingSessionMeta>,
    session_id: &str,
) -> bool {
    matches!(meta, Some(meta) if meta.session_id == session_id && !meta.is_paused)
}

fn ensure_wav_written(
    wav_path: &std::path::Path,
    write_result: Result<(), String>,
) -> Result<String, AppError> {
    write_result
        .map(|()| wav_path.to_string_lossy().to_string())
        .map_err(AppError::Io)
}

fn get_recording_meta(
    state: &AppState,
) -> Result<Option<RecordingSessionMeta>, AppError> {
    state
        .recording_meta
        .lock()
        .map(|guard| guard.clone())
        .map_err(|_| AppError::Audio("recording_meta poisoned".into()))
}

fn set_recording_pause_state(
    state: &AppState,
    session_id: &str,
    is_paused: bool,
) -> Result<(), AppError> {
    let mut guard = state
        .recording_meta
        .lock()
        .map_err(|_| AppError::Audio("recording_meta poisoned".into()))?;
    match guard.as_mut() {
        Some(meta) if meta.session_id == session_id => {
            meta.is_paused = is_paused;
            Ok(())
        }
        Some(_) => Err(AppError::Validation("录音会话不匹配".into())),
        None => Err(AppError::Validation("当前没有活跃录音会话".into())),
    }
}

async fn clear_recording_runtime_state(state: &AppState) {
    if let Ok(mut guard) = state.capture_stop_tx.lock() {
        guard.take();
    }
    if let Ok(mut guard) = state.recording_meta.lock() {
        *guard = None;
    }
    *state.resampler_done_rx.lock().await = None;
    state.resampler_stop.store(false, Ordering::Relaxed);
    state.audio_level.store(0.0f32.to_bits(), Ordering::Relaxed);
}

async fn wait_for_capture_ready(
    capture_ready_rx: std::sync::mpsc::Receiver<Result<(), String>>,
    stop_tx: &std::sync::mpsc::SyncSender<()>,
) -> Result<(), AppError> {
    wait_for_capture_ready_with_timeout(capture_ready_rx, stop_tx, CAPTURE_STARTUP_TIMEOUT).await
}

async fn wait_for_capture_ready_with_timeout(
    capture_ready_rx: std::sync::mpsc::Receiver<Result<(), String>>,
    stop_tx: &std::sync::mpsc::SyncSender<()>,
    timeout: Duration,
) -> Result<(), AppError> {
    match tokio::task::spawn_blocking(move || capture_ready_rx.recv_timeout(timeout))
        .await
        .map_err(|e| AppError::Audio(format!("等待音频采集启动失败: {e}")))?
    {
        Ok(Ok(())) => Ok(()),
        Ok(Err(message)) => {
            let _ = stop_tx.send(());
            Err(AppError::Audio(message))
        }
        Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
            let _ = stop_tx.send(());
            Err(AppError::Audio(format!(
                "等待音频采集启动超时（>{} 秒）",
                timeout.as_secs()
            )))
        }
        Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
            let _ = stop_tx.send(());
            Err(AppError::Audio("音频采集启动线程已断开".into()))
        }
    }
}

// ── Commands ──────────────────────────────────────────────────────────────────

/// 开始实时录音。立即返回 session_id，后续通过 Tauri 事件通知状态变化。
#[tauri::command]
#[specta::specta]
pub async fn start_realtime(
    config: RealtimeConfig,
    state: State<'_, AppState>,
    _app: AppHandle,
) -> Result<String, AppError> {
    if get_recording_meta(&state)?.is_some() {
        return Err(AppError::Validation("已有活跃录音会话，不能重复开始录音".into()));
    }

    // 非"仅录音"模式必须确保 whisper 引擎已加载
    if !matches!(config.mode, RecordingMode::RecordOnly) {
        let has_engine = state.whisper_engine
            .lock()
            .map(|g| g.is_some())
            .unwrap_or(false);
        if !has_engine {
            return Err(AppError::Model(
                "未加载 Whisper 模型。请在设置页面下载并激活一个模型后再开始转录。".into()
            ));
        }
    }

    let session_id = Uuid::new_v4().to_string();
    let started_at_ms = chrono::Utc::now().timestamp_millis();
    let (sample_rate, channels) = resolve_input_config(
        audio::get_device_config(config.device_id.as_deref())
    )?;
    let _ = audio::AudioResampler::new(sample_rate, channels)?;

    if let Ok(mut cache) = state.segments_cache.lock() {
        cache.clear();
    }
    if let Ok(mut cache) = state.pcm_cache.lock() {
        cache.clear();
    }
    state.audio_level.store(0.0f32.to_bits(), Ordering::Relaxed);

    // 1. 创建原始 PCM channel（capture → resampler thread）
    let (raw_tx, raw_rx) = std::sync::mpsc::sync_channel::<Vec<f32>>(64);
    // 2. 创建 stop channel（stop_realtime → capture thread）
    let (stop_tx, stop_rx) = std::sync::mpsc::sync_channel::<()>(1);
    let (capture_ready_tx, capture_ready_rx) =
        std::sync::mpsc::sync_channel::<Result<(), String>>(1);

    // 4. 在 std::thread 中创建并持有 cpal stream（cpal::Stream is !Send on macOS）
    let device_id = config.device_id.clone();
    std::thread::spawn(move || {
        let handle = match audio::start_capture(device_id.as_deref(), raw_tx) {
            Ok(h) => h,
            Err(e) => {
                let _ = capture_ready_tx.send(Err(e.to_string()));
                eprintln!("[capture] start_capture failed: {e}");
                return;
            }
        };
        let _ = capture_ready_tx.send(Ok(()));
        // Block until stop signal; stream lives on this thread
        let _ = stop_rx.recv();
        // pause() 先于 drop()：macOS CoreAudio 在 pause() 时立即停止回调并释放麦克风图标
        handle.stop();
        eprintln!("[capture] stream paused and dropped");
    });

    wait_for_capture_ready(capture_ready_rx, &stop_tx).await?;

    // 5. 启动 resampler + VAD 转发线程
    let transcription_tx = state.transcription_tx.clone();
    let threshold = config.vad_threshold;
    let pcm_cache = std::sync::Arc::clone(&state.pcm_cache);
    // 轮询方案：VadFilter 回调直接写 AtomicU32，前端每 100ms 调用 get_audio_level() 读取
    // 彻底绕过 Tauri 事件系统（在 macOS 开发模式下 AppHandle::emit 无法可靠到达 WebView）
    let audio_level_atomic = std::sync::Arc::clone(&state.audio_level);
    let session_id_for_pcm = session_id.clone();
    // RecordOnly 模式：仅录音，不发 AudioChunk 到 whisper pipeline
    let send_to_pipeline = !matches!(config.mode, RecordingMode::RecordOnly);
    let recording_meta = std::sync::Arc::clone(&state.recording_meta);

    // 重置停止标志（防止上次停止的标志影响新会话）
    state.resampler_stop.store(false, Ordering::Relaxed);
    *state.capture_stop_tx
        .lock()
        .map_err(|_| AppError::Audio("capture_stop_tx poisoned".into()))? = Some(stop_tx);
    *state.recording_meta
        .lock()
        .map_err(|_| AppError::Audio("recording_meta poisoned".into()))? = Some(RecordingSessionMeta {
        session_id: session_id.clone(),
        started_at_ms,
        is_paused: false,
    });

    // 创建 resampler 完成信号通道，stop_realtime 等待此信号后再发 Stop 给 pipeline
    let (resampler_done_tx, resampler_done_rx) = tokio::sync::oneshot::channel::<()>();
    *state.resampler_done_rx.lock().await = Some(resampler_done_rx);

    // 共享停止标志：stop_realtime 设为 true，resampler 线程轮询退出
    // 比依赖 raw_rx disconnect 更可靠：macOS CoreAudio 可能延迟数秒才真正停止回调
    let resampler_stop_flag = std::sync::Arc::clone(&state.resampler_stop);

    // 6. 通知 TranscriptionWorker 开始新会话
    let sid = session_id.clone();
    if let Err(_err) = state.transcription_tx
        .send(TranscriptionCommand::Start {
            session_id: sid,
            language: config.language,
            mode: config.mode,
            vad_threshold: config.vad_threshold,
        })
    {
        if let Ok(mut guard) = state.capture_stop_tx.lock() {
            if let Some(stop_tx) = guard.take() {
                let _ = stop_tx.send(());
            }
        }
        clear_recording_runtime_state(&state).await;
        return Err(AppError::ChannelClosed);
    }

    std::thread::spawn(move || {
        eprintln!("[pipeline] resampler thread started: {}Hz x{}ch", sample_rate, channels);
        let mut resampler = match audio::AudioResampler::new(sample_rate, channels) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("[pipeline] resampler init failed: {e}");
                let _ = resampler_done_tx.send(());
                return;
            }
        };
        // VadFilter 回调：写 AtomicU32（f32 bits），前端轮询读取
        let audio_level_cb = std::sync::Arc::clone(&audio_level_atomic);
        let mut vad = audio::VadFilter::new(threshold, move |rms| {
            audio_level_cb.store(rms.to_bits(), Ordering::Relaxed);
        });
        let mut chunks_received: u64 = 0;

        macro_rules! process_chunk {
            ($chunk:expr) => {{
                let resampled = match resampler.push(&$chunk) {
                    Ok(r) => r,
                    Err(e) => {
                        eprintln!("[pipeline] resample error: {e}");
                        let _ = resampler_done_tx.send(());
                        return;
                    }
                };
                if !resampled.is_empty() {
                    let can_process = match recording_meta.lock() {
                        Ok(meta_guard) => should_process_live_audio(meta_guard.as_ref(), &session_id_for_pcm),
                        Err(_) => false,
                    };

                    if !can_process {
                        audio_level_atomic.store(0.0f32.to_bits(), Ordering::Relaxed);
                    } else {
                        if let Ok(mut cache) = pcm_cache.lock() {
                            cache.entry(session_id_for_pcm.clone())
                                .or_default()
                                .extend_from_slice(&resampled);
                        }
                        if send_to_pipeline {
                            for frame in vad.process(resampled) {
                                let _ = transcription_tx.try_send(TranscriptionCommand::AudioChunk(frame));
                            }
                        } else {
                            let _ = vad.process(resampled);
                        }
                    }
                }
            }};
        }

        loop {
            if resampler_stop_flag.load(Ordering::Relaxed) {
                while let Ok(chunk) = raw_rx.try_recv() {
                    chunks_received += 1;
                    process_chunk!(chunk);
                }
                eprintln!("[pipeline] resampler stop flag received, exiting after {chunks_received} total chunks");
                let _ = resampler_done_tx.send(());
                return;
            }

            match raw_rx.recv_timeout(std::time::Duration::from_millis(20)) {
                Ok(chunk) => {
                    chunks_received += 1;
                    if chunks_received == 1 || chunks_received.is_multiple_of(100) {
                        eprintln!("[pipeline] chunks received: {chunks_received}");
                    }
                    process_chunk!(chunk);
                }
                Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {}
                Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                    eprintln!("[pipeline] resampler raw_rx disconnected, exiting after {chunks_received} chunks");
                    let _ = resampler_done_tx.send(());
                    return;
                }
            }
        }
    });

    Ok(session_id)
}

#[tauri::command]
#[specta::specta]
pub async fn pause_realtime(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    set_recording_pause_state(&state, &session_id, true)?;
    state.audio_level.store(0.0f32.to_bits(), Ordering::Relaxed);
    state.transcription_tx
        .send(TranscriptionCommand::Pause { session_id })
        .map_err(|_| AppError::ChannelClosed)
}

#[tauri::command]
#[specta::specta]
pub async fn resume_realtime(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    set_recording_pause_state(&state, &session_id, false)?;
    state.transcription_tx
        .send(TranscriptionCommand::Resume { session_id })
        .map_err(|_| AppError::ChannelClosed)
}

/// 停止录音，保存 WAV 文件并写入数据库，返回 recording_id
#[tauri::command]
#[specta::specta]
pub async fn stop_realtime(
    session_id: String,
    state: State<'_, AppState>,
    app: AppHandle,
) -> Result<String, AppError> {
    eprintln!("[stop] begin stop_realtime for session {session_id}");
    let active_meta = get_recording_meta(&state)?;
    match active_meta.as_ref() {
        Some(meta) if meta.session_id == session_id => {}
        Some(_) => return Err(AppError::Validation("录音会话不匹配".into())),
        None => return Err(AppError::Validation("当前没有活跃录音会话".into())),
    }

    let result: Result<String, AppError> = async {
        // 1. 设置 resampler 停止标志（原子操作，resampler 线程在 20ms 内感知并退出）
        //    必须在发送 capture stop 信号之前设置，确保 resampler 在排空后立即退出
        state.resampler_stop.store(true, Ordering::Relaxed);
        state.audio_level.store(0.0f32.to_bits(), Ordering::Relaxed);
        eprintln!("[stop] resampler stop flag set");

        // 2. 停止 cpal 采集（通过 stop channel，capture 线程会 pause+drop stream 释放麦克风）
        if let Ok(mut guard) = state.capture_stop_tx.lock() {
            if let Some(tx) = guard.take() {
                let _ = tx.send(());
                eprintln!("[stop] capture stop signal sent");
            }
        }

        // 3. 等待 resampler 线程排空（设置标志后应在 <100ms 内完成，设 2s 为保险超时）
        if let Some(done_rx) = state.resampler_done_rx.lock().await.take() {
            match tokio::time::timeout(tokio::time::Duration::from_secs(2), done_rx).await {
                Ok(_) => eprintln!("[stop] resampler thread drained"),
                Err(_) => eprintln!("[stop] resampler drain timeout (2s), proceeding anyway"),
            }
        }

        // 4. 通知 pipeline 最终 flush，用 oneshot channel 等待完成信号
        let (done_tx, done_rx) = tokio::sync::oneshot::channel::<()>();
        state.transcription_tx
            .send(TranscriptionCommand::Stop { session_id: session_id.clone(), done_tx })
            .map_err(|_| AppError::ChannelClosed)?;
        eprintln!("[stop] pipeline Stop command sent, waiting for flush...");

        match tokio::time::timeout(
            tokio::time::Duration::from_secs(30),
            done_rx,
        ).await {
            Ok(_) => eprintln!("[stop] pipeline flush confirmed"),
            Err(_) => eprintln!("[stop] pipeline flush timeout (30s), proceeding anyway"),
        }

        let segments = state.segments_cache
            .lock()
            .map_err(|_| AppError::Storage("segments_cache poisoned".into()))?
            .get(&session_id)
            .cloned()
            .unwrap_or_default();
        eprintln!("[stop] collected {} segments", segments.len());

        let pcm_data = state.pcm_cache
            .lock()
            .map_err(|_| AppError::Storage("pcm_cache poisoned".into()))?
            .remove(&session_id)
            .unwrap_or_default();
        eprintln!("[stop] pcm_data length: {} samples", pcm_data.len());

        let recordings_dir = {
            let cfg = state.config.read().await;
            std::path::PathBuf::from(&cfg.recordings_path)
        };
        eprintln!("[stop] recordings_dir: {}", recordings_dir.display());
        tokio::fs::create_dir_all(&recordings_dir).await
            .map_err(|e| AppError::Io(e.to_string()))?;

        let recording_id = Uuid::new_v4().to_string();
        let wav_path = recordings_dir.join(format!("recording_{session_id}.wav"));
        let wav_path_str = {
            let wav_path_clone = wav_path.clone();
            let pcm_clone = pcm_data;
            let write_result = tokio::task::spawn_blocking(move || -> Result<(), String> {
                eprintln!("[stop] writing WAV: {} samples → {}", pcm_clone.len(), wav_path_clone.display());
                let spec = hound::WavSpec {
                    channels: 1,
                    sample_rate: 16_000,
                    bits_per_sample: 16,
                    sample_format: hound::SampleFormat::Int,
                };
                let mut writer = hound::WavWriter::create(&wav_path_clone, spec)
                    .map_err(|e| e.to_string())?;
                for sample in pcm_clone {
                    let s = (sample * i16::MAX as f32) as i16;
                    writer.write_sample(s).map_err(|e| e.to_string())?;
                }
                writer.finalize().map_err(|e| e.to_string())
            })
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;

            let wav_path_str = ensure_wav_written(&wav_path, write_result)?;
            eprintln!("[stop] WAV written OK: {}", wav_path.display());
            wav_path_str
        };

        eprintln!("[stop] starting DB write, wav_path={wav_path_str:?}");
        let duration_ms = segments.last().map(|s| s.end_ms as i64).unwrap_or(0);
        let now = chrono::Utc::now().timestamp_millis();
        let title = format!("Recording {}", chrono::Local::now().format("%Y-%m-%d %H:%M"));
        let doc_id = Uuid::new_v4().to_string();
        let asset_id = Uuid::new_v4().to_string();
        let transcript_text: String = segments.iter()
            .map(|s| s.text.as_str())
            .collect::<Vec<_>>()
            .join(" ");
        let rec_id = recording_id.clone();

        let mut tx = state.db.pool.begin().await
            .map_err(|e| AppError::Storage(e.to_string()))?;

        sqlx::query(
            "INSERT INTO recordings (id, title, file_path, duration_ms, language, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        .bind(&rec_id)
        .bind(&title)
        .bind(&wav_path_str)
        .bind(duration_ms)
        .bind("auto")
        .bind(now)
        .bind(now)
        .execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;

        for seg in &segments {
            sqlx::query(
                "INSERT INTO transcription_segments (recording_id, start_ms, end_ms, text, language)
                 VALUES (?, ?, ?, ?, ?)"
            )
            .bind(&rec_id)
            .bind(seg.start_ms as i64)
            .bind(seg.end_ms as i64)
            .bind(&seg.text)
            .bind(&seg.language)
            .execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;
        }

        sqlx::query(
            "INSERT INTO workspace_documents (id, title, source_type, recording_id, created_at, updated_at)
             VALUES (?, ?, 'recording', ?, ?, ?)"
        )
        .bind(&doc_id)
        .bind(&title)
        .bind(&rec_id)
        .bind(now)
        .bind(now)
        .execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;

        if !transcript_text.is_empty() {
            sqlx::query(
                "INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
                 VALUES (?, ?, 'transcript', ?, ?, ?)"
            )
            .bind(&asset_id)
            .bind(&doc_id)
            .bind(&transcript_text)
            .bind(now)
            .bind(now)
            .execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;
        }

        tx.commit().await.map_err(|e| AppError::Storage(e.to_string()))?;
        eprintln!("[stop] DB commit OK, recording_id={recording_id}");
        let _ = app.emit(
            "transcription:status",
            RecordingStatus::Stopped {
                session_id: session_id.clone(),
                recording_id: recording_id.clone(),
            },
        );

        Ok(recording_id)
    }.await;

    clear_recording_runtime_state(&state).await;
    result
}

/// 前端轮询当前会话已转录的 segments。
/// 同一套轮询方案替代 Tauri 事件（事件在 macOS 开发模式下不可靠）。
/// 前端每 500ms 调用一次，stop 后再调用一次获取最终 segments。
#[tauri::command]
#[specta::specta]
pub async fn get_realtime_segments(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<SegmentPayload>, AppError> {
    let segments = state.segments_cache
        .lock()
        .map_err(|_| AppError::Storage("segments_cache poisoned".into()))?
        .get(&session_id)
        .cloned()
        .unwrap_or_default();
    Ok(segments)
}

/// 前端轮询当前音频 RMS 电平（0.0–1.0）。
/// Tauri 事件系统在 macOS 开发模式下不可靠，改用轮询方案。
/// 前端每 100ms 调用一次，录音结束后停止调用。
#[tauri::command]
#[specta::specta]
pub async fn get_audio_level(
    state: State<'_, AppState>,
) -> Result<f32, AppError> {
    let bits = state.audio_level.load(Ordering::Relaxed);
    Ok(f32::from_bits(bits))
}

#[tauri::command]
#[specta::specta]
pub async fn get_recording_status(
    state: State<'_, AppState>,
) -> Result<RecordingStatus, AppError> {
    let meta = get_recording_meta(&state)?;
    Ok(build_recording_status(meta.as_ref()))
}

#[tauri::command]
#[specta::specta]
pub async fn check_ffmpeg_available() -> bool {
    tokio::task::spawn_blocking(detect_ffmpeg)
        .await
        .unwrap_or(false)
}

#[tauri::command]
#[specta::specta]
pub async fn add_files_to_batch(
    paths: Vec<String>,
    state: State<'_, AppState>,
) -> Result<Vec<String>, AppError> {
    let mut job_ids = Vec::with_capacity(paths.len());

    for path in paths {
        let file_path = std::path::PathBuf::from(&path);
        if !file_path.exists() {
            return Err(AppError::Io(format!("File not found: {path}")));
        }

        if !is_supported_format(&file_path) {
            return Err(AppError::Validation(format!(
                "Unsupported format: {}",
                file_path
                    .extension()
                    .and_then(|ext| ext.to_str())
                    .unwrap_or("unknown")
            )));
        }

        let job_id = Uuid::new_v4().to_string();
        state
            .batch_tx
            .send(BatchCommand::Enqueue {
                job_id: job_id.clone(),
                file_path,
                language: None,
            })
            .await
            .map_err(AppError::channel)?;
        job_ids.push(job_id);
    }

    Ok(job_ids)
}

#[tauri::command]
#[specta::specta]
pub async fn get_batch_queue(
    _state: State<'_, AppState>,
) -> Result<Vec<BatchJobView>, AppError> {
    Err(AppError::Validation(
        "batch queue not wired yet".to_string(),
    ))
}

#[tauri::command]
#[specta::specta]
pub async fn cancel_batch_job(
    job_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    state
        .batch_tx
        .send(BatchCommand::Cancel { job_id })
        .await
        .map_err(AppError::channel)
}

#[tauri::command]
#[specta::specta]
pub async fn clear_completed_jobs(
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    state
        .batch_tx
        .send(BatchCommand::ClearCompleted)
        .await
        .map_err(AppError::channel)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_recording_status_idle() {
        assert!(matches!(build_recording_status(None), RecordingStatus::Idle));
    }

    #[test]
    fn test_build_recording_status_recording() {
        let meta = RecordingSessionMeta {
            session_id: "session-1".into(),
            started_at_ms: 42,
            is_paused: false,
        };
        assert!(matches!(
            build_recording_status(Some(&meta)),
            RecordingStatus::Recording { session_id, started_at } if session_id == "session-1" && started_at == 42
        ));
    }

    #[test]
    fn test_build_recording_status_paused() {
        let meta = RecordingSessionMeta {
            session_id: "session-2".into(),
            started_at_ms: 99,
            is_paused: true,
        };
        assert!(matches!(
            build_recording_status(Some(&meta)),
            RecordingStatus::Paused { session_id } if session_id == "session-2"
        ));
    }

    #[test]
    fn test_resolve_input_config_propagates_error() {
        let result = resolve_input_config(Err(AppError::Audio("device config failed".into())));
        assert!(matches!(result, Err(AppError::Audio(message)) if message == "device config failed"));
    }

    #[test]
    fn test_should_process_live_audio_only_when_active_and_not_paused() {
        let active = RecordingSessionMeta {
            session_id: "session-3".into(),
            started_at_ms: 1,
            is_paused: false,
        };
        let paused = RecordingSessionMeta {
            session_id: "session-3".into(),
            started_at_ms: 1,
            is_paused: true,
        };

        assert!(should_process_live_audio(Some(&active), "session-3"));
        assert!(!should_process_live_audio(Some(&paused), "session-3"));
        assert!(!should_process_live_audio(Some(&active), "other"));
        assert!(!should_process_live_audio(None, "session-3"));
    }

    #[test]
    fn test_ensure_wav_written_requires_success() {
        let wav_path = std::path::Path::new("/tmp/test.wav");
        let err = ensure_wav_written(wav_path, Err("disk full".into())).unwrap_err();
        assert!(matches!(err, AppError::Io(message) if message == "disk full"));

        let ok = ensure_wav_written(wav_path, Ok(())).unwrap();
        assert_eq!(ok, "/tmp/test.wav");
    }

    #[tokio::test]
    async fn test_set_recording_pause_state_updates_shared_meta() {
        let state = crate::state::make_test_state(std::path::PathBuf::from("/tmp/echonote-transcription-tests")).await;
        *state.recording_meta.lock().unwrap() = Some(RecordingSessionMeta {
            session_id: "session-4".into(),
            started_at_ms: 7,
            is_paused: false,
        });

        set_recording_pause_state(&state, "session-4", true).unwrap();
        let meta = get_recording_meta(&state).unwrap().unwrap();
        assert!(meta.is_paused);
    }

    #[tokio::test]
    async fn test_wait_for_capture_ready_times_out_and_sends_stop() {
        let (_ready_tx, ready_rx) = std::sync::mpsc::sync_channel::<Result<(), String>>(1);
        let (stop_tx, stop_rx) = std::sync::mpsc::sync_channel::<()>(1);

        let err = wait_for_capture_ready_with_timeout(ready_rx, &stop_tx, Duration::from_millis(1))
            .await
            .unwrap_err();
        assert!(matches!(err, AppError::Audio(message) if message.contains("等待音频采集启动超时")));
        assert!(stop_rx.try_recv().is_ok(), "timeout should trigger capture stop cleanup");
    }
}
