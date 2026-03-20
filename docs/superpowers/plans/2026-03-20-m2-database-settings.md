# M2: Database Layer + Settings System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the SQLite database layer (WAL mode, migrations, FTS5, triggers) and the settings system (AppConfig, Tauri commands, React UI with Zustand store) as the shared foundation for all subsequent milestones.

**Architecture:** sqlx with an `SqlitePool` (WAL mode) is initialized at startup and injected into `AppState`; all schema changes are managed via embedded `sqlx::migrate!()` migrations. Application config (`AppConfig`) is persisted as a single JSON blob in the `app_settings` table and held in an `Arc<RwLock<AppConfig>>` for low-contention reads by all commands. The React settings page reads/writes config via three Tauri commands (`get_config`, `update_config`, `reset_config`) with a Zustand store as the client-side cache.

**Tech Stack:** Rust · sqlx 0.8 (sqlite, runtime-tokio, macros) · SQLite WAL · serde/serde_json · tauri-specta 2 · React 18 · TypeScript · Zustand · shadcn/ui · TanStack Router

---

### Task 1: Cargo.toml Dependencies

**Files:**
- Modify: `src-tauri/Cargo.toml`

- [ ] **Step 1: Add required dependencies**

  Ensure `src-tauri/Cargo.toml` contains the following under `[dependencies]`. Do not touch entries that already exist; only add what is missing:

  ```toml
  sqlx = { version = "0.8", features = ["sqlite", "runtime-tokio", "macros"] }
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  tokio = { version = "1", features = ["full"] }
  thiserror = "1"
  uuid = { version = "1", features = ["v4"] }
  tauri = { version = "2", features = ["protocol-asset"] }
  specta = "2"
  tauri-specta = { version = "2", features = ["derive"] }
  ```

  Also add `[features]`:
  ```toml
  [features]
  default = []
  cuda = []
  ```

- [ ] **Commit:** `feat(m2): add sqlx, serde, uuid deps to Cargo.toml`

---

### Task 2: Error Type

**Files:**
- Create: `src-tauri/src/error.rs`
- Modify: `src-tauri/src/lib.rs` (add `pub mod error;`)

- [ ] **Step 1: Write the unified `AppError` type**

  Create `src-tauri/src/error.rs`:

  ```rust
  #[derive(Debug, thiserror::Error, serde::Serialize, specta::Type)]
  #[serde(tag = "kind", content = "message")]
  pub enum AppError {
      #[error("audio error: {0}")]
      Audio(String),
      #[error("transcription error: {0}")]
      Transcription(String),
      #[error("llm error: {0}")]
      Llm(String),
      #[error("storage error: {0}")]
      Storage(String),
      #[error("io error: {0}")]
      Io(String),
      #[error("model error: {0}")]
      Model(String),
      #[error("workspace error: {0}")]
      Workspace(String),
      #[error("not found: {0}")]
      NotFound(String),
      #[error("validation: {0}")]
      Validation(String),
      #[error("channel closed")]
      ChannelClosed,
  }

  // Allow sqlx errors to convert automatically
  impl From<sqlx::Error> for AppError {
      fn from(e: sqlx::Error) -> Self {
          AppError::Storage(e.to_string())
      }
  }

  impl From<std::io::Error> for AppError {
      fn from(e: std::io::Error) -> Self {
          AppError::Io(e.to_string())
      }
  }
  ```

- [ ] **Step 2: Expose module in `lib.rs`**

  Add `pub mod error;` near the top of `src-tauri/src/lib.rs`.

- [ ] **Commit:** `feat(m2): add unified AppError type with sqlx/io conversions`

---

### Task 3: Migration Files

**Files:**
- Create: `src-tauri/src/storage/migrations/0001_initial.sql`
- Create: `src-tauri/src/storage/migrations/0002_llm_tasks.sql`

