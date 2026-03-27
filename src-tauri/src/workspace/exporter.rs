use std::path::Path;

use sqlx::SqlitePool;
use tokio::fs;

use crate::error::AppError;

pub fn ms_to_srt_timestamp(ms: i64) -> String {
    let total_secs = ms / 1000;
    let millis = ms % 1000;
    let hours = total_secs / 3600;
    let minutes = (total_secs % 3600) / 60;
    let secs = total_secs % 60;
    format!("{hours:02}:{minutes:02}:{secs:02},{millis:03}")
}

pub fn ms_to_vtt_timestamp(ms: i64) -> String {
    let total_secs = ms / 1000;
    let millis = ms % 1000;
    let hours = total_secs / 3600;
    let minutes = (total_secs % 3600) / 60;
    let secs = total_secs % 60;
    format!("{hours:02}:{minutes:02}:{secs:02}.{millis:03}")
}

pub async fn export_as_srt(
    pool: &SqlitePool,
    document_id: &str,
    target_path: &Path,
) -> Result<(), AppError> {
    let recording_id = fetch_recording_id(pool, document_id).await?;
    let segments: Vec<(i64, i64, String)> = sqlx::query_as(
        "SELECT start_ms, end_ms, text
         FROM transcription_segments
         WHERE recording_id = ?
         ORDER BY start_ms ASC",
    )
    .bind(recording_id)
    .fetch_all(pool)
    .await?;

    let mut body = String::new();
    for (idx, (start_ms, end_ms, text)) in segments.iter().enumerate() {
        body.push_str(&format!(
            "{}\n{} --> {}\n{}\n\n",
            idx + 1,
            ms_to_srt_timestamp(*start_ms),
            ms_to_srt_timestamp(*end_ms),
            text.trim()
        ));
    }

    fs::write(target_path, body).await?;
    Ok(())
}

pub async fn export_as_vtt(
    pool: &SqlitePool,
    document_id: &str,
    target_path: &Path,
) -> Result<(), AppError> {
    let recording_id = fetch_recording_id(pool, document_id).await?;
    let segments: Vec<(i64, i64, String)> = sqlx::query_as(
        "SELECT start_ms, end_ms, text
         FROM transcription_segments
         WHERE recording_id = ?
         ORDER BY start_ms ASC",
    )
    .bind(recording_id)
    .fetch_all(pool)
    .await?;

    let mut body = String::from("WEBVTT\n\n");
    for (idx, (start_ms, end_ms, text)) in segments.iter().enumerate() {
        body.push_str(&format!(
            "{}\n{} --> {}\n{}\n\n",
            idx + 1,
            ms_to_vtt_timestamp(*start_ms),
            ms_to_vtt_timestamp(*end_ms),
            text.trim()
        ));
    }

    fs::write(target_path, body).await?;
    Ok(())
}

pub async fn export_as_markdown(
    pool: &SqlitePool,
    document_id: &str,
    target_path: &Path,
) -> Result<(), AppError> {
    let content = fetch_best_text(pool, document_id).await?;
    fs::write(target_path, content).await?;
    Ok(())
}

pub async fn export_as_txt(
    pool: &SqlitePool,
    document_id: &str,
    target_path: &Path,
) -> Result<(), AppError> {
    let content = fetch_best_text(pool, document_id).await?;
    let plain = content
        .lines()
        .map(|line| line.trim_start_matches('#').trim())
        .collect::<Vec<_>>()
        .join("\n")
        .replace("**", "")
        .replace("__", "");

    fs::write(target_path, plain).await?;
    Ok(())
}

async fn fetch_recording_id(pool: &SqlitePool, document_id: &str) -> Result<String, AppError> {
    let row: Option<(Option<String>,)> = sqlx::query_as(
        "SELECT recording_id FROM workspace_documents WHERE id = ?",
    )
    .bind(document_id)
    .fetch_optional(pool)
    .await?;

    row.and_then(|(recording_id,)| recording_id)
        .ok_or_else(|| AppError::Validation("document has no associated recording".to_string()))
}

async fn fetch_best_text(pool: &SqlitePool, document_id: &str) -> Result<String, AppError> {
    let row: Option<(String,)> = sqlx::query_as(
        "SELECT content
         FROM workspace_text_assets
         WHERE document_id = ?
         ORDER BY CASE role
            WHEN 'document_text' THEN 0
            WHEN 'transcript' THEN 1
            WHEN 'meeting_brief' THEN 2
            WHEN 'summary' THEN 3
            ELSE 99
         END
         LIMIT 1",
    )
    .bind(document_id)
    .fetch_optional(pool)
    .await?;

    row.map(|(content,)| content)
        .ok_or_else(|| AppError::NotFound(format!("no text asset for document {document_id}")))
}

#[cfg(test)]
mod tests {
    use super::{ms_to_srt_timestamp, ms_to_vtt_timestamp};

    #[test]
    fn exporter_timestamp_helpers_format_expected_values() {
        assert_eq!(ms_to_srt_timestamp(0), "00:00:00,000");
        assert_eq!(ms_to_srt_timestamp(1_500), "00:00:01,500");
        assert_eq!(ms_to_vtt_timestamp(0), "00:00:00.000");
        assert_eq!(ms_to_vtt_timestamp(1_500), "00:00:01.500");
    }
}
