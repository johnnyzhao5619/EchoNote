// src-tauri/src/llm/engine.rs
//
// llama-cpp-2 同步封装。
// 注意：generate() 是阻塞调用，调用方必须通过 tokio::task::spawn_blocking 包裹。

use std::num::NonZeroU32;
use std::path::Path;
use std::sync::Arc;

use llama_cpp_2::{
    context::params::LlamaContextParams,
    llama_backend::LlamaBackend,
    llama_batch::LlamaBatch,
    model::{params::LlamaModelParams, AddBos, LlamaModel},
    sampling::LlamaSampler,
};

use crate::error::AppError;

const TRUNCATION_MARKER: &str = "\n\n...[content truncated for local context window]...\n\n";
const DEFAULT_RESERVED_CONTEXT_TOKENS: u32 = 256;

// llama-cpp-2 的 LlamaBackend 需全局初始化一次。
// 使用 OnceLock<Result<...>> 存储初始化结果以兼容 stable Rust。
static LLAMA_BACKEND: std::sync::OnceLock<Result<LlamaBackend, String>> =
    std::sync::OnceLock::new();

fn get_backend() -> Result<&'static LlamaBackend, AppError> {
    let result = LLAMA_BACKEND.get_or_init(|| {
        LlamaBackend::init().map_err(|e| format!("backend init: {e}"))
    });
    result
        .as_ref()
        .map_err(|e| AppError::Llm(e.clone()))
}

pub struct ContextParams {
    pub ctx_size: u32,
    pub n_threads: i32,
}

impl Default for ContextParams {
    fn default() -> Self {
        Self {
            ctx_size: 4096,
            n_threads: num_cpus::get() as i32 / 2,
        }
    }
}

pub struct LlmEngine {
    pub inner_model: Arc<LlamaModel>,
    pub ctx_params: ContextParams,
}

#[derive(Debug, Clone)]
pub struct GenerationProfile {
    pub max_tokens: u32,
    pub max_input_tokens: u32,
    pub temperature: f32,
    pub top_p: f32,
    pub top_k: i32,
    pub min_p: f32,
    pub repeat_penalty: f32,
    pub frequency_penalty: f32,
    pub presence_penalty: f32,
    pub dry_multiplier: f32,
    pub dry_base: f32,
    pub dry_allowed_length: i32,
    pub dry_penalty_last_n: i32,
    pub stop_sequences: Vec<String>,
    pub grammar: Option<String>,
}

impl GenerationProfile {
    pub fn new(ctx_size: u32, max_tokens: u32, grammar: Option<String>) -> Self {
        let reserved = max_tokens.saturating_add(DEFAULT_RESERVED_CONTEXT_TOKENS);
        let max_input_tokens = ctx_size.saturating_sub(reserved).max(256);

        Self {
            max_tokens,
            max_input_tokens,
            temperature: 0.0,
            top_p: 0.9,
            top_k: 40,
            min_p: 0.05,
            repeat_penalty: 1.15,
            frequency_penalty: 0.05,
            presence_penalty: 0.05,
            dry_multiplier: 0.8,
            dry_base: 1.75,
            dry_allowed_length: 2,
            dry_penalty_last_n: 64,
            stop_sequences: vec!["<|im_end|>".to_string()],
            grammar,
        }
    }
}

impl LlmEngine {
    pub fn new(model_path: &Path, ctx_params: ContextParams) -> Result<Self, AppError> {
        let backend = get_backend()?;

        let model_params = LlamaModelParams::default();
        let model = LlamaModel::load_from_file(backend, model_path, &model_params)
            .map_err(|e| AppError::Llm(format!("load model: {e}")))?;

        Ok(Self {
            inner_model: Arc::new(model),
            ctx_params,
        })
    }

