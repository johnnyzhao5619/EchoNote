use std::fs;
use std::path::PathBuf;

#[test]
fn package_manifest_sets_default_run_to_main_app_binary() {
    let manifest_path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml");
    let manifest = fs::read_to_string(manifest_path).expect("read Cargo.toml");
    let parsed: toml::Value = toml::from_str(&manifest).expect("parse Cargo.toml");

    let default_run = parsed
        .get("package")
        .and_then(|package| package.get("default-run"))
        .and_then(toml::Value::as_str);

    assert_eq!(default_run, Some("echonote"));
}