- [ ] **Step 1: Write `0001_initial.sql`**

  Create `src-tauri/src/storage/migrations/0001_initial.sql` with the exact content below (every table, index, FTS5 virtual table, `workspace_text_assets`, and all triggers):

  ```sql
  -- recordings: audio file metadata
  CREATE TABLE recordings (
      id          TEXT PRIMARY KEY,
      title       TEXT NOT NULL,
      file_path   TEXT NOT NULL,
      duration_ms INTEGER NOT NULL DEFAULT 0,
      language    TEXT,
      created_at  INTEGER NOT NULL,
      updated_at  INTEGER NOT NULL
  );

  -- transcription_segments: word/sentence segments from whisper
  CREATE TABLE transcription_segments (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
      start_ms     INTEGER NOT NULL,
      end_ms       INTEGER NOT NULL,
      text         TEXT NOT NULL,
      language     TEXT,
      confidence   REAL
  );
  CREATE INDEX idx_segments_recording ON transcription_segments(recording_id);

  -- workspace_folders: hierarchical folder tree
  CREATE TABLE workspace_folders (
      id          TEXT PRIMARY KEY,
      parent_id   TEXT REFERENCES workspace_folders(id) ON DELETE CASCADE,
      name        TEXT NOT NULL,
      folder_kind TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'inbox' | 'system_root' | 'event' | 'batch_task'
      is_system   INTEGER NOT NULL DEFAULT 0,     -- 1 = cannot rename/delete/move
      created_at  INTEGER NOT NULL
  );

  -- workspace_documents: document records (transcripts, imports, notes)
  CREATE TABLE workspace_documents (
      id           TEXT PRIMARY KEY,
      folder_id    TEXT REFERENCES workspace_folders(id) ON DELETE SET NULL,
      title        TEXT NOT NULL,
      file_path    TEXT,
      content_text TEXT,                          -- maintained by trigger; do NOT write directly
      source_type  TEXT NOT NULL,                 -- 'recording' | 'import' | 'manual' | 'batch_task'
      recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
      created_at   INTEGER NOT NULL,
      updated_at   INTEGER NOT NULL
  );

  -- workspace_fts: full-text search virtual table over workspace_documents
  CREATE VIRTUAL TABLE workspace_fts USING fts5(
      title,
      content_text,
      content=workspace_documents,
      content_rowid=rowid
  );

  -- workspace_text_assets: versioned text content per document per role
  CREATE TABLE workspace_text_assets (
      id          TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
      role        TEXT NOT NULL,   -- 'document_text'|'transcript'|'meeting_brief'|'summary'|
                                   -- 'translation'|'decisions'|'action_items'|'next_steps'
      content     TEXT NOT NULL,
      file_path   TEXT,            -- optional disk path of the corresponding .md file
      created_at  INTEGER NOT NULL,
      updated_at  INTEGER NOT NULL,
      UNIQUE(document_id, role)    -- one record per role per document
  );
  CREATE INDEX idx_assets_document ON workspace_text_assets(document_id, role);

  -- Trigger: after INSERT on workspace_text_assets, sync content_text on parent document
  CREATE TRIGGER sync_content_text_on_asset_insert
  AFTER INSERT ON workspace_text_assets
  BEGIN
      UPDATE workspace_documents
      SET content_text = (
          SELECT content FROM workspace_text_assets
          WHERE document_id = NEW.document_id
          ORDER BY CASE role
              WHEN 'document_text' THEN 0
              WHEN 'transcript'    THEN 1
              WHEN 'meeting_brief' THEN 2
              WHEN 'summary'       THEN 3
              WHEN 'translation'   THEN 4
              WHEN 'decisions'     THEN 5
              WHEN 'action_items'  THEN 6
              WHEN 'next_steps'    THEN 7
              ELSE 99 END
          LIMIT 1
      )
      WHERE id = NEW.document_id;
  END;

  -- Trigger: after UPDATE on workspace_text_assets, sync content_text on parent document
  CREATE TRIGGER sync_content_text_on_asset_update
  AFTER UPDATE ON workspace_text_assets
  BEGIN
      UPDATE workspace_documents
      SET content_text = (
          SELECT content FROM workspace_text_assets
          WHERE document_id = NEW.document_id
          ORDER BY CASE role
              WHEN 'document_text' THEN 0
              WHEN 'transcript'    THEN 1
              WHEN 'meeting_brief' THEN 2
              WHEN 'summary'       THEN 3
              WHEN 'translation'   THEN 4
              WHEN 'decisions'     THEN 5
              WHEN 'action_items'  THEN 6
              WHEN 'next_steps'    THEN 7
              ELSE 99 END
          LIMIT 1
      )
      WHERE id = NEW.document_id;
  END;

  -- timeline_events: local calendar events (no OAuth)
  CREATE TABLE timeline_events (
      id           TEXT PRIMARY KEY,
      title        TEXT NOT NULL,
      start_at     INTEGER NOT NULL,
      end_at       INTEGER NOT NULL,
      description  TEXT,
      tags         TEXT,                          -- JSON array of strings
      recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
      document_id  TEXT REFERENCES workspace_documents(id) ON DELETE SET NULL,
      created_at   INTEGER NOT NULL
  );

  -- model_registry: tracks downloaded AI model files
  CREATE TABLE model_registry (
      model_id      TEXT PRIMARY KEY,             -- e.g. 'whisper/base' | 'llm/qwen2.5-7b-q4'
      file_path     TEXT NOT NULL,
      sha256        TEXT NOT NULL,
      size_bytes    INTEGER NOT NULL,
      downloaded_at INTEGER NOT NULL
  );

  -- app_settings: key-value store for application configuration
  CREATE TABLE app_settings (
      key        TEXT PRIMARY KEY,
      value      TEXT NOT NULL,                   -- JSON-serialized value
      updated_at INTEGER NOT NULL
  );
  ```

- [ ] **Step 2: Write `0002_llm_tasks.sql`**

  Create `src-tauri/src/storage/migrations/0002_llm_tasks.sql`:

  ```sql
  -- llm_tasks: tracks AI processing tasks per document
  CREATE TABLE llm_tasks (
      id           TEXT PRIMARY KEY,
      document_id  TEXT REFERENCES workspace_documents(id) ON DELETE CASCADE,
      task_type    TEXT NOT NULL,                 -- 'summary' | 'translation' | 'meeting_brief' | 'qa'
      status       TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'running' | 'done' | 'error' | 'cancelled'
      result_text  TEXT,
      error_msg    TEXT,
      created_at   INTEGER NOT NULL,
      completed_at INTEGER
  );
  CREATE INDEX idx_llm_tasks_document ON llm_tasks(document_id, status);
  ```

- [ ] **Commit:** `feat(m2): add SQL migration files 0001_initial and 0002_llm_tasks`

---

### Task 4: Database Connection Pool (`storage/db.rs`)

**Files:**
- Create: `src-tauri/src/storage/mod.rs`
- Create: `src-tauri/src/storage/db.rs`
- Modify: `src-tauri/src/lib.rs` (add `pub mod storage;`)

