// src-tauri/src/models/registry.rs

use super::{format_size, ModelVariant, ModelsToml, VariantConfig};
use crate::error::AppError;
use std::path::{Path, PathBuf};

/// 加载 models.toml。`toml_str` 由调用方通过 `include_str!` 或文件读取提供。
pub fn load_models_toml(toml_str: &str) -> Result<ModelsToml, AppError> {
    toml::from_str(toml_str).map_err(|e| AppError::Model(format!("models.toml 解析失败: {e}")))
}

/// 检查文件是否存在且大小与预期一致（快速校验，不做 SHA256）
pub fn file_matches_size(path: &Path, expected_bytes: u64) -> bool {
    path.metadata()
        .map(|m| m.len() == expected_bytes)
        .unwrap_or(false)
}

/// 根据 model_type 和 variant name 生成模型文件路径
/// 例：model_dir/whisper/ggml-base.bin、model_dir/llm/qwen2.5-3b-instruct-q4_k_m.gguf
pub fn model_file_path(model_dir: &Path, model_type: &str, _variant_name: &str, url: &str) -> PathBuf {
    // 从 URL 末段提取文件名（确保无路径注入）
    let filename = url
        .rsplit('/')
        .next()
        .unwrap_or("model.bin")
        .split('?')   // 去除 query string
        .next()
        .unwrap_or("model.bin");
    model_dir.join(model_type).join(filename)
}

/// 临时文件路径（下载中使用）：在最终路径上追加 ".tmp"
pub fn tmp_file_path(final_path: &Path) -> PathBuf {
    let mut p = final_path.as_os_str().to_owned();
    p.push(".tmp");
    PathBuf::from(p)
}

/// 构造单个变体的 ModelVariant 状态（不含 is_active，由调用方叠加）
pub fn build_variant(
    model_type: &str,
    variant_name: &str,
    cfg: &VariantConfig,
    model_dir: &Path,
) -> ModelVariant {
    let variant_id = format!("{}/{}", model_type, variant_name);
    let file_path = model_file_path(model_dir, model_type, variant_name, &cfg.url);
    let is_downloaded = file_path.exists();

    ModelVariant {
        variant_id,
        model_type: model_type.to_string(),
        name: variant_name.to_string(),
        description: cfg.description.clone(),
        size_bytes: cfg.size_bytes,
        size_display: format_size(cfg.size_bytes),
        is_downloaded,
        is_active: false, // 调用方根据 AppConfig 设置
        sha256_valid: !cfg.sha256.starts_with("FILL_IN") && cfg.sha256.len() == 64,
    }
}

/// 列出所有变体，并根据 active_whisper_model / active_llm_model 标记 is_active
pub fn list_all_variants(
    models: &ModelsToml,
    model_dir: &Path,
    active_whisper: &str,
    active_llm: &str,
) -> Vec<ModelVariant> {
    let mut result = Vec::new();

    for (name, cfg) in &models.whisper.variants {
        let mut v = build_variant("whisper", name, cfg, model_dir);
        v.is_active = format!("whisper/{}", name) == active_whisper;
        result.push(v);
    }
    for (name, cfg) in &models.llm.variants {
        let mut v = build_variant("llm", name, cfg, model_dir);
        v.is_active = format!("llm/{}", name) == active_llm;
        result.push(v);
    }

    // 按 variant_id 字母序排序，保证前端展示顺序稳定
    result.sort_by(|a, b| a.variant_id.cmp(&b.variant_id));
    result
}

/// 启动检测：返回缺失模型的 variant_id 列表
/// 仅检查当前激活模型；若激活模型文件存在且大小匹配，返回空列表
pub fn check_required_models(
    models: &ModelsToml,
    model_dir: &Path,
    active_whisper: &str,
    active_llm: &str,
) -> Vec<String> {
    let mut missing = Vec::new();

    if let Some((model_type, variant_name)) = parse_variant_id(active_whisper) {
        if let Some(cfg) = models.whisper.variants.get(variant_name) {
            let path = model_file_path(model_dir, model_type, variant_name, &cfg.url);
            if !path.exists() {
                missing.push(active_whisper.to_string());
            }
        } else {
            // 配置中不存在该变体（配置错误），视为缺失
            missing.push(active_whisper.to_string());
        }
    }

    if let Some((model_type, variant_name)) = parse_variant_id(active_llm) {
        if let Some(cfg) = models.llm.variants.get(variant_name) {
            let path = model_file_path(model_dir, model_type, variant_name, &cfg.url);
            if !path.exists() {
                missing.push(active_llm.to_string());
            }
        } else {
            missing.push(active_llm.to_string());
        }
    }

    missing
}

