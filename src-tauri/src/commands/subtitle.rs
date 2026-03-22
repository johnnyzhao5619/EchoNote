// src-tauri/src/commands/subtitle.rs
// Subtitle system: segment queries with translations, timing/translation edits,
// proportional alignment, and multi-format export (SRT / VTT / LRC).
//
// Uses runtime sqlx::query() forms (no DATABASE_URL / .sqlx cache required).

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;
use uuid::Uuid;
use crate::error::AppError;
use crate::state::AppState;
use super::workspace::sanitize_filename;

// ── Types ────────────────────────────────────────────────────────────────────

/// One transcription segment with optional translation.
#[derive(Debug, Serialize, Deserialize, Clone, Type, sqlx::FromRow)]
pub struct SegmentRow {
    pub id: i64,
    pub recording_id: String,
    pub start_ms: i64,
    pub end_ms: i64,
    pub text: String,
    pub translated_text: Option<String>,
}

/// Subtitle export format.
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(rename_all = "snake_case")]
pub enum SubtitleFormat {
    Srt,
    Vtt,
    Lrc,
}

/// Which language to use when exporting.
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(tag = "type", content = "data", rename_all = "snake_case")]
pub enum SubtitleLanguage {
    Original,
    Translation(String),
}

// ── Commands ──────────────────────────────────────────────────────────────────

/// Return all segments for a recording, optionally joined with translations.
#[tauri::command]
#[specta::specta]
pub async fn get_segments_with_translations(
    recording_id: String,
    language: Option<String>,
    state: State<'_, AppState>,
) -> Result<Vec<SegmentRow>, AppError> {
    let pool = &state.db.pool;

    let rows: Vec<SegmentRow> = if let Some(ref lang) = language {
        sqlx::query_as::<_, SegmentRow>(
            "SELECT ts.id, ts.recording_id, ts.start_ms, ts.end_ms, ts.text,
                    st.text AS translated_text
             FROM transcription_segments ts
             LEFT JOIN segment_translations st
                 ON st.segment_id = ts.id AND st.language = ?
             WHERE ts.recording_id = ?
             ORDER BY ts.start_ms",
        )
        .bind(lang)
        .bind(&recording_id)
        .fetch_all(pool)
        .await?
    } else {
        sqlx::query_as::<_, SegmentRow>(
            "SELECT id, recording_id, start_ms, end_ms, text, NULL AS translated_text
             FROM transcription_segments
             WHERE recording_id = ?
             ORDER BY start_ms",
        )
        .bind(&recording_id)
        .fetch_all(pool)
        .await?
    };

    Ok(rows)
}

/// Update the start/end timing of a segment.
#[tauri::command]
#[specta::specta]
pub async fn update_segment_timing(
    segment_id: i64,
    start_ms: i64,
    end_ms: i64,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    if start_ms >= end_ms {
        return Err(AppError::Validation(
            "start_ms must be less than end_ms".to_string(),
        ));
    }

    sqlx::query(
        "UPDATE transcription_segments SET start_ms = ?, end_ms = ? WHERE id = ?",
    )
    .bind(start_ms)
    .bind(end_ms)
    .bind(segment_id)
    .execute(&state.db.pool)
    .await?;

    Ok(())
}

/// Upsert a translation for a segment.
#[tauri::command]
#[specta::specta]
pub async fn update_segment_translation(
    segment_id: i64,
    language: String,
    text: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    let now = now_ms();
    let id = Uuid::new_v4().to_string();

    sqlx::query(
        "INSERT INTO segment_translations (id, segment_id, language, text, created_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(segment_id, language) DO UPDATE SET text = excluded.text",
    )
    .bind(id)
    .bind(segment_id)
    .bind(&language)
    .bind(&text)
    .bind(now)
    .execute(&state.db.pool)
    .await?;

    Ok(())
}

/// Proportionally align a document's translation asset text to its segments.
/// Maps translated sentences → segments using i * M / N ratio.
#[tauri::command]
#[specta::specta]
pub async fn align_translation_to_segments(
    document_id: String,
    language: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    let pool = &state.db.pool;

    // Resolve recording_id from document
    let recording_id: Option<String> = sqlx::query_scalar(
        "SELECT recording_id FROM workspace_documents WHERE id = ?",
    )
    .bind(&document_id)
    .fetch_optional(pool)
    .await?;

    let recording_id = recording_id.ok_or_else(|| {
        AppError::NotFound(format!("document {document_id} has no linked recording"))
    })?;

    // Load segment IDs ordered by start_ms
    let segment_ids: Vec<i64> = sqlx::query_scalar(
        "SELECT id FROM transcription_segments WHERE recording_id = ? ORDER BY start_ms",
    )
    .bind(&recording_id)
    .fetch_all(pool)
    .await?;

    let n = segment_ids.len();
    if n == 0 {
        return Ok(());
    }

    // Load translation asset content
    let translation_content: Option<String> = sqlx::query_scalar(
        "SELECT content FROM workspace_text_assets WHERE document_id = ? AND role = 'translation'",
    )
    .bind(&document_id)
    .fetch_optional(pool)
    .await?;

    let content = translation_content.ok_or_else(|| {
        AppError::Validation("no translation asset found".to_string())
    })?;

    // Split by sentence boundaries
    let sentences: Vec<String> = split_sentences(&content);
    let m = sentences.len();
    if m == 0 {
        return Ok(());
    }

    // Proportional mapping: segment i → sentence min(round(i * M / N), M-1)
    let now = now_ms();
    for (i, &seg_id) in segment_ids.iter().enumerate() {
        let sent_idx = ((i * m) / n).min(m - 1); // floor division
        let text = &sentences[sent_idx];
        let id = Uuid::new_v4().to_string();

        sqlx::query(
            "INSERT INTO segment_translations (id, segment_id, language, text, created_at)
             VALUES (?, ?, ?, ?, ?)
             ON CONFLICT(segment_id, language) DO UPDATE SET text = excluded.text",
        )
        .bind(id)
        .bind(seg_id)
        .bind(&language)
        .bind(text)
        .bind(now)
        .execute(pool)
        .await?;
    }

    Ok(())
}

