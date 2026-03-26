// src-tauri/src/transcription/pipeline.rs

use std::collections::HashMap;
use std::sync::{Arc, Mutex, mpsc};
use std::time::Instant;
use tauri::{AppHandle, Emitter};
use tokio::task;
use tokio::sync::mpsc as async_mpsc;

use crate::transcription::engine::WhisperEngine;
use crate::commands::transcription::{RecordingMode, RecordingStatus, SegmentPayload};

// ── 双缓冲 + 异步推理参数 ────────────────────────────────────────
/// 500ms 无新帧 → 触发推理（句子边界，参考 WhisperLive 中文实践）
const PAUSE_FLUSH_MS: u64 = 500;
/// 最小推理长度 0.5s（shorter-whisper min_speech）
const MIN_INFER_SAMPLES: usize = 8_000;
/// 安全上限 25s（Whisper 30s 硬限以下留 5s 缓冲）
const MAX_ACCUM_SAMPLES: usize = 16_000 * 25;

/// 发往 TranscriptionWorker 的控制命令
pub enum TranscriptionCommand {
    Start {
        session_id: String,
        language: Option<String>,
        mode: RecordingMode,
        vad_threshold: f32,
    },
    AudioChunk(Vec<f32>),   // 来自 VAD 过滤后的有效音频帧
    Pause { session_id: String },
    Resume { session_id: String },
    /// done_tx: pipeline 完成 flush 后发送信号，用于替代 stop_realtime 的 sleep(500ms)
    Stop { session_id: String, done_tx: tokio::sync::oneshot::Sender<()> },
}

/// 后台推理任务的返回值，通过 result_rx 回传给 pipeline 循环
struct InferenceResult {
    session_id: String,
    segments: Vec<SegmentPayload>,
}

pub struct TranscriptionWorker {
    rx: mpsc::Receiver<TranscriptionCommand>,
    app: AppHandle,
    engine: Arc<Mutex<Option<WhisperEngine>>>,
    segments_cache: Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,
    /// 推理结果回传通道（在 new() 内部创建，run_inference spawn 时 clone sender）
    result_tx: async_mpsc::Sender<InferenceResult>,
    result_rx: async_mpsc::Receiver<InferenceResult>,
}

impl TranscriptionWorker {
    pub fn new(
        rx: mpsc::Receiver<TranscriptionCommand>,
        app: AppHandle,
        engine: Arc<Mutex<Option<WhisperEngine>>>,
        segments_cache: Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,
    ) -> Self {
        let (result_tx, result_rx) = async_mpsc::channel(4);
        Self { rx, app, engine, segments_cache, result_tx, result_rx }
    }

    /// 在独立 tokio task 内调用此方法（`tokio::spawn(worker.run())`）
    pub async fn run(self) {
        let Self { rx, app, engine, segments_cache, result_tx, mut result_rx } = self;

        let mut active_buf: Vec<f32> = Vec::new();
        let mut session_id: Option<String> = None;
        let mut language: Option<String> = None;
        let mut translate = false;
        let mut segment_counter: u32 = 0;
        let mut paused = false;
        let mut last_audio_at = Instant::now();
        let mut inference_in_flight = false;

        loop {
            // ── Step 1: 收集已完成的推理结果（非阻塞）────────────────
            if let Ok(result) = result_rx.try_recv() {
                segment_counter += result.segments.len() as u32;
                if let Ok(mut cache) = segments_cache.lock() {
                    cache.entry(result.session_id.clone()).or_default().extend(result.segments);
                }
                inference_in_flight = false;
            }

            // ── Step 2: 处理 TranscriptionCommand ─────────────────────
            match rx.try_recv() {
                Ok(cmd) => match cmd {
                    TranscriptionCommand::Start { session_id: sid, language: lang, mode, .. } => {
                        session_id = Some(sid.clone());
                        language = lang;
                        translate = matches!(mode, RecordingMode::TranscribeAndTranslate { .. });
                        active_buf.clear();
                        segment_counter = 0;
                        paused = false;
                        inference_in_flight = false;
                        last_audio_at = Instant::now();
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Recording {
                                session_id: sid,
                                started_at: chrono::Utc::now().timestamp_millis(),
                            });
                    }
                    TranscriptionCommand::AudioChunk(chunk) if !paused && session_id.is_some() => {
                        active_buf.extend_from_slice(&chunk);
                        last_audio_at = Instant::now();
                    }
                    TranscriptionCommand::Pause { session_id: sid } => {
                        paused = true;
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Paused { session_id: sid });
                    }
                    TranscriptionCommand::Resume { session_id: sid } => {
                        paused = false;
                        last_audio_at = Instant::now();
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Recording {
                                session_id: sid,
                                started_at: chrono::Utc::now().timestamp_millis(),
                            });
                    }
                    TranscriptionCommand::Stop { session_id: _sid, done_tx } => {
                        // 1. 等待进行中的推理完成（最多 30s）
                        if inference_in_flight {
                            match tokio::time::timeout(
                                tokio::time::Duration::from_secs(30),
                                result_rx.recv(),
                            ).await {
                                Ok(Some(result)) => {
                                    segment_counter += result.segments.len() as u32;
                                    if let Ok(mut cache) = segments_cache.lock() {
                                        cache.entry(result.session_id.clone()).or_default().extend(result.segments);
                                    }
                                }
                                Ok(None) => eprintln!("[pipeline] result_rx closed during stop"),
                                Err(_) => eprintln!("[pipeline] timeout waiting for in-flight inference on stop"),
                            }
                            inference_in_flight = false;
                        }

                        // 2. 刷新剩余 active_buf（Stop 时绕过 MIN_INFER_SAMPLES 防止数据丢失）
                        if !active_buf.is_empty() {
                            flush_to_whisper(
                                &mut active_buf, &session_id, &language,
                                translate, &mut segment_counter,
                                &engine, &segments_cache,
                            ).await;
                        }

                        // 3. 重置状态，通知调用方
                        session_id = None;
                        paused = false;
                        let _ = done_tx.send(());
                    }
                    _ => {} // AudioChunk while paused → discard
                },

