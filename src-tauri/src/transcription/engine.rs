// src-tauri/src/transcription/engine.rs

use std::path::Path;
use std::sync::{Arc, Mutex};
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};
use crate::error::AppError;

pub struct RawSegment {
    pub start_ms: u32,
    pub end_ms: u32,
    pub text: String,
    pub language: String,
}

pub struct WhisperEngine {
    /// Arc<Mutex<>> 使多线程场景下安全共享；
    /// 实际只从 spawn_blocking 单线程串行访问，Mutex 主要用于满足 Send 约束
    pub(crate) ctx: Arc<Mutex<WhisperContext>>,
}

impl WhisperEngine {
    pub fn new(model_path: &Path) -> Result<Self, AppError> {
        let params = WhisperContextParameters::default();
        let ctx = WhisperContext::new_with_params(
            model_path.to_str().ok_or_else(|| AppError::Model("invalid path".into()))?,
            params,
        )
        .map_err(|e| AppError::Model(format!("whisper init: {e}")))?;
        Ok(Self { ctx: Arc::new(Mutex::new(ctx)) })
    }

    /// 同步阻塞推理，必须在 `tokio::task::spawn_blocking` 内调用。
    /// `audio`: 16000Hz 单声道 f32
    /// `language`: None = 自动检测；Some("zh") / Some("en") 等 ISO 639-1 代码
    /// `translate`: true = whisper task=translate（输出英文）
    pub fn transcribe(
        &self,
        audio: &[f32],
        language: Option<&str>,
        translate: bool,
    ) -> Result<Vec<RawSegment>, AppError> {
        let ctx = self.ctx.lock()
            .map_err(|_| AppError::Transcription("whisper ctx poisoned".into()))?;

        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(true);
        params.set_translate(translate);
        if let Some(lang) = language {
            params.set_language(Some(lang));
        }

        // ── 实时转录最佳实践参数 ─────────────────────────────────────
        // no_speech_thold：超过此阈值认为是无语音，抑制幻觉输出（默认 0.6）
        params.set_no_speech_thold(0.6);
        // logprob_thold：段落平均 log 概率低于此值时丢弃（默认 -1.0）
        params.set_logprob_thold(-1.0);
        // entropy_thold：熵值超过此值时认为是重复幻觉，丢弃段落（等价于 OpenAI compression_ratio_threshold，默认 2.4）
        params.set_entropy_thold(2.4);
        // 不强制单段落，允许 whisper 自由分割较长音频
        params.set_single_segment(false);
        // temperature = 0（贪心解码），兼顾速度与一致性
        params.set_temperature(0.0);

        let mut state = ctx.create_state()
            .map_err(|e| AppError::Transcription(format!("create state: {e}")))?;
        state.full(params, audio)
            .map_err(|e| AppError::Transcription(format!("full: {e}")))?;

        let n = state.full_n_segments()
            .map_err(|e| AppError::Transcription(e.to_string()))?;

        let mut segments = Vec::with_capacity(n as usize);
        for i in 0..n {
            let text = state.full_get_segment_text(i)
                .map_err(|e| AppError::Transcription(e.to_string()))?;
            let t0 = state.full_get_segment_t0(i)
                .map_err(|e| AppError::Transcription(e.to_string()))?;
            let t1 = state.full_get_segment_t1(i)
                .map_err(|e| AppError::Transcription(e.to_string()))?;
            // whisper 时间戳单位为 10ms，转换为 ms
            segments.push(RawSegment {
                start_ms: (t0 * 10) as u32,
                end_ms: (t1 * 10) as u32,
                text: text.trim().to_string(),
                language: language.unwrap_or("auto").to_string(),
            });
        }
        Ok(segments)
    }
}

// 需要 Send + Sync 以便在 Arc 中跨线程使用
// WhisperContext 本身满足 Send（whisper-rs 文档说明），Mutex 提供 Sync
unsafe impl Send for WhisperEngine {}
unsafe impl Sync for WhisperEngine {}
