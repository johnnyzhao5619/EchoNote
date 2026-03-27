#[cfg(test)]
mod tests {
    use super::*;
    use crate::error::AppError;
    use crate::timeline::{CreateEventRequest, NullableStringPatch, UpdateEventRequest};
    use sqlx::sqlite::SqlitePoolOptions;

    async fn make_pool() -> sqlx::SqlitePool {
        let pool = SqlitePoolOptions::new()
            .connect("sqlite::memory:")
            .await
            .unwrap();

        sqlx::query(
            r#"
            CREATE TABLE timeline_events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                start_at INTEGER NOT NULL,
                end_at INTEGER NOT NULL,
                description TEXT,
                tags TEXT,
                recording_id TEXT,
                document_id TEXT,
                created_at INTEGER NOT NULL
            )
            "#,
        )
        .execute(&pool)
        .await
        .unwrap();

        pool
    }

    #[tokio::test]
    async fn create_event_rejects_end_before_start() {
        let mgr = TimelineManager::new(make_pool().await);
        let err = mgr
            .create_event(CreateEventRequest {
                title: "Broken".into(),
                start_at: 2_000,
                end_at: 1_000,
                description: None,
                tags: None,
                recording_id: None,
                document_id: None,
            })
            .await
            .unwrap_err();

        assert!(matches!(err, AppError::Validation(_)));
    }

    #[tokio::test]
    async fn list_events_in_range_includes_overlapping_events() {
        let mgr = TimelineManager::new(make_pool().await);

        let overlapping = mgr
            .create_event(CreateEventRequest {
                title: "Overnight".into(),
                start_at: 1_000,
                end_at: 6_000,
                description: None,
                tags: Some(vec!["night".into()]),
                recording_id: None,
                document_id: None,
            })
            .await
            .unwrap();

        mgr.create_event(CreateEventRequest {
            title: "Outside".into(),
            start_at: 7_000,
            end_at: 8_000,
            description: None,
            tags: None,
            recording_id: None,
            document_id: None,
        })
        .await
        .unwrap();

        let results = mgr.list_events_in_range(4_000, 5_000).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].id, overlapping.id);
    }

    #[tokio::test]
    async fn search_is_case_insensitive_and_tags_round_trip() {
        let mgr = TimelineManager::new(make_pool().await);
        let event = mgr
            .create_event(CreateEventRequest {
                title: "Team STANDUP".into(),
                start_at: 10_000,
                end_at: 12_000,
                description: Some("Daily sync with engineering".into()),
                tags: Some(vec!["standup".into(), "internal".into()]),
                recording_id: None,
                document_id: None,
            })
            .await
            .unwrap();

        let results = mgr.search_events("engineering").await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].id, event.id);
        assert_eq!(results[0].tags, vec!["standup", "internal"]);
    }

    #[tokio::test]
    async fn update_event_can_clear_and_unlink_fields() {
        let mgr = TimelineManager::new(make_pool().await);
        let event = mgr
            .create_event(CreateEventRequest {
                title: "Sync".into(),
                start_at: 10_000,
                end_at: 12_000,
                description: Some("keep notes".into()),
                tags: Some(vec!["team".into()]),
                recording_id: Some("rec-1".into()),
                document_id: Some("doc-1".into()),
            })
            .await
            .unwrap();

        let updated = mgr
            .update_event(
                &event.id,
                UpdateEventRequest {
                    title: None,
                    start_at: None,
                    end_at: None,
                    description: NullableStringPatch::Clear,
                    tags: Some(vec![]),
                    recording_id: NullableStringPatch::Clear,
                    document_id: NullableStringPatch::Unchanged,
                },
            )
            .await
            .unwrap();

        assert_eq!(updated.description, None);
        assert_eq!(updated.tags, Vec::<String>::new());
        assert_eq!(updated.recording_id, None);
        assert_eq!(updated.document_id.as_deref(), Some("doc-1"));
    }
}

use sqlx::{Row, SqlitePool};
use uuid::Uuid;

use crate::error::AppError;

use super::{
    CreateEventRequest, NullableStringPatch, TimelineEvent, TimelineEventRow, UpdateEventRequest,
};

pub struct TimelineManager {
    pool: SqlitePool,
}

impl TimelineManager {
    pub fn new(pool: SqlitePool) -> Self {
        Self { pool }
    }

    fn validate_range(start_at: i64, end_at: i64) -> Result<(), AppError> {
        if end_at <= start_at {
            return Err(AppError::Validation(
                "timeline event end_at must be after start_at".into(),
            ));
        }

        Ok(())
    }

    fn tags_to_json(tags: &[String]) -> Result<String, AppError> {
        serde_json::to_string(tags)
            .map_err(|err| AppError::Storage(format!("serialize timeline tags: {err}")))
    }

    fn map_event_row(row: sqlx::sqlite::SqliteRow) -> Result<TimelineEventRow, AppError> {
        Ok(TimelineEventRow {
            id: row.try_get("id")?,
            title: row.try_get("title")?,
            start_at: row.try_get("start_at")?,
            end_at: row.try_get("end_at")?,
            description: row.try_get("description")?,
            tags_json: row.try_get("tags")?,
            recording_id: row.try_get("recording_id")?,
            document_id: row.try_get("document_id")?,
            created_at: row.try_get("created_at")?,
        })
    }