                Err(mpsc::TryRecvError::Empty) => {
                    // ── Step 3: flush 条件检查（仅在 Empty 分支，避免 inference 重叠）──
                    if !paused && session_id.is_some() && !inference_in_flight {
                        let elapsed_ms = last_audio_at.elapsed().as_millis() as u64;
                        let cond_a = elapsed_ms >= PAUSE_FLUSH_MS
                            && active_buf.len() >= MIN_INFER_SAMPLES;
                        let cond_b = active_buf.len() >= MAX_ACCUM_SAMPLES;

                        if cond_a || cond_b {
                            let audio = std::mem::take(&mut active_buf);
                            inference_in_flight = true;
                            tokio::spawn(run_inference(
                                audio,
                                session_id.clone().unwrap_or_default(),
                                language.clone(),
                                translate,
                                segment_counter,
                                Arc::clone(&engine),
                                result_tx.clone(),
                            ));
                        }
                    }
                }

                Err(mpsc::TryRecvError::Disconnected) => break,
            }

            // ── Step 4: 10ms sleep ─────────────────────────────────────
            tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
        }
    }
}

/// 后台推理任务：在 spawn_blocking 中运行 Whisper，完成后通过 result_tx 回传结果。
/// 即使出错也必须发送（保证 inference_in_flight 被清除）。
async fn run_inference(
    audio: Vec<f32>,
    session_id: String,
    language: Option<String>,
    translate: bool,
    counter_snapshot: u32,
    engine: Arc<Mutex<Option<WhisperEngine>>>,
    result_tx: async_mpsc::Sender<InferenceResult>,
) {
    // 提前检查 engine 是否就绪（避免进入 spawn_blocking）
    // 注意：guard 必须在 await 前 drop，否则 MutexGuard 跨越 await 点导致 !Send
    let engine_ready = engine.lock().unwrap().is_some();
    if !engine_ready {
        let _ = result_tx.send(InferenceResult { session_id, segments: vec![] }).await;
        return;
    }

    let sid = session_id.clone();
    let raw_segments = task::spawn_blocking(move || {
        let guard = engine.lock().unwrap();
        if let Some(eng) = guard.as_ref() {
            eng.transcribe(&audio, language.as_deref(), translate)
                .unwrap_or_else(|e| { eprintln!("[pipeline] whisper error: {e}"); vec![] })
        } else {
            vec![]
        }
    })
    .await
    .unwrap_or_default();

    let segments: Vec<SegmentPayload> = raw_segments
        .iter()
        .enumerate()
        .map(|(i, seg)| SegmentPayload {
            id: counter_snapshot + i as u32,
            recording_session_id: sid.clone(),
            start_ms: seg.start_ms,
            end_ms: seg.end_ms,
            text: seg.text.clone(),
            language: seg.language.clone(),
            is_partial: false,
        })
        .collect();

    let _ = result_tx.send(InferenceResult { session_id: sid, segments }).await;
}