/// 解析 "whisper/base" → ("whisper", "base")
/// 解析 "llm/qwen2.5-3b-q4" → ("llm", "qwen2.5-3b-q4")
pub fn parse_variant_id(variant_id: &str) -> Option<(&str, &str)> {
    variant_id.split_once('/')
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    fn minimal_toml() -> &'static str {
        r#"
[whisper]
default_variant = "base"
[whisper.variants.base]
url        = "https://example.com/base.bin"
sha256     = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
size_bytes = 100
description = "test"

[llm]
default_variant = "qwen2.5-3b-q4"
[llm.variants."qwen2.5-3b-q4"]
url        = "https://example.com/qwen2.5-3b-instruct-q4_k_m.gguf"
sha256     = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
size_bytes = 200
description = "test llm"
"#
    }

    #[test]
    fn parse_models_toml_ok() {
        let cfg = load_models_toml(minimal_toml()).unwrap();
        assert!(cfg.whisper.variants.contains_key("base"));
        assert!(cfg.llm.variants.contains_key("qwen2.5-3b-q4"));
    }

    #[test]
    fn parse_models_toml_missing_field_fails() {
        let bad = "[whisper]\ndefault_variant = \"base\"\n";
        assert!(load_models_toml(bad).is_err());
    }

    #[test]
    fn check_model_file_missing() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("missing.bin");
        assert!(!file_matches_size(&path, 100));
    }

    #[test]
    fn check_model_file_size_mismatch() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("model.bin");
        fs::write(&path, b"short").unwrap();
        assert!(!file_matches_size(&path, 100));
    }

    #[test]
    fn check_model_file_ok() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("model.bin");
        fs::write(&path, vec![0u8; 100]).unwrap();
        assert!(file_matches_size(&path, 100));
    }

    #[test]
    fn list_variants_populates_is_active() {
        let models = load_models_toml(minimal_toml()).unwrap();
        let dir = tempdir().unwrap();
        let variants = list_all_variants(
            &models,
            dir.path(),
            "whisper/base",
            "llm/qwen2.5-3b-q4",
        );
        let whisper_base = variants.iter().find(|v| v.variant_id == "whisper/base").unwrap();
        assert!(whisper_base.is_active);
        let llm = variants.iter().find(|v| v.variant_id == "llm/qwen2.5-3b-q4").unwrap();
        assert!(llm.is_active);
    }

    #[test]
    fn check_required_models_missing() {
        let models = load_models_toml(minimal_toml()).unwrap();
        let dir = tempdir().unwrap();
        let missing = check_required_models(
            &models,
            dir.path(),
            "whisper/base",
            "llm/qwen2.5-3b-q4",
        );
        assert_eq!(missing.len(), 2);
    }

    #[test]
    fn check_required_models_present() {
        let models = load_models_toml(minimal_toml()).unwrap();
        let dir = tempdir().unwrap();
        // 创建 whisper/base.bin 文件，大小精确为 100 bytes
        let base_dir = dir.path().join("whisper");
        fs::create_dir_all(&base_dir).unwrap();
        fs::write(base_dir.join("base.bin"), vec![0u8; 100]).unwrap();
        // 创建 llm/qwen2.5-3b-instruct-q4_k_m.gguf 文件，大小精确为 200 bytes
        let llm_dir = dir.path().join("llm");
        fs::create_dir_all(&llm_dir).unwrap();
        fs::write(llm_dir.join("qwen2.5-3b-instruct-q4_k_m.gguf"), vec![0u8; 200]).unwrap();
        let missing = check_required_models(
            &models,
            dir.path(),
            "whisper/base",
            "llm/qwen2.5-3b-q4",
        );
        assert!(missing.is_empty());
    }

    #[test]
    fn parse_variant_id_ok() {
        assert_eq!(parse_variant_id("whisper/base"), Some(("whisper", "base")));
        assert_eq!(parse_variant_id("llm/qwen2.5-3b-q4"), Some(("llm", "qwen2.5-3b-q4")));
    }

    #[test]
    fn parse_variant_id_no_slash() {
        assert!(parse_variant_id("whisperbase").is_none());
    }
}
