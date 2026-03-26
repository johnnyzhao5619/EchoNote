use serde::Deserialize;

use crate::error::AppError;
use crate::llm::tasks::LlmTaskType;

#[derive(Debug, Clone)]
pub struct StructuredTaskOutput {
    pub result_text: String,
    pub asset_role: String,
    pub assets_to_write: Vec<(String, String)>,
}

#[derive(Debug, Clone)]
pub struct StructuredPromptSpec {
    pub grammar: Option<String>,
    pub user_prompt: String,
}

#[derive(Debug, Deserialize)]
struct SummaryJson {
    summary: String,
    #[serde(default)]
    key_points: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct MeetingBriefJson {
    summary: String,
    #[serde(default)]
    decisions: Vec<String>,
    #[serde(default)]
    action_items: Vec<String>,
    #[serde(default)]
    next_steps: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct TranslationJson {
    translated_text: String,
}

pub fn structured_prompt_spec(
    task_type: &LlmTaskType,
    base_user_prompt: &str,
) -> Result<StructuredPromptSpec, AppError> {
    match task_type {
        LlmTaskType::Summary => Ok(StructuredPromptSpec {
            // llama.cpp grammar sampler currently aborts on the shipped Qwen2.5-3B model
            // after accepting certain valid JSON pieces. Keep the contract in prompt text and
            // enforce it via Rust-side validation instead of native constrained decoding.
            grammar: None,
            user_prompt: format!(
                "{base_user_prompt}\n\nReturn valid JSON only. Do not use Markdown, code fences, or prose outside JSON.\nSchema: {{\"summary\": string, \"key_points\": string[]}}"
            ),
        }),
        LlmTaskType::MeetingBrief => Ok(StructuredPromptSpec {
            grammar: None,
            user_prompt: format!(
                "{base_user_prompt}\n\nReturn valid JSON only. Do not use Markdown, code fences, or prose outside JSON.\nSchema: {{\"summary\": string, \"decisions\": string[], \"action_items\": string[], \"next_steps\": string[]}}"
            ),
        }),
        LlmTaskType::Translation { .. } => Ok(StructuredPromptSpec {
            grammar: None,
            user_prompt: format!(
                "{base_user_prompt}\n\nReturn valid JSON only. Do not use Markdown, code fences, or prose outside JSON.\nSchema: {{\"translated_text\": string}}"
            ),
        }),
        LlmTaskType::Qa { .. } => Ok(StructuredPromptSpec {
            grammar: None,
            user_prompt: base_user_prompt.to_string(),
        }),
    }
}

pub fn finalize_task_output(task_type: &LlmTaskType, raw_text: &str) -> Result<StructuredTaskOutput, AppError> {
    match task_type {
        LlmTaskType::Summary => finalize_summary(raw_text),
        LlmTaskType::MeetingBrief => finalize_meeting_brief(raw_text),
        LlmTaskType::Translation { .. } => finalize_translation(raw_text),
        LlmTaskType::Qa { .. } => Ok(StructuredTaskOutput {
            result_text: raw_text.trim().to_string(),
            asset_role: "qa_answer".to_string(),
            assets_to_write: vec![("qa_answer".to_string(), raw_text.trim().to_string())],
        }),
    }
}

fn finalize_summary(raw_text: &str) -> Result<StructuredTaskOutput, AppError> {
    let parsed: SummaryJson = serde_json::from_str(raw_text)
        .map_err(|e| AppError::Llm(format!("parse summary json: {e}")))?;
    let summary = require_non_empty("summary.summary", &parsed.summary)?;
    let key_points = sanitize_list("summary.key_points", parsed.key_points)?;
    let result_text = render_summary_markdown(&summary, &key_points);
    Ok(StructuredTaskOutput {
        result_text: result_text.clone(),
        asset_role: "summary".to_string(),
        assets_to_write: vec![("summary".to_string(), result_text)],
    })
}

fn finalize_meeting_brief(raw_text: &str) -> Result<StructuredTaskOutput, AppError> {
    let parsed: MeetingBriefJson = serde_json::from_str(raw_text)
        .map_err(|e| AppError::Llm(format!("parse meeting brief json: {e}")))?;
    let summary = require_non_empty("meeting_brief.summary", &parsed.summary)?;
    let decisions = sanitize_list("meeting_brief.decisions", parsed.decisions)?;
    let action_items = sanitize_list("meeting_brief.action_items", parsed.action_items)?;
    let next_steps = sanitize_list("meeting_brief.next_steps", parsed.next_steps)?;

    let result_text = render_meeting_brief_markdown(
        &summary,
        &decisions,
        &action_items,
        &next_steps,
    );

    Ok(StructuredTaskOutput {
        result_text,
        asset_role: "meeting_brief".to_string(),
        assets_to_write: vec![
            ("summary".to_string(), summary),
            ("decisions".to_string(), render_bullet_list(&decisions)),
            ("action_items".to_string(), render_bullet_list(&action_items)),
            ("next_steps".to_string(), render_bullet_list(&next_steps)),
        ],
    })
}

fn finalize_translation(raw_text: &str) -> Result<StructuredTaskOutput, AppError> {
    let parsed: TranslationJson = serde_json::from_str(raw_text)
        .map_err(|e| AppError::Llm(format!("parse translation json: {e}")))?;
    let translated_text = require_non_empty("translation.translated_text", &parsed.translated_text)?;
    Ok(StructuredTaskOutput {
        result_text: translated_text.clone(),
        asset_role: "translation".to_string(),
        assets_to_write: vec![("translation".to_string(), translated_text)],
    })
}

fn require_non_empty(field_name: &str, value: &str) -> Result<String, AppError> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(AppError::Llm(format!("{field_name} is empty")));
    }
    Ok(trimmed.to_string())
}

