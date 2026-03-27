use serde::{Deserialize, Serialize};
use specta::Type;
use std::collections::HashMap;

/// 数据库行：workspace_folders
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct WorkspaceFolder {
    pub id: String,
    pub parent_id: Option<String>,
    pub name: String,
    pub folder_kind: String,
    pub is_system: bool,
    pub created_at: i64,
}

/// 数据库行：workspace_documents（摘要字段）
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct WorkspaceDocumentRow {
    pub id: String,
    pub folder_id: Option<String>,
    pub title: String,
    pub file_path: Option<String>,
    pub content_text: Option<String>,
    pub source_type: String,
    pub recording_id: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// 数据库行：workspace_text_assets
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct WorkspaceTextAssetRow {
    pub id: String,
    pub document_id: String,
    pub role: String,
    pub language: Option<String>,
    pub content: String,
    pub file_path: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// 文件夹树节点（递归）
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct FolderNode {
    pub id: String,
    pub name: String,
    pub parent_id: Option<String>,
    pub folder_kind: String,
    pub is_system: bool,
    pub document_count: u32,
    pub children: Vec<FolderNode>,
}

/// 文档摘要（列表视图）
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct DocumentSummary {
    pub id: String,
    pub title: String,
    pub folder_id: Option<String>,
    pub source_type: String,
    pub has_transcript: bool,
    pub has_summary: bool,
    pub has_meeting_brief: bool,
    pub recording_id: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// 文本 Asset（IPC 传输用）
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct TextAsset {
    pub id: String,
    pub role: String,
    pub language: Option<String>,
    pub content: String,
    pub updated_at: i64,
}

/// 文档详情（含所有 assets）
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct DocumentDetail {
    pub id: String,
    pub title: String,
    pub folder_id: Option<String>,
    pub source_type: String,
    pub recording_id: Option<String>,
    pub assets: Vec<TextAsset>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// FTS5 搜索结果
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct SearchResult {
    pub document_id: String,
    pub title: String,
    pub snippet: String,
    pub rank: f64,
    pub folder_id: Option<String>,
    pub updated_at: i64,
}

/// PDF/DOCX/TXT/MD 解析结果
#[derive(Debug, Clone)]
pub struct ParsedDocument {
    pub title: String,
    pub text: String,
    pub metadata: HashMap<String, String>,
}
