// src-tauri/src/llm/tasks.rs
//
// 职责：
//   1. PromptTemplates：从 tasks.toml 加载（启动时一次），线程安全（只读）
//   2. build_prompt：填充模板变量，返回 (system, user, max_tokens)
//   3. parse_meeting_brief：Unicode 安全正则，提取四个 section；全部失败时 fallback 全文
//   4. get_best_text：按 asset role 优先级取文档最佳可读文本

use std::collections::HashMap;
use std::path::Path;
use std::sync::OnceLock;

use regex::Regex;
use serde::{Deserialize, Serialize};
use specta::Type;

use crate::error::AppError;

// ── tasks.toml 反序列化结构 ───────────────────────────────────────────────

#[derive(Debug, Deserialize, Clone)]
pub struct TaskTemplate {
    pub system: String,
    pub user: String,
    pub max_tokens: u32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct PromptTemplates {
    pub summary: TaskTemplate,
    pub meeting_brief: TaskTemplate,
    pub translation: TaskTemplate,
    pub qa: TaskTemplate,
}

impl PromptTemplates {
    /// 从磁盘加载 tasks.toml。
    pub fn load(toml_path: &Path) -> Result<Self, AppError> {
        let raw = std::fs::read_to_string(toml_path)
            .map_err(|e| AppError::Io(format!("read tasks.toml: {e}")))?;
        toml::from_str(&raw)
            .map_err(|e| AppError::Llm(format!("parse tasks.toml: {e}")))
    }
}

// ── 任务类型与请求 ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
#[serde(rename_all = "snake_case", tag = "type", content = "data")]
pub enum LlmTaskType {
    Summary,
    MeetingBrief,
    Translation { target_language: String },
    Qa { question: String },
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct LlmTaskRequest {
    pub document_id: String,
    pub task_type: LlmTaskType,
    /// Optional role hint for get_best_text (e.g. "transcript")
    pub text_role_hint: Option<String>,
}

// ── 变量替换 ──────────────────────────────────────────────────────────────

/// 填充模板变量，返回 `(system_prompt, user_prompt, max_tokens)`。
pub fn build_prompt(
    templates: &PromptTemplates,
    task_type: &LlmTaskType,
    vars: &HashMap<&str, &str>,
) -> Result<(String, String, u32), AppError> {
    let template = match task_type {
        LlmTaskType::Summary => &templates.summary,
        LlmTaskType::MeetingBrief => &templates.meeting_brief,
        LlmTaskType::Translation { .. } => &templates.translation,
        LlmTaskType::Qa { .. } => &templates.qa,
    };

    let fill = |s: &str| -> String {
        let mut out = s.to_string();
        for (k, v) in vars {
            out = out.replace(&format!("{{{k}}}"), v);
        }
        out
    };

    Ok((
        fill(&template.system),
        fill(&template.user),
        template.max_tokens,
    ))
}

// ── 会议纪要结构体 ────────────────────────────────────────────────────────

#[derive(Debug, Default, Clone)]
pub struct MeetingBriefSections {
    pub summary: Option<String>,
    pub decisions: Option<String>,
    pub action_items: Option<String>,
    pub next_steps: Option<String>,
    /// 全部 section 解析失败时的 fallback：保存完整文本
    pub full_text_fallback: Option<String>,
}

impl MeetingBriefSections {
    pub fn to_assets(&self) -> Vec<(String, String)> {
        if let Some(ref full) = self.full_text_fallback {
            return vec![("meeting_brief".to_string(), full.clone())];
        }
        let mut assets = Vec::new();
        if let Some(ref s) = self.summary {
            assets.push(("summary".to_string(), s.clone()));
        }
        if let Some(ref d) = self.decisions {
            assets.push(("decisions".to_string(), d.clone()));
        }
        if let Some(ref a) = self.action_items {
            assets.push(("action_items".to_string(), a.clone()));
        }
        if let Some(ref n) = self.next_steps {
            assets.push(("next_steps".to_string(), n.clone()));
        }
        assets
    }
}

// ── 全局编译好的正则（lazy，仅匹配 ## 标题行，不使用不支持的 lookahead）──

fn header_regex() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    // 匹配 "## 标题" 行，多行模式
    RE.get_or_init(|| Regex::new(r"(?m)^##\s+(.+?)\s*$").unwrap())
}

/// Unicode 安全的会议纪要解析器。
///
/// 两遍法：先找所有 ## 标题位置，再按相邻标题间距切割内容。
/// 支持英文和中文 section 标题。全部 section 失败时 fallback 全文。
pub fn parse_meeting_brief(text: &str) -> MeetingBriefSections {
    let re = header_regex();
    let mut sections = MeetingBriefSections::default();

    // 收集 (match_start, header_end, title_lowercase)
    let headers: Vec<(usize, usize, String)> = re
        .captures_iter(text)
        .map(|cap| {
            let m = cap.get(0).unwrap();
            (m.start(), m.end(), cap[1].trim().to_lowercase())
        })
        .collect();

    for (i, (_, header_end, title)) in headers.iter().enumerate() {
        let content_end = if i + 1 < headers.len() {
            headers[i + 1].0
        } else {
            text.len()
        };
        let content = text[*header_end..content_end].trim().to_string();
        if content.is_empty() {
            continue;
        }

        if title.contains("summary")
            || title.contains("摘要")
            || title.contains("总结")
            || title.contains("概述")
        {
            sections.summary = Some(content);
        } else if title.contains("decision")
            || title.contains("决策")
            || title.contains("决定")
        {
            sections.decisions = Some(content);
        } else if title.contains("action")
            || title.contains("行动")
            || title.contains("任务")
        {
            sections.action_items = Some(content);
        } else if title.contains("next")
            || title.contains("下一步")
            || title.contains("后续")
        {
            sections.next_steps = Some(content);
        }
    }

    // Fallback：若所有 section 均为 None，保存完整文本
    if sections.summary.is_none()
        && sections.decisions.is_none()
        && sections.action_items.is_none()
        && sections.next_steps.is_none()
    {
        sections.full_text_fallback = Some(text.to_string());
    }

    sections
}

// ── Asset Role 优先级 ─────────────────────────────────────────────────────

const ROLE_PRIORITY: &[&str] = &[
    "document_text", // 0
    "transcript",    // 1
    "meeting_brief", // 2
    "summary",       // 3
    "translation",   // 4
    "decisions",     // 5
    "action_items",  // 6
    "next_steps",    // 7
];

fn role_rank(role: &str) -> usize {
    ROLE_PRIORITY
        .iter()
        .position(|&r| r == role)
        .unwrap_or(usize::MAX)
}

pub fn get_best_text<'a>(
    assets: &'a [(String, String)],
    role_hint: Option<&str>,
) -> Option<&'a str> {
    if let Some(hint) = role_hint {
        if let Some((_, content)) = assets.iter().find(|(r, _)| r == hint) {
            return Some(content.as_str());
        }
    }

    assets
        .iter()
        .min_by_key(|(role, _)| role_rank(role))
        .map(|(_, content)| content.as_str())
}

