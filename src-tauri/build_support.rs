pub const EMPTY_MACOS_FRAMEWORKS_CONFIG: &str = r#"{"bundle":{"macOS":{"frameworks":[]}}}"#;

pub fn should_skip_tauri_framework_copy(profile: &str, explicit_skip: bool) -> bool {
    explicit_skip || profile != "release"
}

pub fn tauri_config_override(profile: &str, explicit_skip: bool) -> Option<&'static str> {
    if should_skip_tauri_framework_copy(profile, explicit_skip) {
        Some(EMPTY_MACOS_FRAMEWORKS_CONFIG)
    } else {
        None
    }
}
