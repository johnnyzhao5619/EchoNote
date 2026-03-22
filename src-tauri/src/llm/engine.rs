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
    model::{params::LlamaModelParams, AddBos, LlamaModel, Special},
    sampling::LlamaSampler,
};

use crate::error::AppError;

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

    pub fn generate(
        &self,
        system_prompt: &str,
        user_prompt: &str,
        max_tokens: u32,
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

        // Build sampler chain: temp -> top_p -> greedy
        let mut sampler = LlamaSampler::chain_simple([
            LlamaSampler::temp(0.7),
            LlamaSampler::top_p(0.9, 1),
            LlamaSampler::greedy(),
        ]);

        let mut result = String::new();
        let mut n_cur = n_prompt as i32;

        loop {
            if n_cur >= n_prompt as i32 + max_tokens as i32 {
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
                .token_to_str(new_token, Special::Tokenize)
                .map_err(|e| AppError::Llm(format!("token to str: {e}")))?;

            result.push_str(&piece);

            if !token_cb(piece) {
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

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
                16,
                |tok| {
                    tokens.push(tok);
                    true
                },
            )
            .expect("generate");

        assert!(!result.is_empty(), "generated text should not be empty");
        assert!(!tokens.is_empty(), "should have received tokens via callback");
    }
}