// ── 单元测试 ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_meeting_brief_english_headers() {
        let text = "## Summary\nWe discussed Q1 targets.\n\
                    ## Decisions\nAdopt new CI pipeline.\n\
                    ## Action Items\nAlice: update docs.\n\
                    ## Next Steps\nSchedule follow-up for April.";

        let sections = parse_meeting_brief(text);

        assert!(sections.full_text_fallback.is_none(), "no fallback expected");
        assert_eq!(
            sections.summary.as_deref(),
            Some("We discussed Q1 targets.")
        );
        assert_eq!(
            sections.decisions.as_deref(),
            Some("Adopt new CI pipeline.")
        );
        assert_eq!(
            sections.action_items.as_deref(),
            Some("Alice: update docs.")
        );
        assert_eq!(
            sections.next_steps.as_deref(),
            Some("Schedule follow-up for April.")
        );
    }

    #[test]
    fn test_parse_meeting_brief_chinese_headers() {
        let text = "## 总结\n本次会议讨论了 Q1 目标。\n\
                    ## 决策\n采用新的 CI 流程。\n\
                    ## 任务\n张三：更新文档。\n\
                    ## 下一步\n四月份安排跟进。";

        let sections = parse_meeting_brief(text);

        assert!(sections.full_text_fallback.is_none(), "no fallback expected");
        assert_eq!(
            sections.summary.as_deref(),
            Some("本次会议讨论了 Q1 目标。")
        );
        assert_eq!(
            sections.decisions.as_deref(),
            Some("采用新的 CI 流程。")
        );
        assert_eq!(
            sections.action_items.as_deref(),
            Some("张三：更新文档。")
        );
        assert_eq!(
            sections.next_steps.as_deref(),
            Some("四月份安排跟进。")
        );
    }

    #[test]
    fn test_parse_meeting_brief_fallback_when_no_sections() {
        let text = "This is a plain paragraph with no section headers at all.";

        let sections = parse_meeting_brief(text);

        assert!(sections.summary.is_none());
        assert!(sections.decisions.is_none());
        assert!(sections.action_items.is_none());
        assert!(sections.next_steps.is_none());
        assert_eq!(
            sections.full_text_fallback.as_deref(),
            Some(text),
            "fallback should contain the original text"
        );
    }

    #[test]
    fn test_build_prompt_summary_variable_substitution() {
        let templates = PromptTemplates {
            summary: TaskTemplate {
                system: "You are a summarizer.".into(),
                user: "Summarize: {text}".into(),
                max_tokens: 256,
            },
            meeting_brief: TaskTemplate {
                system: "".into(),
                user: "{text}".into(),
                max_tokens: 1024,
            },
            translation: TaskTemplate {
                system: "".into(),
                user: "Translate to {target_language}:\n{text}".into(),
                max_tokens: 2048,
            },
            qa: TaskTemplate {
                system: "".into(),
                user: "Context: {context}\nQ: {question}".into(),
                max_tokens: 512,
            },
        };

        let vars: HashMap<&str, &str> =
            [("text", "Hello world")].into_iter().collect();

        let (system, user, max_tokens) =
            build_prompt(&templates, &LlmTaskType::Summary, &vars).unwrap();

        assert_eq!(system, "You are a summarizer.");
        assert_eq!(user, "Summarize: Hello world");
        assert_eq!(max_tokens, 256);
        assert!(!user.contains('{'), "no unresolved placeholders in user prompt");
    }

    #[test]
    fn test_build_prompt_translation_substitutes_language_and_text() {
        let templates = PromptTemplates {
            summary: TaskTemplate { system: "".into(), user: "{text}".into(), max_tokens: 1 },
            meeting_brief: TaskTemplate { system: "".into(), user: "{text}".into(), max_tokens: 1 },
            translation: TaskTemplate {
                system: "Translator".into(),
                user: "Translate to {target_language}:\n{text}".into(),
                max_tokens: 512,
            },
            qa: TaskTemplate { system: "".into(), user: "{context}{question}".into(), max_tokens: 1 },
        };

        let vars: HashMap<&str, &str> = [
            ("target_language", "Chinese"),
            ("text", "Good morning"),
        ]
        .into_iter()
        .collect();

        let task = LlmTaskType::Translation { target_language: "Chinese".into() };
        let (_, user, _) = build_prompt(&templates, &task, &vars).unwrap();

        assert_eq!(user, "Translate to Chinese:\nGood morning");
    }

    #[test]
    fn test_get_best_text_returns_highest_priority_role() {
        let assets = vec![
            ("summary".to_string(), "summary content".to_string()),
            ("transcript".to_string(), "transcript content".to_string()),
        ];
        assert_eq!(
            get_best_text(&assets, None),
            Some("transcript content")
        );
    }

    #[test]
    fn test_get_best_text_respects_role_hint() {
        let assets = vec![
            ("transcript".to_string(), "transcript content".to_string()),
            ("summary".to_string(), "summary content".to_string()),
        ];
        assert_eq!(
            get_best_text(&assets, Some("summary")),
            Some("summary content")
        );
    }

    #[test]
    fn test_get_best_text_empty_returns_none() {
        let assets: Vec<(String, String)> = vec![];
        assert_eq!(get_best_text(&assets, None), None);
    }
}
