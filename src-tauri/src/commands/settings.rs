use tauri::State;
use crate::{
    config::{AppConfig, PartialAppConfig, normalized_app_config},
    error::AppError,
    state::AppState,
    storage::db::Database,
};

const CONFIG_KEY: &str = "app_config";

// ──────────────────────────────────────────────────────────────────────────────
// Internal helpers (used both by commands and tests)
// ──────────────────────────────────────────────────────────────────────────────

pub(crate) async fn get_config_inner(state: &AppState) -> Result<AppConfig, AppError> {
    let cfg = state.config.read().await;
    Ok(cfg.clone())
}

pub(crate) async fn update_config_inner(
    state: &AppState,
    partial: PartialAppConfig,
) -> Result<(), AppError> {
    state.update_config(partial).await?;
    Ok(())
}

pub(crate) async fn reset_config_inner(state: &AppState) -> Result<AppConfig, AppError> {
    state.persist_config(state.default_config()).await
}

/// Load AppConfig from `app_settings` DB on startup.
/// Returns `AppConfig::default()` if no row exists yet.
pub async fn load_config_from_db(
    db: &Database,
    app_data_dir: &std::path::Path,
) -> Result<AppConfig, AppError> {
    match db.load_setting(CONFIG_KEY).await? {
        None => Ok(normalized_app_config(AppConfig::default(), app_data_dir)),
        Some(json) => {
            let parsed: AppConfig = serde_json::from_str(&json)
                .map_err(|e| AppError::Storage(format!("parse config: {e}")))?;
            Ok(normalized_app_config(parsed, app_data_dir))
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Tauri commands (thin wrappers around inner helpers)
// ──────────────────────────────────────────────────────────────────────────────

#[tauri::command]
#[specta::specta]
pub async fn get_config(state: State<'_, AppState>) -> Result<AppConfig, AppError> {
    get_config_inner(&state).await
}

#[tauri::command]
#[specta::specta]
pub async fn update_config(
    state: State<'_, AppState>,
    partial: PartialAppConfig,
) -> Result<(), AppError> {
    update_config_inner(&state, partial).await
}

#[tauri::command]
#[specta::specta]
pub async fn reset_config(state: State<'_, AppState>) -> Result<AppConfig, AppError> {
    reset_config_inner(&state).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{config::AppConfig, storage::db::Database};
    use std::sync::Arc;
    use tokio::sync::RwLock;

    async fn make_state() -> AppState {
        use crate::models::{DownloadCommand, ModelsToml};
        use tokio::sync::mpsc;

        let app_data_dir = Arc::new(std::path::PathBuf::from("/tmp/echonote-settings-tests"));
        let db = Arc::new(Database::open("sqlite::memory:").await.unwrap());
        let config = Arc::new(RwLock::new(normalized_app_config(
            AppConfig::default(),
            app_data_dir.as_ref(),
        )));
        let model_config = Arc::new(ModelsToml {
            whisper: crate::models::ModelGroup {
                default_variant: "base".to_string(),
                variants: std::collections::HashMap::new(),
            },
            llm: crate::models::ModelGroup {
                default_variant: "qwen2.5-3b-q4".to_string(),
                variants: std::collections::HashMap::new(),
            },
        });
        let (download_tx, _rx) = mpsc::channel::<DownloadCommand>(1);
        let (transcription_tx, _trx) = std::sync::mpsc::sync_channel(1);
        AppState {
            app_data_dir,
            db,
            config,
            model_config,
            download_tx,
            transcription_tx,
            whisper_engine: std::sync::Arc::new(std::sync::Mutex::new(None)),
            capture_stop_tx: std::sync::Arc::new(std::sync::Mutex::new(None)),
            segments_cache: std::sync::Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
            pcm_cache: std::sync::Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
            current_session_id: std::sync::Arc::new(tokio::sync::Mutex::new(None)),
            resampler_done_rx: std::sync::Arc::new(tokio::sync::Mutex::new(None)),
            resampler_stop: std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
            audio_level: std::sync::Arc::new(std::sync::atomic::AtomicU32::new(0)),
            llm_tx: { let (tx, _) = tokio::sync::mpsc::channel(1); tx },
            llm_engine: std::sync::Arc::new(tokio::sync::Mutex::new(None)),
            active_llm_cancels: std::sync::Arc::new(dashmap::DashMap::new()),
            prompt_templates: std::sync::Arc::new(
                crate::llm::tasks::PromptTemplates {
                    summary: crate::llm::tasks::TaskTemplate { system: String::new(), user: String::new(), max_tokens: 512 },
                    meeting_brief: crate::llm::tasks::TaskTemplate { system: String::new(), user: String::new(), max_tokens: 1024 },
                    translation: crate::llm::tasks::TaskTemplate { system: String::new(), user: String::new(), max_tokens: 2048 },
                    qa: crate::llm::tasks::TaskTemplate { system: String::new(), user: String::new(), max_tokens: 512 },
                }
            ),
            llm_engine_status: std::sync::Arc::new(tokio::sync::Mutex::new(crate::llm::LlmEngineStatus::NotLoaded)),
        }
    }

    /// get_config_inner must return the current AppConfig.
    #[tokio::test]
    async fn test_get_config_returns_default() {
        let state = make_state().await;
        let cfg = get_config_inner(&state).await.unwrap();
        assert_eq!(cfg.locale, "zh_CN");
        assert_eq!(cfg.active_theme, "Tokyo Night");
        assert_eq!(cfg.vault_path, "/tmp/echonote-settings-tests/vault");
        assert_eq!(cfg.recordings_path, "/tmp/echonote-settings-tests/recordings");
    }

    /// update_config_inner must persist a locale change to the DB and update in-memory state.
    #[tokio::test]
    async fn test_update_config_persists_locale() {
        let state = make_state().await;
        let partial = crate::config::PartialAppConfig {
            locale: Some("en_US".to_string()),
            ..Default::default()
        };
        update_config_inner(&state, partial).await.unwrap();

        // In-memory state should reflect the change
        let cfg = state.config.read().await;
        assert_eq!(cfg.locale, "en_US");

        // DB should have the updated value
        let row: (String, i64) = sqlx::query_as(
            "SELECT value, updated_at FROM app_settings WHERE key = 'app_config'"
        )
        .fetch_one(&state.db.pool)
        .await
        .unwrap();
        let saved: AppConfig = serde_json::from_str(&row.0).unwrap();
        assert_eq!(saved.locale, "en_US");
    }

    /// reset_config_inner must restore defaults and persist to DB.
    #[tokio::test]
    async fn test_reset_config_restores_defaults() {
        let state = make_state().await;

        // First set a non-default value
        let partial = crate::config::PartialAppConfig {
            locale: Some("fr_FR".to_string()),
            ..Default::default()
        };
        update_config_inner(&state, partial).await.unwrap();

        // Now reset
        let cfg = reset_config_inner(&state).await.unwrap();
        assert_eq!(cfg.locale, "zh_CN", "reset should restore default locale");

        // In-memory state must be restored
        let in_mem = state.config.read().await;
        assert_eq!(in_mem.locale, "zh_CN");
        assert_eq!(in_mem.vault_path, "/tmp/echonote-settings-tests/vault");
        assert_eq!(in_mem.recordings_path, "/tmp/echonote-settings-tests/recordings");
    }

    /// Two successive update_config calls must accumulate changes correctly.
    #[tokio::test]
    async fn test_update_config_accumulates_changes() {
        let state = make_state().await;

        let p1 = crate::config::PartialAppConfig {
            locale: Some("en_US".to_string()),
            ..Default::default()
        };
        update_config_inner(&state, p1).await.unwrap();

        let p2 = crate::config::PartialAppConfig {
            active_theme: Some("tokyo-night-storm".to_string()),
            ..Default::default()
        };
        update_config_inner(&state, p2).await.unwrap();

        let cfg = get_config_inner(&state).await.unwrap();
        assert_eq!(cfg.locale, "en_US");
        assert_eq!(cfg.active_theme, "tokyo-night-storm");
    }

    /// Full round-trip: open DB → load config (empty → default) → update → reload → verify.
    #[tokio::test]
    async fn test_full_round_trip() {
        let state = make_state().await;

        // 1. First load should return defaults (no row in DB yet)
        let loaded = load_config_from_db(&state.db, state.app_data_dir.as_ref()).await.unwrap();
        assert_eq!(loaded.locale, "zh_CN");

        // 2. Update locale
        let partial = crate::config::PartialAppConfig {
            locale: Some("fr_FR".to_string()),
            vad_threshold: Some(0.05),
            ..Default::default()
        };
        update_config_inner(&state, partial).await.unwrap();

        // 3. Re-load from DB should reflect changes
        let reloaded = load_config_from_db(&state.db, state.app_data_dir.as_ref()).await.unwrap();
        assert_eq!(reloaded.locale, "fr_FR");
        assert!((reloaded.vad_threshold - 0.05).abs() < 1e-5);

        // 4. Reset should restore defaults
        reset_config_inner(&state).await.unwrap();
        let after_reset = load_config_from_db(&state.db, state.app_data_dir.as_ref()).await.unwrap();
        assert_eq!(after_reset.locale, "zh_CN");
        assert_eq!(after_reset.vault_path, "/tmp/echonote-settings-tests/vault");
        assert_eq!(after_reset.recordings_path, "/tmp/echonote-settings-tests/recordings");
    }

    #[tokio::test]
    async fn test_update_config_keeps_memory_unchanged_when_db_write_fails() {
        let state = make_state().await;
        state.db.pool.close().await;

        let result = update_config_inner(
            &state,
            crate::config::PartialAppConfig {
                locale: Some("en_US".to_string()),
                ..Default::default()
            },
        )
        .await;

        assert!(result.is_err());
        let cfg = state.config.read().await;
        assert_eq!(cfg.locale, "zh_CN");
    }

    #[tokio::test]
    async fn test_load_config_from_db_normalizes_runtime_paths() {
        let state = make_state().await;

        let persisted = AppConfig {
            vault_path: String::new(),
            recordings_path: String::new(),
            ..AppConfig::default()
        };
        state
            .db
            .save_setting(CONFIG_KEY, &serde_json::to_string(&persisted).unwrap())
            .await
            .unwrap();

        let loaded = load_config_from_db(&state.db, state.app_data_dir.as_ref()).await.unwrap();
        assert_eq!(loaded.vault_path, "/tmp/echonote-settings-tests/vault");
        assert_eq!(loaded.recordings_path, "/tmp/echonote-settings-tests/recordings");
    }
}
