use std::path::PathBuf;

fn main() {
    #[cfg(target_os = "macos")]
    stage_llama_dylibs();

    tauri_build::build();

    #[cfg(target_os = "macos")]
    {
        println!("cargo:rustc-env=WHISPER_COREML=1");
        println!("cargo:rustc-link-lib=framework=CoreML");
        println!("cargo:rustc-link-lib=framework=Accelerate");

        // rpath for bundled .app (Contents/Frameworks/ relative to the binary)
        println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path/../Frameworks");

        // rpath for development builds — the cargo target/{profile}/ directory
        // (resolved at build time so `cargo tauri dev` can find the dylibs)
        let out_dir = std::env::var("OUT_DIR").expect("OUT_DIR not set");
        let target_dir = std::path::PathBuf::from(&out_dir)
            .ancestors()
            .nth(3)
            .expect("could not derive target dir from OUT_DIR")
            .to_path_buf();
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", target_dir.display());
    }
}

/// Copy llama.cpp dylibs from the cargo target directory into src-tauri/Frameworks/
/// so Tauri's bundler can pick them up for the production .app bundle.
#[cfg(target_os = "macos")]
fn stage_llama_dylibs() {
    let out_dir = std::env::var("OUT_DIR").expect("OUT_DIR not set");
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR not set");

    // Derive target/{profile}/ from OUT_DIR (…/target/debug/build/<crate>/out)
    let target_dir: PathBuf = PathBuf::from(&out_dir)
        .ancestors()
        .nth(3)
        .expect("could not derive target dir from OUT_DIR")
        .to_path_buf();

    let frameworks_dir = PathBuf::from(&manifest_dir).join("Frameworks");
    std::fs::create_dir_all(&frameworks_dir).ok();

    // Copy only the "main" (unversioned) dylib symlinks (e.g. libllama.dylib, not libllama.0.dylib)
    let is_main_dylib = |name: &str| -> bool {
        let prefixes = ["libllama.", "libggml.", "libggml-base.", "libggml-cpu.", "libggml-metal."];
        prefixes.iter().any(|p| name.starts_with(p))
            && name.ends_with(".dylib")
            // stem must have no dots → unversioned (libllama, not libllama.0 or libllama.0.0.0)
            && name[..name.len() - ".dylib".len()].split('.').count() == 1
    };

    if let Ok(entries) = std::fs::read_dir(&target_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            let name = match path.file_name().and_then(|n| n.to_str()) {
                Some(n) => n.to_string(),
                None => continue,
            };
            if is_main_dylib(&name) {
                let dest = frameworks_dir.join(&name);
                // Resolve symlink so we copy the actual file content
                let src = std::fs::canonicalize(&path).unwrap_or(path);
                if std::fs::copy(&src, &dest).is_ok() {
                    println!("cargo:warning=Staged {name} → Frameworks/{name}");
                }
            }
        }
    }

    // Tell cargo to re-run this script if the staged dylibs change
    println!("cargo:rerun-if-changed=Frameworks");
}
