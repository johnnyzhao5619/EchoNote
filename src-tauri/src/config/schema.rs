use serde::{Deserialize, Serialize};
use specta::Type;
use std::path::{Path, PathBuf};

/// Full application configuration. Stored as a single JSON blob
/// in `app_settings` under the key `"app_config"`.
#[derive(Serialize, Deserialize, Clone, Type)]
#[serde(default)]
pub struct AppConfig {
    /// UI locale. Default: "zh_CN"
    pub locale: String,

    /// Active theme display name. Default: "Tokyo Night"
    pub active_theme: String,

    /// Active whisper model variant id. Default: "whisper/base"
    pub active_whisper_model: String,

    /// Active LLM model variant id. Default: "llm/qwen2.5-3b-q4"
    pub active_llm_model: String,

    /// LLM context window size in tokens. Default: 4096
    pub llm_context_size: u32,

    /// Path to the vault directory (workspace documents). Default: {APP_DATA}/vault
    pub vault_path: String,

    /// Path to the recordings directory (audio WAV files). Default: {APP_DATA}/recordings
    pub recordings_path: String,

    /// Default recording mode. Values: "record_only" | "transcribe_only" | "transcribe_and_translate"
    /// Default: "transcribe_only"
    pub default_recording_mode: String,

    /// Default transcription language. None = auto-detect.
    pub default_language: Option<String>,

    /// Default translation target language. Default: "en"
    pub default_target_language: String,

    /// VAD energy threshold (0.0–1.0). Default: 0.02
    pub vad_threshold: f32,

    /// Automatically trigger AI processing after recording stops. Default: false
    pub auto_llm_on_stop: bool,

    /// Last microphone device ID used. None = not yet set (use system default). Default: None
    pub last_used_device_id: Option<String>,

    /// Default LLM task type. Values: "summary" | "meeting_brief". Default: "summary"
    pub default_llm_task: String,

    /// Model download mirror.
    /// "" / "default" = use URLs as-is from models.toml (huggingface.co)
    /// "hf-mirror"    = replace huggingface.co with hf-mirror.com (China-friendly)
    /// Custom URL     = replace huggingface.co with this base URL
    pub model_mirror: String,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            locale:                  "zh_CN".to_string(),
            active_theme:            "Tokyo Night".to_string(),
            active_whisper_model:    "whisper/base".to_string(),
            active_llm_model:        "llm/qwen2.5-3b-q4".to_string(),
            llm_context_size:        4096,
            vault_path:              String::new(), // populated at runtime from APP_DATA
            recordings_path:         String::new(), // populated at runtime from APP_DATA
            default_recording_mode:  "transcribe_only".to_string(),
            default_language:        None,
            default_target_language: "en".to_string(),
            vad_threshold:           0.010, // iPhone Continuity Camera RMS 通常 0.005–0.030
            auto_llm_on_stop:        false,
            last_used_device_id:     None,
            default_llm_task:        "summary".to_string(),
            model_mirror:            String::new(), // default: use URLs as-is
        }
    }
}

pub fn default_vault_path(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("vault")
}

pub fn default_recordings_path(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("recordings")
}

pub fn default_models_path(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("models")
}

pub fn normalized_app_config(mut config: AppConfig, app_data_dir: &Path) -> AppConfig {
    if config.vault_path.trim().is_empty() {
        config.vault_path = default_vault_path(app_data_dir)
            .to_string_lossy()
            .into_owned();
    }

    if config.recordings_path.trim().is_empty() {
        config.recordings_path = default_recordings_path(app_data_dir)
            .to_string_lossy()
            .into_owned();
    }

    config
}

/// Partial update payload. Every field is `Option<T>`.
/// `None` means "do not update this field".
/// For `default_language`, `Some(None)` clears the value; `Some(Some("zh"))` sets it.
///
/// `skip_serializing_if = "Option::is_none"` ensures that undefined fields
/// from the frontend are absent from the serialized JSON.
#[derive(Serialize, Deserialize, Default, Clone, Type)]
pub struct PartialAppConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub locale: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub active_theme: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub active_whisper_model: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub active_llm_model: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub llm_context_size: Option<u32>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub vault_path: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub recordings_path: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_recording_mode: Option<String>,

    /// `Some(None)` clears the language (auto-detect); `Some(Some("zh"))` sets it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_language: Option<Option<String>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_target_language: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub vad_threshold: Option<f32>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub auto_llm_on_stop: Option<bool>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_used_device_id: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_llm_task: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_mirror: Option<String>,
}

