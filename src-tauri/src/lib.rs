mod commands;
mod error;
mod state;
pub mod storage;
pub mod config;
pub mod models;

use commands::{settings, theme, models as model_cmds};
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
        ])
}

/// 仅在开发构建时重新生成 bindings.ts
#[cfg(debug_assertions)]
fn export_bindings() {
    specta_builder()
        .export(
            &specta_typescript::Typescript::default()
                .bigint(specta_typescript::BigIntExportBehavior::Number),
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

            let state = std::sync::Arc::new(crate::state::AppState {
                db: std::sync::Arc::clone(&db),
                config: std::sync::Arc::clone(&config),
                model_config: std::sync::Arc::clone(&model_config),
                download_tx: download_tx.clone(),
            });

            // Spawn DownloadWorker
            let app_handle = app.handle().clone();
            let state_clone = std::sync::Arc::clone(&state);
            tauri::async_runtime::spawn(crate::models::downloader::run_download_worker(
                download_rx,
                app_handle.clone(),
                state_clone,
            ));

            // Step 6: startup missing-model detection
            // Emit after a brief delay to ensure frontend listeners are registered
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

            // Register managed state (use the Arc's inner value via clone)
            app.manage(crate::state::AppState {
                db,
                config,
                model_config,
                download_tx,
            });
            Ok(())
        })
        .invoke_handler(
            specta_builder().invoke_handler()
        )
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
