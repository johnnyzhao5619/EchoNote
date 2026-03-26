mod commands;
mod error;
mod state;
pub mod storage;
pub mod config;
pub mod models;
pub mod audio;
pub mod transcription;
pub mod llm;

use commands::{settings, theme, models as model_cmds, audio as audio_cmds, transcription as transcription_cmds, workspace as workspace_cmds, llm as llm_cmds};
use tauri::Manager;
use tauri_specta::{collect_commands, Builder};
use crate::llm::{
    engine::LlmEngine,
    tasks::PromptTemplates,
    worker::{LlmWorker, LlmTaskMessage},
    LlmEngineStatus,
};

/// tauri-specta builder（构建时自动导出 bindings.ts）
fn specta_builder() -> Builder {
    Builder::<tauri::Wry>::new()
        .commands(collect_commands![
            theme::get_current_theme,
            theme::set_current_theme,
            theme::list_builtin_themes,
            settings::get_config,
            settings::update_config,
            settings::reset_config,
            model_cmds::list_model_variants,
            model_cmds::download_model,
            model_cmds::cancel_download,
            model_cmds::delete_model,
            model_cmds::set_active_model,
            model_cmds::get_download_error,
            audio_cmds::list_audio_devices,
            transcription_cmds::start_realtime,
            transcription_cmds::pause_realtime,
            transcription_cmds::resume_realtime,
            transcription_cmds::stop_realtime,
            transcription_cmds::get_audio_level,
            transcription_cmds::get_realtime_segments,
            transcription_cmds::get_recording_status,
            workspace_cmds::list_recordings,
            workspace_cmds::get_document_assets,
            workspace_cmds::ensure_document_for_recording,
            workspace_cmds::update_document_asset,
            workspace_cmds::delete_recording,
            llm_cmds::submit_llm_task,
            llm_cmds::cancel_llm_task,
            llm_cmds::get_llm_engine_status,
            llm_cmds::list_document_llm_tasks,
        ])
}