/// Apply a `PartialAppConfig` onto a mutable `AppConfig`.
/// Only fields with `Some(...)` values are updated.
pub fn apply_partial(config: &mut AppConfig, partial: PartialAppConfig) {
    if let Some(v) = partial.locale                  { config.locale                  = v; }
    if let Some(v) = partial.active_theme            { config.active_theme            = v; }
    if let Some(v) = partial.active_whisper_model    { config.active_whisper_model    = v; }
    if let Some(v) = partial.active_llm_model        { config.active_llm_model        = v; }
    if let Some(v) = partial.llm_context_size        { config.llm_context_size        = v; }
    if let Some(v) = partial.vault_path              { config.vault_path              = v; }
    if let Some(v) = partial.recordings_path         { config.recordings_path         = v; }
    if let Some(v) = partial.default_recording_mode  { config.default_recording_mode  = v; }
    if let Some(v) = partial.default_language        { config.default_language        = v; }
    if let Some(v) = partial.default_target_language { config.default_target_language = v; }
    if let Some(v) = partial.vad_threshold           { config.vad_threshold           = v; }
    if let Some(v) = partial.auto_llm_on_stop        { config.auto_llm_on_stop        = v; }
    if let Some(v) = partial.last_used_device_id     { config.last_used_device_id     = Some(v); }
    if let Some(v) = partial.default_llm_task        { config.default_llm_task        = v; }
    if let Some(v) = partial.model_mirror            { config.model_mirror            = v; }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Default AppConfig must serialize and round-trip through JSON correctly.
    #[test]
    fn test_app_config_default_serialization() {
        let cfg = AppConfig::default();
        let json = serde_json::to_string(&cfg).expect("should serialize");
        let restored: AppConfig = serde_json::from_str(&json).expect("should deserialize");
        assert_eq!(cfg.locale, restored.locale);
        assert_eq!(cfg.active_theme, restored.active_theme);
        assert_eq!(cfg.vad_threshold, restored.vad_threshold);
    }

    /// Default locale must be "zh_CN".
    #[test]
    fn test_default_locale_is_zh_cn() {
        let cfg = AppConfig::default();
        assert_eq!(cfg.locale, "zh_CN");
    }

    /// Default active_theme must be "Tokyo Night" (display name, not slug).
    #[test]
    fn test_default_theme() {
        let cfg = AppConfig::default();
        assert_eq!(cfg.active_theme, "Tokyo Night");
    }

    /// Default vad_threshold must be 0.010 (iPhone-friendly).
    #[test]
    fn test_default_vad_threshold() {
        let cfg = AppConfig::default();
        assert!((cfg.vad_threshold - 0.010).abs() < f32::EPSILON);
    }

    /// PartialAppConfig with only `locale` set must not affect other fields.
    #[test]
    fn test_partial_config_apply_locale_only() {
        let mut cfg = AppConfig::default();
        let partial = PartialAppConfig {
            locale: Some("en_US".to_string()),
            ..Default::default()
        };
        apply_partial(&mut cfg, partial);
        assert_eq!(cfg.locale, "en_US");
        // Other fields remain at default
        assert_eq!(cfg.active_theme, "Tokyo Night");
        assert!((cfg.vad_threshold - 0.010).abs() < f32::EPSILON);
    }

    /// PartialAppConfig with `default_language = Some(None)` must clear the field.
    #[test]
    fn test_partial_config_clear_default_language() {
        let mut cfg = AppConfig {
            default_language: Some("zh".to_string()),
            ..Default::default()
        };
        let partial = PartialAppConfig {
            default_language: Some(None),
            ..Default::default()
        };
        apply_partial(&mut cfg, partial);
        assert!(cfg.default_language.is_none());
    }

    /// PartialAppConfig with None fields must leave the config unchanged.
    #[test]
    fn test_partial_config_empty_is_noop() {
        let cfg_before = AppConfig::default();
        let mut cfg = cfg_before.clone();
        apply_partial(&mut cfg, PartialAppConfig::default());
        assert_eq!(
            serde_json::to_string(&cfg).unwrap(),
            serde_json::to_string(&cfg_before).unwrap()
        );
    }

    /// PartialAppConfig must skip None fields during JSON serialization.
    #[test]
    fn test_partial_config_serialization_skips_none() {
        let partial = PartialAppConfig {
            locale: Some("fr_FR".to_string()),
            ..Default::default()
        };
        let json = serde_json::to_string(&partial).unwrap();
        assert!(json.contains("\"locale\""), "locale should be present");
        assert!(!json.contains("\"active_theme\""), "None fields should be absent");
    }

    #[test]
    fn test_normalized_app_config_fills_runtime_paths() {
        let cfg = normalized_app_config(
            AppConfig::default(),
            Path::new("/tmp/echonote-app-data"),
        );

        assert_eq!(cfg.vault_path, "/tmp/echonote-app-data/vault");
        assert_eq!(cfg.recordings_path, "/tmp/echonote-app-data/recordings");
    }
}
