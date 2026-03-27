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
    pub title: Option<String>,
    pub start_at: Option<i64>,
    pub end_at: Option<i64>,
    pub description: NullableStringPatch,
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

#[cfg(test)]
mod tests {
    use super::{TimelineEvent, TimelineEventRow};

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
        let clear = serde_json::to_value(super::NullableStringPatch::Clear).unwrap();
        let set = serde_json::to_value(super::NullableStringPatch::Set("note".into())).unwrap();

        assert_eq!(clear, serde_json::json!({ "kind": "clear" }));
        assert_eq!(set, serde_json::json!({ "kind": "set", "value": "note" }));
    }
}
