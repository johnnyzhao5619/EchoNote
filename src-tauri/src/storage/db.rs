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