- [ ] **Step 1: Write tests first (TDD)**

  At the bottom of `src-tauri/src/storage/db.rs` add a `#[cfg(test)]` block before writing any implementation:

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;

      /// Pool must open successfully on an in-memory database.
      #[tokio::test]
      async fn test_init_pool_in_memory() {
          let db = Db::open("sqlite::memory:").await
              .expect("should open in-memory db");
          // Verify migrations ran: app_settings table must exist
          let row: (i64,) = sqlx::query_as(
              "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='app_settings'"
          )
          .fetch_one(&db.pool)
          .await
          .expect("query should succeed");
          assert_eq!(row.0, 1, "app_settings table should exist after migration");
      }

      /// All tables from 0001_initial.sql must be present.
      #[tokio::test]
      async fn test_all_tables_created() {
          let db = Db::open("sqlite::memory:").await.unwrap();
          let expected = [
              "recordings",
              "transcription_segments",
              "workspace_folders",
              "workspace_documents",
              "workspace_text_assets",
              "timeline_events",
              "model_registry",
              "app_settings",
          ];
          for table in &expected {
              let row: (i64,) = sqlx::query_as(
                  "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?"
              )
              .bind(table)
              .fetch_one(&db.pool)
              .await
              .unwrap_or_else(|_| panic!("query for table {} failed", table));
              assert_eq!(row.0, 1, "table '{}' should exist", table);
          }
      }

      /// llm_tasks table from 0002_llm_tasks.sql must be present.
      #[tokio::test]
      async fn test_llm_tasks_table_created() {
          let db = Db::open("sqlite::memory:").await.unwrap();
          let row: (i64,) = sqlx::query_as(
              "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='llm_tasks'"
          )
          .fetch_one(&db.pool)
          .await
          .unwrap();
          assert_eq!(row.0, 1);
      }

      /// workspace_fts virtual table (FTS5) must be present.
      #[tokio::test]
      async fn test_fts5_virtual_table_created() {
          let db = Db::open("sqlite::memory:").await.unwrap();
          let row: (i64,) = sqlx::query_as(
              "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='workspace_fts'"
          )
          .fetch_one(&db.pool)
          .await
          .unwrap();
          assert_eq!(row.0, 1, "workspace_fts FTS5 virtual table should exist");
      }

      /// workspace_text_assets UNIQUE constraint must prevent duplicate (document_id, role).
      #[tokio::test]
      async fn test_asset_unique_constraint() {
          let db = Db::open("sqlite::memory:").await.unwrap();
          let now = 1_700_000_000_000_i64;

          // Insert a document to satisfy FK
          sqlx::query(
              "INSERT INTO workspace_documents (id, title, source_type, created_at, updated_at)
               VALUES ('doc1', 'Test', 'manual', ?, ?)"
          )
          .bind(now)
          .bind(now)
          .execute(&db.pool)
          .await
          .unwrap();

          // First insert: should succeed
          sqlx::query(
              "INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
               VALUES ('a1', 'doc1', 'transcript', 'hello', ?, ?)"
          )
          .bind(now)
          .bind(now)
          .execute(&db.pool)
          .await
          .expect("first insert should succeed");

          // Second insert with same (document_id, role): should fail
          let result = sqlx::query(
              "INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
               VALUES ('a2', 'doc1', 'transcript', 'world', ?, ?)"
          )
          .bind(now)
          .bind(now)
          .execute(&db.pool)
          .await;
          assert!(result.is_err(), "duplicate (document_id, role) should violate UNIQUE constraint");
      }

      /// Trigger must sync content_text on workspace_documents after asset insert.
      #[tokio::test]
      async fn test_sync_trigger_on_asset_insert() {
          let db = Db::open("sqlite::memory:").await.unwrap();
          let now = 1_700_000_000_000_i64;

          sqlx::query(
              "INSERT INTO workspace_documents (id, title, source_type, created_at, updated_at)
               VALUES ('doc2', 'TriggerTest', 'manual', ?, ?)"
          )
          .bind(now).bind(now).execute(&db.pool).await.unwrap();

          sqlx::query(
              "INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
               VALUES ('a3', 'doc2', 'transcript', 'trigger content', ?, ?)"
          )
          .bind(now).bind(now).execute(&db.pool).await.unwrap();

          let row: (Option<String>,) = sqlx::query_as(
              "SELECT content_text FROM workspace_documents WHERE id = 'doc2'"
          )
          .fetch_one(&db.pool)
          .await
          .unwrap();

          assert_eq!(
              row.0.as_deref(),
              Some("trigger content"),
              "trigger should sync content_text after asset insert"
          );
      }

      /// WAL mode must be active after pool initialization.
      #[tokio::test]
      async fn test_wal_mode_enabled() {
          let db = Db::open("sqlite::memory:").await.unwrap();
          // In-memory SQLite does not support WAL; this test verifies the PRAGMA
          // executes without error (WAL silently falls back to "memory" journal mode).
          let row: (String,) = sqlx::query_as("PRAGMA journal_mode")
              .fetch_one(&db.pool)
              .await
              .unwrap();
          // Acceptable values: "wal" (file-based) or "memory" (in-memory db fallback)
          assert!(
              row.0 == "wal" || row.0 == "memory",
              "unexpected journal_mode: {}",
              row.0
          );
      }
  }
  ```

- [ ] **Step 2: Implement `Db` struct and `open()`**

  Write the full implementation in `src-tauri/src/storage/db.rs`:

  ```rust
  use sqlx::{sqlite::{SqliteConnectOptions, SqlitePoolOptions}, SqlitePool};
  use std::str::FromStr;
  use crate::error::AppError;

  /// Thin wrapper around an `SqlitePool` with migrations applied at open time.
  pub struct Db {
      pub pool: SqlitePool,
  }

  impl Db {
      /// Open (or create) an SQLite database at `url`, enable WAL mode,
      /// and run all pending sqlx migrations.
      ///
      /// `url` examples:
      ///   - `"sqlite::memory:"` — in-memory (tests)
      ///   - `"sqlite:///path/to/echonote.db?mode=rwc"` — file-based
      pub async fn open(url: &str) -> Result<Self, AppError> {
          let opts = SqliteConnectOptions::from_str(url)
              .map_err(|e| AppError::Storage(e.to_string()))?
              .create_if_missing(true)
              .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal)
              .foreign_keys(true);

          let pool = SqlitePoolOptions::new()
              .max_connections(8)
              .connect_with(opts)
              .await
              .map_err(|e| AppError::Storage(format!("failed to connect: {e}")))?;

          // Run all pending migrations from src/storage/migrations/
          sqlx::migrate!("src/storage/migrations")
              .run(&pool)
              .await
              .map_err(|e| AppError::Storage(format!("migration failed: {e}")))?;

          Ok(Self { pool })
      }
  }

  // --- tests (see Step 1 above) ---
  ```

- [ ] **Step 3: Expose the module**

  Create `src-tauri/src/storage/mod.rs`:
  ```rust
  pub mod db;
  pub use db::Db;
  ```

  Add `pub mod storage;` to `src-tauri/src/lib.rs`.

- [ ] **Step 4: Run tests**

  ```bash
  cd src-tauri && cargo test storage::db::tests -- --nocapture
  ```

  All six tests must pass.

- [ ] **Commit:** `feat(m2): implement Db connection pool with WAL mode and auto-migrations`

---

### Task 5: Config Schema (`config/schema.rs`)

**Files:**
- Create: `src-tauri/src/config/mod.rs`
- Create: `src-tauri/src/config/schema.rs`
- Modify: `src-tauri/src/lib.rs` (add `pub mod config;`)

- [ ] **Step 1: Write tests first (TDD)**

  Add a `#[cfg(test)]` block at the bottom of `src-tauri/src/config/schema.rs` before implementing anything:

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;

      /// Default AppConfig must serialize and round-trip through JSON correctly.
      #[test]
      fn test_app_config_default_serialization() {
          let cfg = AppConfig::default();
          let json = serde_json::to_string(&cfg).expect("should serialize");
          let restored: AppConfig = serde_json::from_str(&json).expect("should deserialize");
          assert_eq!(cfg.locale, restored.locale);
          assert_eq!(cfg.active_theme, restored.active_theme);
          assert_eq!(cfg.vad_threshold, restored.vad_threshold);
      }

      /// Default locale must be "zh_CN".
      #[test]
      fn test_default_locale_is_zh_cn() {
          let cfg = AppConfig::default();
          assert_eq!(cfg.locale, "zh_CN");
      }

      /// Default active_theme must be "tokyo-night".
      #[test]
      fn test_default_theme() {
          let cfg = AppConfig::default();
          assert_eq!(cfg.active_theme, "tokyo-night");
      }

      /// Default vad_threshold must be 0.02.
      #[test]
      fn test_default_vad_threshold() {
          let cfg = AppConfig::default();
          assert!((cfg.vad_threshold - 0.02).abs() < f32::EPSILON);
      }

      /// PartialAppConfig with only `locale` set must not affect other fields.
      #[test]
      fn test_partial_config_apply_locale_only() {
          let mut cfg = AppConfig::default();
          let partial = PartialAppConfig {
              locale: Some("en_US".to_string()),
              ..Default::default()
          };
          apply_partial(&mut cfg, partial);
          assert_eq!(cfg.locale, "en_US");
          // Other fields remain at default
          assert_eq!(cfg.active_theme, "tokyo-night");
          assert!((cfg.vad_threshold - 0.02).abs() < f32::EPSILON);
      }

      /// PartialAppConfig with `default_language = Some(None)` must clear the field.
      #[test]
      fn test_partial_config_clear_default_language() {
          let mut cfg = AppConfig {
              default_language: Some("zh".to_string()),
              ..Default::default()
          };
          let partial = PartialAppConfig {
              default_language: Some(None),
              ..Default::default()
          };
          apply_partial(&mut cfg, partial);
          assert!(cfg.default_language.is_none());
      }

      /// PartialAppConfig with None fields must leave the config unchanged.
      #[test]
      fn test_partial_config_empty_is_noop() {
          let cfg_before = AppConfig::default();
          let mut cfg = cfg_before.clone();
          apply_partial(&mut cfg, PartialAppConfig::default());
          assert_eq!(
              serde_json::to_string(&cfg).unwrap(),
              serde_json::to_string(&cfg_before).unwrap()
          );
      }

      /// PartialAppConfig must skip None fields during JSON serialization.
      #[test]
      fn test_partial_config_serialization_skips_none() {
          let partial = PartialAppConfig {
              locale: Some("fr_FR".to_string()),
              ..Default::default()
          };
          let json = serde_json::to_string(&partial).unwrap();
          assert!(json.contains("\"locale\""), "locale should be present");
          assert!(!json.contains("\"active_theme\""), "None fields should be absent");
      }
  }
  ```

- [ ] **Step 2: Implement `AppConfig`, `PartialAppConfig`, and `apply_partial`**

  Write the full schema in `src-tauri/src/config/schema.rs`:

  ```rust
  use serde::{Deserialize, Serialize};
  use specta::Type;

  /// Full application configuration. Stored as a single JSON blob
  /// in `app_settings` under the key `"app_config"`.
  #[derive(Serialize, Deserialize, Clone, Type)]
  #[serde(default)]
  pub struct AppConfig {
      /// UI locale. Default: "zh_CN"
      pub locale: String,

      /// Active theme id. Default: "tokyo-night"
      pub active_theme: String,

      /// Active whisper model variant id. Default: "whisper/base"
      pub active_whisper_model: String,

      /// Active LLM model variant id. Default: "llm/qwen2.5-3b-q4"
      pub active_llm_model: String,

      /// LLM context window size in tokens. Default: 4096
      pub llm_context_size: u32,

      /// Path to the vault directory (workspace documents). Default: {APP_DATA}/vault
      pub vault_path: String,

      /// Path to the recordings directory (audio WAV files). Default: {APP_DATA}/recordings
      pub recordings_path: String,

      /// Default recording mode. Values: "record_only" | "transcribe_only" | "transcribe_and_translate"
      /// Default: "transcribe_only"
      pub default_recording_mode: String,

      /// Default transcription language. None = auto-detect.
      pub default_language: Option<String>,

      /// Default translation target language. Default: "en"
      pub default_target_language: String,

      /// VAD energy threshold (0.0–1.0). Default: 0.02
      pub vad_threshold: f32,

      /// Audio chunk duration sent to whisper (ms). Default: 500
      pub audio_chunk_ms: u32,

      /// Automatically trigger AI processing after recording stops. Default: false
      pub auto_llm_on_stop: bool,

      /// Default LLM task type. Values: "summary" | "meeting_brief". Default: "summary"
      pub default_llm_task: String,
  }

  impl Default for AppConfig {
      fn default() -> Self {
          Self {
              locale:                  "zh_CN".to_string(),
              active_theme:            "tokyo-night".to_string(),
              active_whisper_model:    "whisper/base".to_string(),
              active_llm_model:        "llm/qwen2.5-3b-q4".to_string(),
              llm_context_size:        4096,
              vault_path:              String::new(), // populated at runtime from APP_DATA
              recordings_path:         String::new(), // populated at runtime from APP_DATA
              default_recording_mode:  "transcribe_only".to_string(),
              default_language:        None,
              default_target_language: "en".to_string(),
              vad_threshold:           0.02,
              audio_chunk_ms:          500,
              auto_llm_on_stop:        false,
              default_llm_task:        "summary".to_string(),
          }
      }
  }

  /// Partial update payload. Every field is `Option<T>`.
  /// `None` means "do not update this field".
  /// For `default_language`, `Some(None)` clears the value; `Some(Some("zh"))` sets it.
  ///
  /// `skip_serializing_if = "Option::is_none"` ensures that undefined fields
  /// from the frontend are absent from the serialized JSON.
  #[derive(Serialize, Deserialize, Default, Clone, Type)]
  pub struct PartialAppConfig {
      #[serde(skip_serializing_if = "Option::is_none")]
      pub locale: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub active_theme: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub active_whisper_model: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub active_llm_model: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub llm_context_size: Option<u32>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub vault_path: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub recordings_path: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub default_recording_mode: Option<String>,

      /// `Some(None)` clears the language (auto-detect); `Some(Some("zh"))` sets it.
      #[serde(skip_serializing_if = "Option::is_none")]
      pub default_language: Option<Option<String>>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub default_target_language: Option<String>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub vad_threshold: Option<f32>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub audio_chunk_ms: Option<u32>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub auto_llm_on_stop: Option<bool>,

      #[serde(skip_serializing_if = "Option::is_none")]
      pub default_llm_task: Option<String>,
  }

  /// Apply a `PartialAppConfig` onto a mutable `AppConfig`.
  /// Only fields with `Some(...)` values are updated.
  pub fn apply_partial(config: &mut AppConfig, partial: PartialAppConfig) {
      if let Some(v) = partial.locale                  { config.locale                  = v; }
      if let Some(v) = partial.active_theme            { config.active_theme            = v; }
      if let Some(v) = partial.active_whisper_model    { config.active_whisper_model    = v; }
      if let Some(v) = partial.active_llm_model        { config.active_llm_model        = v; }
      if let Some(v) = partial.llm_context_size        { config.llm_context_size        = v; }
      if let Some(v) = partial.vault_path              { config.vault_path              = v; }
      if let Some(v) = partial.recordings_path         { config.recordings_path         = v; }
      if let Some(v) = partial.default_recording_mode  { config.default_recording_mode  = v; }
      if let Some(v) = partial.default_language        { config.default_language        = v; }
      if let Some(v) = partial.default_target_language { config.default_target_language = v; }
      if let Some(v) = partial.vad_threshold           { config.vad_threshold           = v; }
      if let Some(v) = partial.audio_chunk_ms          { config.audio_chunk_ms          = v; }
      if let Some(v) = partial.auto_llm_on_stop        { config.auto_llm_on_stop        = v; }
      if let Some(v) = partial.default_llm_task        { config.default_llm_task        = v; }
  }

  // --- tests (see Step 1 above) ---
  ```

- [ ] **Step 3: Create `config/mod.rs`**

  ```rust
  pub mod schema;
  pub use schema::{AppConfig, PartialAppConfig, apply_partial};
  ```

  Add `pub mod config;` to `src-tauri/src/lib.rs`.

- [ ] **Step 4: Run tests**

  ```bash
  cd src-tauri && cargo test config::schema::tests -- --nocapture
  ```

  All seven tests must pass.

- [ ] **Commit:** `feat(m2): add AppConfig, PartialAppConfig, apply_partial with full serde support`

---

### Task 6: Settings Tauri Commands (`commands/settings.rs`)

**Files:**
- Create: `src-tauri/src/commands/settings.rs`
- Modify: `src-tauri/src/commands/mod.rs` (add `pub mod settings;`)
- Modify: `src-tauri/src/state.rs` (add `config` and `db` fields to `AppState`)
- Modify: `src-tauri/src/lib.rs` (register the three commands)

- [ ] **Step 1: Update `AppState` to hold `db` and `config`**

  Ensure `src-tauri/src/state.rs` includes at minimum:

  ```rust
  use std::sync::Arc;
  use tokio::sync::RwLock;
  use crate::{config::AppConfig, storage::Db};

  pub struct AppState {
      pub db: Arc<Db>,
      pub config: Arc<RwLock<AppConfig>>,
      // Other fields will be added in later milestones (worker channels, engines, etc.)
  }
  ```

- [ ] **Step 2: Write tests first (TDD)**

  Add `#[cfg(test)]` at the bottom of `src-tauri/src/commands/settings.rs`:

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use crate::{config::{AppConfig, apply_partial}, storage::Db};
      use std::sync::Arc;
      use tokio::sync::RwLock;

      async fn make_state() -> AppState {
          let db = Arc::new(Db::open("sqlite::memory:").await.unwrap());
          let config = Arc::new(RwLock::new(AppConfig::default()));
          AppState { db, config }
      }

      /// get_config_inner must return the current AppConfig.
      #[tokio::test]
      async fn test_get_config_returns_default() {
          let state = make_state().await;
          let cfg = get_config_inner(&state).await.unwrap();
          assert_eq!(cfg.locale, "zh_CN");
          assert_eq!(cfg.active_theme, "tokyo-night");
      }

      /// update_config_inner must persist a locale change to the DB and update in-memory state.
      #[tokio::test]
      async fn test_update_config_persists_locale() {
          let state = make_state().await;
          let partial = crate::config::PartialAppConfig {
              locale: Some("en_US".to_string()),
              ..Default::default()
          };
          update_config_inner(&state, partial).await.unwrap();

          // In-memory state should reflect the change
          let cfg = state.config.read().await;
          assert_eq!(cfg.locale, "en_US");

          // DB should have the updated value
          let row: (String, i64) = sqlx::query_as(
              "SELECT value, updated_at FROM app_settings WHERE key = 'app_config'"
          )
          .fetch_one(&state.db.pool)
          .await
          .unwrap();
          let saved: AppConfig = serde_json::from_str(&row.0).unwrap();
          assert_eq!(saved.locale, "en_US");
      }

      /// reset_config_inner must restore defaults and persist to DB.
      #[tokio::test]
      async fn test_reset_config_restores_defaults() {
          let state = make_state().await;

          // First set a non-default value
          let partial = crate::config::PartialAppConfig {
              locale: Some("fr_FR".to_string()),
              ..Default::default()
          };
          update_config_inner(&state, partial).await.unwrap();

          // Now reset
          let cfg = reset_config_inner(&state).await.unwrap();
          assert_eq!(cfg.locale, "zh_CN", "reset should restore default locale");

          // In-memory state must be restored
          let in_mem = state.config.read().await;
          assert_eq!(in_mem.locale, "zh_CN");
      }

      /// Two successive update_config calls must accumulate changes correctly.
      #[tokio::test]
      async fn test_update_config_accumulates_changes() {
          let state = make_state().await;

          let p1 = crate::config::PartialAppConfig {
              locale: Some("en_US".to_string()),
              ..Default::default()
          };
          update_config_inner(&state, p1).await.unwrap();

          let p2 = crate::config::PartialAppConfig {
              active_theme: Some("tokyo-night-storm".to_string()),
              ..Default::default()
          };
          update_config_inner(&state, p2).await.unwrap();

          let cfg = get_config_inner(&state).await.unwrap();
          assert_eq!(cfg.locale, "en_US");
          assert_eq!(cfg.active_theme, "tokyo-night-storm");
      }
  }
  ```

- [ ] **Step 3: Implement the three commands**

  Write `src-tauri/src/commands/settings.rs`:

  ```rust
  use tauri::State;
  use crate::{
      config::{AppConfig, PartialAppConfig, apply_partial},
      error::AppError,
      state::AppState,
  };

  const CONFIG_KEY: &str = "app_config";

  // ──────────────────────────────────────────────────────────────────────────────
  // Internal helpers (used both by commands and tests)
  // ──────────────────────────────────────────────────────────────────────────────

  pub(crate) async fn get_config_inner(state: &AppState) -> Result<AppConfig, AppError> {
      let cfg = state.config.read().await;
      Ok(cfg.clone())
  }

  pub(crate) async fn update_config_inner(
      state: &AppState,
      partial: PartialAppConfig,
  ) -> Result<(), AppError> {
      // 1. Apply partial update to in-memory config
      let updated = {
          let mut cfg = state.config.write().await;
          apply_partial(&mut cfg, partial);
          cfg.clone()
      };

      // 2. Persist serialized config to app_settings table
      let json = serde_json::to_string(&updated)
          .map_err(|e| AppError::Storage(format!("serialize config: {e}")))?;
      let now = chrono_or_system_ms();

      sqlx::query(
          "INSERT INTO app_settings (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
      )
      .bind(CONFIG_KEY)
      .bind(&json)
      .bind(now)
      .execute(&state.db.pool)
      .await?;

      Ok(())
  }

  pub(crate) async fn reset_config_inner(state: &AppState) -> Result<AppConfig, AppError> {
      let default_cfg = AppConfig::default();

      // Overwrite in-memory state
      {
          let mut cfg = state.config.write().await;
          *cfg = default_cfg.clone();
      }

      // Persist reset config
      let json = serde_json::to_string(&default_cfg)
          .map_err(|e| AppError::Storage(format!("serialize default config: {e}")))?;
      let now = chrono_or_system_ms();

      sqlx::query(
          "INSERT INTO app_settings (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
      )
      .bind(CONFIG_KEY)
      .bind(&json)
      .bind(now)
      .execute(&state.db.pool)
      .await?;

      Ok(default_cfg)
  }

  /// Load AppConfig from `app_settings` DB on startup.
  /// Returns `AppConfig::default()` if no row exists yet.
  pub async fn load_config_from_db(state: &AppState) -> Result<AppConfig, AppError> {
      let row: Option<(String,)> = sqlx::query_as(
          "SELECT value FROM app_settings WHERE key = ?"
      )
      .bind(CONFIG_KEY)
      .fetch_optional(&state.db.pool)
      .await?;

      match row {
          None => Ok(AppConfig::default()),
          Some((json,)) => {
              serde_json::from_str(&json)
                  .map_err(|e| AppError::Storage(format!("parse config: {e}")))
          }
      }
  }

  // ──────────────────────────────────────────────────────────────────────────────
  // Tauri commands (thin wrappers around inner helpers)
  // ──────────────────────────────────────────────────────────────────────────────

  #[tauri::command]
  #[specta::specta]
  pub async fn get_config(state: State<'_, AppState>) -> Result<AppConfig, AppError> {
      get_config_inner(&state).await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn update_config(
      state: State<'_, AppState>,
      partial: PartialAppConfig,
  ) -> Result<(), AppError> {
      update_config_inner(&state, partial).await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn reset_config(state: State<'_, AppState>) -> Result<AppConfig, AppError> {
      reset_config_inner(&state).await
  }

  // ──────────────────────────────────────────────────────────────────────────────
  // Helper: current Unix timestamp in milliseconds (no external crate dependency)
  // ──────────────────────────────────────────────────────────────────────────────
  fn chrono_or_system_ms() -> i64 {
      std::time::SystemTime::now()
          .duration_since(std::time::UNIX_EPOCH)
          .unwrap_or_default()
          .as_millis() as i64
  }

  // --- tests (see Step 2 above) ---
  ```

- [ ] **Step 4: Register commands in `lib.rs`**

  In the Tauri builder in `src-tauri/src/lib.rs`, add the three commands to `.invoke_handler(...)`:

  ```rust
  .invoke_handler(tauri::generate_handler![
      commands::settings::get_config,
      commands::settings::update_config,
      commands::settings::reset_config,
  ])
  ```

- [ ] **Step 5: Run tests**

  ```bash
  cd src-tauri && cargo test commands::settings::tests -- --nocapture
  ```

  All four tests must pass.

- [ ] **Commit:** `feat(m2): implement get_config, update_config, reset_config Tauri commands`

---

### Task 7: `AppState` Initialization in `lib.rs`

**Files:**
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Wire up DB + config initialization in `run()`**

  The `run()` function must perform startup steps 1–3 from the spec before building the Tauri app:

  ```rust
  pub fn run() {
      tauri::Builder::default()
          .setup(|app| {
              let app_data_dir = app.path().app_data_dir()
                  .expect("APP_DATA dir not resolvable");
              std::fs::create_dir_all(&app_data_dir)?;

              let db_path = app_data_dir.join("echonote.db");
              let db_url = format!("sqlite://{}?mode=rwc", db_path.display());

              // Step 1+2: open DB and run migrations (blocking inside setup)
              let db = tauri::async_runtime::block_on(
                  crate::storage::Db::open(&db_url)
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
          .invoke_handler(tauri::generate_handler![
              crate::commands::settings::get_config,
              crate::commands::settings::update_config,
              crate::commands::settings::reset_config,
          ])
          .run(tauri::generate_context!())
          .expect("error while running Tauri application");
  }
  ```

- [ ] **Commit:** `feat(m2): wire AppState initialization (db + config) in lib.rs setup`

---

### Task 8: Zustand Settings Store (`src/store/settings.ts`)

**Files:**
- Create: `src/store/settings.ts`

- [ ] **Step 1: Write the store**

  Create `src/store/settings.ts`:

  ```typescript
  import { create } from 'zustand'
  import { invoke } from '@tauri-apps/api/core'

  // Mirror of Rust AppConfig — keep in sync with config/schema.rs
  // In the final project this will be imported from src/lib/bindings.ts (tauri-specta generated).
  export interface AppConfig {
    locale: string
    active_theme: string
    active_whisper_model: string
    active_llm_model: string
    llm_context_size: number
    vault_path: string
    recordings_path: string
    default_recording_mode: string
    default_language: string | null
    default_target_language: string
    vad_threshold: number
    audio_chunk_ms: number
    auto_llm_on_stop: boolean
    default_llm_task: string
  }

  // PartialAppConfig: every field is optional (undefined = do not update)
  export type PartialAppConfig = {
    [K in keyof AppConfig]?: AppConfig[K] | undefined
  }

  interface SettingsStore {
    config: AppConfig | null
    isLoading: boolean
    error: string | null
    translations: Record<string, unknown>

    // Actions
    loadConfig: () => Promise<void>
    updateConfig: (partial: PartialAppConfig) => Promise<void>
    resetConfig: () => Promise<void>
  }

  const DEFAULT_CONFIG: AppConfig = {
    locale: 'zh_CN',
    active_theme: 'tokyo-night',
    active_whisper_model: 'whisper/base',
    active_llm_model: 'llm/qwen2.5-3b-q4',
    llm_context_size: 4096,
    vault_path: '',
    recordings_path: '',
    default_recording_mode: 'transcribe_only',
    default_language: null,
    default_target_language: 'en',
    vad_threshold: 0.02,
    audio_chunk_ms: 500,
    auto_llm_on_stop: false,
    default_llm_task: 'summary',
  }

  export const useSettingsStore = create<SettingsStore>((set, get) => ({
    config: null,
    isLoading: false,
    error: null,
    translations: {},

    loadConfig: async () => {
      set({ isLoading: true, error: null })
      try {
        const config = await invoke<AppConfig>('get_config')
        set({ config, isLoading: false })
      } catch (e) {
        set({ error: String(e), isLoading: false, config: DEFAULT_CONFIG })
      }
    },

    updateConfig: async (partial: PartialAppConfig) => {
      set({ isLoading: true, error: null })
      try {
        await invoke<void>('update_config', { partial })
        // Optimistically update local state
        set((state) => ({
          config: state.config ? { ...state.config, ...filterUndefined(partial) } : state.config,
          isLoading: false,
        }))
      } catch (e) {
        set({ error: String(e), isLoading: false })
        throw e
      }
    },

    resetConfig: async () => {
      set({ isLoading: true, error: null })
      try {
        const config = await invoke<AppConfig>('reset_config')
        set({ config, isLoading: false })
      } catch (e) {
        set({ error: String(e), isLoading: false })
        throw e
      }
    },
  }))

  /** Remove keys with `undefined` values before sending to Tauri. */
  function filterUndefined<T extends object>(obj: T): Partial<T> {
    return Object.fromEntries(
      Object.entries(obj).filter(([, v]) => v !== undefined)
    ) as Partial<T>
  }
  ```

- [ ] **Commit:** `feat(m2): add useSettingsStore Zustand store with get/update/reset config`

---

### Task 9: Settings Route (`/settings`)

**Files:**
- Create: `src/components/settings/SettingsPanel.tsx`
- Create: `src/components/settings/SettingsMain.tsx`
- Modify: `src/router.tsx` (add `/settings` route)

- [ ] **Step 1: Create `SettingsPanel.tsx` (SecondPanel content)**

  Create `src/components/settings/SettingsPanel.tsx`:

  ```tsx
  import { NavLink } from '@tanstack/react-router'

  export function SettingsPanel() {
    const navItems = [
      { to: '/settings',        label: 'General' },
      { to: '/settings/models', label: 'Models' },
      { to: '/settings/theme',  label: 'Theme' },
    ]

    return (
      <nav className="flex flex-col gap-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [
                'rounded px-3 py-1.5 text-sm transition-colors',
                isActive
                  ? 'bg-accent text-white'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
              ].join(' ')
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    )
  }
  ```

- [ ] **Step 2: Create `SettingsMain.tsx` (general settings form)**

  Create `src/components/settings/SettingsMain.tsx`:

  ```tsx
  import { useEffect } from 'react'
  import { useSettingsStore } from '../../store/settings'

  const LOCALES = [
    { value: 'zh_CN', label: '中文（简体）' },
    { value: 'en_US', label: 'English (US)' },
    { value: 'fr_FR', label: 'Français' },
  ]

  const RECORDING_MODES = [
    { value: 'record_only',             label: 'Record Only' },
    { value: 'transcribe_only',         label: 'Transcribe' },
    { value: 'transcribe_and_translate', label: 'Transcribe & Translate' },
  ]

  const LLM_TASKS = [
    { value: 'summary',       label: 'Summary' },
    { value: 'meeting_brief', label: 'Meeting Brief' },
  ]

  export function SettingsMain() {
    const { config, isLoading, error, loadConfig, updateConfig, resetConfig } =
      useSettingsStore()

    useEffect(() => {
      if (!config) loadConfig()
    }, [config, loadConfig])

    if (isLoading && !config) {
      return (
        <div className="flex h-full items-center justify-center text-text-muted text-sm">
          Loading settings…
        </div>
      )
    }

    if (!config) return null

    return (
      <div className="mx-auto max-w-2xl space-y-8 p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-text-primary">General Settings</h1>
          <button
            onClick={() => resetConfig()}
            className="rounded border border-border px-3 py-1.5 text-sm text-text-secondary
                       hover:border-status-error hover:text-status-error transition-colors"
          >
            Reset to Defaults
          </button>
        </div>

        {error && (
          <p className="rounded bg-status-error/10 px-3 py-2 text-sm text-status-error">
            {error}
          </p>
        )}

        {/* ── Language & Display ── */}
        <section className="space-y-4">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
            Language &amp; Display
          </h2>

          <FormRow label="Interface Language">
            <Select
              value={config.locale}
              options={LOCALES}
              onChange={(v) => updateConfig({ locale: v })}
            />
          </FormRow>
        </section>

        {/* ── Recording ── */}
        <section className="space-y-4">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
            Recording
          </h2>

          <FormRow label="Default Recording Mode">
            <Select
              value={config.default_recording_mode}
              options={RECORDING_MODES}
              onChange={(v) => updateConfig({ default_recording_mode: v })}
            />
          </FormRow>

          <FormRow label="Default Language (transcription)">
            <input
              type="text"
              placeholder="auto"
              value={config.default_language ?? ''}
              onChange={(e) =>
                updateConfig({
                  default_language: e.target.value === '' ? null : e.target.value,
                })
              }
              className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                         text-sm text-text-primary focus:outline-none focus:border-accent"
            />
          </FormRow>

          <FormRow label="VAD Threshold">
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={config.vad_threshold}
                onChange={(e) =>
                  updateConfig({ vad_threshold: parseFloat(e.target.value) })
                }
                className="flex-1"
              />
              <span className="w-12 text-right text-sm text-text-secondary">
                {config.vad_threshold.toFixed(2)}
              </span>
            </div>
          </FormRow>

          <FormRow label="Auto AI processing after stop">
            <input
              type="checkbox"
              checked={config.auto_llm_on_stop}
              onChange={(e) => updateConfig({ auto_llm_on_stop: e.target.checked })}
              className="h-4 w-4 rounded border-border accent-accent"
            />
          </FormRow>
        </section>

        {/* ── AI ── */}
        <section className="space-y-4">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
            AI
          </h2>

          <FormRow label="Default AI Task">
            <Select
              value={config.default_llm_task}
              options={LLM_TASKS}
              onChange={(v) => updateConfig({ default_llm_task: v })}
            />
          </FormRow>

          <FormRow label="LLM Context Size (tokens)">
            <input
              type="number"
              min={512}
              max={32768}
              step={512}
              value={config.llm_context_size}
              onChange={(e) =>
                updateConfig({ llm_context_size: parseInt(e.target.value, 10) })
              }
              className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                         text-sm text-text-primary focus:outline-none focus:border-accent"
            />
          </FormRow>
        </section>

        {/* ── Storage ── */}
        <section className="space-y-4">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
            Storage
          </h2>

          <FormRow label="Vault Path">
            <input
              type="text"
              value={config.vault_path}
              onChange={(e) => updateConfig({ vault_path: e.target.value })}
              className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                         text-sm text-text-primary focus:outline-none focus:border-accent"
            />
          </FormRow>

          <FormRow label="Recordings Path">
            <input
              type="text"
              value={config.recordings_path}
              onChange={(e) => updateConfig({ recordings_path: e.target.value })}
              className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                         text-sm text-text-primary focus:outline-none focus:border-accent"
            />
          </FormRow>
        </section>
      </div>
    )
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function FormRow({
    label,
    children,
  }: {
    label: string
    children: React.ReactNode
  }) {
    return (
      <div className="flex items-center gap-4">
        <label className="w-52 shrink-0 text-sm text-text-secondary">{label}</label>
        <div className="flex-1">{children}</div>
      </div>
    )
  }

  function Select({
    value,
    options,
    onChange,
  }: {
    value: string
    options: { value: string; label: string }[]
    onChange: (v: string) => void
  }) {
    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                   text-sm text-text-primary focus:outline-none focus:border-accent"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    )
  }
  ```

- [ ] **Step 3: Register the `/settings` route in `router.tsx`**

  In `src/router.tsx`, add the settings route. The exact form depends on the TanStack Router setup already in place from M1, but the essential addition is:

  ```tsx
  import { SettingsPanel } from './components/settings/SettingsPanel'
  import { SettingsMain }  from './components/settings/SettingsMain'

  // Inside the route tree definition add:
  const settingsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/settings',
    component: () => (
      <Shell
        panel={<SettingsPanel />}
        main={<SettingsMain />}
      />
    ),
  })
  ```

  Ensure `/settings` is included in the `routeTree` passed to `createRouter(...)`.

- [ ] **Commit:** `feat(m2): add SettingsPanel, SettingsMain components and /settings route`

---

### Task 10: Integration Smoke Test

**Files:**
- Create: `src-tauri/src/tests/integration_settings.rs` (or inline in `commands/settings.rs`)

- [ ] **Step 1: Write an end-to-end DB + settings round-trip test**

  Add the following test to `src-tauri/src/commands/settings.rs` (within the existing `#[cfg(test)]` block):

  ```rust
  /// Full round-trip: open DB → load config (empty → default) → update → reload → verify.
  #[tokio::test]
  async fn test_full_round_trip() {
      let state = make_state().await;

      // 1. First load should return defaults (no row in DB yet)
      let loaded = load_config_from_db(&state).await.unwrap();
      assert_eq!(loaded.locale, "zh_CN");

      // 2. Update locale
      let partial = crate::config::PartialAppConfig {
          locale: Some("fr_FR".to_string()),
          vad_threshold: Some(0.05),
          ..Default::default()
      };
      update_config_inner(&state, partial).await.unwrap();

      // 3. Re-load from DB should reflect changes
      let reloaded = load_config_from_db(&state).await.unwrap();
      assert_eq!(reloaded.locale, "fr_FR");
      assert!((reloaded.vad_threshold - 0.05).abs() < 1e-5);

      // 4. Reset should restore defaults
      reset_config_inner(&state).await.unwrap();
      let after_reset = load_config_from_db(&state).await.unwrap();
      assert_eq!(after_reset.locale, "zh_CN");
  }
  ```

- [ ] **Step 2: Run the full test suite**

  ```bash
  cd src-tauri && cargo test -- --nocapture
  ```

  All tests must pass with zero compile warnings.

- [ ] **Commit:** `test(m2): add full round-trip integration test for settings persistence`

---

### Task 11: Final Verification Checklist

- [ ] `cargo build` in `src-tauri/` succeeds without warnings or errors
- [ ] `cargo test` in `src-tauri/` — all tests green
- [ ] `npm run tauri dev` starts the app, navigates to `/settings`, and the form renders
- [ ] Changing a setting (e.g., locale dropdown) invokes `update_config` without console errors
- [ ] "Reset to Defaults" button calls `reset_config` and restores form values
- [ ] DB file `echonote.db` in app data directory contains `app_settings`, `recordings`, `workspace_documents`, `workspace_text_assets`, `llm_tasks` tables (verify with `sqlite3 echonote.db .tables`)
- [ ] `PRAGMA journal_mode` returns `wal` on the file-based DB

- [ ] **Final commit:** `feat(m2): complete database layer and settings system milestone`
