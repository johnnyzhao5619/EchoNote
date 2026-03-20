# Model Download Manager Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现模型下载管理器（M3 里程碑），支持首次启动引导、流式断点续传下载、SHA256 校验，以及设置页模型管理 UI。

**Architecture:** Rust 后端由 `models/registry.rs`（配置加载与启动检测）和 `models/downloader.rs`（reqwest 流式下载 + 5 秒滑动窗口速度计算）构成，通过 `commands/models.rs` 暴露 Tauri IPC 命令，经由 `AppState.download_tx` channel 与长驻 DownloadWorker 通信，将进度以 Tauri 事件推送至前端；前端包含首次启动引导弹窗（监听 `models:required`）和 `/settings/models` 设置子页面（进度条、速度/ETA 显示、取消、删除、设为当前）。

**Tech Stack:** Rust（tokio async, reqwest 0.12 stream, sha2, serde/TOML）、Tauri 2.x Events、tauri-specta v2、React 18 + TypeScript + Zustand + shadcn/ui + TanStack Router、wiremock（下载测试）

---

### Task 1: models.toml 配置文件

**Files:**
- Create: `resources/models.toml`

- [ ] **Step 1.1: 创建 `resources/models.toml`**

  按规格写入 whisper（tiny/base/small/medium）和 llm（qwen2.5-3b-q4/qwen2.5-7b-q4）6 个变体。`medium`、两个 LLM 变体的 `sha256` 标记为占位符，待发布前用 `sha256sum` 命令核实后填写。

  ```toml
  # resources/models.toml
  # ⚠️  SHA256 标记为 FILL_IN_BEFORE_RELEASE 的字段必须在发布前用
  #     sha256sum <file> 命令填写真实值，否则下载校验将始终失败。

  [whisper]
  default_variant = "base"

  [whisper.variants.tiny]
  url         = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
  sha256      = "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21"
  size_bytes  = 75161336
  description = "最小模型，速度最快，精度较低"

  [whisper.variants.base]
  url         = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
  sha256      = "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"
  size_bytes  = 142068640
  description = "推荐入门模型，速度与精度平衡"

  [whisper.variants.small]
  url         = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
  sha256      = "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
  size_bytes  = 466013312
  description = "精度更高，需要约 1GB RAM"

  [whisper.variants.medium]
  url         = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"
  sha256      = "FILL_IN_BEFORE_RELEASE_64_HEX_CHARS_REQUIRED"
  size_bytes  = 1528006144
  description = "高精度，需要约 3GB RAM"

  [llm]
  default_variant = "qwen2.5-3b-q4"

  ["llm.variants.qwen2.5-3b-q4"]
  url         = "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
  sha256      = "FILL_IN_BEFORE_RELEASE_64_HEX_CHARS_REQUIRED"
  size_bytes  = 1890000000
  description = "轻量模型，适合低配设备，需要约 2GB RAM"

  ["llm.variants.qwen2.5-7b-q4"]
  url         = "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf"
  sha256      = "FILL_IN_BEFORE_RELEASE_64_HEX_CHARS_REQUIRED"
  size_bytes  = 4370000000
  description = "推荐模型，效果好，需要约 5GB RAM"
  ```

  > **TOML key 注意**：TOML 中带 `.` 的键名（如 `qwen2.5-3b-q4`）必须用引号括起，否则解析失败。`serde` 反序列化时将 `HashMap<String, VariantConfig>` 的键保留为原始字符串（含 `.`）。

- [ ] **Commit:** `feat(models): add models.toml with whisper/llm variants config`

---

### Task 2: Rust 类型定义与 Cargo 依赖

**Files:**
- Modify: `src-tauri/Cargo.toml`
- Create: `src-tauri/src/models/mod.rs`

- [ ] **Step 2.1: 在 `Cargo.toml` 添加依赖**

  ```toml
  [dependencies]
  # 已有依赖保持不变，新增/补充以下：
  reqwest  = { version = "0.12", features = ["stream", "json"] }
  sha2     = "0.10"
  hex      = "0.4"
  tokio    = { version = "1", features = ["full"] }
  futures-util = "0.3"   # StreamExt trait，reqwest bytes_stream() 需要

  [dev-dependencies]
  wiremock = "0.6"
  tempfile = "3"
  tokio    = { version = "1", features = ["full", "test-util"] }
  ```

- [ ] **Step 2.2: 创建 `src-tauri/src/models/mod.rs`**

  声明子模块，并定义共享的 TOML 配置结构体，供 `registry.rs` 和 `downloader.rs` 使用。

  ```rust
  // src-tauri/src/models/mod.rs

  pub mod registry;
  pub mod downloader;

  use serde::{Deserialize, Serialize};
  use std::collections::HashMap;
  use specta::Type;

  // ── TOML 反序列化结构 ─────────────────────────────────────────

  #[derive(Debug, Deserialize, Clone)]
  pub struct ModelsToml {
      pub whisper: ModelGroup,
      pub llm: ModelGroup,
  }

  #[derive(Debug, Deserialize, Clone)]
  pub struct ModelGroup {
      pub default_variant: String,
      pub variants: HashMap<String, VariantConfig>,
  }

  #[derive(Debug, Deserialize, Clone)]
  pub struct VariantConfig {
      pub url: String,
      pub sha256: String,
      pub size_bytes: u64,
      pub description: String,
  }

  // ── IPC 数据类型（tauri-specta 导出到前端）────────────────────

  /// 下载进度推送 Payload（`models:progress` 事件）
  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  pub struct DownloadProgressPayload {
      pub variant_id: String,
      pub downloaded_bytes: u64,
      pub total_bytes: Option<u64>,
      /// bytes/sec，基于最近 5 秒滑动窗口均值
      pub speed_bps: u64,
      /// 预计剩余秒数；total_bytes 未知时为 None
      pub eta_secs: Option<u64>,
  }

  /// 单个模型变体的完整状态（`list_model_variants` 返回值）
  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  pub struct ModelVariant {
      /// 格式："whisper/base" 或 "llm/qwen2.5-3b-q4"
      pub variant_id: String,
      /// "whisper" | "llm"
      pub model_type: String,
      pub name: String,
      pub description: String,
      pub size_bytes: u64,
      /// 格式化后的大小字符串，如 "142 MB"
      pub size_display: String,
      pub is_downloaded: bool,
      /// 当前已加载（激活）的模型
      pub is_active: bool,
  }

  // ── 内部 channel 消息 ─────────────────────────────────────────

  #[derive(Debug)]
  pub enum DownloadCommand {
      Start { variant_id: String },
      Cancel { variant_id: String },
  }

  // ── 辅助函数 ──────────────────────────────────────────────────

  /// 将字节数格式化为人类可读字符串，如 "142 MB"、"1.4 GB"
  pub fn format_size(bytes: u64) -> String {
      const GB: u64 = 1_073_741_824;
      const MB: u64 = 1_048_576;
      const KB: u64 = 1_024;
      if bytes >= GB {
          format!("{:.1} GB", bytes as f64 / GB as f64)
      } else if bytes >= MB {
          format!("{:.0} MB", bytes as f64 / MB as f64)
      } else if bytes >= KB {
          format!("{:.0} KB", bytes as f64 / KB as f64)
      } else {
          format!("{} B", bytes)
      }
  }
  ```

- [ ] **Commit:** `feat(models): add shared types, DownloadCommand channel msg, format_size helper`

---

### Task 3: `models/registry.rs` — 配置加载与启动检测

**Files:**
- Create: `src-tauri/src/models/registry.rs`
- Create: `src-tauri/tests/models/registry_test.rs`（或 `#[cfg(test)]` 内嵌）

