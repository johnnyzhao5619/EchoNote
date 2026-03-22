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
            audio_cmds::list_audio_devices,
            transcription_cmds::start_realtime,
            transcription_cmds::pause_realtime,
            transcription_cmds::resume_realtime,
            transcription_cmds::stop_realtime,
            transcription_cmds::get_audio_level,
            transcription_cmds::get_realtime_segments,
            transcription_cmds::get_recording_status,
            workspace_cmds::list_recordings,
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

            let db_path = app_data_dir.join("echonote.db");
            let db_url = format!("sqlite://{}?mode=rwc", db_path.display());

            // Step 1+2: open DB and run migrations (blocking inside setup)
            let db = tauri::async_runtime::block_on(
                crate::storage::db::Db::open(&db_url)
            ).expect("DB initialization failed");
            let db = std::sync::Arc::new(db);

            // Step 3: load AppConfig from DB (or default)
            let config = {
                let tmp_state = crate::state::AppState {
                    db: std::sync::Arc::clone(&db),
                    config: std::sync::Arc::new(tokio::sync::RwLock::new(
                        crate::config::AppConfig::default(),
                    )),
                    model_config: std::sync::Arc::new(
                        crate::models::registry::load_models_toml(
                            include_str!("../../resources/models.toml")
                        ).expect("models.toml 解析失败")
                    ),
                    download_tx: {
                        let (tx, _rx) = tokio::sync::mpsc::channel(1);
                        tx
                    },
                    transcription_tx: {
                        let (tx, _rx) = std::sync::mpsc::sync_channel(1);
                        tx
                    },
                    whisper_engine: std::sync::Arc::new(std::sync::Mutex::new(None)),
                    capture_stop_tx: std::sync::Arc::new(std::sync::Mutex::new(None)),
                    segments_cache: std::sync::Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
                    pcm_cache: std::sync::Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
                    current_session_id: std::sync::Arc::new(tokio::sync::Mutex::new(None)),
                    resampler_done_rx: std::sync::Arc::new(tokio::sync::Mutex::new(None)),
                    resampler_stop: std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
                    audio_level: std::sync::Arc::new(std::sync::atomic::AtomicU32::new(0)),
                };
                let loaded = tauri::async_runtime::block_on(
                    crate::commands::settings::load_config_from_db(&tmp_state)
                ).unwrap_or_default();

                // Fill in runtime-derived paths if still empty
                let mut cfg = loaded;
                if cfg.vault_path.is_empty() {
                    cfg.vault_path = app_data_dir.join("vault")
                        .to_string_lossy()
                        .to_string();
                }
                if cfg.recordings_path.is_empty() {
                    cfg.recordings_path = app_data_dir.join("recordings")
                        .to_string_lossy()
                        .to_string();
                }
                std::sync::Arc::new(tokio::sync::RwLock::new(cfg))
            };

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

            // Try to load whisper model if already downloaded
            {
                let cfg_guard = tauri::async_runtime::block_on(config.read());
                let model_dir = std::path::Path::new(&cfg_guard.vault_path)
                    .parent()
                    .unwrap_or(std::path::Path::new(&cfg_guard.vault_path))
                    .join("models");

                if let Some((model_type, variant_name)) =
                    crate::models::registry::parse_variant_id(&cfg_guard.active_whisper_model)
                {
                    if let Some(variant_cfg) = model_config.whisper.variants.get(variant_name) {
                        let model_path = crate::models::registry::model_file_path(
                            &model_dir, model_type, variant_name, &variant_cfg.url,
                        );
                        if model_path.exists() {
                            match crate::transcription::WhisperEngine::new(&model_path) {
                                Ok(engine) => {
                                    *whisper_engine.lock().unwrap() = Some(engine);
                                    log::info!("whisper engine loaded from {}", model_path.display());
                                }
                                Err(e) => log::warn!("whisper load failed: {e}"),
                            }
                        }
                    }
                }
            }

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

            // Step 7: startup missing-model detection
            let missing = {
                let cfg_guard = tauri::async_runtime::block_on(config.read());
                let model_dir = std::path::Path::new(&cfg_guard.vault_path)
                    .parent()
                    .unwrap_or(std::path::Path::new(&cfg_guard.vault_path))
                    .join("models");
                crate::models::registry::check_required_models(
                    &model_config,
                    &model_dir,
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
            });
            Ok(())
        })
        .invoke_handler(
            specta_builder().invoke_handler()
        )
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
