# M8 Timeline Revised Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local timeline feature on the current EchoNote v3 codebase: Rust-backed event CRUD with JSON tags, file-route based timeline UI, month/week/day views, and event linking to recordings plus workspace documents.

**Architecture:** The backend adds a dedicated `timeline` domain with a `TimelineManager` that owns SQLite CRUD, overlap-aware range queries, and transparent tag JSON serialization. The frontend follows the repo's current conventions: file-based TanStack routes, `useShellStore` for `SecondPanel` injection, generated `commands.*` IPC wrappers from `src/lib/bindings.ts`, and a single Zustand timeline store that feeds `TimelinePanel`, `TimelineMain`, `EventCard`, and `EventModal`.

**Tech Stack:** Rust · sqlx 0.8 · serde_json · uuid · chrono · React 18 · TypeScript · Zustand · date-fns · TanStack Router (file routes) · Vitest · Testing Library · tauri-specta

---

## Source Context

- There is no dedicated approved timeline spec file in `docs/superpowers/specs/`; execution should use:
  - user acceptance criteria from the request,
  - the existing milestone intent in `docs/superpowers/plans/2026-03-20-m8-timeline.md`,
  - the repo's current routing/layout/bindings patterns,
  - `docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md` as the global product contract.
- Do not reuse the old M8 plan's outdated assumptions:
  - do not hand-wire routes in `src/router.tsx`,
  - do not call non-existent top-level binding helpers,
  - do not fetch linkable documents from an undefined `listDocuments()` API,
  - do not use nested `Option<Option<T>>` request shapes that make specta output awkward in TypeScript.

## File Map

**Rust domain and IPC**
- Create: `src-tauri/src/timeline/mod.rs`
- Create: `src-tauri/src/timeline/manager.rs`
- Create: `src-tauri/src/commands/timeline.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/src/state.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/bindings.rs`

**Workspace document source for timeline linking**
- Modify: `src-tauri/src/workspace/manager.rs`
- Modify: `src-tauri/src/commands/workspace.rs`
- Modify: `src-tauri/tests/workspace_manager_api.rs`

**Generated IPC bindings**
- Regenerate: `src/lib/bindings.ts`

**Frontend timeline helpers, store, and UI**
- Modify: `package.json`
- Modify: `package-lock.json`
- Create: `src/lib/timeUtils.ts`
- Create: `src/lib/timelineLayout.ts`
- Create: `src/lib/__tests__/timeUtils.test.ts`
- Create: `src/lib/__tests__/timelineLayout.test.ts`
- Create: `src/store/timeline.ts`
- Create: `src/store/__tests__/timeline.test.ts`
- Create: `src/components/timeline/EventCard.tsx`
- Create: `src/components/timeline/EventModal.tsx`
- Create: `src/components/timeline/TimelineMain.tsx`
- Create: `src/components/timeline/TimelinePanel.tsx`
- Create: `src/components/timeline/__tests__/EventCard.test.tsx`
- Create: `src/components/timeline/__tests__/EventModal.test.tsx`
- Create: `src/components/timeline/__tests__/TimelineMain.test.tsx`
- Create: `src/components/timeline/__tests__/TimelinePanel.test.tsx`
- Modify: `src/routes/timeline.tsx`
- Create: `src/routes/__tests__/-timeline-routing.test.tsx`
- Regenerate if touched by plugin: `src/routeTree.gen.ts`

**Required docs sync**
- Modify: `AGENTS.md`
- Modify: `docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md`
- Modify: `CHANGELOG.md`

---

### Task 1: Timeline Domain Types and Tag Decoding