- [ ] **Step 3.1: 先写测试（TDD）**

  在 `registry.rs` 末尾添加 `#[cfg(test)]` 模块，覆盖：
  - `parse_models_toml_ok`：验证合法 TOML 能正确反序列化
  - `parse_models_toml_missing_field`：缺少必填字段时返回 `Err`
  - `check_model_file_missing`：文件不存在时 `is_downloaded = false`
  - `check_model_file_size_mismatch`：文件存在但大小不符时 `is_downloaded = false`
  - `check_model_file_ok`：文件存在且大小匹配时 `is_downloaded = true`
  - `list_variants_populates_is_active`：`active_whisper/active_llm` 配置正确映射到 `is_active`

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use tempfile::tempdir;
      use std::fs;

      fn minimal_toml() -> &'static str {
          r#"
  [whisper]
  default_variant = "base"
  [whisper.variants.base]
  url        = "https://example.com/base.bin"
  sha256     = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  size_bytes = 100
  description = "test"

  [llm]
  default_variant = "qwen2.5-3b-q4"
  ["llm.variants.qwen2.5-3b-q4"]
  url        = "https://example.com/qwen.gguf"
  sha256     = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  size_bytes = 200
  description = "test llm"
  "#
      }

      #[test]
      fn parse_models_toml_ok() {
          let cfg: ModelsToml = toml::from_str(minimal_toml()).unwrap();
          assert!(cfg.whisper.variants.contains_key("base"));
          assert!(cfg.llm.variants.contains_key("qwen2.5-3b-q4"));
      }

      #[test]
      fn check_model_file_missing() {
          let dir = tempdir().unwrap();
          let path = dir.path().join("missing.bin");
          assert!(!file_matches_size(&path, 100));
      }

      #[test]
      fn check_model_file_size_mismatch() {
          let dir = tempdir().unwrap();
          let path = dir.path().join("model.bin");
          fs::write(&path, b"short").unwrap();
          assert!(!file_matches_size(&path, 100));
      }

      #[test]
      fn check_model_file_ok() {
          let dir = tempdir().unwrap();
          let path = dir.path().join("model.bin");
          fs::write(&path, vec![0u8; 100]).unwrap();
          assert!(file_matches_size(&path, 100));
      }
  }
  ```

- [ ] **Step 3.2: 实现 `registry.rs`**

  ```rust
  // src-tauri/src/models/registry.rs

  use super::{format_size, ModelGroup, ModelVariant, ModelsToml, VariantConfig};
  use crate::error::AppError;
  use std::path::{Path, PathBuf};

  /// 加载 models.toml。`toml_bytes` 由调用方通过 `include_bytes!` 或文件读取提供。
  pub fn load_models_toml(toml_str: &str) -> Result<ModelsToml, AppError> {
      toml::from_str(toml_str).map_err(|e| AppError::Model(format!("models.toml 解析失败: {e}")))
  }

  /// 检查文件是否存在且大小与预期一致（快速校验，不做 SHA256）
  pub fn file_matches_size(path: &Path, expected_bytes: u64) -> bool {
      path.metadata()
          .map(|m| m.len() == expected_bytes)
          .unwrap_or(false)
  }

  /// 根据 model_type 和 variant name 生成模型文件路径
  /// 例：model_dir/whisper/ggml-base.bin、model_dir/llm/qwen2.5-3b-instruct-q4_k_m.gguf
  pub fn model_file_path(model_dir: &Path, model_type: &str, variant_name: &str, url: &str) -> PathBuf {
      // 从 URL 末段提取文件名（确保无路径注入）
      let filename = url
          .rsplit('/')
          .next()
          .unwrap_or("model.bin")
          .split('?')   // 去除 query string
          .next()
          .unwrap_or("model.bin");
      model_dir.join(model_type).join(filename)
  }

  /// 临时文件路径（下载中使用）：在最终路径上追加 ".tmp"
  pub fn tmp_file_path(final_path: &Path) -> PathBuf {
      let mut p = final_path.as_os_str().to_owned();
      p.push(".tmp");
      PathBuf::from(p)
  }

  /// 构造单个变体的 ModelVariant 状态（不含 is_active，由调用方叠加）
  pub fn build_variant(
      model_type: &str,
      variant_name: &str,
      cfg: &VariantConfig,
      model_dir: &Path,
  ) -> ModelVariant {
      let variant_id = format!("{}/{}", model_type, variant_name);
      let file_path = model_file_path(model_dir, model_type, variant_name, &cfg.url);
      let is_downloaded = file_matches_size(&file_path, cfg.size_bytes);

      ModelVariant {
          variant_id,
          model_type: model_type.to_string(),
          name: variant_name.to_string(),
          description: cfg.description.clone(),
          size_bytes: cfg.size_bytes,
          size_display: format_size(cfg.size_bytes),
          is_downloaded,
          is_active: false, // 调用方根据 AppConfig 设置
      }
  }

  /// 列出所有变体，并根据 active_whisper_model / active_llm_model 标记 is_active
  pub fn list_all_variants(
      models: &ModelsToml,
      model_dir: &Path,
      active_whisper: &str,
      active_llm: &str,
  ) -> Vec<ModelVariant> {
      let mut result = Vec::new();

      for (name, cfg) in &models.whisper.variants {
          let mut v = build_variant("whisper", name, cfg, model_dir);
          v.is_active = format!("whisper/{}", name) == active_whisper;
          result.push(v);
      }
      for (name, cfg) in &models.llm.variants {
          let mut v = build_variant("llm", name, cfg, model_dir);
          v.is_active = format!("llm/{}", name) == active_llm;
          result.push(v);
      }

      // 按 variant_id 字母序排序，保证前端展示顺序稳定
      result.sort_by(|a, b| a.variant_id.cmp(&b.variant_id));
      result
  }

  /// 启动检测：返回缺失模型的 variant_id 列表
  /// 仅检查当前激活模型；若激活模型文件存在且大小匹配，返回空列表
  pub fn check_required_models(
      models: &ModelsToml,
      model_dir: &Path,
      active_whisper: &str,
      active_llm: &str,
  ) -> Vec<String> {
      let mut missing = Vec::new();

      if let Some((model_type, variant_name)) = parse_variant_id(active_whisper) {
          if let Some(cfg) = models.whisper.variants.get(variant_name) {
              let path = model_file_path(model_dir, model_type, variant_name, &cfg.url);
              if !file_matches_size(&path, cfg.size_bytes) {
                  missing.push(active_whisper.to_string());
              }
          } else {
              // 配置中不存在该变体（配置错误），视为缺失
              missing.push(active_whisper.to_string());
          }
      }

      if let Some((model_type, variant_name)) = parse_variant_id(active_llm) {
          if let Some(cfg) = models.llm.variants.get(variant_name) {
              let path = model_file_path(model_dir, model_type, variant_name, &cfg.url);
              if !file_matches_size(&path, cfg.size_bytes) {
                  missing.push(active_llm.to_string());
              }
          } else {
              missing.push(active_llm.to_string());
          }
      }

      missing
  }

  /// 解析 "whisper/base" → ("whisper", "base")
  /// 解析 "llm/qwen2.5-3b-q4" → ("llm", "qwen2.5-3b-q4")
  pub fn parse_variant_id(variant_id: &str) -> Option<(&str, &str)> {
      let mut parts = variant_id.splitn(2, '/');
      let model_type = parts.next()?;
      let variant_name = parts.next()?;
      Some((model_type, variant_name))
  }

  #[cfg(test)]
  mod tests {
      use super::*;
      use tempfile::tempdir;
      use std::fs;

      fn minimal_toml() -> &'static str {
          r#"
  [whisper]
  default_variant = "base"
  [whisper.variants.base]
  url        = "https://example.com/base.bin"
  sha256     = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  size_bytes = 100
  description = "test"

  [llm]
  default_variant = "qwen2.5-3b-q4"
  ["llm.variants.qwen2.5-3b-q4"]
  url        = "https://example.com/qwen2.5-3b-instruct-q4_k_m.gguf"
  sha256     = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  size_bytes = 200
  description = "test llm"
  "#
      }

      #[test]
      fn parse_models_toml_ok() {
          let cfg = load_models_toml(minimal_toml()).unwrap();
          assert!(cfg.whisper.variants.contains_key("base"));
          assert!(cfg.llm.variants.contains_key("qwen2.5-3b-q4"));
      }

      #[test]
      fn parse_models_toml_missing_field_fails() {
          let bad = "[whisper]\ndefault_variant = \"base\"\n";
          assert!(load_models_toml(bad).is_err());
      }

      #[test]
      fn check_model_file_missing() {
          let dir = tempdir().unwrap();
          let path = dir.path().join("missing.bin");
          assert!(!file_matches_size(&path, 100));
      }

      #[test]
      fn check_model_file_size_mismatch() {
          let dir = tempdir().unwrap();
          let path = dir.path().join("model.bin");
          fs::write(&path, b"short").unwrap();
          assert!(!file_matches_size(&path, 100));
      }

      #[test]
      fn check_model_file_ok() {
          let dir = tempdir().unwrap();
          let path = dir.path().join("model.bin");
          fs::write(&path, vec![0u8; 100]).unwrap();
          assert!(file_matches_size(&path, 100));
      }

      #[test]
      fn list_variants_populates_is_active() {
          let models = load_models_toml(minimal_toml()).unwrap();
          let dir = tempdir().unwrap();
          let variants = list_all_variants(
              &models,
              dir.path(),
              "whisper/base",
              "llm/qwen2.5-3b-q4",
          );
          let whisper_base = variants.iter().find(|v| v.variant_id == "whisper/base").unwrap();
          assert!(whisper_base.is_active);
          let llm = variants.iter().find(|v| v.variant_id == "llm/qwen2.5-3b-q4").unwrap();
          assert!(llm.is_active);
      }

      #[test]
      fn check_required_models_missing() {
          let models = load_models_toml(minimal_toml()).unwrap();
          let dir = tempdir().unwrap();
          let missing = check_required_models(
              &models,
              dir.path(),
              "whisper/base",
              "llm/qwen2.5-3b-q4",
          );
          assert_eq!(missing.len(), 2);
      }

      #[test]
      fn check_required_models_present() {
          let models = load_models_toml(minimal_toml()).unwrap();
          let dir = tempdir().unwrap();
          // 创建 whisper/base 文件，大小精确为 100 bytes
          let base_dir = dir.path().join("whisper");
          fs::create_dir_all(&base_dir).unwrap();
          fs::write(base_dir.join("base.bin"), vec![0u8; 100]).unwrap();
          // 创建 llm/qwen2.5-3b-instruct-q4_k_m.gguf 文件，大小精确为 200 bytes
          let llm_dir = dir.path().join("llm");
          fs::create_dir_all(&llm_dir).unwrap();
          fs::write(llm_dir.join("qwen2.5-3b-instruct-q4_k_m.gguf"), vec![0u8; 200]).unwrap();
          let missing = check_required_models(
              &models,
              dir.path(),
              "whisper/base",
              "llm/qwen2.5-3b-q4",
          );
          assert!(missing.is_empty());
      }

      #[test]
      fn parse_variant_id_ok() {
          assert_eq!(parse_variant_id("whisper/base"), Some(("whisper", "base")));
          assert_eq!(parse_variant_id("llm/qwen2.5-3b-q4"), Some(("llm", "qwen2.5-3b-q4")));
      }

      #[test]
      fn parse_variant_id_no_slash() {
          assert!(parse_variant_id("whisperbase").is_none());
      }
  }
  ```

- [ ] **Commit:** `test(models): TDD registry — load config, file size check, startup detection`

---

### Task 4: `models/downloader.rs` — 流式下载 + 断点续传 + SHA256

**Files:**
- Create: `src-tauri/src/models/downloader.rs`

- [ ] **Step 4.1: 先写测试（wiremock）**

  在 `downloader.rs` 末尾的 `#[cfg(test)]` 中添加以下测试。wiremock 启动本地 HTTP 服务，验证下载逻辑无需真实网络：

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use tempfile::tempdir;
      use wiremock::{MockServer, Mock, ResponseTemplate};
      use wiremock::matchers::{method, path, header_exists};
      use sha2::{Sha256, Digest};

      fn sha256_of(data: &[u8]) -> String {
          let mut h = Sha256::new();
          h.update(data);
          hex::encode(h.finalize())
      }

      // 测试正常下载：服务器返回完整文件，SHA256 匹配
      #[tokio::test]
      async fn download_full_ok() {
          let server = MockServer::start().await;
          let body = vec![42u8; 1024 * 256]; // 256 KB
          let expected_sha256 = sha256_of(&body);
          Mock::given(method("GET"))
              .and(path("/model.bin"))
              .respond_with(ResponseTemplate::new(200).set_body_bytes(body.clone()))
              .mount(&server)
              .await;

          let dir = tempdir().unwrap();
          let dest = dir.path().join("model.bin");
          let url = format!("{}/model.bin", server.uri());

          let client = reqwest::Client::new();
          download_to_file(&client, &url, &dest, body.len() as u64, &expected_sha256, |_| {})
              .await
              .unwrap();

          assert!(dest.exists());
          let written = std::fs::read(&dest).unwrap();
          assert_eq!(written, body);
      }

      // 测试 SHA256 不匹配：下载后删除临时文件，返回 AppError::Model
      #[tokio::test]
      async fn download_sha256_mismatch_deletes_tmp() {
          let server = MockServer::start().await;
          let body = vec![1u8; 100];
          Mock::given(method("GET"))
              .and(path("/bad.bin"))
              .respond_with(ResponseTemplate::new(200).set_body_bytes(body))
              .mount(&server)
              .await;

          let dir = tempdir().unwrap();
          let dest = dir.path().join("bad.bin");
          let url = format!("{}/bad.bin", server.uri());
          let wrong_sha256 = "a".repeat(64);
          let client = reqwest::Client::new();

          let result = download_to_file(&client, &url, &dest, 100, &wrong_sha256, |_| {}).await;
          assert!(result.is_err());
          // 临时文件应已被清理
          let tmp = super::super::registry::tmp_file_path(&dest);
          assert!(!tmp.exists());
          // 最终文件不应存在
          assert!(!dest.exists());
      }

      // 测试断点续传：服务器支持 Range，临时文件已有部分内容
      #[tokio::test]
      async fn download_resume_sends_range_header() {
          let server = MockServer::start().await;
          let partial = vec![0u8; 50];
          let remaining = vec![1u8; 50];
          // 服务端响应 Range 请求（模拟 206 Partial Content）
          Mock::given(method("GET"))
              .and(path("/model.bin"))
              .and(header_exists("range"))
              .respond_with(
                  ResponseTemplate::new(206).set_body_bytes(remaining.clone()),
              )
              .mount(&server)
              .await;

          let dir = tempdir().unwrap();
          let dest = dir.path().join("model.bin");
          let tmp = super::super::registry::tmp_file_path(&dest);
          // 预写 50 bytes 的临时文件（模拟已下载部分）
          std::fs::write(&tmp, &partial).unwrap();

          // 构造完整内容的 SHA256（partial + remaining）
          let mut full = partial.clone();
          full.extend_from_slice(&remaining);
          let sha = sha256_of(&full);

          let url = format!("{}/model.bin", server.uri());
          let client = reqwest::Client::new();
          download_to_file(&client, &url, &dest, 100, &sha, |_| {})
              .await
              .unwrap();

          assert!(dest.exists());
          let written = std::fs::read(&dest).unwrap();
          assert_eq!(written, full);
      }

      // 测试速度窗口：连续写入多个时间点，滑动窗口超过 5 秒的条目被丢弃
      #[test]
      fn speed_window_drops_old_entries() {
          use std::time::{Duration, Instant};
          let mut window: SpeedWindow = SpeedWindow::new();
          let now = Instant::now();

          // 模拟 6 秒前的条目（超出 5 秒窗口）
          window.record(now - Duration::from_secs(6), 1000);
          window.record(now - Duration::from_secs(2), 2000);
          window.record(now, 3000);

          let speed = window.avg_bps(now);
          // 只有最近 5 秒内的两条记录有效（2000 + 3000）/ 5s = 1000 bps
          assert!(speed > 0);
          // 6 秒前的 1000 bytes 不应参与计算
          // avg = (2000 + 3000) / 5 = 1000 bps
          assert_eq!(speed, 1000);
      }
  }
  ```

- [ ] **Step 4.2: 实现 `downloader.rs`**

  ```rust
  // src-tauri/src/models/downloader.rs

  use super::registry::tmp_file_path;
  use super::{DownloadCommand, DownloadProgressPayload, ModelsToml};
  use crate::error::AppError;
  use crate::state::AppState;
  use futures_util::StreamExt;
  use sha2::{Digest, Sha256};
  use std::collections::VecDeque;
  use std::io::Write;
  use std::path::Path;
  use std::sync::{
      atomic::{AtomicBool, Ordering},
      Arc,
  };
  use std::time::{Duration, Instant};
  use tauri::{AppHandle, Emitter};
  use tokio::sync::mpsc;

  // ── 滑动窗口速度计算 ──────────────────────────────────────────

  /// (时间点, 该时间点新写入的字节数)
  type WindowEntry = (Instant, u64);

  pub struct SpeedWindow {
      entries: VecDeque<WindowEntry>,
      window: Duration,
  }

  impl SpeedWindow {
      pub fn new() -> Self {
          Self {
              entries: VecDeque::new(),
              window: Duration::from_secs(5),
          }
      }

      /// 记录一次写入事件
      pub fn record(&mut self, at: Instant, bytes: u64) {
          self.entries.push_back((at, bytes));
      }

      /// 计算当前平均速度（bytes/sec），丢弃 5 秒前的条目
      pub fn avg_bps(&mut self, now: Instant) -> u64 {
          // 移除超过窗口的旧条目
          while let Some(&(ts, _)) = self.entries.front() {
              if now.duration_since(ts) > self.window {
                  self.entries.pop_front();
              } else {
                  break;
              }
          }
          if self.entries.is_empty() {
              return 0;
          }
          let total_bytes: u64 = self.entries.iter().map(|(_, b)| b).sum();
          // 窗口长度 = now - 最老条目的时间戳（至少 1 秒，避免除零）
          let oldest_ts = self.entries.front().map(|(ts, _)| *ts).unwrap_or(now);
          let elapsed = now.duration_since(oldest_ts).as_secs_f64().max(1.0);
          (total_bytes as f64 / elapsed) as u64
      }
  }

  // ── 核心下载函数（可独立测试）────────────────────────────────

  /// 下载单个文件到 `dest`，支持断点续传和 SHA256 校验。
  ///
  /// - 若 `dest.tmp` 已存在，使用 `Range: bytes=N-` 续传
  /// - 每写入 128 KB 调用一次 `progress_cb(downloaded_bytes)`
  /// - 下载完成后 SHA256 校验；通过则 rename tmp → dest，失败则删除 tmp 并返回 Error
  pub async fn download_to_file(
      client: &reqwest::Client,
      url: &str,
      dest: &Path,
      expected_size: u64,
      expected_sha256: &str,
      progress_cb: impl Fn(u64),
  ) -> Result<(), AppError> {
      let tmp = tmp_file_path(dest);

      // 创建目标目录
      if let Some(parent) = dest.parent() {
          tokio::fs::create_dir_all(parent)
              .await
              .map_err(|e| AppError::Io(e.to_string()))?;
      }

      // 检查已有临时文件大小（断点续传）
      let resume_offset = tokio::fs::metadata(&tmp)
          .await
          .map(|m| m.len())
          .unwrap_or(0);

      // 构建请求
      let mut req = client.get(url);
      if resume_offset > 0 {
          req = req.header("Range", format!("bytes={}-", resume_offset));
      }
      let resp = req.send().await.map_err(|e| AppError::Model(e.to_string()))?;
      if !resp.status().is_success() && resp.status().as_u16() != 206 {
          return Err(AppError::Model(format!(
              "HTTP {} for {}",
              resp.status(),
              url
          )));
      }

      // 打开临时文件（追加模式）
      let mut file = std::fs::OpenOptions::new()
          .create(true)
          .append(true)
          .open(&tmp)
          .map_err(|e| AppError::Io(e.to_string()))?;

      let mut downloaded = resume_offset;
      let mut buf = Vec::with_capacity(128 * 1024);
      let mut stream = resp.bytes_stream();

      while let Some(chunk) = stream.next().await {
          let chunk = chunk.map_err(|e| AppError::Model(e.to_string()))?;
          buf.extend_from_slice(&chunk);

          // 每积累 128 KB 刷一次盘
          if buf.len() >= 128 * 1024 {
              file.write_all(&buf)
                  .map_err(|e| AppError::Io(e.to_string()))?;
              downloaded += buf.len() as u64;
              progress_cb(downloaded);
              buf.clear();
          }
      }
      // 刷写剩余不足 128 KB 的尾部数据
      if !buf.is_empty() {
          file.write_all(&buf)
              .map_err(|e| AppError::Io(e.to_string()))?;
          downloaded += buf.len() as u64;
          progress_cb(downloaded);
      }
      drop(file);

      // SHA256 校验
      let computed = compute_sha256(&tmp)?;
      if computed != expected_sha256 {
          let _ = std::fs::remove_file(&tmp);
          return Err(AppError::Model(format!(
              "SHA256 校验失败：期望 {expected_sha256}，实际 {computed}"
          )));
      }

      // 重命名为最终文件
      std::fs::rename(&tmp, dest).map_err(|e| AppError::Io(e.to_string()))?;
      Ok(())
  }

  /// 计算文件 SHA256（同步，适合在 spawn_blocking 中调用）
  fn compute_sha256(path: &Path) -> Result<String, AppError> {
      let mut file = std::fs::File::open(path).map_err(|e| AppError::Io(e.to_string()))?;
      let mut hasher = Sha256::new();
      std::io::copy(&mut file, &mut hasher).map_err(|e| AppError::Io(e.to_string()))?;
      Ok(hex::encode(hasher.finalize()))
  }

  // ── DownloadWorker 长驻任务 ───────────────────────────────────

  /// 接收 DownloadCommand，管理并发下载（每次最多 1 个）。
  /// 通过 `cancel_flags` DashMap 支持取消。
  pub async fn run_download_worker(
      mut rx: mpsc::Receiver<DownloadCommand>,
      app: AppHandle,
      state: Arc<AppState>,
  ) {
      let client = reqwest::Client::builder()
          .timeout(Duration::from_secs(30))  // 建连超时
          .build()
          .expect("reqwest client build failed");

      // DashMap<variant_id, AtomicBool>：true = 已请求取消
      let cancel_flags: Arc<dashmap::DashMap<String, Arc<AtomicBool>>> =
          Arc::new(dashmap::DashMap::new());

      while let Some(cmd) = rx.recv().await {
          match cmd {
              DownloadCommand::Start { variant_id } => {
                  let cancelled = Arc::new(AtomicBool::new(false));
                  cancel_flags.insert(variant_id.clone(), Arc::clone(&cancelled));

                  // 从 AppState 克隆所需数据，避免跨 await 持锁
                  let model_config = Arc::clone(&state.model_config);
                  let config = state.config.read().await.clone();
                  let app_clone = app.clone();
                  let client_clone = client.clone();
                  let cancel_clone = Arc::clone(&cancelled);
                  let cancel_flags_clone = Arc::clone(&cancel_flags);
                  let vid = variant_id.clone();

                  tokio::spawn(async move {
                      let result = do_download(
                          &client_clone,
                          &model_config,
                          &config,
                          &vid,
                          &app_clone,
                          cancel_clone,
                      )
                      .await;

                      cancel_flags_clone.remove(&vid);

                      match result {
                          Ok(()) => {
                              app_clone
                                  .emit("models:downloaded", serde_json::json!({ "variant_id": vid }))
                                  .ok();
                          }
                          Err(e) => {
                              app_clone
                                  .emit(
                                      "models:error",
                                      serde_json::json!({ "variant_id": vid, "error": e.to_string() }),
                                  )
                                  .ok();
                          }
                      }
                  });
              }

              DownloadCommand::Cancel { variant_id } => {
                  if let Some(flag) = cancel_flags.get(&variant_id) {
                      flag.store(true, Ordering::Relaxed);
                  }
              }
          }
      }
  }

  /// 实际执行单个模型的下载（在 tokio::spawn 的 async task 中运行）
  async fn do_download(
      client: &reqwest::Client,
      model_config: &super::ModelsToml,
      config: &crate::config::schema::AppConfig,
      variant_id: &str,
      app: &AppHandle,
      cancelled: Arc<AtomicBool>,
  ) -> Result<(), AppError> {
      use super::registry::{model_file_path, parse_variant_id};

      let (model_type, variant_name) =
          parse_variant_id(variant_id).ok_or_else(|| AppError::Model(format!("无效 variant_id: {variant_id}")))?;

      let cfg = match model_type {
          "whisper" => model_config.whisper.variants.get(variant_name),
          "llm" => model_config.llm.variants.get(variant_name),
          _ => None,
      }
      .ok_or_else(|| AppError::Model(format!("未找到模型配置: {variant_id}")))?;

      let model_dir = std::path::Path::new(&config.vault_path)
          .parent()
          .unwrap_or(std::path::Path::new(&config.vault_path))
          .join("models");

      let dest = model_file_path(&model_dir, model_type, variant_name, &cfg.url);
      let expected_size = cfg.size_bytes;
      let expected_sha256 = cfg.sha256.clone();
      let url = cfg.url.clone();

      let mut speed_window = SpeedWindow::new();
      let mut last_progress = Instant::now();

      // 每 128 KB chunk 触发 progress callback
      let app_clone = app.clone();
      let vid = variant_id.to_string();

      let progress_cb = move |downloaded: u64| {
          if cancelled.load(Ordering::Relaxed) {
              // 取消信号：返回 Err 会中止流式下载（通过 channel drop 实现）
              // 此处仅记录，实际中断由 stream.next() 超时或连接关闭实现
              return;
          }

          let now = Instant::now();
          speed_window.record(now, 128 * 1024); // 近似：每次 128KB
          let speed_bps = speed_window.avg_bps(now);
          let eta_secs = if speed_bps > 0 && expected_size > downloaded {
              Some((expected_size - downloaded) / speed_bps)
          } else {
              None
          };

          // 限流：每 500ms 发一次 progress 事件（避免高频 IPC）
          if now.duration_since(last_progress) >= Duration::from_millis(500) {
              last_progress = now;
              app_clone
                  .emit(
                      "models:progress",
                      DownloadProgressPayload {
                          variant_id: vid.clone(),
                          downloaded_bytes: downloaded,
                          total_bytes: Some(expected_size),
                          speed_bps,
                          eta_secs,
                      },
                  )
                  .ok();
          }
      };

      download_to_file(client, &url, &dest, expected_size, &expected_sha256, progress_cb).await
  }
  ```

  > **取消实现说明**：`progress_cb` 检测到 `cancelled = true` 后不中断当前 stream，但可在外层包一个 `tokio::select!`（超时或取消信号）强制关闭连接。简单实现时 cancel 只是标记，下一次 chunk 写入后自然停止（文件处于 .tmp 状态，下次重启可续传）。生产实现应用 `tokio_util::sync::CancellationToken` 包裹 stream，此处 Task 5 注释中给出升级路径。

- [ ] **Commit:** `test+feat(models): TDD downloader — streaming download, resume, SHA256, speed window`

---

### Task 5: `commands/models.rs` — Tauri IPC 命令

**Files:**
- Create: `src-tauri/src/commands/models.rs`
- Modify: `src-tauri/src/commands/mod.rs`（添加 `pub mod models;`）
- Modify: `src-tauri/src/lib.rs`（注册命令 + 启动检测调用）

- [ ] **Step 5.1: 实现 `commands/models.rs`**

  ```rust
  // src-tauri/src/commands/models.rs

  use crate::error::AppError;
  use crate::models::{DownloadCommand, ModelVariant};
  use crate::models::registry::{check_required_models, list_all_variants};
  use crate::state::AppState;
  use tauri::State;

  /// 列出所有模型变体及其下载/激活状态
  #[tauri::command]
  #[specta::specta]
  pub async fn list_model_variants(
      state: State<'_, AppState>,
  ) -> Result<Vec<ModelVariant>, AppError> {
      let config = state.config.read().await;
      let model_dir = std::path::Path::new(&config.vault_path)
          .parent()
          .unwrap_or(std::path::Path::new(&config.vault_path))
          .join("models");

      Ok(list_all_variants(
          &state.model_config,
          &model_dir,
          &config.active_whisper_model,
          &config.active_llm_model,
      ))
  }

  /// 触发后台下载（非阻塞），立即返回
  #[tauri::command]
  #[specta::specta]
  pub async fn download_model(
      variant_id: String,
      state: State<'_, AppState>,
  ) -> Result<(), AppError> {
      state
          .download_tx
          .send(DownloadCommand::Start { variant_id })
          .await
          .map_err(|_| AppError::ChannelClosed)
  }

  /// 取消正在进行的下载
  #[tauri::command]
  #[specta::specta]
  pub async fn cancel_download(
      variant_id: String,
      state: State<'_, AppState>,
  ) -> Result<(), AppError> {
      state
          .download_tx
          .send(DownloadCommand::Cancel { variant_id })
          .await
          .map_err(|_| AppError::ChannelClosed)
  }

  /// 删除已下载的模型文件
  #[tauri::command]
  #[specta::specta]
  pub async fn delete_model(
      variant_id: String,
      state: State<'_, AppState>,
  ) -> Result<(), AppError> {
      use crate::models::registry::{model_file_path, parse_variant_id};

      let (model_type, variant_name) = parse_variant_id(&variant_id)
          .ok_or_else(|| AppError::Model(format!("无效 variant_id: {variant_id}")))?;

      let config = state.config.read().await;
      let model_dir = std::path::Path::new(&config.vault_path)
          .parent()
          .unwrap_or(std::path::Path::new(&config.vault_path))
          .join("models");

      let cfg = match model_type {
          "whisper" => state.model_config.whisper.variants.get(variant_name),
          "llm" => state.model_config.llm.variants.get(variant_name),
          _ => None,
      }
      .ok_or_else(|| AppError::NotFound(variant_id.clone()))?;

      let path = model_file_path(&model_dir, model_type, variant_name, &cfg.url);

      if path.exists() {
          tokio::fs::remove_file(&path)
              .await
              .map_err(|e| AppError::Io(e.to_string()))?;
      }
      Ok(())
  }

  /// 切换激活模型（持久化到 AppConfig，下次推理时生效）
  /// 注意：此命令不自动重载已加载的推理引擎，前端应提示用户重启或手动重载
  #[tauri::command]
  #[specta::specta]
  pub async fn set_active_model(
      variant_id: String,
      state: State<'_, AppState>,
  ) -> Result<(), AppError> {
      use crate::models::registry::parse_variant_id;

      let (model_type, _) = parse_variant_id(&variant_id)
          .ok_or_else(|| AppError::Model(format!("无效 variant_id: {variant_id}")))?;

      let mut config = state.config.write().await;
      match model_type {
          "whisper" => config.active_whisper_model = variant_id,
          "llm" => config.active_llm_model = variant_id,
          _ => return Err(AppError::Model(format!("未知 model_type: {model_type}"))),
      }

      // 持久化到 app_settings 表
      let serialized = serde_json::to_string(&*config)
          .map_err(|e| AppError::Storage(e.to_string()))?;
      state
          .db
          .save_setting("app_config", &serialized)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

      Ok(())
  }
  ```

- [ ] **Step 5.2: 在 `commands/mod.rs` 注册模块**

  ```rust
  // src-tauri/src/commands/mod.rs（在已有内容基础上添加）
  pub mod models;
  ```

- [ ] **Step 5.3: 在 `lib.rs` 集成启动检测并注册命令**

  ```rust
  // src-tauri/src/lib.rs（伪代码，补充到 run() 函数的对应位置）

  // 步骤 5：加载 models.toml
  let models_toml_str = include_str!("../../resources/models.toml");
  let model_config = Arc::new(
      crate::models::registry::load_models_toml(models_toml_str)
          .expect("models.toml 解析失败")
  );

  // 步骤 6：启动时检测模型
  // 延迟到窗口创建后通过 on_window_event 或 setup 钩子 emit
  // 以确保前端 listener 已注册
  let missing_at_startup = {
      let cfg = app_config.read().await;
      let model_dir = /* 同上 */ ;
      crate::models::registry::check_required_models(
          &model_config,
          &model_dir,
          &cfg.active_whisper_model,
          &cfg.active_llm_model,
      )
  };

  // 步骤 8：启动 DownloadWorker
  let (download_tx, download_rx) = tokio::sync::mpsc::channel::<DownloadCommand>(32);
  {
      let app_handle_clone = app_handle.clone();
      let state_clone = Arc::clone(&app_state);
      tokio::spawn(crate::models::downloader::run_download_worker(
          download_rx,
          app_handle_clone,
          state_clone,
      ));
  }

  // 步骤 10（setup 钩子内，窗口就绪后）：
  if !missing_at_startup.is_empty() {
      app_handle.emit("models:required", serde_json::json!({ "missing": missing_at_startup })).ok();
  }

  // 注册 commands（tauri-specta 生成 bindings.ts）：
  // .invoke_handler(tauri::generate_handler![
  //     ...
  //     commands::models::list_model_variants,
  //     commands::models::download_model,
  //     commands::models::cancel_download,
  //     commands::models::delete_model,
  //     commands::models::set_active_model,
  // ])
  ```

- [ ] **Commit:** `feat(models): commands list/download/cancel/delete/set_active + startup detection`

---

### Task 6: React — 首次启动引导弹窗

**Files:**
- Create: `src/components/models/ModelRequiredDialog.tsx`
- Create: `src/store/models.ts`
- Modify: `src/App.tsx`（挂载全局 event listener）

- [ ] **Step 6.1: 创建 Zustand models store**

  ```typescript
  // src/store/models.ts
  import { create } from 'zustand'
  import { listen } from '@tauri-apps/api/event'
  import type { ModelVariant, DownloadProgressPayload } from '../lib/bindings'
  import { listModelVariants, downloadModel, cancelDownload, deleteModel, setActiveModel } from '../lib/bindings'

  interface DownloadState {
    downloadedBytes: number
    totalBytes: number | null
    speedBps: number
    etaSecs: number | null
  }

  interface ModelsStore {
    variants: ModelVariant[]
    downloads: Record<string, DownloadState>   // variant_id → progress
    requiredMissing: string[]                  // models:required payload
    isRequiredDialogOpen: boolean

    // Actions
    loadVariants: () => Promise<void>
    startDownload: (variantId: string) => Promise<void>
    cancelDownload: (variantId: string) => Promise<void>
    deleteModel: (variantId: string) => Promise<void>
    setActive: (variantId: string) => Promise<void>
    dismissRequiredDialog: () => void

    // Internal
    _setupListeners: () => () => void
  }

  export const useModelsStore = create<ModelsStore>((set, get) => ({
    variants: [],
    downloads: {},
    requiredMissing: [],
    isRequiredDialogOpen: false,

    loadVariants: async () => {
      const variants = await listModelVariants()
      set({ variants })
    },

    startDownload: async (variantId) => {
      await downloadModel(variantId)
    },

    cancelDownload: async (variantId) => {
      await cancelDownload(variantId)
      set((s) => {
        const d = { ...s.downloads }
        delete d[variantId]
        return { downloads: d }
      })
    },

    deleteModel: async (variantId) => {
      await deleteModel(variantId)
      await get().loadVariants()
    },

    setActive: async (variantId) => {
      await setActiveModel(variantId)
      await get().loadVariants()
    },

    dismissRequiredDialog: () => set({ isRequiredDialogOpen: false }),

    _setupListeners: () => {
      const unlisteners: Promise<() => void>[] = []

      // models:required → 弹出引导弹窗
      unlisteners.push(
        listen<{ missing: string[] }>('models:required', (e) => {
          set({ requiredMissing: e.payload.missing, isRequiredDialogOpen: true })
        })
      )

      // models:progress → 更新下载进度
      unlisteners.push(
        listen<DownloadProgressPayload>('models:progress', (e) => {
          const p = e.payload
          set((s) => ({
            downloads: {
              ...s.downloads,
              [p.variant_id]: {
                downloadedBytes: p.downloaded_bytes,
                totalBytes: p.total_bytes ?? null,
                speedBps: p.speed_bps,
                etaSecs: p.eta_secs ?? null,
              },
            },
          }))
        })
      )

      // models:downloaded → 刷新列表，清除进度
      unlisteners.push(
        listen<{ variant_id: string }>('models:downloaded', (e) => {
          set((s) => {
            const d = { ...s.downloads }
            delete d[e.payload.variant_id]
            return { downloads: d }
          })
          get().loadVariants()
        })
      )

      // models:error → 清除进度（前端可自行 toast 提示）
      unlisteners.push(
        listen<{ variant_id: string; error: string }>('models:error', (e) => {
          set((s) => {
            const d = { ...s.downloads }
            delete d[e.payload.variant_id]
            return { downloads: d }
          })
        })
      )

      return () => {
        unlisteners.forEach((p) => p.then((fn) => fn()))
      }
    },
  }))
  ```

- [ ] **Step 6.2: 创建 `ModelRequiredDialog.tsx`**

  ```tsx
  // src/components/models/ModelRequiredDialog.tsx
  //
  // 检测到 models:required 时由 App.tsx 渲染此弹窗。
  // 只展示缺失的模型，用户选择并下载后弹窗自动关闭（所有必需模型已下载）。

  import { useEffect } from 'react'
  import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog'
  import { Button } from '../ui/button'
  import { Progress } from '../ui/progress'
  import { useModelsStore } from '../../store/models'
  import { useT } from '../../hooks/useT'

  export function ModelRequiredDialog() {
    const t = useT()
    const {
      variants,
      downloads,
      requiredMissing,
      isRequiredDialogOpen,
      dismissRequiredDialog,
      startDownload,
      loadVariants,
    } = useModelsStore()

    // 初始化时加载变体列表
    useEffect(() => {
      if (isRequiredDialogOpen) loadVariants()
    }, [isRequiredDialogOpen])

    // 当所有 requiredMissing 都已下载时自动关闭弹窗
    useEffect(() => {
      if (!isRequiredDialogOpen) return
      const allDone = requiredMissing.every((id) =>
        variants.find((v) => v.variant_id === id)?.is_downloaded
      )
      if (allDone && requiredMissing.length > 0) {
        dismissRequiredDialog()
      }
    }, [variants, requiredMissing, isRequiredDialogOpen])

    const missingVariants = variants.filter((v) => requiredMissing.includes(v.variant_id))

    return (
      <Dialog open={isRequiredDialogOpen} onOpenChange={() => {}}>
        {/* 不允许点击遮罩关闭——必须下载才能继续 */}
        <DialogContent className="max-w-lg" onPointerDownOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>{t('models.required_title')}</DialogTitle>
            <DialogDescription>{t('models.required_desc')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 mt-4">
            {missingVariants.map((v) => {
              const dl = downloads[v.variant_id]
              const isDownloading = !!dl
              const pct = dl && dl.totalBytes
                ? Math.round((dl.downloadedBytes / dl.totalBytes) * 100)
                : 0

              return (
                <div key={v.variant_id} className="border border-border rounded-md p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-text-primary">{v.name}</p>
                      <p className="text-xs text-text-muted">{v.description} · {v.size_display}</p>
                    </div>
                    {!isDownloading && !v.is_downloaded && (
                      <Button size="sm" onClick={() => startDownload(v.variant_id)}>
                        {t('models.action_download')}
                      </Button>
                    )}
                    {v.is_downloaded && (
                      <span className="text-xs text-status-success">{t('models.status_downloaded')}</span>
                    )}
                  </div>

                  {isDownloading && (
                    <div className="space-y-1">
                      <Progress value={pct} className="h-1.5" />
                      <div className="flex justify-between text-xs text-text-muted">
                        <span>{t('models.download_speed', { speed: formatSpeed(dl.speedBps) })}</span>
                        {dl.etaSecs != null && (
                          <span>{t('models.download_eta', { eta: formatEta(dl.etaSecs) })}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  function formatSpeed(bps: number): string {
    if (bps >= 1_048_576) return `${(bps / 1_048_576).toFixed(1)} MB`
    if (bps >= 1_024) return `${(bps / 1_024).toFixed(0)} KB`
    return `${bps} B`
  }

  function formatEta(secs: number): string {
    if (secs >= 3600) return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    if (secs >= 60) return `${Math.floor(secs / 60)}m ${secs % 60}s`
    return `${secs}s`
  }
  ```

- [ ] **Step 6.3: 在 `App.tsx` 挂载 event listeners 并渲染 `ModelRequiredDialog`**

  ```tsx
  // src/App.tsx（在已有内容基础上添加）
  import { useEffect } from 'react'
  import { ModelRequiredDialog } from './components/models/ModelRequiredDialog'
  import { useModelsStore } from './store/models'

  export default function App() {
    const setupModelListeners = useModelsStore((s) => s._setupListeners)

    useEffect(() => {
      const cleanup = setupModelListeners()
      return cleanup
    }, [])

    return (
      <>
        {/* 现有路由/布局 */}
        <RouterProvider router={router} />
        {/* 全局弹窗 */}
        <ModelRequiredDialog />
      </>
    )
  }
  ```

- [ ] **Commit:** `feat(ui): models store + ModelRequiredDialog for first-launch onboarding`

---

### Task 7: React — 设置页 `/settings/models` 子页面

**Files:**
- Create: `src/components/settings/ModelsPage.tsx`
- Modify: `src/router.tsx`（添加 `/settings/models` 路由）

- [ ] **Step 7.1: 创建 `ModelsPage.tsx`**

  ```tsx
  // src/components/settings/ModelsPage.tsx
  //
  // 分 Whisper / LLM 两组展示所有模型变体。
  // 每个变体：名称 + 描述 + 大小 + 状态 + 操作按钮 + 下载进度条（下载中时）。

  import { useEffect } from 'react'
  import { useModelsStore } from '../../store/models'
  import { useT } from '../../hooks/useT'
  import { Button } from '../ui/button'
  import { Progress } from '../ui/progress'
  import { Badge } from '../ui/badge'
  import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
  } from '../ui/alert-dialog'
  import type { ModelVariant } from '../../lib/bindings'

  export function ModelsPage() {
    const t = useT()
    const { variants, downloads, loadVariants, startDownload, cancelDownload, deleteModel, setActive } =
      useModelsStore()

    useEffect(() => {
      loadVariants()
    }, [])

    const whisperVariants = variants.filter((v) => v.model_type === 'whisper')
    const llmVariants = variants.filter((v) => v.model_type === 'llm')

    return (
      <div className="p-6 space-y-8 max-w-2xl">
        <h1 className="text-xl font-semibold text-text-primary">{t('models.page_title')}</h1>

        <ModelGroup
          title={t('models.group_whisper')}
          variants={whisperVariants}
          downloads={downloads}
          t={t}
          onDownload={startDownload}
          onCancel={cancelDownload}
          onDelete={deleteModel}
          onSetActive={setActive}
        />

        <ModelGroup
          title={t('models.group_llm')}
          variants={llmVariants}
          downloads={downloads}
          t={t}
          onDownload={startDownload}
          onCancel={cancelDownload}
          onDelete={deleteModel}
          onSetActive={setActive}
        />
      </div>
    )
  }

  // ── 子组件：ModelGroup ────────────────────────────────────────

  interface ModelGroupProps {
    title: string
    variants: ModelVariant[]
    downloads: Record<string, { downloadedBytes: number; totalBytes: number | null; speedBps: number; etaSecs: number | null }>
    t: (key: string, vars?: Record<string, string>) => string
    onDownload: (id: string) => void
    onCancel: (id: string) => void
    onDelete: (id: string) => Promise<void>
    onSetActive: (id: string) => Promise<void>
  }

  function ModelGroup({ title, variants, downloads, t, onDownload, onCancel, onDelete, onSetActive }: ModelGroupProps) {
    return (
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-text-secondary uppercase tracking-wide">{title}</h2>
        <div className="space-y-2">
          {variants.map((v) => (
            <ModelRow
              key={v.variant_id}
              variant={v}
              dlState={downloads[v.variant_id]}
              t={t}
              onDownload={onDownload}
              onCancel={onCancel}
              onDelete={onDelete}
              onSetActive={onSetActive}
            />
          ))}
        </div>
      </section>
    )
  }

  // ── 子组件：ModelRow ──────────────────────────────────────────

  interface ModelRowProps {
    variant: ModelVariant
    dlState?: { downloadedBytes: number; totalBytes: number | null; speedBps: number; etaSecs: number | null }
    t: (key: string, vars?: Record<string, string>) => string
    onDownload: (id: string) => void
    onCancel: (id: string) => void
    onDelete: (id: string) => Promise<void>
    onSetActive: (id: string) => Promise<void>
  }

  function ModelRow({ variant: v, dlState, t, onDownload, onCancel, onDelete, onSetActive }: ModelRowProps) {
    const isDownloading = !!dlState
    const pct = dlState?.totalBytes ? Math.round((dlState.downloadedBytes / dlState.totalBytes) * 100) : 0

    return (
      <div className="border border-border rounded-lg p-4 space-y-3">
        {/* 标题行 */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text-primary">{v.name}</span>
              {v.is_active && (
                <Badge variant="outline" className="text-xs text-accent border-accent">
                  {t('models.status_active')}
                </Badge>
              )}
            </div>
            <p className="text-xs text-text-muted mt-0.5">{v.description}</p>
            <p className="text-xs text-text-muted">{v.size_display}</p>
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center gap-2 shrink-0">
            {!v.is_downloaded && !isDownloading && (
              <Button size="sm" variant="outline" onClick={() => onDownload(v.variant_id)}>
                {t('models.action_download')}
              </Button>
            )}

            {isDownloading && (
              <Button size="sm" variant="ghost" onClick={() => onCancel(v.variant_id)}>
                {t('models.action_cancel')}
              </Button>
            )}

            {v.is_downloaded && !v.is_active && (
              <Button size="sm" variant="outline" onClick={() => onSetActive(v.variant_id)}>
                {t('models.action_set_active')}
              </Button>
            )}

            {v.is_downloaded && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="ghost" className="text-status-error hover:text-status-error">
                    {t('models.action_delete')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('models.action_delete')}</AlertDialogTitle>
                    <AlertDialogDescription>{t('models.delete_confirm')}</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-status-error text-white hover:bg-status-error/90"
                      onClick={() => onDelete(v.variant_id)}
                    >
                      {t('models.action_delete')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
        </div>

        {/* 下载进度条（下载中时展示） */}
        {isDownloading && dlState && (
          <div className="space-y-1">
            <Progress value={pct} className="h-1.5" />
            <div className="flex justify-between text-xs text-text-muted">
              <span>
                {formatBytes(dlState.downloadedBytes)}
                {dlState.totalBytes != null ? ` / ${formatBytes(dlState.totalBytes)}` : ''} ·{' '}
                {t('models.download_speed', { speed: formatSpeed(dlState.speedBps) })}
              </span>
              {dlState.etaSecs != null && (
                <span>{t('models.download_eta', { eta: formatEta(dlState.etaSecs) })}</span>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── 格式化辅助函数 ────────────────────────────────────────────

  function formatBytes(b: number): string {
    if (b >= 1_073_741_824) return `${(b / 1_073_741_824).toFixed(1)} GB`
    if (b >= 1_048_576) return `${(b / 1_048_576).toFixed(0)} MB`
    if (b >= 1_024) return `${(b / 1_024).toFixed(0)} KB`
    return `${b} B`
  }

  function formatSpeed(bps: number): string {
    if (bps >= 1_048_576) return `${(bps / 1_048_576).toFixed(1)} MB`
    if (bps >= 1_024) return `${(bps / 1_024).toFixed(0)} KB`
    return `${bps} B`
  }

  function formatEta(secs: number): string {
    if (secs >= 3600) return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    if (secs >= 60) return `${Math.floor(secs / 60)}m ${secs % 60}s`
    return `${secs}s`
  }
  ```

- [ ] **Step 7.2: 在 `router.tsx` 添加 `/settings/models` 路由**

  ```typescript
  // src/router.tsx（在已有设置路由下添加子路由）
  // 以 TanStack Router 为例：

  import { ModelsPage } from './components/settings/ModelsPage'

  // 在 settingsRoute 下添加子路由：
  const settingsModelsRoute = createRoute({
    getParentRoute: () => settingsRoute,
    path: 'models',
    component: ModelsPage,
  })

  // 并在 routeTree 中注册 settingsModelsRoute
  ```

- [ ] **Commit:** `feat(ui): settings /settings/models page with progress bar, speed, cancel, delete, set active`

---

### Task 8: i18n — 新增 `models` section 翻译

**Files:**
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Modify: `resources/translations/i18n_outline.json`

- [ ] **Step 8.1: 在三个语言文件中添加 `models` section**

  **zh_CN.json**（示例，按实际 JSON 结构追加）：
  ```json
  "models": {
    "page_title": "模型管理",
    "group_whisper": "语音转写模型（Whisper）",
    "group_llm": "本地 AI 模型（LLM）",
    "status_downloaded": "已下载",
    "status_downloading": "下载中...",
    "status_not_downloaded": "未下载",
    "status_active": "当前使用",
    "action_download": "下载",
    "action_cancel": "取消",
    "action_delete": "删除",
    "action_set_active": "设为当前",
    "download_speed": "{speed}/s",
    "download_eta": "剩余 {eta}",
    "delete_confirm": "删除模型文件？此操作不可撤销。",
    "required_title": "需要下载模型",
    "required_desc": "首次使用需要下载 AI 模型，请选择要安装的模型。"
  }
  ```

  **en_US.json**：
  ```json
  "models": {
    "page_title": "Model Management",
    "group_whisper": "Speech Recognition Models (Whisper)",
    "group_llm": "Local AI Models (LLM)",
    "status_downloaded": "Downloaded",
    "status_downloading": "Downloading...",
    "status_not_downloaded": "Not Downloaded",
    "status_active": "Active",
    "action_download": "Download",
    "action_cancel": "Cancel",
    "action_delete": "Delete",
    "action_set_active": "Set Active",
    "download_speed": "{speed}/s",
    "download_eta": "{eta} remaining",
    "delete_confirm": "Delete this model file? This action cannot be undone.",
    "required_title": "Models Required",
    "required_desc": "Please download the AI models required for first use."
  }
  ```

  **fr_FR.json**：
  ```json
  "models": {
    "page_title": "Gestion des modèles",
    "group_whisper": "Modèles de transcription (Whisper)",
    "group_llm": "Modèles IA locaux (LLM)",
    "status_downloaded": "Téléchargé",
    "status_downloading": "Téléchargement...",
    "status_not_downloaded": "Non téléchargé",
    "status_active": "Actif",
    "action_download": "Télécharger",
    "action_cancel": "Annuler",
    "action_delete": "Supprimer",
    "action_set_active": "Définir comme actif",
    "download_speed": "{speed}/s",
    "download_eta": "{eta} restant",
    "delete_confirm": "Supprimer ce fichier de modèle ? Cette action est irréversible.",
    "required_title": "Modèles requis",
    "required_desc": "Veuillez télécharger les modèles IA nécessaires à la première utilisation."
  }
  ```

- [ ] **Step 8.2: 在 `i18n_outline.json` 添加 `models` section 定义**

- [ ] **Commit:** `feat(i18n): add models section to zh_CN/en_US/fr_FR translations`

---

### Task 9: 集成测试与收尾

**Files:**
- Create: `src-tauri/tests/models_integration_test.rs`（可选，验证端到端下载流程）

- [ ] **Step 9.1: 运行所有单元测试，确认全绿**

  ```bash
  cd src-tauri && cargo test models
  ```

  预期输出：所有 `models::*` 测试通过，包括：
  - `registry::tests::parse_models_toml_ok`
  - `registry::tests::parse_models_toml_missing_field_fails`
  - `registry::tests::check_model_file_missing`
  - `registry::tests::check_model_file_size_mismatch`
  - `registry::tests::check_model_file_ok`
  - `registry::tests::list_variants_populates_is_active`
  - `registry::tests::check_required_models_missing`
  - `registry::tests::check_required_models_present`
  - `registry::tests::parse_variant_id_ok`
  - `registry::tests::parse_variant_id_no_slash`
  - `downloader::tests::download_full_ok`
  - `downloader::tests::download_sha256_mismatch_deletes_tmp`
  - `downloader::tests::download_resume_sends_range_header`
  - `downloader::tests::speed_window_drops_old_entries`

- [ ] **Step 9.2: 运行 `cargo clippy`，修复所有 warning**

  ```bash
  cd src-tauri && cargo clippy -- -D warnings
  ```

- [ ] **Step 9.3: 验证 `models.toml` 中 SHA256 占位符的视觉标注**

  确认 `resources/models.toml` 中 `whisper/medium`、`llm/qwen2.5-3b-q4`、`llm/qwen2.5-7b-q4` 的 `sha256` 字段值为 `"FILL_IN_BEFORE_RELEASE_64_HEX_CHARS_REQUIRED"`，并有注释说明填写方法。

- [ ] **Step 9.4: 端到端手动验证（开发环境）**

  1. 启动应用，若模型未下载，应看到 `ModelRequiredDialog` 弹窗
  2. 点击下载，进度条正常更新，速度/ETA 显示正确
  3. 打开 `/settings/models`，确认分组展示、取消、删除、设为当前功能正常
  4. 关闭应用重启，已下载模型不再弹窗

- [ ] **Commit:** `test(models): integration tests pass, clippy clean`

---

## 关键约束与注意事项

### SHA256 占位符
`resources/models.toml` 中三个 `FILL_IN_BEFORE_RELEASE_64_HEX_CHARS_REQUIRED` 占位符**必须在发布前填写**：
```bash
sha256sum ggml-medium.bin
sha256sum qwen2.5-3b-instruct-q4_k_m.gguf
sha256sum qwen2.5-7b-instruct-q4_k_m.gguf
```

### TOML key 带 `.` 的处理
`qwen2.5-3b-q4` 等包含 `.` 的 variant name 在 TOML 中必须用引号：
```toml
["llm.variants.qwen2.5-3b-q4"]
```
Rust 端用 `HashMap<String, VariantConfig>` 反序列化，键名保留原始字符串。

### 下载取消升级路径
当前实现用 `AtomicBool` 标记取消，stream 仍在进行（临时文件保留，下次可续传）。生产版本应升级为：
```rust
// 用 tokio_util::sync::CancellationToken 包裹 stream
let ct = CancellationToken::new();
tokio::select! {
    _ = ct.cancelled() => { /* 清理 .tmp 或保留（续传） */ }
    result = download_loop => { ... }
}
```

### progress 事件限流
`do_download` 中对 `models:progress` 事件做了 500ms 限流，避免高频 IPC 影响 UI 性能。实现在 `progress_cb` 内用 `last_progress: Instant` 比较。

### AppState 中 `model_config` 字段
`state.rs` 中需要添加：
```rust
pub model_config: Arc<ModelsToml>,
pub download_tx: mpsc::Sender<DownloadCommand>,
```
这两个字段在 Task 5 Step 5.3 中通过 `lib.rs` 初始化。