/// Export segments as SRT / VTT / LRC string and write to disk.
/// Returns the absolute path of the written file.
#[tauri::command]
#[specta::specta]
pub async fn export_subtitle(
    recording_id: String,
    format: SubtitleFormat,
    language: SubtitleLanguage,
    state: State<'_, AppState>,
) -> Result<String, AppError> {
    let pool = &state.db.pool;

    // Resolve recording title
    let title: Option<String> = sqlx::query_scalar(
        "SELECT title FROM recordings WHERE id = ?",
    )
    .bind(&recording_id)
    .fetch_optional(pool)
    .await?;

    let title = title.ok_or_else(|| AppError::NotFound(format!("recording {recording_id}")))?;

    let cfg = state.config.read().await;
    let recordings_path = cfg.recordings_path.clone();
    drop(cfg);

    // Load segments with optional translation
    let lang_code = match &language {
        SubtitleLanguage::Original => None,
        SubtitleLanguage::Translation(l) => Some(l.clone()),
    };

    let rows: Vec<SegmentRow> = if let Some(ref lang) = lang_code {
        sqlx::query_as::<_, SegmentRow>(
            "SELECT ts.id, ts.recording_id, ts.start_ms, ts.end_ms, ts.text,
                    st.text AS translated_text
             FROM transcription_segments ts
             LEFT JOIN segment_translations st
                 ON st.segment_id = ts.id AND st.language = ?
             WHERE ts.recording_id = ?
             ORDER BY ts.start_ms",
        )
        .bind(lang)
        .bind(&recording_id)
        .fetch_all(pool)
        .await?
    } else {
        sqlx::query_as::<_, SegmentRow>(
            "SELECT id, recording_id, start_ms, end_ms, text, NULL AS translated_text
             FROM transcription_segments
             WHERE recording_id = ?
             ORDER BY start_ms",
        )
        .bind(&recording_id)
        .fetch_all(pool)
        .await?
    };

    // Generate content string
    let content = match format {
        SubtitleFormat::Srt => render_srt(&rows, &language),
        SubtitleFormat::Vtt => render_vtt(&rows, &language),
        SubtitleFormat::Lrc => render_lrc(&rows, &language),
    };

    let ext = match format {
        SubtitleFormat::Srt => "srt",
        SubtitleFormat::Vtt => "vtt",
        SubtitleFormat::Lrc => "lrc",
    };

    let safe_name = sanitize_filename(&title);
    let out_path = std::path::Path::new(&recordings_path).join(format!("{safe_name}.{ext}"));

    std::fs::write(&out_path, content)
        .map_err(|e| AppError::Io(format!("failed to write subtitle: {e}")))?;

    Ok(out_path.to_string_lossy().into_owned())
}

// ── Format renderers ──────────────────────────────────────────────────────────

fn seg_text<'a>(row: &'a SegmentRow, language: &SubtitleLanguage) -> &'a str {
    match language {
        SubtitleLanguage::Original => &row.text,
        SubtitleLanguage::Translation(_) => row
            .translated_text
            .as_deref()
            .unwrap_or(&row.text),
    }
}

fn render_srt(rows: &[SegmentRow], language: &SubtitleLanguage) -> String {
    let mut out = String::new();
    for (i, row) in rows.iter().enumerate() {
        let text = seg_text(row, language);
        if text.is_empty() { continue; }
        out.push_str(&format!(
            "{}\n{} --> {}\n{}\n\n",
            i + 1,
            srt_timestamp(row.start_ms),
            srt_timestamp(row.end_ms),
            text,
        ));
    }
    out
}

fn render_vtt(rows: &[SegmentRow], language: &SubtitleLanguage) -> String {
    let mut out = "WEBVTT\n\n".to_string();
    for row in rows {
        let text = seg_text(row, language);
        if text.is_empty() { continue; }
        out.push_str(&format!(
            "{} --> {}\n{}\n\n",
            vtt_timestamp(row.start_ms),
            vtt_timestamp(row.end_ms),
            text,
        ));
    }
    out
}