**Files:**
- Create: `src-tauri/src/timeline/mod.rs`
- Create: `src-tauri/src/timeline/manager.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Write the failing Rust unit tests in `src-tauri/src/timeline/mod.rs`**

  Add the tests first, before any production structs:

  ```rust
  #[cfg(test)]
  mod tests {
      use super::{NullableStringPatch, TimelineEvent, TimelineEventRow};
      use serde_json::json;

      #[test]
      fn timeline_event_from_row_decodes_json_tags() {
          let row = TimelineEventRow {
              id: "evt-1".into(),
              title: "Demo".into(),
              start_at: 1000,
              end_at: 2000,
              description: Some("desc".into()),
              tags_json: Some(r#"["meeting","client"]"#.into()),
              recording_id: Some("rec-1".into()),
              document_id: Some("doc-1".into()),
              created_at: 999,
          };

          let event = TimelineEvent::from(row);
          assert_eq!(event.tags, vec!["meeting", "client"]);
      }

      #[test]
      fn timeline_event_from_row_falls_back_to_empty_tags_on_invalid_json() {
          let row = TimelineEventRow {
              id: "evt-2".into(),
              title: "Broken".into(),
              start_at: 1000,
              end_at: 2000,
              description: None,
              tags_json: Some("{oops}".into()),
              recording_id: None,
              document_id: None,
              created_at: 999,
          };

          let event = TimelineEvent::from(row);
          assert!(event.tags.is_empty());
      }

      #[test]
      fn nullable_string_patch_serializes_to_tagged_enum_shape() {
          let clear = serde_json::to_value(NullableStringPatch::Clear).unwrap();
          let set = serde_json::to_value(NullableStringPatch::Set("note".into())).unwrap();
          let unchanged = serde_json::to_value(NullableStringPatch::Unchanged).unwrap();

          assert_eq!(clear, json!({ "kind": "clear" }));
          assert_eq!(set, json!({ "kind": "set", "value": "note" }));
          assert_eq!(unchanged, json!({ "kind": "unchanged" }));
      }
  }
  ```

- [ ] **Step 2: Run the unit tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test timeline::tests --lib
  ```

  Expected: FAIL because `timeline` module and its types do not exist yet.

- [ ] **Step 3: Implement the timeline types and register the module**

  Create an empty `src-tauri/src/timeline/manager.rs` file first so `pub mod manager;` resolves cleanly during Task 1. The file must stay empty in this task; Task 2 will populate it.

  Then create `src-tauri/src/timeline/mod.rs` with replace-style update requests to keep the specta TypeScript shape simple:

  ```rust
  use serde::{Deserialize, Serialize};
  use specta::Type;

  pub mod manager;

  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct TimelineEvent {
      pub id: String,
      pub title: String,
      pub start_at: i64,
      pub end_at: i64,
      pub description: Option<String>,
      pub tags: Vec<String>,
      pub recording_id: Option<String>,
      pub document_id: Option<String>,
      pub created_at: i64,
  }

  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct CreateEventRequest {
      pub title: String,
      pub start_at: i64,
      pub end_at: i64,
      pub description: Option<String>,
      #[serde(skip_serializing_if = "Option::is_none")]
      pub tags: Option<Vec<String>>,
      pub recording_id: Option<String>,
      pub document_id: Option<String>,
  }

  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  #[serde(tag = "kind", content = "value", rename_all = "snake_case")]
  pub enum NullableStringPatch {
      Unchanged,
      Set(String),
      Clear,
  }

  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct UpdateEventRequest {
      #[serde(skip_serializing_if = "Option::is_none")]
      pub title: Option<String>,
      #[serde(skip_serializing_if = "Option::is_none")]
      pub start_at: Option<i64>,
      #[serde(skip_serializing_if = "Option::is_none")]
      pub end_at: Option<i64>,
      pub description: NullableStringPatch,
      #[serde(skip_serializing_if = "Option::is_none")]
      pub tags: Option<Vec<String>>,
      pub recording_id: NullableStringPatch,
      pub document_id: NullableStringPatch,
  }

  #[derive(Debug, Clone)]
  pub(crate) struct TimelineEventRow {
      pub id: String,
      pub title: String,
      pub start_at: i64,
      pub end_at: i64,
      pub description: Option<String>,
      pub tags_json: Option<String>,
      pub recording_id: Option<String>,
      pub document_id: Option<String>,
      pub created_at: i64,
  }

  impl From<TimelineEventRow> for TimelineEvent {
      fn from(row: TimelineEventRow) -> Self {
          let tags = row
              .tags_json
              .as_deref()
              .and_then(|raw| serde_json::from_str::<Vec<String>>(raw).ok())
              .unwrap_or_default();

          Self {
              id: row.id,
              title: row.title,
              start_at: row.start_at,
              end_at: row.end_at,
              description: row.description,
              tags,
              recording_id: row.recording_id,
              document_id: row.document_id,
              created_at: row.created_at,
          }
      }
  }
  ```

  Register it in `src-tauri/src/lib.rs`:

  ```rust
  pub mod timeline;
  ```

- [ ] **Step 4: Re-run the unit tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test timeline::tests --lib
  ```

  Expected: PASS for the new decoding tests.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/timeline/mod.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/timeline/manager.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/lib.rs
  git commit -m "feat(m8): add timeline domain types and tag decoding"
  ```

---

### Task 2: TimelineManager CRUD, Validation, and Overlap Queries

**Files:**
- Create: `src-tauri/src/timeline/manager.rs`

- [ ] **Step 1: Write the failing manager tests first**

  Start `src-tauri/src/timeline/manager.rs` with the test module below before the production implementation:

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
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
  ```

- [ ] **Step 2: Run the manager tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test timeline::manager::tests --lib
  ```

  Expected: FAIL because `TimelineManager` and its methods are not implemented yet.

- [ ] **Step 3: Implement `TimelineManager`**

  Add the manager with explicit validation and overlap-aware range queries:

  ```rust
  use sqlx::SqlitePool;
  use uuid::Uuid;

  use crate::error::AppError;
  use super::{CreateEventRequest, NullableStringPatch, TimelineEvent, TimelineEventRow, UpdateEventRequest};

  pub struct TimelineManager {
      pool: SqlitePool,
  }

  impl TimelineManager {
      pub fn new(pool: SqlitePool) -> Self {
          Self { pool }
      }

      fn validate_range(start_at: i64, end_at: i64) -> Result<(), AppError> {
          if end_at <= start_at {
              return Err(AppError::Validation("timeline event end_at must be after start_at".into()));
          }
          Ok(())
      }

      fn tags_to_json(tags: &[String]) -> Result<String, AppError> {
          serde_json::to_string(tags)
              .map_err(|err| AppError::Storage(format!("serialize timeline tags: {err}")))
      }

      async fn get_event_by_id(&self, id: &str) -> Result<TimelineEvent, AppError> {
          let row = sqlx::query!(
              r#"
              SELECT id, title, start_at, end_at, description, tags as "tags_json?", recording_id, document_id, created_at
              FROM timeline_events
              WHERE id = ?
              "#,
              id
          )
          .fetch_optional(&self.pool)
          .await
          .map_err(|err| AppError::Storage(err.to_string()))?
          .map(|row| TimelineEventRow {
              id: row.id,
              title: row.title,
              start_at: row.start_at,
              end_at: row.end_at,
              description: row.description,
              tags_json: row.tags_json,
              recording_id: row.recording_id,
              document_id: row.document_id,
              created_at: row.created_at,
          })
          .ok_or_else(|| AppError::NotFound(format!("timeline event {id}")))?;

          Ok(TimelineEvent::from(row))
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
          .await
          .map_err(|err| AppError::Storage(err.to_string()))?;

          self.get_event_by_id(&id).await
      }

      pub async fn update_event(&self, id: &str, req: UpdateEventRequest) -> Result<TimelineEvent, AppError> {
          let current = self.get_event_by_id(id).await?;
          let title = req.title.unwrap_or(current.title);
          let start_at = req.start_at.unwrap_or(current.start_at);
          let end_at = req.end_at.unwrap_or(current.end_at);
          Self::validate_range(start_at, end_at)?;
          let description = match req.description {
              NullableStringPatch::Unchanged => current.description,
              NullableStringPatch::Set(value) => Some(value),
              NullableStringPatch::Clear => None,
          };
          let tags = req.tags.unwrap_or(current.tags);
          let recording_id = match req.recording_id {
              NullableStringPatch::Unchanged => current.recording_id,
              NullableStringPatch::Set(value) => Some(value),
              NullableStringPatch::Clear => None,
          };
          let document_id = match req.document_id {
              NullableStringPatch::Unchanged => current.document_id,
              NullableStringPatch::Set(value) => Some(value),
              NullableStringPatch::Clear => None,
          };
          let tags_json = Self::tags_to_json(&tags)?;
          let result = sqlx::query(
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
          .await
          .map_err(|err| AppError::Storage(err.to_string()))?;

          if result.rows_affected() == 0 {
              return Err(AppError::NotFound(format!("timeline event {id}")));
          }

          self.get_event_by_id(id).await
      }

      pub async fn delete_event(&self, id: &str) -> Result<(), AppError> {
          let result = sqlx::query("DELETE FROM timeline_events WHERE id = ?")
              .bind(id)
              .execute(&self.pool)
              .await
              .map_err(|err| AppError::Storage(err.to_string()))?;

          if result.rows_affected() == 0 {
              return Err(AppError::NotFound(format!("timeline event {id}")));
          }

          Ok(())
      }
      pub async fn list_events_in_range(&self, start_ms: i64, end_ms: i64) -> Result<Vec<TimelineEvent>, AppError> {
          let rows = sqlx::query!(
              r#"
              SELECT id, title, start_at, end_at, description, tags as "tags_json?", recording_id, document_id, created_at
              FROM timeline_events
              WHERE end_at >= ? AND start_at <= ?
              ORDER BY start_at ASC, created_at ASC
              "#,
              start_ms,
              end_ms
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|err| AppError::Storage(err.to_string()))?;

          Ok(rows
              .into_iter()
              .map(|row| TimelineEvent::from(TimelineEventRow {
                  id: row.id,
                  title: row.title,
                  start_at: row.start_at,
                  end_at: row.end_at,
                  description: row.description,
                  tags_json: row.tags_json,
                  recording_id: row.recording_id,
                  document_id: row.document_id,
                  created_at: row.created_at,
              }))
              .collect())
      }
      pub async fn search_events(&self, query: &str) -> Result<Vec<TimelineEvent>, AppError> {
          let pattern = format!("%{}%", query.trim().to_lowercase());
          let rows = sqlx::query!(
              r#"
              SELECT id, title, start_at, end_at, description, tags as "tags_json?", recording_id, document_id, created_at
              FROM timeline_events
              WHERE LOWER(title) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?
              ORDER BY start_at DESC, created_at DESC
              "#,
              pattern,
              pattern
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|err| AppError::Storage(err.to_string()))?;

          Ok(rows
              .into_iter()
              .map(|row| TimelineEvent::from(TimelineEventRow {
                  id: row.id,
                  title: row.title,
                  start_at: row.start_at,
                  end_at: row.end_at,
                  description: row.description,
                  tags_json: row.tags_json,
                  recording_id: row.recording_id,
                  document_id: row.document_id,
                  created_at: row.created_at,
              }))
              .collect())
      }

      pub async fn link_recording(&self, event_id: &str, recording_id: &str) -> Result<(), AppError> {
          let result = sqlx::query("UPDATE timeline_events SET recording_id = ? WHERE id = ?")
              .bind(recording_id)
              .bind(event_id)
              .execute(&self.pool)
              .await
              .map_err(|err| AppError::Storage(err.to_string()))?;

          if result.rows_affected() == 0 {
              return Err(AppError::NotFound(format!("timeline event {event_id}")));
          }

          Ok(())
      }

      pub async fn link_document(&self, event_id: &str, document_id: &str) -> Result<(), AppError> {
          let result = sqlx::query("UPDATE timeline_events SET document_id = ? WHERE id = ?")
              .bind(document_id)
              .bind(event_id)
              .execute(&self.pool)
              .await
              .map_err(|err| AppError::Storage(err.to_string()))?;

          if result.rows_affected() == 0 {
              return Err(AppError::NotFound(format!("timeline event {event_id}")));
          }

          Ok(())
      }
  }
  ```

  Implementation requirements:
  - `create_event` and `update_event` must call `validate_range`.
  - Always store tags as compact JSON, even for `[]`.
  - `search_events` must search `LOWER(title)` and `LOWER(COALESCE(description, ''))`.
  - `delete_event`, `link_recording`, and `link_document` must return `AppError::NotFound` when `rows_affected() == 0`.

- [ ] **Step 4: Re-run the manager tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test timeline::manager::tests --lib
  ```

  Expected: PASS for validation, overlap query, and search/tag tests.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/timeline/manager.rs
  git commit -m "feat(m8): implement timeline manager CRUD and overlap queries"
  ```

---

### Task 3: Timeline IPC Commands, AppState Wiring, and Generated Bindings

**Files:**
- Create: `src-tauri/src/commands/timeline.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/state.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/src/bindings.rs`
- Modify: `src/lib/bindings.ts`
- Modify: `src/lib/__tests__/bindings.test.ts`

- [ ] **Step 1: Write the failing bindings smoke test**

  Extend `src/lib/__tests__/bindings.test.ts` with:

  ```typescript
  it("exports timeline M8 commands", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.createTimelineEvent).toBe("function");
    expect(typeof bindings.commands.updateTimelineEvent).toBe("function");
    expect(typeof bindings.commands.deleteTimelineEvent).toBe("function");
    expect(typeof bindings.commands.listTimelineEvents).toBe("function");
    expect(typeof bindings.commands.searchTimelineEvents).toBe("function");
    expect(typeof bindings.commands.linkEventToRecording).toBe("function");
    expect(typeof bindings.commands.linkEventToDocument).toBe("function");
  });
  ```

- [ ] **Step 2: Run the bindings smoke test to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- bindings
  ```

  Expected: FAIL because the generated bindings do not expose the timeline commands yet.

- [ ] **Step 3: Implement the IPC surface and regenerate `src/lib/bindings.ts`**

  Create `src-tauri/src/commands/timeline.rs`:

  ```rust
  use tauri::State;

  use crate::error::AppError;
  use crate::state::AppState;
  use crate::timeline::{CreateEventRequest, TimelineEvent, UpdateEventRequest};

  #[tauri::command]
  #[specta::specta]
  pub async fn create_timeline_event(
      state: State<'_, AppState>,
      req: CreateEventRequest,
  ) -> Result<TimelineEvent, AppError> {
      state.timeline.create_event(req).await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn update_timeline_event(
      state: State<'_, AppState>,
      id: String,
      req: UpdateEventRequest,
  ) -> Result<TimelineEvent, AppError> {
      state.timeline.update_event(&id, req).await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn delete_timeline_event(state: State<'_, AppState>, id: String) -> Result<(), AppError> {
      state.timeline.delete_event(&id).await
  }
  ```

  Wire the rest:
  - add `pub mod timeline;` in `src-tauri/src/commands/mod.rs`,
  - add `pub timeline: crate::timeline::manager::TimelineManager,` to `AppState`,
  - initialize it from `db.pool.clone()` in both `app.manage(...)` and `make_test_state(...)`,
  - register all 7 commands in `src-tauri/src/bindings.rs`,
  - regenerate bindings:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo run --bin export_bindings
  ```

- [ ] **Step 4: Re-run the tests and compile checks to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- bindings
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo check
  ```

  Expected: bindings smoke test PASS, and Rust compile PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/timeline.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/mod.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/state.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/lib.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/bindings.rs /Users/weijiazhao/Dev/EchoNote/src/lib/bindings.ts /Users/weijiazhao/Dev/EchoNote/src/lib/__tests__/bindings.test.ts
  git commit -m "feat(m8): add timeline IPC commands and bindings"
  ```

---

### Task 4: Workspace Global Document Listing for Timeline Linking

**Files:**
- Modify: `src-tauri/src/workspace/manager.rs`
- Modify: `src-tauri/src/commands/workspace.rs`
- Modify: `src-tauri/src/bindings.rs`
- Modify: `src/lib/bindings.ts`
- Modify: `src-tauri/tests/workspace_manager_api.rs`
- Modify: `src/lib/__tests__/bindings.test.ts`

- [ ] **Step 1: Write the failing document-source tests**

  Add this Rust integration test in `src-tauri/tests/workspace_manager_api.rs`:

  ```rust
  #[tokio::test]
  async fn workspace_manager_can_list_all_documents_across_folders() {
      let db = Database::open("sqlite::memory:").await.unwrap();
      let manager = WorkspaceManager::new(db.pool.clone());

      let folder = manager.create_folder("Meetings", None).await.unwrap();
      let root_doc = manager.create_document("Root Note", None, "manual", None).await.unwrap();
      let nested_doc = manager
          .create_document("Nested Note", Some(&folder.id), "manual", None)
          .await
          .unwrap();

      let docs = manager.list_all_documents().await.unwrap();
      let ids: Vec<String> = docs.into_iter().map(|doc| doc.id).collect();

      assert!(ids.contains(&root_doc.id));
      assert!(ids.contains(&nested_doc.id));
  }
  ```

  Extend the bindings smoke test too:

  ```typescript
  it("exports listAllDocuments for timeline link pickers", async () => {
    const bindings = await import("../bindings");
    expect(typeof bindings.commands.listAllDocuments).toBe("function");
  });
  ```

- [ ] **Step 2: Run the RED checks**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test workspace_manager_can_list_all_documents_across_folders --test workspace_manager_api
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- bindings
  ```

  Expected: FAIL because `list_all_documents` and `listAllDocuments` do not exist yet.

- [ ] **Step 3: Implement the backend command and regenerate bindings**

  Add `WorkspaceManager::list_all_documents()` in `src-tauri/src/workspace/manager.rs`:

  ```rust
  pub async fn list_all_documents(&self) -> Result<Vec<DocumentSummary>, AppError> {
      let rows = sqlx::query_as::<_, WorkspaceDocumentRow>(
          "SELECT id, folder_id, title, file_path, content_text, source_type, recording_id, created_at, updated_at
           FROM workspace_documents
           ORDER BY updated_at DESC, created_at DESC",
      )
      .fetch_all(&self.pool)
      .await?;

      let mut docs = Vec::with_capacity(rows.len());
      for doc in rows {
          let (has_transcript, has_summary, has_meeting_brief) =
              self.fetch_asset_flags(&doc.id).await?;
          docs.push(DocumentSummary {
              id: doc.id,
              title: doc.title,
              folder_id: doc.folder_id,
              source_type: doc.source_type,
              has_transcript,
              has_summary,
              has_meeting_brief,
              recording_id: doc.recording_id,
              created_at: doc.created_at,
              updated_at: doc.updated_at,
          });
      }

      Ok(docs)
  }
  ```

  Expose it via `src-tauri/src/commands/workspace.rs` and `src-tauri/src/bindings.rs`:

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn list_all_documents(
      state: State<'_, AppState>,
  ) -> Result<Vec<DocumentSummary>, AppError> {
      state.workspace_manager.list_all_documents().await
  }
  ```

  Then regenerate:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo run --bin export_bindings
  ```

- [ ] **Step 4: Re-run the tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test workspace_manager_can_list_all_documents_across_folders --test workspace_manager_api
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- bindings
  ```

  Expected: PASS for both the Rust API test and the bindings smoke test.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/workspace/manager.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/workspace.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/bindings.rs /Users/weijiazhao/Dev/EchoNote/src/lib/bindings.ts /Users/weijiazhao/Dev/EchoNote/src-tauri/tests/workspace_manager_api.rs /Users/weijiazhao/Dev/EchoNote/src/lib/__tests__/bindings.test.ts
  git commit -m "feat(m8): add global workspace document listing for timeline linking"
  ```

---

### Task 5: Local Time Utilities and Timeline Layout Helpers

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Create: `src/lib/timeUtils.ts`
- Create: `src/lib/timelineLayout.ts`
- Create: `src/lib/__tests__/timeUtils.test.ts`
- Create: `src/lib/__tests__/timelineLayout.test.ts`

- [ ] **Step 1: Write the failing frontend helper tests**

  `src/lib/__tests__/timeUtils.test.ts`:

  ```typescript
  import {
    datetimeLocalToMs,
    msToDatetimeLocal,
    monthBounds,
    weekBounds,
    dayBounds,
  } from "../timeUtils";

  describe("timeUtils", () => {
    const FIXED_MS = Date.UTC(2026, 2, 20, 14, 30, 0);

    it("round-trips datetime-local strings through local time", () => {
      const localValue = msToDatetimeLocal(FIXED_MS);
      expect(localValue).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
      expect(Math.abs(datetimeLocalToMs(localValue) - FIXED_MS)).toBeLessThan(60_000);
    });

    it("returns inclusive month/week/day bounds", () => {
      const ref = new Date("2026-03-20T14:30:00Z");
      const month = monthBounds(ref);
      const week = weekBounds(ref);
      const day = dayBounds(ref);

      expect(month.start).toBeLessThanOrEqual(ref.getTime());
      expect(month.end).toBeGreaterThanOrEqual(ref.getTime());
      expect(week.start).toBeLessThanOrEqual(ref.getTime());
      expect(week.end).toBeGreaterThanOrEqual(ref.getTime());
      expect(day.end - day.start).toBe(86_399_999);
    });
  });
  ```

  `src/lib/__tests__/timelineLayout.test.ts`:

  ```typescript
  import {
    eventOccursOnDay,
    getClampedEventBlock,
  } from "../timelineLayout";

  const day = new Date("2026-03-20T00:00:00");

  describe("timelineLayout", () => {
    it("treats overnight events as occurring on both days", () => {
      const event = {
        start_at: new Date("2026-03-19T23:30:00").getTime(),
        end_at: new Date("2026-03-20T01:00:00").getTime(),
      };

      expect(eventOccursOnDay(event, new Date("2026-03-19T00:00:00"))).toBe(true);
      expect(eventOccursOnDay(event, new Date("2026-03-20T00:00:00"))).toBe(true);
    });

    it("enforces a 30px minimum block height", () => {
      const block = getClampedEventBlock(
        new Date("2026-03-20T09:00:00").getTime(),
        new Date("2026-03-20T09:10:00").getTime(),
        day.getTime(),
      );

      expect(block.heightPx).toBe(30);
      expect(block.topPx).toBe(540);
    });
  });
  ```

- [ ] **Step 2: Run the helper tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- timeUtils timelineLayout
  ```

  Expected: FAIL because the helper modules do not exist yet and `date-fns` is not installed.

- [ ] **Step 3: Install `date-fns` and implement the helper modules**

  Install the dependency:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm install date-fns
  ```

  `src/lib/timeUtils.ts`:

  ```typescript
  import {
    addDays,
    addMonths,
    addWeeks,
    eachDayOfInterval,
    endOfDay,
    endOfMonth,
    endOfWeek,
    format,
    startOfDay,
    startOfMonth,
    startOfWeek,
  } from "date-fns";

  export type TimelineViewMode = "month" | "week" | "day";

  export function datetimeLocalToMs(value: string): number {
    return new Date(value).getTime();
  }

  export function msToDatetimeLocal(ms: number): string {
    const date = new Date(ms);
    const offsetMs = date.getTimezoneOffset() * 60 * 1000;
    return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
  }

  export function monthBounds(date: Date) {
    return { start: startOfMonth(date).getTime(), end: endOfMonth(date).getTime() };
  }

  export function weekBounds(date: Date) {
    return {
      start: startOfWeek(date, { weekStartsOn: 0 }).getTime(),
      end: endOfWeek(date, { weekStartsOn: 0 }).getTime(),
    };
  }

  export function dayBounds(date: Date) {
    return { start: startOfDay(date).getTime(), end: endOfDay(date).getTime() };
  }

  export function daysInRange(startMs: number, endMs: number) {
    return eachDayOfInterval({ start: new Date(startMs), end: new Date(endMs) });
  }
  export function formatEventTime(ms: number) { return format(new Date(ms), "HH:mm"); }
  export function formatEventDate(ms: number) { return format(new Date(ms), "MMM d"); }
  export function rangeForView(anchor: Date, viewMode: TimelineViewMode) {
    if (viewMode === "month") return monthBounds(anchor);
    if (viewMode === "week") return weekBounds(anchor);
    return dayBounds(anchor);
  }
  export function shiftAnchor(anchor: Date, viewMode: TimelineViewMode, amount: number) {
    if (viewMode === "month") return addMonths(anchor, amount);
    if (viewMode === "week") return addWeeks(anchor, amount);
    return addDays(anchor, amount);
  }
  ```

  `src/lib/timelineLayout.ts`:

  ```typescript
  import { endOfDay, startOfDay } from "date-fns";

  const HOUR_HEIGHT_PX = 60;
  const MIN_EVENT_HEIGHT_PX = 30;

  export function eventOccursOnDay(
    event: { start_at: number; end_at: number },
    day: Date,
  ): boolean {
    const dayStart = startOfDay(day).getTime();
    const dayEnd = endOfDay(day).getTime();
    return event.end_at >= dayStart && event.start_at <= dayEnd;
  }

  export function getClampedEventBlock(startAt: number, endAt: number, dayStartMs: number) {
    const dayEndMs = endOfDay(new Date(dayStartMs)).getTime();
    const clampedStart = Math.max(startAt, dayStartMs);
    const clampedEnd = Math.min(endAt, dayEndMs);
    const topPx = ((clampedStart - dayStartMs) / 3_600_000) * HOUR_HEIGHT_PX;
    const heightPx = Math.max(((clampedEnd - clampedStart) / 3_600_000) * HOUR_HEIGHT_PX, MIN_EVENT_HEIGHT_PX);
    return { topPx, heightPx };
  }

  export { HOUR_HEIGHT_PX, MIN_EVENT_HEIGHT_PX };
  ```

- [ ] **Step 4: Re-run the helper tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- timeUtils timelineLayout
  ```

  Expected: PASS for both helper suites.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/package.json /Users/weijiazhao/Dev/EchoNote/package-lock.json /Users/weijiazhao/Dev/EchoNote/src/lib/timeUtils.ts /Users/weijiazhao/Dev/EchoNote/src/lib/timelineLayout.ts /Users/weijiazhao/Dev/EchoNote/src/lib/__tests__/timeUtils.test.ts /Users/weijiazhao/Dev/EchoNote/src/lib/__tests__/timelineLayout.test.ts
  git commit -m "feat(m8): add timeline time and layout helpers"
  ```

---

### Task 6: Zustand Timeline Store

**Files:**
- Create: `src/store/timeline.ts`
- Create: `src/store/__tests__/timeline.test.ts`

- [ ] **Step 1: Write the failing store tests**

  Create `src/store/__tests__/timeline.test.ts`:

  ```typescript
  import { beforeEach, describe, expect, it, vi } from "vitest";
  import { act } from "@testing-library/react";

  const { mockCommands } = vi.hoisted(() => ({
    mockCommands: {
      listTimelineEvents: vi.fn(),
      searchTimelineEvents: vi.fn(),
      createTimelineEvent: vi.fn(),
      updateTimelineEvent: vi.fn(),
      deleteTimelineEvent: vi.fn(),
      listRecordings: vi.fn(),
      listAllDocuments: vi.fn(),
    },
  }));

  vi.mock("@/lib/bindings", () => ({ commands: mockCommands }));

  import { useTimelineStore } from "../timeline";

  describe("useTimelineStore", () => {
    beforeEach(() => {
      Object.values(mockCommands).forEach((fn) => fn.mockReset());
      useTimelineStore.setState({
        events: [],
        anchorDate: new Date("2026-03-20T00:00:00"),
        viewMode: "month",
        viewRange: {
          start: new Date("2026-03-01T00:00:00"),
          end: new Date("2026-03-31T23:59:59"),
        },
        selectedEventId: null,
        linkableRecordings: [],
        linkableDocuments: [],
        searchQuery: "",
        isLoading: false,
        error: null,
      });
    });

    it("fetchRange hydrates events for the current window", async () => {
      mockCommands.listTimelineEvents.mockResolvedValue({
        status: "ok",
        data: [{ id: "evt-1", title: "Demo", start_at: 1000, end_at: 2000, description: null, tags: [], recording_id: null, document_id: null, created_at: 999 }],
      });

      await act(async () => {
        await useTimelineStore.getState().fetchRange(new Date(0), new Date(5000));
      });

      expect(mockCommands.listTimelineEvents).toHaveBeenCalledWith(0, 5000);
      expect(useTimelineStore.getState().events).toHaveLength(1);
    });

    it("loadLinkables loads both recordings and documents for the modal", async () => {
      mockCommands.listRecordings.mockResolvedValue({ status: "ok", data: [{ id: "rec-1", title: "Interview" }] });
      mockCommands.listAllDocuments.mockResolvedValue({ status: "ok", data: [{ id: "doc-1", title: "Summary" }] });

      await act(async () => {
        await useTimelineStore.getState().loadLinkables();
      });

      expect(useTimelineStore.getState().linkableRecordings).toHaveLength(1);
      expect(useTimelineStore.getState().linkableDocuments).toHaveLength(1);
    });
  });
  ```

- [ ] **Step 2: Run the store test to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- timeline.test.ts
  ```

  Expected: FAIL because `src/store/timeline.ts` does not exist yet.

- [ ] **Step 3: Implement `src/store/timeline.ts`**

  Follow the repo's `commands` + `unwrapResult` pattern:

  ```typescript
  import { create } from "zustand";
  import { commands } from "@/lib/bindings";
  import type { CreateEventRequest, DocumentSummary, RecordingItem, TimelineEvent, UpdateEventRequest } from "@/lib/bindings";
  import { rangeForView, shiftAnchor, type TimelineViewMode } from "@/lib/timeUtils";

  function unwrapResult<T>(result: { status: "ok"; data: T } | { status: "error"; error: unknown }): T {
    if (result.status === "error") throw result.error;
    return result.data;
  }

  interface TimelineState {
    events: TimelineEvent[];
    anchorDate: Date;
    viewMode: TimelineViewMode;
    viewRange: { start: Date; end: Date };
    selectedEventId: string | null;
    linkableRecordings: RecordingItem[];
    linkableDocuments: DocumentSummary[];
    searchQuery: string;
    isLoading: boolean;
    error: string | null;
    fetchRange: (start: Date, end: Date) => Promise<void>;
    search: (query: string) => Promise<void>;
    loadLinkables: () => Promise<void>;
    createEvent: (req: CreateEventRequest) => Promise<TimelineEvent>;
    updateEvent: (id: string, req: UpdateEventRequest) => Promise<TimelineEvent>;
    deleteEvent: (id: string) => Promise<void>;
    setViewMode: (mode: TimelineViewMode) => Promise<void>;
    navigatePrev: () => Promise<void>;
    navigateNext: () => Promise<void>;
    navigateToday: () => Promise<void>;
    selectEvent: (id: string | null) => void;
  }

  const initialAnchor = new Date();
  const initialRange = rangeForView(initialAnchor, "month");

  export const useTimelineStore = create<TimelineState>((set, get) => ({
    events: [],
    anchorDate: initialAnchor,
    viewMode: "month",
    viewRange: { start: new Date(initialRange.start), end: new Date(initialRange.end) },
    selectedEventId: null,
    linkableRecordings: [],
    linkableDocuments: [],
    searchQuery: "",
    isLoading: false,
    error: null,
    fetchRange: async (start, end) => {
      set({ isLoading: true, error: null });
      try {
        const events = unwrapResult(await commands.listTimelineEvents(start.getTime(), end.getTime()))
          .slice()
          .sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at);
        set({ events, viewRange: { start, end }, isLoading: false });
      } catch (error) {
        set({ isLoading: false, error: String(error) });
      }
    },
    search: async (query) => {
      const trimmed = query.trim();
      set({ searchQuery: query, error: null });
      if (!trimmed) {
        const { viewRange } = get();
        await get().fetchRange(viewRange.start, viewRange.end);
        return;
      }

      set({ isLoading: true });
      try {
        const events = unwrapResult(await commands.searchTimelineEvents(trimmed))
          .slice()
          .sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at);
        set({ events, isLoading: false });
      } catch (error) {
        set({ isLoading: false, error: String(error) });
      }
    },
    loadLinkables: async () => {
      const [recordings, documents] = await Promise.all([
        commands.listRecordings(),
        commands.listAllDocuments(),
      ]);
      set({
        linkableRecordings: unwrapResult(recordings),
        linkableDocuments: unwrapResult(documents),
      });
    },
    createEvent: async (req) => {
      const event = unwrapResult(await commands.createTimelineEvent(req));
      set((state) => ({
        events: [...state.events, event].sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at),
      }));
      return event;
    },
    updateEvent: async (id, req) => {
      const updated = unwrapResult(await commands.updateTimelineEvent(id, req));
      set((state) => ({
        events: state.events
          .map((event) => (event.id === id ? updated : event))
          .sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at),
      }));
      return updated;
    },
    deleteEvent: async (id) => {
      unwrapResult(await commands.deleteTimelineEvent(id));
      set((state) => ({
        events: state.events.filter((event) => event.id !== id),
        selectedEventId: state.selectedEventId === id ? null : state.selectedEventId,
      }));
    },
    setViewMode: async (mode) => {
      const { anchorDate } = get();
      const nextRange = rangeForView(anchorDate, mode);
      set({
        viewMode: mode,
        viewRange: { start: new Date(nextRange.start), end: new Date(nextRange.end) },
      });
      await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
    },
    navigatePrev: async () => {
      const { anchorDate, viewMode } = get();
      const nextAnchor = shiftAnchor(anchorDate, viewMode, -1);
      const nextRange = rangeForView(nextAnchor, viewMode);
      set({ anchorDate: nextAnchor });
      await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
    },
    navigateNext: async () => {
      const { anchorDate, viewMode } = get();
      const nextAnchor = shiftAnchor(anchorDate, viewMode, 1);
      const nextRange = rangeForView(nextAnchor, viewMode);
      set({ anchorDate: nextAnchor });
      await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
    },
    navigateToday: async () => {
      const nextAnchor = new Date();
      const { viewMode } = get();
      const nextRange = rangeForView(nextAnchor, viewMode);
      set({ anchorDate: nextAnchor });
      await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
    },
    selectEvent: (id) => set({ selectedEventId: id }),
  }));
  ```

- [ ] **Step 4: Re-run the store tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- timeline.test.ts
  ```

  Expected: PASS for range hydration and linkable-resource loading.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src/store/timeline.ts /Users/weijiazhao/Dev/EchoNote/src/store/__tests__/timeline.test.ts
  git commit -m "feat(m8): add timeline store with CRUD and linkable resources"
  ```

---

### Task 7: EventCard Component

**Files:**
- Create: `src/components/timeline/EventCard.tsx`
- Create: `src/components/timeline/__tests__/EventCard.test.tsx`

- [ ] **Step 1: Write the failing EventCard tests**

  `src/components/timeline/__tests__/EventCard.test.tsx`:

  ```typescript
  import { fireEvent, render, screen } from "@testing-library/react";
  import { describe, expect, it, vi } from "vitest";
  import { EventCard } from "../EventCard";

  const event = {
    id: "evt-1",
    title: "Design Review",
    start_at: new Date("2026-03-20T09:00:00").getTime(),
    end_at: new Date("2026-03-20T10:30:00").getTime(),
    description: "Review timeline UI",
    tags: ["design", "review"],
    recording_id: "rec-1",
    document_id: "doc-1",
    created_at: 1,
  };

  describe("EventCard", () => {
    it("renders title, time range, tags, and link indicators", () => {
      render(<EventCard event={event} />);
      expect(screen.getByText("Design Review")).toBeInTheDocument();
      expect(screen.getByText(/09:00/)).toBeInTheDocument();
      expect(screen.getByText("design")).toBeInTheDocument();
      expect(screen.getByLabelText("Linked recording")).toBeInTheDocument();
      expect(screen.getByLabelText("Linked document")).toBeInTheDocument();
    });

    it("invokes onClick and hides metadata in compact mode", () => {
      const onClick = vi.fn();
      render(<EventCard event={event} compact onClick={onClick} />);
      fireEvent.click(screen.getByRole("button", { name: /Design Review/i }));
      expect(onClick).toHaveBeenCalledWith(event);
      expect(screen.queryByText("design")).not.toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run the component tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- EventCard.test.tsx
  ```

  Expected: FAIL because `EventCard.tsx` does not exist yet.

- [ ] **Step 3: Implement `EventCard.tsx`**

  Build the card around the shared time formatter:

  ```tsx
  import type { TimelineEvent } from "@/lib/bindings";
  import { formatEventTime } from "@/lib/timeUtils";

  const TAG_COLORS = ["bg-blue-500", "bg-emerald-500", "bg-amber-500", "bg-rose-500"] as const;

  function tagColor(tags: string[]) {
    if (tags.length === 0) return TAG_COLORS[0];
    const hash = tags[0].split("").reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
    return TAG_COLORS[hash % TAG_COLORS.length];
  }

  export function EventCard({ event, compact = false, onClick }: { event: TimelineEvent; compact?: boolean; onClick?: (event: TimelineEvent) => void }) {
    return (
      <button type="button" onClick={() => onClick?.(event)} aria-label={event.title} className={`w-full rounded-md text-left text-white ${tagColor(event.tags)}`}>
        <span className="block truncate font-medium">{event.title}</span>
        {!compact ? <span className="block text-xs opacity-80">{formatEventTime(event.start_at)} - {formatEventTime(event.end_at)}</span> : null}
        {!compact ? <div className="mt-1 flex flex-wrap gap-1">{event.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
        {!compact && (event.recording_id || event.document_id) ? (
          <div className="mt-1 flex gap-2 text-[10px] opacity-80">
            {event.recording_id ? <span aria-label="Linked recording">REC</span> : null}
            {event.document_id ? <span aria-label="Linked document">DOC</span> : null}
          </div>
        ) : null}
      </button>
    );
  }
  ```

- [ ] **Step 4: Re-run the component tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- EventCard.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src/components/timeline/EventCard.tsx /Users/weijiazhao/Dev/EchoNote/src/components/timeline/__tests__/EventCard.test.tsx
  git commit -m "feat(m8): add timeline event card component"
  ```

---

### Task 8: EventModal Component

**Files:**
- Create: `src/components/timeline/EventModal.tsx`
- Create: `src/components/timeline/__tests__/EventModal.test.tsx`

- [ ] **Step 1: Write the failing EventModal tests**

  `src/components/timeline/__tests__/EventModal.test.tsx`:

  ```typescript
  import { fireEvent, render, screen, waitFor } from "@testing-library/react";
  import { describe, expect, it, vi } from "vitest";

  const createEvent = vi.fn();
  const updateEvent = vi.fn();
  const deleteEvent = vi.fn();
  const loadLinkables = vi.fn();

  vi.mock("@/store/timeline", () => ({
    useTimelineStore: () => ({
      createEvent,
      updateEvent,
      deleteEvent,
      loadLinkables,
      linkableRecordings: [{ id: "rec-1", title: "Interview" }],
      linkableDocuments: [{ id: "doc-1", title: "Summary", folder_id: null }],
    }),
  }));

  import { EventModal } from "../EventModal";

  describe("EventModal", () => {
    it("creates an event with tag chips and selected links", async () => {
      render(<EventModal defaultStartMs={new Date("2026-03-20T09:00:00").getTime()} onClose={() => {}} />);

      fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: "Planning" } });
      fireEvent.change(screen.getByPlaceholderText(/Add tag/i), { target: { value: "work" } });
      fireEvent.click(screen.getByRole("button", { name: /Add tag/i }));
      fireEvent.click(screen.getByRole("button", { name: /Create/i }));

      await waitFor(() => expect(createEvent).toHaveBeenCalled());
      expect(loadLinkables).toHaveBeenCalled();
      expect(screen.getByText("work")).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run the component tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- EventModal.test.tsx
  ```

  Expected: FAIL because `EventModal.tsx` does not exist yet.

- [ ] **Step 3: Implement `EventModal.tsx`**

  Keep all IPC behind the store and use the generated full-update request shape:

  ```tsx
  import { useEffect, useState } from "react";
  import type { TimelineEvent, CreateEventRequest, UpdateEventRequest } from "@/lib/bindings";
  import { datetimeLocalToMs, msToDatetimeLocal } from "@/lib/timeUtils";
  import { useTimelineStore } from "@/store/timeline";

  export function EventModal({ event, defaultStartMs, onClose }: { event?: TimelineEvent; defaultStartMs?: number; onClose: () => void }) {
    const { createEvent, updateEvent, deleteEvent, loadLinkables, linkableRecordings, linkableDocuments } = useTimelineStore();
    const isEdit = Boolean(event);
    const [title, setTitle] = useState(event?.title ?? "");
    const [startLocal, setStartLocal] = useState(msToDatetimeLocal(event?.start_at ?? defaultStartMs ?? Date.now()));
    const [endLocal, setEndLocal] = useState(msToDatetimeLocal(event?.end_at ?? (defaultStartMs ?? Date.now()) + 3_600_000));
    const [description, setDescription] = useState(event?.description ?? "");
    const [tags, setTags] = useState<string[]>(event?.tags ?? []);
    const [tagInput, setTagInput] = useState("");
    const [recordingId, setRecordingId] = useState(event?.recording_id ?? "");
    const [documentId, setDocumentId] = useState(event?.document_id ?? "");

    useEffect(() => { void loadLinkables(); }, [loadLinkables]);

    async function handleSave() {
      const start_at = datetimeLocalToMs(startLocal);
      const end_at = datetimeLocalToMs(endLocal);
      if (isEdit && event) {
        const nextDescription = description.trim()
          ? { kind: "set", value: description.trim() }
          : { kind: "clear" };
        const req: UpdateEventRequest = {
          title: title.trim() || undefined,
          start_at,
          end_at,
          description: nextDescription,
          tags,
          recording_id: recordingId ? { kind: "set", value: recordingId } : { kind: "clear" },
          document_id: documentId ? { kind: "set", value: documentId } : { kind: "clear" },
        };
        await updateEvent(event.id, req);
      } else {
        const req: CreateEventRequest = {
          title,
          start_at,
          end_at,
          description: description.trim() || null,
          tags,
          recording_id: recordingId || null,
          document_id: documentId || null,
        };
        await createEvent(req);
      }
      onClose();
    }
  }
  ```

  UI requirements:
  - must open in create or edit mode,
  - must expose a description input bound to the generated create/update request shape,
  - must allow adding/removing tag chips,
  - must expose recording/document `<select>` controls backed by store data,
  - must validate `title.trim()` and `end_at > start_at`,
  - must support delete in edit mode.

- [ ] **Step 4: Re-run the component tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- EventModal.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src/components/timeline/EventModal.tsx /Users/weijiazhao/Dev/EchoNote/src/components/timeline/__tests__/EventModal.test.tsx
  git commit -m "feat(m8): add timeline event modal"
  ```

---

### Task 9: TimelineMain Month / Week / Day Views

**Files:**
- Create: `src/components/timeline/TimelineMain.tsx`
- Create: `src/components/timeline/__tests__/TimelineMain.test.tsx`

- [ ] **Step 1: Write the failing main-view tests**

  `src/components/timeline/__tests__/TimelineMain.test.tsx`:

  ```typescript
  import { fireEvent, render, screen } from "@testing-library/react";
  import { describe, expect, it, vi } from "vitest";

  let timelineState: any;

  vi.mock("@/store/timeline", () => ({
    useTimelineStore: () => timelineState,
  }));

  vi.mock("../EventModal", () => ({
    EventModal: ({ defaultStartMs }: { defaultStartMs?: number }) => (
      <div data-testid="timeline-modal">{String(defaultStartMs)}</div>
    ),
  }));

  import { TimelineMain } from "../TimelineMain";

  describe("TimelineMain", () => {
    it("highlights event days in month view and opens create modal on empty cell click", () => {
      timelineState = {
        events: [{ id: "evt-1", title: "Demo", start_at: new Date("2026-03-20T09:00:00").getTime(), end_at: new Date("2026-03-20T10:00:00").getTime(), description: null, tags: [], recording_id: null, document_id: null, created_at: 1 }],
        viewMode: "month",
        viewRange: { start: new Date("2026-03-01T00:00:00"), end: new Date("2026-03-31T23:59:59") },
        selectedEventId: null,
        selectEvent: vi.fn(),
      };

      render(<TimelineMain />);
      fireEvent.click(screen.getByRole("gridcell", { name: /March 20, 2026/i }));
      expect(screen.getByTestId("timeline-modal")).toBeInTheDocument();
      expect(screen.getByText("Demo")).toBeInTheDocument();
    });

    it("uses a minimum 30px height in week view", () => {
      timelineState = {
        events: [{ id: "evt-2", title: "Short", start_at: new Date("2026-03-20T09:00:00").getTime(), end_at: new Date("2026-03-20T09:10:00").getTime(), description: null, tags: [], recording_id: null, document_id: null, created_at: 1 }],
        viewMode: "week",
        viewRange: { start: new Date("2026-03-15T00:00:00"), end: new Date("2026-03-21T23:59:59") },
        selectedEventId: null,
        selectEvent: vi.fn(),
      };

      render(<TimelineMain />);
      expect(screen.getByTestId("week-event-evt-2")).toHaveStyle({ height: "30px" });
    });
  });
  ```

- [ ] **Step 2: Run the view tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- TimelineMain.test.tsx
  ```

  Expected: FAIL because `TimelineMain.tsx` does not exist yet.

- [ ] **Step 3: Implement `TimelineMain.tsx`**

  Requirements for the implementation:
  - month view uses a semantic grid with clickable day cells,
  - `aria-label` each day cell with `format(day, "MMMM d, yyyy")`,
  - use `eventOccursOnDay()` for month/day/week filtering so overnight events still render,
  - use `getClampedEventBlock()` for week/day positioning so height remains proportional and never below 30px,
  - open `EventModal` when clicking an empty slot/day,
  - open edit mode when clicking an existing `EventCard`.

  Core skeleton:

  ```tsx
  import { useState } from "react";
  import { format, isSameDay, isSameMonth } from "date-fns";
  import { EventCard } from "./EventCard";
  import { EventModal } from "./EventModal";
  import { daysInRange } from "@/lib/timeUtils";
  import { eventOccursOnDay, getClampedEventBlock, HOUR_HEIGHT_PX } from "@/lib/timelineLayout";
  import { useTimelineStore } from "@/store/timeline";

  export function TimelineMain() {
    const { events, viewMode, viewRange, selectEvent } = useTimelineStore();
    const [modalState, setModalState] = useState<{ eventId?: string; defaultStartMs?: number } | null>(null);
    // render MonthView / WeekView / DayView
  }
  ```

- [ ] **Step 4: Re-run the view tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- TimelineMain.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src/components/timeline/TimelineMain.tsx /Users/weijiazhao/Dev/EchoNote/src/components/timeline/__tests__/TimelineMain.test.tsx
  git commit -m "feat(m8): add timeline main month week day views"
  ```

---

### Task 10: TimelinePanel and File-Route Integration

**Files:**
- Create: `src/components/timeline/TimelinePanel.tsx`
- Create: `src/components/timeline/__tests__/TimelinePanel.test.tsx`
- Modify: `src/routes/timeline.tsx`
- Create: `src/routes/__tests__/-timeline-routing.test.tsx`
- Regenerate if changed: `src/routeTree.gen.ts`

- [ ] **Step 1: Write the failing panel and route tests**

  `src/components/timeline/__tests__/TimelinePanel.test.tsx`:

  ```typescript
  import { fireEvent, render, screen } from "@testing-library/react";
  import { describe, expect, it, vi } from "vitest";

  const storeState = {
    events: [{ id: "evt-1", title: "Demo", start_at: new Date("2026-03-20T09:00:00").getTime(), end_at: new Date("2026-03-20T10:00:00").getTime(), description: null, tags: [], recording_id: null, document_id: null, created_at: 1 }],
    viewMode: "month",
    viewRange: { start: new Date("2026-03-01T00:00:00"), end: new Date("2026-03-31T23:59:59") },
    fetchRange: vi.fn(),
    search: vi.fn(),
    setViewMode: vi.fn(),
    navigatePrev: vi.fn(),
    navigateNext: vi.fn(),
    navigateToday: vi.fn(),
  };

  vi.mock("@/store/timeline", () => ({
    useTimelineStore: () => storeState,
  }));

  import { TimelinePanel } from "../TimelinePanel";

  describe("TimelinePanel", () => {
    it("renders view mode controls and forwards search input", () => {
      render(<TimelinePanel />);
      fireEvent.change(screen.getByPlaceholderText(/Search events/i), { target: { value: "Demo" } });
      expect(storeState.search).toHaveBeenCalledWith("Demo");
      expect(screen.getByRole("button", { name: /month/i })).toBeInTheDocument();
    });
  });
  ```

  `src/routes/__tests__/-timeline-routing.test.tsx`:

  ```typescript
  import { render, screen } from "@testing-library/react";
  import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
  import { describe, expect, it } from "vitest";
  import { routeTree } from "../../routeTree.gen";

  describe("timeline routing", () => {
    it("renders timeline panel in SecondPanel and timeline main in content area", async () => {
      const history = createMemoryHistory({ initialEntries: ["/timeline"] });
      const router = createRouter({ routeTree, history });
      render(<RouterProvider router={router} />);

      await screen.findByPlaceholderText(/Search events/i);
      await screen.findByRole("grid");
    });
  });
  ```

- [ ] **Step 2: Run the panel and routing tests to confirm RED**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- src/components/timeline/__tests__/TimelinePanel.test.tsx src/routes/__tests__/-timeline-routing.test.tsx
  ```

  Expected: FAIL because the real panel component and route integration are not implemented yet.

- [ ] **Step 3: Implement `TimelinePanel.tsx` and update `src/routes/timeline.tsx` using the current file-route pattern**

  `src/components/timeline/TimelinePanel.tsx` should:
  - fetch the initial range on mount,
  - render mini-calendar event dots using `eventOccursOnDay`,
  - render month/week/day buttons,
  - forward search input to `useTimelineStore().search`,
  - use `navigatePrev`, `navigateNext`, and `navigateToday`.

  `src/routes/timeline.tsx` must follow the same pattern as `workspace.tsx`, `settings.tsx`, and `transcription.tsx`:

  ```tsx
  import { useEffect } from "react";
  import { createFileRoute } from "@tanstack/react-router";
  import { TimelineMain } from "@/components/timeline/TimelineMain";
  import { TimelinePanel } from "@/components/timeline/TimelinePanel";
  import { useShellStore } from "@/store/shell";

  export const Route = createFileRoute("/timeline")({
    component: TimelinePage,
  });

  function TimelinePage() {
    const setSecondPanelContent = useShellStore((state) => state.setSecondPanelContent);

    useEffect(() => {
      setSecondPanelContent(<TimelinePanel />);
      return () => setSecondPanelContent(null);
    }, [setSecondPanelContent]);

    return (
      <div className="flex h-full flex-col">
        <TimelineMain />
      </div>
    );
  }
  ```

  After route changes, let the plugin regenerate `src/routeTree.gen.ts` as needed by running a Vite-backed command:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm run build
  ```

- [ ] **Step 4: Re-run the panel and routing tests to confirm GREEN**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm test -- src/components/timeline/__tests__/TimelinePanel.test.tsx src/routes/__tests__/-timeline-routing.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/src/components/timeline/TimelinePanel.tsx /Users/weijiazhao/Dev/EchoNote/src/components/timeline/__tests__/TimelinePanel.test.tsx /Users/weijiazhao/Dev/EchoNote/src/routes/timeline.tsx /Users/weijiazhao/Dev/EchoNote/src/routes/__tests__/-timeline-routing.test.tsx /Users/weijiazhao/Dev/EchoNote/src/routeTree.gen.ts
  git commit -m "feat(m8): integrate timeline panel and file route"
  ```

---

### Task 11: Docs Sync, Full Verification, and Manual Smoke

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run the failing docs-audit gate**

  Run this exact audit:

  ```bash
  rg -n "create_timeline_event|list_all_documents|TimelinePanel|TimelineMain|useShellStore" /Users/weijiazhao/Dev/EchoNote/AGENTS.md /Users/weijiazhao/Dev/EchoNote/docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md /Users/weijiazhao/Dev/EchoNote/CHANGELOG.md
  ```

  Expected: FAIL the gate manually because at least some of the new timeline command names and route-injection details are still missing from the docs.

- [ ] **Step 2: Update the required docs in the same change**

  Update:
  - `AGENTS.md`
    - note the concrete timeline command group under the frontend/backend architecture section,
    - note that timeline uses file routes plus `useShellStore` injection instead of hand-built `router.tsx` routes.
  - `docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md`
    - add the final timeline IPC command names,
    - document JSON tag storage and overlap-aware range queries,
    - document `list_all_documents` as the link-picker source for timeline document association.
  - `CHANGELOG.md`
    - add an `[Unreleased]` bullet summarizing the completed local timeline feature.

- [ ] **Step 3: Re-run the docs-audit gate to confirm GREEN**

  Run:

  ```bash
  rg -n "create_timeline_event|list_all_documents|TimelinePanel|TimelineMain|useShellStore" /Users/weijiazhao/Dev/EchoNote/AGENTS.md /Users/weijiazhao/Dev/EchoNote/docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md /Users/weijiazhao/Dev/EchoNote/CHANGELOG.md
  ```

  Expected: PASS the gate because the grep now finds the synchronized references in all required files.

- [ ] **Step 4: Run full automated verification before any completion claim**

  Run:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo run --bin export_bindings
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test
  cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo check
  cd /Users/weijiazhao/Dev/EchoNote && npm test
  cd /Users/weijiazhao/Dev/EchoNote && npm run typecheck
  cd /Users/weijiazhao/Dev/EchoNote && npm run build
  ```

  Expected:
  - `cargo test`: PASS
  - `cargo check`: PASS
  - `npm test`: PASS
  - `npm run typecheck`: PASS
  - `npm run build`: PASS

- [ ] **Step 5: Run manual smoke and commit the milestone completion**

  Manual smoke in a live app session:

  ```bash
  cd /Users/weijiazhao/Dev/EchoNote && npm run tauri dev
  ```

  Verify all of the following:
  - `/timeline` opens through the existing ActivityBar entry.
  - `TimelinePanel` appears in `SecondPanel`; `TimelineMain` appears in main content.
  - clicking an empty month cell opens create modal.
  - creating an event with two tags shows the event in month view and highlights the day.
  - week view block height scales with duration and never drops below `30px`.
  - day view shows the same event at the correct hour.
  - search narrows the event list and clearing search reloads the current range.
  - editing the event updates the card immediately.
  - deleting the event removes it from all views.
  - if recordings/documents exist, selecting them in the modal persists and the icon markers appear on the event card.

  Then commit:

  ```bash
  git add /Users/weijiazhao/Dev/EchoNote/AGENTS.md /Users/weijiazhao/Dev/EchoNote/docs/superpowers/specs/2026-03-20-echonote-v3-implementation-spec.md /Users/weijiazhao/Dev/EchoNote/CHANGELOG.md
  git commit -m "chore(m8): finalize timeline docs and verification"
  ```

---

## Acceptance Mapping

- Month view shows the current month with event-highlighted dates:
  - Task 5 helper coverage
  - Task 9 month-view rendering
  - Task 10 route/panel integration
- Week view event height is proportional with a 30px minimum:
  - Task 5 `getClampedEventBlock()` tests
  - Task 9 week-view DOM tests
- Clicking blank space opens a create form with tag chips:
  - Task 8 modal behavior
  - Task 9 empty-slot/day click behavior
- Rust test coverage includes range boundaries and tags JSON serialization:
  - Task 1 row decoding tests
  - Task 2 validation / overlap / search / tag tests
- Event can link to recordings and workspace documents using real data sources:
  - Task 4 `list_all_documents`
  - Task 6 `loadLinkables`
  - Task 8 modal selects

## Execution Notes

- Treat `src/lib/bindings.ts` and `src/routeTree.gen.ts` as generated files. Regenerate them; do not hand-edit them except through their generators.
- Do not collapse tasks or skip the RED step. Each task has an explicit failing test or failing audit gate first.
- Do not execute on `main`; create an isolated worktree/branch before implementation.
