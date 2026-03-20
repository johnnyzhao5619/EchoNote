mod commands;
mod error;
mod state;
pub mod storage;
pub mod config;

use commands::{settings, theme};
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
        ])
}

/// 仅在开发构建时重新生成 bindings.ts
#[cfg(debug_assertions)]
fn export_bindings() {
    specta_builder()
        .export(
            &specta_typescript::Typescript::default(),
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

            let state = crate::state::AppState { db, config };
            app.manage(state);
            Ok(())
        })
        .invoke_handler(
            specta_builder().invoke_handler()
        )
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