/// 仅在开发构建时重新生成 bindings.ts
#[cfg(debug_assertions)]
fn export_bindings() {
    specta_builder()
        .export(
            &specta_typescript::Typescript::default()
                .bigint(specta_typescript::BigIntExportBehavior::Number)
                .header("// @ts-nocheck\n// Event payload types not in commands:\nexport type DownloadProgressPayload = { variant_id: string; downloaded_bytes: number; total_bytes: number | null; speed_bps: number; eta_secs: number | null }"),
            "../src/lib/bindings.ts",
        )
        .expect("Failed to export TypeScript bindings");
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[cfg(debug_assertions)]
    export_bindings();

    tauri::Builder::default()
        .setup(|app| {
            let app_data_dir = app.path().app_data_dir()
                .expect("APP_DATA dir not resolvable");
            std::fs::create_dir_all(&app_data_dir)?;
            let app_data_dir = std::sync::Arc::new(app_data_dir);

            let db_path = app_data_dir.join("echonote.db");
            let db_url = format!("sqlite://{}?mode=rwc", db_path.display());

            // Step 1+2: open DB and run migrations (blocking inside setup)
            let db = tauri::async_runtime::block_on(
                crate::storage::db::Database::open(&db_url)
            ).expect("DB initialization failed");
            let db = std::sync::Arc::new(db);

            // Step 3: load AppConfig from DB (or default)
            let loaded_config = tauri::async_runtime::block_on(
                crate::commands::settings::load_config_from_db(&db, app_data_dir.as_ref())
            ).unwrap_or_else(|_| crate::config::normalized_app_config(
                crate::config::AppConfig::default(),
                app_data_dir.as_ref(),
            ));
            let config = std::sync::Arc::new(tokio::sync::RwLock::new(loaded_config));

            // Step 4: load models.toml
            let model_config = std::sync::Arc::new(
                crate::models::registry::load_models_toml(
                    include_str!("../../resources/models.toml")
                ).expect("models.toml 解析失败")
            );

            // Step 5: create download channel + worker
            let (download_tx, download_rx) = tokio::sync::mpsc::channel::<crate::models::DownloadCommand>(32);

            // Step 6: M4 — create transcription channel + whisper engine
            let (transcription_tx, transcription_rx) = std::sync::mpsc::sync_channel::<crate::transcription::TranscriptionCommand>(128);
            let whisper_engine: std::sync::Arc<std::sync::Mutex<Option<crate::transcription::WhisperEngine>>> =
                std::sync::Arc::new(std::sync::Mutex::new(None));

            // Step M5: Load prompt templates
            let prompts_path = {
                let resource_attempt = app.path()
                    .resource_dir()
                    .ok()
                    .map(|d| d.join("resources/prompts/tasks.toml"))
                    .filter(|p| p.exists());

                resource_attempt.unwrap_or_else(|| {
                    // Development fallback: relative to cargo manifest
                    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                        .join("../resources/prompts/tasks.toml")
                })
            };

            let prompt_templates = std::sync::Arc::new(
                PromptTemplates::load(&prompts_path)
                    .expect("failed to load tasks.toml — ensure resources/prompts/tasks.toml exists")
            );

            // LLM channel (bounded 64)
            let (llm_tx, llm_rx) = tokio::sync::mpsc::channel::<LlmTaskMessage>(64);

            let llm_engine: std::sync::Arc<tokio::sync::Mutex<Option<std::sync::Arc<LlmEngine>>>> =
                std::sync::Arc::new(tokio::sync::Mutex::new(None));
            let active_llm_cancels: std::sync::Arc<dashmap::DashMap<String, std::sync::Arc<std::sync::atomic::AtomicBool>>> =
                std::sync::Arc::new(dashmap::DashMap::new());
            let llm_engine_status: std::sync::Arc<tokio::sync::Mutex<LlmEngineStatus>> =
                std::sync::Arc::new(tokio::sync::Mutex::new(LlmEngineStatus::NotLoaded));
            let download_errors: std::sync::Arc<dashmap::DashMap<String, String>> =
                std::sync::Arc::new(dashmap::DashMap::new());

            // M4 shared state (Arc wrappers for sharing with worker)
            let segments_cache = std::sync::Arc::new(std::sync::Mutex::new(std::collections::HashMap::new()));
            let pcm_cache = std::sync::Arc::new(std::sync::Mutex::new(std::collections::HashMap::new()));
            let current_session_id = std::sync::Arc::new(tokio::sync::Mutex::new(None));
            let capture_stop_tx: std::sync::Arc<std::sync::Mutex<Option<std::sync::mpsc::SyncSender<()>>>> =
                std::sync::Arc::new(std::sync::Mutex::new(None));

            let resampler_done_rx: std::sync::Arc<tokio::sync::Mutex<Option<tokio::sync::oneshot::Receiver<()>>>> =
                std::sync::Arc::new(tokio::sync::Mutex::new(None));
            let resampler_stop = std::sync::Arc::new(
                std::sync::atomic::AtomicBool::new(false)
            );
            let audio_level = std::sync::Arc::new(std::sync::atomic::AtomicU32::new(0));

            // Build the AppState that Tauri manages
            let state_for_download = std::sync::Arc::new(crate::state::AppState {
                app_data_dir: std::sync::Arc::clone(&app_data_dir),
                db: std::sync::Arc::clone(&db),
                config: std::sync::Arc::clone(&config),
                model_config: std::sync::Arc::clone(&model_config),
                download_tx: download_tx.clone(),
                transcription_tx: transcription_tx.clone(),
                whisper_engine: std::sync::Arc::clone(&whisper_engine),
                capture_stop_tx: std::sync::Arc::clone(&capture_stop_tx),
                segments_cache: std::sync::Arc::clone(&segments_cache),
                pcm_cache: std::sync::Arc::clone(&pcm_cache),
                current_session_id: std::sync::Arc::clone(&current_session_id),
                resampler_done_rx: std::sync::Arc::clone(&resampler_done_rx),
                resampler_stop: std::sync::Arc::clone(&resampler_stop),
                audio_level: std::sync::Arc::clone(&audio_level),
                llm_tx: llm_tx.clone(),
                llm_engine: std::sync::Arc::clone(&llm_engine),
                active_llm_cancels: std::sync::Arc::clone(&active_llm_cancels),
                download_errors: std::sync::Arc::clone(&download_errors),
                prompt_templates: std::sync::Arc::clone(&prompt_templates),
                llm_engine_status: std::sync::Arc::clone(&llm_engine_status),
            });

            // Spawn DownloadWorker
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(crate::models::downloader::run_download_worker(
                download_rx,
                app_handle.clone(),
                std::sync::Arc::clone(&state_for_download),
            ));

            // Spawn TranscriptionWorker
            let worker = crate::transcription::TranscriptionWorker::new(
                transcription_rx,
                app_handle.clone(),
                std::sync::Arc::clone(&whisper_engine),
                std::sync::Arc::clone(&segments_cache),
            );
            tauri::async_runtime::spawn(worker.run());

            // Spawn LlmWorker
            let llm_app_handle = app_handle.clone();
            let llm_pool = db.pool.clone();
            let llm_engine_clone = std::sync::Arc::clone(&llm_engine);
            let llm_templates_clone = std::sync::Arc::clone(&prompt_templates);
            let llm_cancels_clone = std::sync::Arc::clone(&active_llm_cancels);
            tauri::async_runtime::spawn(LlmWorker::run(
                llm_rx,
                llm_app_handle,
                llm_engine_clone,
                llm_templates_clone,
                llm_cancels_clone,
                llm_pool,
            ));

            // Step 7: startup missing-model detection
            let missing = {
                let cfg_guard = tauri::async_runtime::block_on(config.read());
                crate::models::registry::check_required_models(
                    &model_config,
                    &state_for_download.models_dir(),
                    &cfg_guard.active_whisper_model,
                    &cfg_guard.active_llm_model,
                )
            };

            if !missing.is_empty() {
                let app_handle2 = app_handle.clone();
                let missing_clone = missing.clone();
                tauri::async_runtime::spawn(async move {
                    // Small delay so frontend event listeners are registered
                    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
                    use tauri::Emitter;
                    app_handle2.emit(
                        "models:required",
                        serde_json::json!({ "missing": missing_clone }),
                    ).ok();
                });
            }

            // Register managed state
            app.manage(crate::state::AppState {
                app_data_dir,
                db,
                config,
                model_config,
                download_tx,
                transcription_tx,
                whisper_engine,
                capture_stop_tx,
                segments_cache,
                pcm_cache,
                current_session_id,
                resampler_done_rx,
                resampler_stop,
                audio_level,
                llm_tx,
                llm_engine,
                active_llm_cancels,
                download_errors,
                prompt_templates,
                llm_engine_status,
            });

            // Try to load engines if models already downloaded.
            // Spawned after manage() so try_load_* can use proper Loading state and spawn_blocking.
            let app_handle_for_init = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                let state = app_handle_for_init.state::<crate::state::AppState>();
                state.try_load_whisper().await;
                state.try_load_llm().await;
            });

            Ok(())
        })
        .invoke_handler(
            specta_builder().invoke_handler()
        )
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
