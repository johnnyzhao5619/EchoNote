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
pub async fn delete_timeline_event(
    state: State<'_, AppState>,
    id: String,
) -> Result<(), AppError> {
    state.timeline.delete_event(&id).await
}

#[tauri::command]
#[specta::specta]
pub async fn list_timeline_events(
    state: State<'_, AppState>,
    start_ms: i64,
    end_ms: i64,
) -> Result<Vec<TimelineEvent>, AppError> {
    state.timeline.list_events_in_range(start_ms, end_ms).await
}

#[tauri::command]
#[specta::specta]
pub async fn search_timeline_events(
    state: State<'_, AppState>,
    query: String,
) -> Result<Vec<TimelineEvent>, AppError> {
    state.timeline.search_events(&query).await
}

#[tauri::command]
#[specta::specta]
pub async fn link_event_to_recording(
    state: State<'_, AppState>,
    event_id: String,
    recording_id: String,
) -> Result<(), AppError> {
    state.timeline.link_recording(&event_id, &recording_id).await
}

#[tauri::command]
#[specta::specta]
pub async fn link_event_to_document(
    state: State<'_, AppState>,
    event_id: String,
    document_id: String,
) -> Result<(), AppError> {
    state.timeline.link_document(&event_id, &document_id).await
}
