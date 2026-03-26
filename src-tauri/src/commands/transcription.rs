// src-tauri/src/commands/transcription.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use std::sync::atomic::Ordering;
use tauri::{AppHandle, State};
use uuid::Uuid;

use crate::audio;
use crate::error::AppError;
use crate::state::AppState;
use crate::transcription::pipeline::TranscriptionCommand;

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

// ── Commands ──────────────────────────────────────────────────────────────────

/// 开始实时录音。立即返回 session_id，后续通过 Tauri 事件通知状态变化。
#[tauri::command]
#[specta::specta]
pub async fn start_realtime(
    config: RealtimeConfig,
    state: State<'_, AppState>,
    _app: AppHandle,
) -> Result<String, AppError> {
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

    // 清理旧会话的 segments_cache（保证内存不无限增长）
    {
        if let Ok(mut cache) = state.segments_cache.lock() {
            cache.clear();
        }
    }

    // 1. 创建原始 PCM channel（capture → resampler thread）
    let (raw_tx, raw_rx) = std::sync::mpsc::sync_channel::<Vec<f32>>(64);
    // 2. 创建 stop channel（stop_realtime → capture thread）
    let (stop_tx, stop_rx) = std::sync::mpsc::sync_channel::<()>(1);

    // 3. 保存 stop_tx 以便 stop_realtime 使用
    *state.capture_stop_tx.lock()
        .map_err(|_| AppError::Audio("capture_stop_tx poisoned".into()))? = Some(stop_tx);

    // 4. 在 std::thread 中创建并持有 cpal stream（cpal::Stream is !Send on macOS）
    let device_id = config.device_id.clone();
    std::thread::spawn(move || {
        let handle = match audio::start_capture(device_id.as_deref(), raw_tx) {
            Ok(h) => h,
            Err(e) => {
                eprintln!("[capture] start_capture failed: {e}");
                return;
            }
        };
        // Block until stop signal; stream lives on this thread
        let _ = stop_rx.recv();
        // pause() 先于 drop()：macOS CoreAudio 在 pause() 时立即停止回调并释放麦克风图标
        handle.stop();
        eprintln!("[capture] stream paused and dropped");
    });

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

    // Query actual device format before spawning threads
    let (sample_rate, channels) = match audio::get_device_config(config.device_id.as_deref()) {
        Ok(cfg) => {
            eprintln!("[pipeline] device config: {}Hz x{}ch", cfg.0, cfg.1);
            cfg
        }
        Err(e) => {
            eprintln!("[pipeline] get_device_config failed: {e}, falling back to 44100/1");
            (44_100, 1)
        }
    };

    // 重置停止标志（防止上次停止的标志影响新会话）
    state.resampler_stop.store(false, std::sync::atomic::Ordering::Relaxed);

    // 创建 resampler 完成信号通道，stop_realtime 等待此信号后再发 Stop 给 pipeline
    let (resampler_done_tx, resampler_done_rx) = tokio::sync::oneshot::channel::<()>();
    *state.resampler_done_rx.lock().await = Some(resampler_done_rx);

    // 共享停止标志：stop_realtime 设为 true，resampler 线程轮询退出
    // 比依赖 raw_rx disconnect 更可靠：macOS CoreAudio 可能延迟数秒才真正停止回调
    let resampler_stop_flag = std::sync::Arc::clone(&state.resampler_stop);

    std::thread::spawn(move || {
        eprintln!("[pipeline] resampler thread started: {}Hz x{}ch", sample_rate, channels);
        let mut resampler = match audio::AudioResampler::new(sample_rate, channels) {
            Ok(r) => r,
            Err(e) => { eprintln!("[pipeline] resampler init failed: {e}"); return; }
        };
        // VadFilter 回调：写 AtomicU32（f32 bits），前端轮询读取
        let audio_level_cb = std::sync::Arc::clone(&audio_level_atomic);
        let mut vad = audio::VadFilter::new(threshold, move |rms| {
            audio_level_cb.store(rms.to_bits(), Ordering::Relaxed);
        });
        let mut chunks_received: u64 = 0;

        // 内联处理函数：对一个 chunk 完成 resample → pcm_cache → VAD → pipeline
        macro_rules! process_chunk {
            ($chunk:expr) => {{
                let resampled = match resampler.push(&$chunk) {
                    Ok(r) => r,
                    Err(e) => { eprintln!("[pipeline] resample error: {e}"); return; }
                };
                if !resampled.is_empty() {
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
                        vad.process(resampled);
                    }
                }
            }};
        }

        loop {
            // 原子标志为 true → 进入"排空并退出"模式
            // 这比等待 raw_tx drop 可靠：macOS CoreAudio 不立即停止回调
            if resampler_stop_flag.load(std::sync::atomic::Ordering::Relaxed) {
                // 排空 raw_rx 中已缓冲的音频（避免截断最后几帧语音）
                while let Ok(chunk) = raw_rx.try_recv() {
                    chunks_received += 1;
                    process_chunk!(chunk);
                }
                eprintln!("[pipeline] resampler stop flag received, exiting after {chunks_received} total chunks");
                let _ = resampler_done_tx.send(());
                return;
            }

            // 正常接收，使用 recv_timeout 避免永久阻塞（每 20ms 检查一次停止标志）
            match raw_rx.recv_timeout(std::time::Duration::from_millis(20)) {
                Ok(chunk) => {
                    chunks_received += 1;
                    if chunks_received == 1 || chunks_received.is_multiple_of(100) {
                        eprintln!("[pipeline] chunks received: {chunks_received}");
                    }
                    process_chunk!(chunk);
                }
                Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                    // 正常超时，继续轮询
                }
                Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                    eprintln!("[pipeline] resampler raw_rx disconnected, exiting after {chunks_received} chunks");
                    let _ = resampler_done_tx.send(());
                    return;
                }
            }
        }
    });

    // 6. 通知 TranscriptionWorker 开始新会话
    let sid = session_id.clone();
    state.transcription_tx
        .send(TranscriptionCommand::Start {
            session_id: sid,
            language: config.language,
            mode: config.mode,
            vad_threshold: config.vad_threshold,
        })
        .map_err(|_| AppError::ChannelClosed)?;

    // 7. 更新 AppState 中的 session_id
    *state.current_session_id.lock().await = Some(session_id.clone());

    Ok(session_id)
}