    pub fn fit_text_to_context(
        &self,
        text: &str,
        max_input_tokens: u32,
    ) -> Result<String, AppError> {
        let token_count = self
            .inner_model
            .str_to_token(text, AddBos::Never)
            .map_err(|e| AppError::Llm(format!("tokenize input text: {e}")))?
            .len() as u32;

        if token_count <= max_input_tokens {
            return Ok(text.to_string());
        }

        let chars: Vec<char> = text.chars().collect();
        let mut head_chars = ((chars.len() as f32) * 0.4).ceil() as usize;
        let mut tail_chars = chars.len().saturating_sub(head_chars);
        let min_chunk = 128usize.min(chars.len());

        while head_chars >= min_chunk && tail_chars >= min_chunk {
            let head: String = chars[..head_chars].iter().collect();
            let tail: String = chars[chars.len().saturating_sub(tail_chars)..].iter().collect();
            let candidate = format!("{head}{TRUNCATION_MARKER}{tail}");
            let candidate_tokens = self
                .inner_model
                .str_to_token(&candidate, AddBos::Never)
                .map_err(|e| AppError::Llm(format!("tokenize cropped text: {e}")))?
                .len() as u32;

            if candidate_tokens <= max_input_tokens {
                return Ok(candidate);
            }

            head_chars = ((head_chars as f32) * 0.9) as usize;
            tail_chars = ((tail_chars as f32) * 0.9) as usize;
        }

        Ok(chars
            .iter()
            .take(min_chunk)
            .collect::<String>())
    }

    pub fn generate(
        &self,
        system_prompt: &str,
        user_prompt: &str,
        profile: &GenerationProfile,
        mut token_cb: impl FnMut(String) -> bool,
    ) -> Result<String, AppError> {
        let backend = get_backend()?;

        let ctx_params = LlamaContextParams::default()
            .with_n_ctx(NonZeroU32::new(self.ctx_params.ctx_size))
            .with_n_threads(self.ctx_params.n_threads);

        let mut ctx = self
            .inner_model
            .new_context(backend, ctx_params)
            .map_err(|e| AppError::Llm(format!("create context: {e}")))?;

        // 构建 ChatML 格式 prompt
        let full_prompt = format!(
            "<|im_start|>system\n{system_prompt}<|im_end|>\n\
             <|im_start|>user\n{user_prompt}<|im_end|>\n\
             <|im_start|>assistant\n"
        );

        // Tokenize
        let tokens = self
            .inner_model
            .str_to_token(&full_prompt, AddBos::Always)
            .map_err(|e| AppError::Llm(format!("tokenize: {e}")))?;

        let n_prompt = tokens.len();
        let mut batch = LlamaBatch::new(n_prompt.max(512), 1);

        for (i, &tok) in tokens.iter().enumerate() {
            batch
                .add(tok, i as i32, &[0], i == n_prompt - 1)
                .map_err(|e| AppError::Llm(format!("batch add: {e}")))?;
        }

        ctx.decode(&mut batch)
            .map_err(|e| AppError::Llm(format!("prefill decode: {e}")))?;

        let mut samplers = Vec::new();

        if let Some(grammar) = &profile.grammar {
            samplers.push(
                LlamaSampler::grammar(&self.inner_model, grammar, "root")
                    .map_err(|e| AppError::Llm(format!("grammar init: {e}")))?,
            );
        }

        samplers.extend([
            LlamaSampler::penalties(
                -1,
                profile.repeat_penalty,
                profile.frequency_penalty,
                profile.presence_penalty,
            ),
            LlamaSampler::dry(
                &self.inner_model,
                profile.dry_multiplier,
                profile.dry_base,
                profile.dry_allowed_length,
                profile.dry_penalty_last_n,
                ["\n", "\n\n", ". ", "。", "!", "！", "?", "？"],
            ),
        ]);

        if profile.temperature > 0.0 {
            samplers.push(LlamaSampler::top_k(profile.top_k));
            samplers.push(LlamaSampler::top_p(profile.top_p, 1));
            samplers.push(LlamaSampler::min_p(profile.min_p, 1));
            samplers.push(LlamaSampler::temp(profile.temperature));
            samplers.push(LlamaSampler::dist(0));
        } else {
            samplers.push(LlamaSampler::greedy());
        }

        let mut sampler = LlamaSampler::chain_simple(samplers);

        let mut result = String::new();
        let mut n_cur = n_prompt as i32;
        let mut decoder = encoding_rs::UTF_8.new_decoder();

        loop {
            if n_cur >= n_prompt as i32 + profile.max_tokens as i32 {
                break;
            }

            // sample the next token from the last position in the batch
            let new_token = sampler.sample(&ctx, batch.n_tokens() - 1);
            sampler.accept(new_token);

            if self.inner_model.is_eog_token(new_token) {
                break;
            }

            let piece = self
                .inner_model
                .token_to_piece(new_token, &mut decoder, true, None)
                .map_err(|e| AppError::Llm(format!("token to str: {e}")))?;

            let clipped_piece = clip_stop_sequences(&piece, &profile.stop_sequences);
            if clipped_piece.is_empty() && contains_stop_sequence(&piece, &profile.stop_sequences) {
                break;
            }

            result.push_str(&clipped_piece);

            if !clipped_piece.is_empty() && !token_cb(clipped_piece) {
                break;
            }

            if should_stop_on_complete_structured_output(&result, &profile.grammar) {
                break;
            }

            if contains_stop_sequence(&piece, &profile.stop_sequences) {
                break;
            }

            batch.clear();
            batch
                .add(new_token, n_cur, &[0], true)
                .map_err(|e| AppError::Llm(format!("batch add loop: {e}")))?;

            ctx.decode(&mut batch)
                .map_err(|e| AppError::Llm(format!("decode loop: {e}")))?;

            n_cur += 1;
        }

        Ok(result)
    }
}