fn sanitize_list(field_name: &str, values: Vec<String>) -> Result<Vec<String>, AppError> {
    let mut cleaned = Vec::with_capacity(values.len());
    for value in values {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return Err(AppError::Llm(format!("{field_name} contains an empty item")));
        }
        cleaned.push(trimmed.to_string());
    }
    Ok(cleaned)
}

fn render_summary_markdown(summary: &str, key_points: &[String]) -> String {
    let mut parts = vec!["## Summary".to_string(), summary.to_string()];
    if !key_points.is_empty() {
        parts.push(String::new());
        parts.push("## Key Points".to_string());
        parts.push(render_bullet_list(key_points));
    }
    parts.join("\n")
}

fn render_meeting_brief_markdown(
    summary: &str,
    decisions: &[String],
    action_items: &[String],
    next_steps: &[String],
) -> String {
    [
        ("Summary", summary.to_string()),
        ("Decisions", render_bullet_list(decisions)),
        ("Action Items", render_bullet_list(action_items)),
        ("Next Steps", render_bullet_list(next_steps)),
    ]
    .into_iter()
    .map(|(heading, content)| format!("## {heading}\n{content}"))
    .collect::<Vec<_>>()
    .join("\n\n")
}

fn render_bullet_list(items: &[String]) -> String {
    if items.is_empty() {
        String::new()
    } else {
        items
            .iter()
            .map(|item| format!("- {item}"))
            .collect::<Vec<_>>()
            .join("\n")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_finalize_summary_renders_markdown() {
        let output = finalize_task_output(
            &LlmTaskType::Summary,
            r#"{"summary":"讨论了课程内容规划。","key_points":["细化章节","补充示例"]}"#,
        )
        .unwrap();

        assert_eq!(output.asset_role, "summary");
        assert!(output.result_text.contains("## Summary"));
        assert!(output.result_text.contains("- 细化章节"));
        assert_eq!(output.assets_to_write.len(), 1);
    }

    #[test]
    fn test_finalize_meeting_brief_splits_assets() {
        let output = finalize_task_output(
            &LlmTaskType::MeetingBrief,
            r#"{"summary":"讨论了课程内容规划。","decisions":["细化课程结构"],"action_items":["张三更新文档"],"next_steps":["周五复审"]}"#,
        )
        .unwrap();

        assert_eq!(output.asset_role, "meeting_brief");
        assert_eq!(output.assets_to_write.len(), 4);
        assert!(output.result_text.contains("## Decisions"));
    }

    #[test]
    fn test_finalize_translation_requires_non_empty_text() {
        let err = finalize_task_output(
            &LlmTaskType::Translation {
                target_language: "English".to_string(),
            },
            r#"{"translated_text":""}"#,
        )
        .unwrap_err();

        assert!(err.to_string().contains("translated_text is empty"));
    }

    #[test]
    fn test_structured_prompt_spec_adds_json_contract() {
        let spec = structured_prompt_spec(&LlmTaskType::Summary, "Base prompt").unwrap();
        assert!(spec.grammar.is_none());
        assert!(spec.user_prompt.contains("Return valid JSON only"));
    }
}
