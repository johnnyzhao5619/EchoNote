mod commands;
mod error;
mod state;

use commands::{settings, theme};
use state::AppState;
use tauri_specta::{collect_commands, Builder};

/// tauri-specta builder（构建时自动导出 bindings.ts）
fn specta_builder() -> Builder {
    Builder::<tauri::Wry>::new()
        .commands(collect_commands![
            theme::get_current_theme,
            theme::set_current_theme,
            theme::list_builtin_themes,
            settings::get_app_config,
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

    let app_state = AppState::new();

    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(
            specta_builder().invoke_handler()
        )
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