fn contains_stop_sequence(piece: &str, stop_sequences: &[String]) -> bool {
    stop_sequences.iter().any(|stop| piece.contains(stop))
}

fn clip_stop_sequences(piece: &str, stop_sequences: &[String]) -> String {
    let mut clipped = piece.to_string();
    for stop in stop_sequences {
        if let Some(index) = clipped.find(stop) {
            clipped.truncate(index);
            break;
        }
    }
    clipped
}

fn should_stop_on_complete_structured_output(result: &str, grammar: &Option<String>) -> bool {
    grammar.is_some() && serde_json::from_str::<serde_json::Value>(result.trim()).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    use crate::llm::{
        contracts::{finalize_task_output, structured_prompt_spec},
        LlmTaskType,
    };

    #[test]
    fn test_clip_stop_sequences_strips_im_end() {
        let piece = "hello<|im_end|>ignored";
        let clipped = clip_stop_sequences(piece, &["<|im_end|>".to_string()]);
        assert_eq!(clipped, "hello");
    }

    #[test]
    fn test_should_stop_on_complete_structured_output_when_json_is_complete() {
        assert!(should_stop_on_complete_structured_output(
            r#"{"summary":"ok","key_points":[]}"#,
            &Some("root ::= anything".to_string()),
        ));
        assert!(!should_stop_on_complete_structured_output(
            r#"{"summary":"incomplete""#,
            &Some("root ::= anything".to_string()),
        ));
        assert!(!should_stop_on_complete_structured_output(
            r#"{"summary":"ok"}"#,
            &None,
        ));
    }

    #[test]
    #[ignore]
    fn test_generate_smoke() {
        let model_path = std::env::var("ECHONOTE_LLM_MODEL_PATH").unwrap_or_else(|_| {
            panic!("Set ECHONOTE_LLM_MODEL_PATH to a .gguf file to run this test")
        });
        let path = PathBuf::from(model_path);
        let engine = LlmEngine::new(&path, ContextParams::default()).expect("engine init");

        let mut tokens = Vec::new();
        let result = engine
            .generate(
                "You are a helpful assistant.",
                "Say hello in one word.",
                &GenerationProfile::new(4096, 16, None),
                |tok| {
                    tokens.push(tok);
                    true
                },
            )
            .expect("generate");

        assert!(!result.is_empty(), "generated text should not be empty");
        assert!(!tokens.is_empty(), "should have received tokens via callback");
    }

    #[test]
    #[ignore]
    fn test_generate_summary_structured_smoke() {
        let model_path = std::env::var("ECHONOTE_LLM_MODEL_PATH").unwrap_or_else(|_| {
            panic!("Set ECHONOTE_LLM_MODEL_PATH to a .gguf file to run this test")
        });
        let path = PathBuf::from(model_path);
        let engine = LlmEngine::new(&path, ContextParams::default()).expect("engine init");

        let prompt_spec = structured_prompt_spec(
            &LlmTaskType::Summary,
            "Summarize the following transcript in Chinese:\n\n项目讨论集中在修复摘要重复问题，并决定本周内完成验证。",
        )
        .expect("summary prompt spec");
        let profile = GenerationProfile::new(4096, 96, prompt_spec.grammar.clone());

        let result = engine
            .generate(
                "You are a helpful assistant.",
                &prompt_spec.user_prompt,
                &profile,
                |_| true,
            )
            .expect("structured generate");

        let finalized = finalize_task_output(&LlmTaskType::Summary, &result)
            .expect("finalize structured summary");
        assert!(finalized.result_text.contains("## Summary"));
    }
}