fn render_lrc(rows: &[SegmentRow], language: &SubtitleLanguage) -> String {
    let mut out = String::new();
    for row in rows {
        let text = seg_text(row, language);
        if text.is_empty() { continue; }
        out.push_str(&format!("{}{}\n", lrc_timestamp(row.start_ms), text));
    }
    out
}

// ── Timestamp helpers ─────────────────────────────────────────────────────────

fn srt_timestamp(ms: i64) -> String {
    let h = ms / 3_600_000;
    let m = (ms % 3_600_000) / 60_000;
    let s = (ms % 60_000) / 1_000;
    let millis = ms % 1_000;
    format!("{h:02}:{m:02}:{s:02},{millis:03}")
}

fn vtt_timestamp(ms: i64) -> String {
    let h = ms / 3_600_000;
    let m = (ms % 3_600_000) / 60_000;
    let s = (ms % 60_000) / 1_000;
    let millis = ms % 1_000;
    format!("{h:02}:{m:02}:{s:02}.{millis:03}")
}

fn lrc_timestamp(ms: i64) -> String {
    let m = ms / 60_000;
    let s = (ms % 60_000) / 1_000;
    let cs = (ms % 1_000) / 10;
    format!("[{m:02}:{s:02}.{cs:02}]")
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

/// Split text by sentence-boundary characters, filtering empty strings.
fn split_sentences(text: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut start = 0usize;
    for (i, c) in text.char_indices() {
        if matches!(c, '。' | '.' | '!' | '?' | '！' | '？' | '\n') {
            let end = i + c.len_utf8();
            let slice = text[start..end].trim().to_string();
            if !slice.is_empty() {
                result.push(slice);
            }
            start = end;
        }
    }
    let tail = text[start..].trim().to_string();
    if !tail.is_empty() {
        result.push(tail);
    }
    result
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_srt_timestamp() {
        assert_eq!(srt_timestamp(0), "00:00:00,000");
        assert_eq!(srt_timestamp(3_661_500), "01:01:01,500");
        assert_eq!(srt_timestamp(3200), "00:00:03,200");
    }

    #[test]
    fn test_vtt_timestamp() {
        assert_eq!(vtt_timestamp(0), "00:00:00.000");
        assert_eq!(vtt_timestamp(3200), "00:00:03.200");
    }

    #[test]
    fn test_lrc_timestamp() {
        assert_eq!(lrc_timestamp(0), "[00:00.00]");
        assert_eq!(lrc_timestamp(63_210), "[01:03.21]");
    }

    #[test]
    fn test_render_srt_empty() {
        let out = render_srt(&[], &SubtitleLanguage::Original);
        assert!(out.is_empty());
    }

    #[test]
    fn test_render_srt_basic() {
        let rows = vec![SegmentRow {
            id: 1,
            recording_id: "r1".into(),
            start_ms: 0,
            end_ms: 3200,
            text: "Hello world".into(),
            translated_text: None,
        }];
        let out = render_srt(&rows, &SubtitleLanguage::Original);
        assert!(out.contains("00:00:00,000 --> 00:00:03,200"));
        assert!(out.contains("Hello world"));
    }

    #[test]
    fn test_render_srt_translation_fallback() {
        let rows = vec![SegmentRow {
            id: 1,
            recording_id: "r1".into(),
            start_ms: 0,
            end_ms: 1000,
            text: "原文".into(),
            translated_text: None,
        }];
        let out = render_srt(&rows, &SubtitleLanguage::Translation("en".into()));
        assert!(out.contains("原文"));
    }

    #[test]
    fn test_render_vtt_header() {
        let out = render_vtt(&[], &SubtitleLanguage::Original);
        assert!(out.starts_with("WEBVTT"));
    }

    #[test]
    fn test_render_lrc_basic() {
        let rows = vec![SegmentRow {
            id: 1,
            recording_id: "r1".into(),
            start_ms: 63_210,
            end_ms: 65_000,
            text: "歌词内容".into(),
            translated_text: None,
        }];
        let out = render_lrc(&rows, &SubtitleLanguage::Original);
        assert!(out.contains("[01:03.21]歌词内容"));
    }

    #[test]
    fn test_split_sentences() {
        let text = "Hello world. How are you? Fine!\nGreat";
        let parts = split_sentences(text);
        assert_eq!(parts.len(), 4);
    }

    #[test]
    fn test_split_sentences_chinese() {
        let text = "你好。今天天气不错！是吗？";
        let parts = split_sentences(text);
        assert_eq!(parts.len(), 3);
    }

    #[test]
    fn test_align_proportional_mapping() {
        // floor(i * M / N): N=4 segments, M=2 sentences → [0,0,1,1]
        let n = 4_usize;
        let m = 2_usize;
        let mappings: Vec<usize> = (0..n).map(|i| ((i * m) / n).min(m - 1)).collect();
        assert_eq!(mappings, vec![0, 0, 1, 1]);
    }

    #[test]
    fn test_db_migration_content() {
        let sql = include_str!("../storage/migrations/0003_segment_translations.sql");
        assert!(sql.contains("CREATE TABLE segment_translations"));
        assert!(sql.contains("UNIQUE(segment_id, language)"));
    }
}