    async fn get_event_by_id(&self, id: &str) -> Result<TimelineEvent, AppError> {
        let row = sqlx::query(
            "SELECT id, title, start_at, end_at, description, tags, recording_id, document_id, created_at
             FROM timeline_events
             WHERE id = ?",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("timeline event {id}")))?;

        Ok(TimelineEvent::from(Self::map_event_row(row)?))
    }

    pub async fn create_event(&self, req: CreateEventRequest) -> Result<TimelineEvent, AppError> {
        Self::validate_range(req.start_at, req.end_at)?;

        let id = Uuid::new_v4().to_string();
        let created_at = chrono::Utc::now().timestamp_millis();
        let tags_json = Self::tags_to_json(req.tags.as_deref().unwrap_or(&[]))?;

        sqlx::query(
            "INSERT INTO timeline_events (id, title, start_at, end_at, description, tags, recording_id, document_id, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(&id)
        .bind(&req.title)
        .bind(req.start_at)
        .bind(req.end_at)
        .bind(&req.description)
        .bind(&tags_json)
        .bind(&req.recording_id)
        .bind(&req.document_id)
        .bind(created_at)
        .execute(&self.pool)
        .await?;

        self.get_event_by_id(&id).await
    }

    pub async fn update_event(
        &self,
        id: &str,
        req: UpdateEventRequest,
    ) -> Result<TimelineEvent, AppError> {
        let current = self.get_event_by_id(id).await?;
        let TimelineEvent {
            title: current_title,
            start_at: current_start_at,
            end_at: current_end_at,
            description: current_description,
            tags: current_tags,
            recording_id: current_recording_id,
            document_id: current_document_id,
            ..
        } = current;

        let title = req.title.unwrap_or(current_title);
        let start_at = req.start_at.unwrap_or(current_start_at);
        let end_at = req.end_at.unwrap_or(current_end_at);
        Self::validate_range(start_at, end_at)?;

        let description = match req.description {
            NullableStringPatch::Unchanged => current_description,
            NullableStringPatch::Set(value) => Some(value),
            NullableStringPatch::Clear => None,
        };
        let tags = req.tags.unwrap_or(current_tags);
        let recording_id = match req.recording_id {
            NullableStringPatch::Unchanged => current_recording_id,
            NullableStringPatch::Set(value) => Some(value),
            NullableStringPatch::Clear => None,
        };
        let document_id = match req.document_id {
            NullableStringPatch::Unchanged => current_document_id,
            NullableStringPatch::Set(value) => Some(value),
            NullableStringPatch::Clear => None,
        };
        let tags_json = Self::tags_to_json(&tags)?;

        let affected = sqlx::query(
            "UPDATE timeline_events
             SET title = ?, start_at = ?, end_at = ?, description = ?, tags = ?, recording_id = ?, document_id = ?
             WHERE id = ?",
        )
        .bind(&title)
        .bind(start_at)
        .bind(end_at)
        .bind(&description)
        .bind(&tags_json)
        .bind(&recording_id)
        .bind(&document_id)
        .bind(id)
        .execute(&self.pool)
        .await?
        .rows_affected();

        if affected == 0 {
            return Err(AppError::NotFound(format!("timeline event {id}")));
        }

        self.get_event_by_id(id).await
    }

    pub async fn delete_event(&self, id: &str) -> Result<(), AppError> {
        let affected = sqlx::query("DELETE FROM timeline_events WHERE id = ?")
            .bind(id)
            .execute(&self.pool)
            .await?
            .rows_affected();

        if affected == 0 {
            return Err(AppError::NotFound(format!("timeline event {id}")));
        }

        Ok(())
    }

    pub async fn list_events_in_range(
        &self,
        start_ms: i64,
        end_ms: i64,
    ) -> Result<Vec<TimelineEvent>, AppError> {
        let rows = sqlx::query(
            "SELECT id, title, start_at, end_at, description, tags, recording_id, document_id, created_at
             FROM timeline_events
             WHERE end_at >= ? AND start_at <= ?
             ORDER BY start_at ASC, created_at ASC",
        )
        .bind(start_ms)
        .bind(end_ms)
        .fetch_all(&self.pool)
        .await?;

        rows.into_iter()
            .map(Self::map_event_row)
            .map(|row| row.map(TimelineEvent::from))
            .collect()
    }

    pub async fn search_events(&self, query: &str) -> Result<Vec<TimelineEvent>, AppError> {
        let pattern = format!("%{}%", query.trim().to_lowercase());
        let rows = sqlx::query(
            "SELECT id, title, start_at, end_at, description, tags, recording_id, document_id, created_at
             FROM timeline_events
             WHERE LOWER(title) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?
             ORDER BY start_at DESC, created_at DESC",
        )
        .bind(&pattern)
        .bind(&pattern)
        .fetch_all(&self.pool)
        .await?;

        rows.into_iter()
            .map(Self::map_event_row)
            .map(|row| row.map(TimelineEvent::from))
            .collect()
    }

    pub async fn link_recording(&self, event_id: &str, recording_id: &str) -> Result<(), AppError> {
        let affected = sqlx::query("UPDATE timeline_events SET recording_id = ? WHERE id = ?")
            .bind(recording_id)
            .bind(event_id)
            .execute(&self.pool)
            .await?
            .rows_affected();

        if affected == 0 {
            return Err(AppError::NotFound(format!("timeline event {event_id}")));
        }

        Ok(())
    }

    pub async fn link_document(&self, event_id: &str, document_id: &str) -> Result<(), AppError> {
        let affected = sqlx::query("UPDATE timeline_events SET document_id = ? WHERE id = ?")
            .bind(document_id)
            .bind(event_id)
            .execute(&self.pool)
            .await?
            .rows_affected();

        if affected == 0 {
            return Err(AppError::NotFound(format!("timeline event {event_id}")));
        }

        Ok(())
    }
}
