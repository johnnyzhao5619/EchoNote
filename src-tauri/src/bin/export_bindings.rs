use std::path::PathBuf;

fn main() {
    let output_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../src/lib/bindings.ts");
    echonote_lib::bindings::export_typescript_bindings(&output_path)
        .expect("failed to export TypeScript bindings");
}
