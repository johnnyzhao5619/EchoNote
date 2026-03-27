#[path = "../build_support.rs"]
mod build_support;

#[test]
fn debug_profile_skips_framework_copy() {
    assert!(build_support::should_skip_tauri_framework_copy("debug", false));
    assert_eq!(
        build_support::tauri_config_override("debug", false),
        Some(r#"{"bundle":{"macOS":{"frameworks":[]}}}"#)
    );
}

#[test]
fn release_profile_keeps_framework_copy_by_default() {
    assert!(!build_support::should_skip_tauri_framework_copy("release", false));
    assert_eq!(
        build_support::tauri_config_override("release", false),
        None
    );
}

#[test]
fn explicit_override_skips_release_framework_copy() {
    assert!(build_support::should_skip_tauri_framework_copy("release", true));
    assert_eq!(
        build_support::tauri_config_override("release", true),
        Some(r#"{"bundle":{"macOS":{"frameworks":[]}}}"#)
    );
}