#[tauri::command]
#[specta::specta]
pub async fn pause_realtime(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
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
    _app: AppHandle,
) -> Result<String, AppError> {
    eprintln!("[stop] begin stop_realtime for session {session_id}");

    // 1. 设置 resampler 停止标志（原子操作，resampler 线程在 20ms 内感知并退出）
    //    必须在发送 capture stop 信号之前设置，确保 resampler 在排空后立即退出
    state.resampler_stop.store(true, std::sync::atomic::Ordering::Relaxed);
    eprintln!("[stop] resampler stop flag set");

    // 2. 停止 cpal 采集（通过 stop channel，capture 线程会 pause+drop stream 释放麦克风）
    if let Ok(mut guard) = state.capture_stop_tx.lock() {
        if let Some(tx) = guard.take() {
            let _ = tx.send(());
            eprintln!("[stop] capture stop signal sent");
        }
    }

    // 3. 等待 resampler 线程排空（设置标志后应在 <100ms 内完成，设 2s 为保险超时）
    //    这解决了竞态条件：原来 Stop 可能在 resampler 完成之前到达 pipeline，
    //    导致最后几百毫秒的音频被遗漏。
    if let Some(done_rx) = state.resampler_done_rx.lock().await.take() {
        match tokio::time::timeout(tokio::time::Duration::from_secs(2), done_rx).await {
            Ok(_) => eprintln!("[stop] resampler thread drained"),
            Err(_) => eprintln!("[stop] resampler drain timeout (2s), proceeding anyway"),
        }
    }

    // 3. 通知 pipeline 最终 flush，用 oneshot channel 等待完成信号
    let (done_tx, done_rx) = tokio::sync::oneshot::channel::<()>();
    state.transcription_tx
        .send(TranscriptionCommand::Stop { session_id: session_id.clone(), done_tx })
        .map_err(|_| AppError::ChannelClosed)?;
    eprintln!("[stop] pipeline Stop command sent, waiting for flush...");

    // 4. 等待 pipeline flush 完成（最多 30s，覆盖最长 30s buffer 的 whisper 推理）
    match tokio::time::timeout(
        tokio::time::Duration::from_secs(30),
        done_rx,
    ).await {
        Ok(_) => eprintln!("[stop] pipeline flush confirmed"),
        Err(_) => eprintln!("[stop] pipeline flush timeout (30s), proceeding anyway"),
    }

    // 5. 收集当前会话的所有 segments（从 AppState 的 segments_cache 中读取）
    // 注意：此处保留 cache 中的数据，供前端通过 get_realtime_segments 轮询读取最终结果；
    // 下次 start_realtime 时将清理旧 session 的缓存。
    let segments = state.segments_cache
        .lock()
        .map_err(|_| AppError::Storage("segments_cache poisoned".into()))?
        .get(&session_id)
        .cloned()
        .unwrap_or_default();
    eprintln!("[stop] collected {} segments", segments.len());

    // 6. 读取 PCM 数据
    let pcm_data = state.pcm_cache
        .lock()
        .map_err(|_| AppError::Storage("pcm_cache poisoned".into()))?
        .remove(&session_id)
        .unwrap_or_default();
    eprintln!("[stop] pcm_data length: {} samples", pcm_data.len());

    // 7. 读取 recordings_path from config
    let recordings_dir = {
        let cfg = state.config.read().await;
        std::path::PathBuf::from(&cfg.recordings_path)
    };
    eprintln!("[stop] recordings_dir: {}", recordings_dir.display());
    tokio::fs::create_dir_all(&recordings_dir).await
        .map_err(|e| AppError::Io(e.to_string()))?;

    let recording_id = Uuid::new_v4().to_string();
    let wav_path = recordings_dir.join(format!("recording_{session_id}.wav"));

    // 8. 写 WAV 文件（非致命：写入失败不阻断 DB 保存）
    let wav_path_str = {
        let wav_path_clone = wav_path.clone();
        let pcm_clone = pcm_data;
        let write_result = tokio::task::spawn_blocking(move || -> Result<(), String> {
            if pcm_clone.is_empty() {
                eprintln!("[stop] pcm empty, skipping WAV write");
                return Ok(());
            }
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
        .await;

        match write_result {
            Ok(Ok(())) => {
                eprintln!("[stop] WAV written OK: {}", wav_path.display());
                wav_path.to_string_lossy().to_string()
            }
            Ok(Err(e)) => {
                eprintln!("[stop] WAV write failed (non-fatal): {e}");
                String::new()
            }
            Err(e) => {
                eprintln!("[stop] WAV spawn_blocking panicked (non-fatal): {e}");
                String::new()
            }
        }
    };

    // 9. 写 DB（单一事务：recordings + transcription_segments + workspace_documents）
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

    *state.current_session_id.lock().await = None;

    Ok(recording_id)
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
    let session = state.current_session_id.lock().await.clone();
    Ok(match session {
        None => RecordingStatus::Idle,
        Some(sid) => RecordingStatus::Recording {
            session_id: sid,
            started_at: 0,
        },
    })
}