/// Stop 时的同步 flush：直接 await，保证有序写入 cache（绕过 MIN_INFER_SAMPLES 防数据丢失）
async fn flush_to_whisper(
    accumulator: &mut Vec<f32>,
    session_id: &Option<String>,
    language: &Option<String>,
    translate: bool,
    counter: &mut u32,
    engine: &Arc<Mutex<Option<WhisperEngine>>>,
    segments_cache: &Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,
) {
    let audio = std::mem::take(accumulator);
    if audio.is_empty() { return; }
    let sid = session_id.clone().unwrap_or_default();
    let lang = language.clone();

    {
        let guard = engine.lock().unwrap();
        if guard.is_none() { return; }
    }

    let engine_arc = Arc::clone(engine);
    let result = task::spawn_blocking(move || {
        let guard = engine_arc.lock().unwrap();
        if let Some(eng) = guard.as_ref() {
            eng.transcribe(&audio, lang.as_deref(), translate)
        } else {
            Ok(vec![])
        }
    })
    .await;

    match result {
        Ok(Ok(segments)) => {
            let current_counter = *counter;
            let new_payloads: Vec<SegmentPayload> = segments
                .iter()
                .enumerate()
                .map(|(i, seg)| SegmentPayload {
                    id: current_counter + i as u32,
                    recording_session_id: sid.clone(),
                    start_ms: seg.start_ms,
                    end_ms: seg.end_ms,
                    text: seg.text.clone(),
                    language: seg.language.clone(),
                    is_partial: false,
                })
                .collect();
            *counter += segments.len() as u32;
            if let Ok(mut cache) = segments_cache.lock() {
                cache.entry(sid).or_default().extend(new_payloads);
            }
        }
        Ok(Err(e)) => eprintln!("[pipeline] whisper error on stop flush: {e}"),
        Err(e) => eprintln!("[pipeline] spawn_blocking panicked on stop flush: {e}"),
    }
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;
    use super::TranscriptionCommand;

    #[test]
    fn test_channel_send_recv() {
        let (tx, rx) = mpsc::sync_channel::<TranscriptionCommand>(32);

        tx.send(TranscriptionCommand::AudioChunk(vec![0.0f32; 1600])).unwrap();
        tx.send(TranscriptionCommand::Pause { session_id: "test-session".into() }).unwrap();
        tx.send(TranscriptionCommand::Resume { session_id: "test-session".into() }).unwrap();
        let (done_tx, _done_rx) = tokio::sync::oneshot::channel();
        tx.send(TranscriptionCommand::Stop { session_id: "test-session".into(), done_tx }).unwrap();

        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::AudioChunk(_)));
        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Pause { .. }));
        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Resume { .. }));
        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Stop { .. }));
    }

    #[test]
    fn test_sync_sender_backpressure() {
        let (tx, _rx) = mpsc::sync_channel::<TranscriptionCommand>(1);
        tx.try_send(TranscriptionCommand::AudioChunk(vec![0.0; 100])).unwrap();
        let result = tx.try_send(TranscriptionCommand::AudioChunk(vec![0.0; 100]));
        assert!(result.is_err(), "should fail when channel is full");
    }

    #[test]
    fn test_channel_disconnected() {
        let (tx, rx) = mpsc::sync_channel::<TranscriptionCommand>(4);
        drop(rx);
        let result = tx.send(TranscriptionCommand::AudioChunk(vec![]));
        assert!(result.is_err());
    }

    #[test]
    fn test_pause_flush_constants() {
        // 验证常量符合设计规格
        assert_eq!(super::PAUSE_FLUSH_MS, 500);
        assert_eq!(super::MIN_INFER_SAMPLES, 8_000);
        assert_eq!(super::MAX_ACCUM_SAMPLES, 16_000 * 25);
    }
}

#[cfg(test)]
mod integration_tests {
    use std::path::Path;
    use crate::transcription::engine::WhisperEngine;

    #[test]
    #[ignore = "requires whisper model file at /tmp/ggml-base.bin"]
    fn test_whisper_engine_transcribe_silence() {
        let model_path = Path::new("/tmp/ggml-base.bin");
        if !model_path.exists() {
            eprintln!("model not found, skipping");
            return;
        }
        let engine = WhisperEngine::new(model_path).expect("engine init failed");
        let audio = vec![0.0f32; 16_000];
        let segments = engine.transcribe(&audio, None, false)
            .expect("transcribe failed");
        for seg in &segments {
            assert!(seg.text.trim().is_empty() || seg.text.len() < 5,
                "unexpected text from silence: '{}'", seg.text);
        }
    }
}
