# Workspace Document Library Implementation Plan (M6)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Workspace 文档库全栈功能，包含文件夹树 CRUD、文档 CRUD、全文搜索（FTS5）、多格式导出（MD/TXT/SRT/VTT）、PDF/DOCX 文件导入解析，以及配套的 React 前端（文件夹树面板、文档视图、搜索栏）。

**Architecture:** Rust 后端以 `workspace/manager.rs` 为核心，封装文件夹/文档的所有数据库操作，FTS5 由 SQLite trigger 自动维护（`0003_workspace_assets.sql`）；`workspace/parser.rs` 负责 PDF/DOCX/TXT/MD 文本提取并写入 `workspace_text_assets`；`workspace/exporter.rs` 处理 SRT/VTT 时间戳格式化（从 `transcription_segments` 读取）；前端 Zustand store `useWorkspaceStore` 管理文件夹树、打开的标签页和搜索状态，`WorkspacePanel` 渲染可折叠递归文件夹树，`WorkspaceMain` / `DocumentView` 渲染文档内容和 AI 操作区，`SearchBar` 提供 debounce 搜索并高亮片段。

**Tech Stack:** `sqlx 0.8`（SQLite FTS5）、`pdf-extract 0.7`、`docx-rs 0.4`、`uuid 1`、`thiserror 1`、`serde`/`serde_json`、React 18 + TypeScript + Zustand + TanStack Router + shadcn/ui + `use-debounce`

---

### Task 1: 数据库补充 Migration

**Files:**
- Create: `src-tauri/src/storage/migrations/0003_workspace_assets.sql`

- [ ] **Step 1.1: 创建 `workspace_text_assets` 表**

  ```sql
  -- 0003_workspace_assets.sql

  -- 文档文本 Asset 表（每个 document_id + role 唯一）
  CREATE TABLE workspace_text_assets (
      id          TEXT    PRIMARY KEY,
      document_id TEXT    NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
      role        TEXT    NOT NULL,   -- 'transcript'|'summary'|'meeting_brief'|'translation'
                                     -- |'document_text'|'decisions'|'action_items'|'next_steps'
      language    TEXT,
      content     TEXT    NOT NULL,
      file_path   TEXT,              -- 对应磁盘上的 .md 文件路径（可为 NULL）
      created_at  INTEGER NOT NULL,
      updated_at  INTEGER NOT NULL,
      UNIQUE(document_id, role)
  );
  CREATE INDEX idx_assets_doc ON workspace_text_assets(document_id, role);
  ```

- [ ] **Step 1.2: 添加 content_text 同步 trigger**

  当 `workspace_text_assets` 写入时，自动按优先级更新 `workspace_documents.content_text`（供 FTS5 虚表使用）。**应用层代码不直接写 `content_text`**。

  ```sql
  -- Trigger：asset 写入后自动同步 content_text（FTS5 索引源）
  -- 优先级：document_text(0) > transcript(1) > meeting_brief(2) > summary(3) > 其余(99)
  CREATE TRIGGER sync_content_text_on_asset_insert
  AFTER INSERT ON workspace_text_assets
  BEGIN
      UPDATE workspace_documents
      SET content_text = (
          SELECT content FROM workspace_text_assets
          WHERE document_id = NEW.document_id
          ORDER BY CASE role
              WHEN 'document_text' THEN 0
              WHEN 'transcript'    THEN 1
              WHEN 'meeting_brief' THEN 2
              WHEN 'summary'       THEN 3
              ELSE 99 END
          LIMIT 1
      )
      WHERE id = NEW.document_id;
  END;

  CREATE TRIGGER sync_content_text_on_asset_update
  AFTER UPDATE ON workspace_text_assets
  BEGIN
      UPDATE workspace_documents
      SET content_text = (
          SELECT content FROM workspace_text_assets
          WHERE document_id = NEW.document_id
          ORDER BY CASE role
              WHEN 'document_text' THEN 0
              WHEN 'transcript'    THEN 1
              WHEN 'meeting_brief' THEN 2
              WHEN 'summary'       THEN 3
              ELSE 99 END
          LIMIT 1
      )
      WHERE id = NEW.document_id;
  END;
  ```

- [ ] **Step 1.3: 添加 FTS5 自动维护 trigger**

  `workspace_fts` 虚表基于 `content=workspace_documents`，需要 trigger 手动同步（SQLite content table 模式要求显式维护）。

  ```sql
  -- FTS5 自动维护 trigger
  CREATE TRIGGER fts_docs_insert
  AFTER INSERT ON workspace_documents
  BEGIN
      INSERT INTO workspace_fts(rowid, title, content_text)
      VALUES (NEW.rowid, NEW.title, NEW.content_text);
  END;

  CREATE TRIGGER fts_docs_update
  AFTER UPDATE ON workspace_documents
  BEGIN
      DELETE FROM workspace_fts WHERE rowid = OLD.rowid;
      INSERT INTO workspace_fts(rowid, title, content_text)
      VALUES (NEW.rowid, NEW.title, NEW.content_text);
  END;

  CREATE TRIGGER fts_docs_delete
  AFTER DELETE ON workspace_documents
  BEGIN
      DELETE FROM workspace_fts WHERE rowid = OLD.rowid;
  END;
  ```

- [ ] **Step 1.4: 注册 migration 到 db.rs**

  在 `src-tauri/src/storage/db.rs` 的 `sqlx::migrate!("src/storage/migrations")` 宏覆盖范围内确认 `0003_workspace_assets.sql` 会被自动执行（无需手动改代码，sqlx migrate! 按文件名升序执行所有 .sql）。

- [ ] **Step 1.5: Commit**

  ```
  feat(db): add workspace_text_assets table and FTS5 sync triggers (migration 0003)
  ```

---

### Task 2: `workspace/document.rs` — 数据结构定义

**Files:**
- Create: `src-tauri/src/workspace/document.rs`
- Modify: `src-tauri/src/workspace/mod.rs`

- [ ] **Step 2.1: 定义核心结构体（与 sqlx query_as! 映射）**

  所有字段名称与数据库列名一一对应，便于 `sqlx::query_as!` 直接映射。

  ```rust
  // src-tauri/src/workspace/document.rs

  use serde::{Deserialize, Serialize};
  use specta::Type;
  use std::collections::HashMap;

  // ─── 数据库映射结构体（与 sqlx query_as! 配合使用）────────────────────────

  /// 数据库行：workspace_folders
  #[derive(Debug, Clone, sqlx::FromRow)]
  pub struct WorkspaceFolder {
      pub id:          String,
      pub parent_id:   Option<String>,
      pub name:        String,
      pub folder_kind: String,   // 'user'|'inbox'|'system_root'|'event'|'batch_task'
      pub is_system:   bool,
      pub created_at:  i64,
  }

  /// 数据库行：workspace_documents（摘要字段）
  #[derive(Debug, Clone, sqlx::FromRow)]
  pub struct WorkspaceDocumentRow {
      pub id:           String,
      pub folder_id:    Option<String>,
      pub title:        String,
      pub file_path:    Option<String>,
      pub content_text: Option<String>,
      pub source_type:  String,
      pub recording_id: Option<String>,
      pub created_at:   i64,
      pub updated_at:   i64,
  }

  /// 数据库行：workspace_text_assets
  #[derive(Debug, Clone, sqlx::FromRow)]
  pub struct WorkspaceTextAssetRow {
      pub id:          String,
      pub document_id: String,
      pub role:        String,
      pub language:    Option<String>,
      pub content:     String,
      pub file_path:   Option<String>,
      pub created_at:  i64,
      pub updated_at:  i64,
  }

  // ─── IPC 传输结构体（Serialize + specta::Type，暴露给前端）────────────────

  /// 文件夹树节点（递归，children 包含子节点）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct FolderNode {
      pub id:             String,
      pub name:           String,
      pub parent_id:      Option<String>,
      pub folder_kind:    String,
      pub is_system:      bool,
      pub document_count: u32,
      pub children:       Vec<FolderNode>,
  }

  /// 文档摘要（列表视图）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct DocumentSummary {
      pub id:                String,
      pub title:             String,
      pub folder_id:         Option<String>,
      pub source_type:       String,
      pub has_transcript:    bool,
      pub has_summary:       bool,
      pub has_meeting_brief: bool,
      pub recording_id:      Option<String>,
      pub created_at:        i64,
      pub updated_at:        i64,
  }

  /// 文本 Asset（IPC 传输用）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct TextAsset {
      pub id:         String,
      pub role:       String,
      pub language:   Option<String>,
      pub content:    String,
      pub updated_at: i64,
  }

  /// 文档详情（含所有 assets）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct DocumentDetail {
      pub id:           String,
      pub title:        String,
      pub folder_id:    Option<String>,
      pub source_type:  String,
      pub recording_id: Option<String>,
      pub assets:       Vec<TextAsset>,
      pub created_at:   i64,
      pub updated_at:   i64,
  }

  /// FTS5 搜索结果
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct SearchResult {
      pub document_id: String,
      pub title:       String,
      pub snippet:     String,   // FTS5 highlight/snippet 结果
      pub rank:        f64,
      pub folder_id:   Option<String>,
      pub updated_at:  i64,
  }

  // ─── parser.rs 返回类型 ───────────────────────────────────────────────────

  /// PDF/DOCX/TXT/MD 解析结果
  #[derive(Debug, Clone)]
  pub struct ParsedDocument {
      pub title:    String,
      pub text:     String,
      pub metadata: HashMap<String, String>,
  }
  ```

- [ ] **Step 2.2: 在 `workspace/mod.rs` 导出子模块**

  ```rust
  // src-tauri/src/workspace/mod.rs
  pub mod document;
  pub mod manager;
  pub mod parser;
  pub mod exporter;   // Task 4 中创建
  ```

- [ ] **Step 2.3: Commit**

  ```
  feat(workspace): add domain types in document.rs (FolderNode, DocumentDetail, SearchResult)
  ```

---

### Task 3: `workspace/manager.rs` — 文件夹与文档 CRUD + FTS5 搜索

**Files:**
- Create: `src-tauri/src/workspace/manager.rs`

- [ ] **Step 3.1: 文件夹 CRUD**

  ```rust
  // src-tauri/src/workspace/manager.rs

  use crate::error::AppError;
  use crate::workspace::document::*;
  use sqlx::SqlitePool;
  use uuid::Uuid;

  pub struct WorkspaceManager {
      pool: SqlitePool,
  }

  impl WorkspaceManager {
      pub fn new(pool: SqlitePool) -> Self {
          Self { pool }
      }

      /// 创建文件夹（用户文件夹，folder_kind='user'）
      /// 校验：名称非空，不含 /\:*?"<>|，同一父文件夹下无同名文件夹
      pub async fn create_folder(
          &self,
          name: &str,
          parent_id: Option<&str>,
      ) -> Result<FolderNode, AppError> {
          validate_folder_name(name)?;
          self.check_duplicate_name(parent_id, name, None).await?;

          let id = Uuid::new_v4().to_string();
          let now = now_ms();

          sqlx::query!(
              "INSERT INTO workspace_folders (id, parent_id, name, folder_kind, is_system, created_at)
               VALUES (?, ?, ?, 'user', 0, ?)",
              id, parent_id, name, now
          )
          .execute(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          Ok(FolderNode {
              id,
              name: name.to_string(),
              parent_id: parent_id.map(str::to_string),
              folder_kind: "user".to_string(),
              is_system: false,
              document_count: 0,
              children: vec![],
          })
      }

      /// 重命名文件夹（系统文件夹不可操作）
      pub async fn rename_folder(&self, id: &str, name: &str) -> Result<(), AppError> {
          let folder = self.get_folder_row(id).await?;
          if folder.is_system {
              return Err(AppError::Validation("workspace.system_folder_immutable".to_string()));
          }
          validate_folder_name(name)?;
          self.check_duplicate_name(folder.parent_id.as_deref(), name, Some(id)).await?;

          sqlx::query!("UPDATE workspace_folders SET name = ? WHERE id = ?", name, id)
              .execute(&self.pool)
              .await
              .map_err(|e| AppError::Storage(e.to_string()))?;
          Ok(())
      }

      /// 删除文件夹（递归删除子文件夹和子文档，依赖 ON DELETE CASCADE）
      /// 系统文件夹不可删除
      pub async fn delete_folder(&self, id: &str) -> Result<(), AppError> {
          let folder = self.get_folder_row(id).await?;
          if folder.is_system {
              return Err(AppError::Validation("workspace.system_folder_immutable".to_string()));
          }
          // SQLite ON DELETE CASCADE 会递归删除子文件夹（ON DELETE CASCADE 在 workspace_folders
          // 表的 parent_id 外键上），以及每个文件夹下的文档（workspace_documents.folder_id
          // 是 ON DELETE SET NULL，不级联删除文档本身）。
          // 因此需要先手动递归收集所有子孙文件夹 ID，批量删除文档，再删除文件夹。
          let descendant_ids = self.collect_descendant_folder_ids(id).await?;
          let mut tx = self.pool.begin().await.map_err(|e| AppError::Storage(e.to_string()))?;

          // 删除所有子孙文件夹下的文档（含级联 assets / llm_tasks）
          for fid in &descendant_ids {
              sqlx::query!("DELETE FROM workspace_documents WHERE folder_id = ?", fid)
                  .execute(&mut *tx)
                  .await
                  .map_err(|e| AppError::Storage(e.to_string()))?;
          }
          // 删除目标文件夹下的文档
          sqlx::query!("DELETE FROM workspace_documents WHERE folder_id = ?", id)
              .execute(&mut *tx)
              .await
              .map_err(|e| AppError::Storage(e.to_string()))?;

          // 删除文件夹本身（ON DELETE CASCADE 自动删除子文件夹）
          sqlx::query!("DELETE FROM workspace_folders WHERE id = ?", id)
              .execute(&mut *tx)
              .await
              .map_err(|e| AppError::Storage(e.to_string()))?;

          tx.commit().await.map_err(|e| AppError::Storage(e.to_string()))?;
          Ok(())
      }

      /// 返回完整文件夹树（含 document_count）
      pub async fn list_folders(&self) -> Result<Vec<FolderNode>, AppError> {
          let rows = sqlx::query_as!(
              WorkspaceFolder,
              "SELECT id, parent_id, name, folder_kind, is_system as \"is_system: bool\", created_at
               FROM workspace_folders ORDER BY name ASC"
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          // 统计每个 folder 的文档数
          let counts = sqlx::query!("SELECT folder_id, COUNT(*) as cnt FROM workspace_documents GROUP BY folder_id")
              .fetch_all(&self.pool)
              .await
              .map_err(|e| AppError::Storage(e.to_string()))?;
          let count_map: std::collections::HashMap<String, u32> = counts
              .into_iter()
              .filter_map(|r| r.folder_id.map(|fid| (fid, r.cnt as u32)))
              .collect();

          // 构建树形结构
          build_folder_tree(rows, &count_map, None)
      }

      // ─── 内部辅助方法 ────────────────────────────────────────────────────

      async fn get_folder_row(&self, id: &str) -> Result<WorkspaceFolder, AppError> {
          sqlx::query_as!(
              WorkspaceFolder,
              "SELECT id, parent_id, name, folder_kind, is_system as \"is_system: bool\", created_at
               FROM workspace_folders WHERE id = ?",
              id
          )
          .fetch_optional(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?
          .ok_or_else(|| AppError::NotFound(format!("folder {id}")))
      }

      async fn check_duplicate_name(
          &self,
          parent_id: Option<&str>,
          name: &str,
          exclude_id: Option<&str>,
      ) -> Result<(), AppError> {
          let existing = sqlx::query!(
              "SELECT id FROM workspace_folders WHERE parent_id IS ? AND name = ? AND id != ?",
              parent_id,
              name,
              exclude_id.unwrap_or("")
          )
          .fetch_optional(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          if existing.is_some() {
              return Err(AppError::Validation("workspace.duplicate_name".to_string()));
          }
          Ok(())
      }

      /// 递归收集某文件夹的所有子孙 folder ID（不含自身）
      async fn collect_descendant_folder_ids(&self, root_id: &str) -> Result<Vec<String>, AppError> {
          // 使用 SQLite 递归 CTE
          let rows = sqlx::query!(
              "WITH RECURSIVE sub(id) AS (
                 SELECT id FROM workspace_folders WHERE parent_id = ?
                 UNION ALL
                 SELECT f.id FROM workspace_folders f JOIN sub s ON f.parent_id = s.id
               )
               SELECT id FROM sub",
              root_id
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          Ok(rows.into_iter().map(|r| r.id).collect())
      }
  }

  // ─── 文档 CRUD ──────────────────────────────────────────────────────────

  impl WorkspaceManager {
      pub async fn create_document(
          &self,
          title: &str,
          folder_id: Option<&str>,
          source_type: &str,
          recording_id: Option<&str>,
      ) -> Result<DocumentSummary, AppError> {
          if title.is_empty() || title.len() > 255 {
              return Err(AppError::Validation("workspace.invalid_title".to_string()));
          }
          let id = Uuid::new_v4().to_string();
          let now = now_ms();

          sqlx::query!(
              "INSERT INTO workspace_documents (id, folder_id, title, source_type, recording_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)",
              id, folder_id, title, source_type, recording_id, now, now
          )
          .execute(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          Ok(DocumentSummary {
              id,
              title: title.to_string(),
              folder_id: folder_id.map(str::to_string),
              source_type: source_type.to_string(),
              has_transcript: false,
              has_summary: false,
              has_meeting_brief: false,
              recording_id: recording_id.map(str::to_string),
              created_at: now,
              updated_at: now,
          })
      }

      pub async fn get_document(&self, id: &str) -> Result<DocumentDetail, AppError> {
          let doc = sqlx::query_as!(
              WorkspaceDocumentRow,
              "SELECT id, folder_id, title, file_path, content_text, source_type, recording_id,
                      created_at, updated_at
               FROM workspace_documents WHERE id = ?",
              id
          )
          .fetch_optional(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?
          .ok_or_else(|| AppError::NotFound(format!("document {id}")))?;

          let asset_rows = sqlx::query_as!(
              WorkspaceTextAssetRow,
              "SELECT id, document_id, role, language, content, file_path, created_at, updated_at
               FROM workspace_text_assets WHERE document_id = ? ORDER BY created_at ASC",
              id
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          let assets = asset_rows
              .into_iter()
              .map(|r| TextAsset {
                  id: r.id,
                  role: r.role,
                  language: r.language,
                  content: r.content,
                  updated_at: r.updated_at,
              })
              .collect();

          Ok(DocumentDetail {
              id: doc.id,
              title: doc.title,
              folder_id: doc.folder_id,
              source_type: doc.source_type,
              recording_id: doc.recording_id,
              assets,
              created_at: doc.created_at,
              updated_at: doc.updated_at,
          })
      }

      /// 更新文档标题
      pub async fn update_document_title(&self, id: &str, title: &str) -> Result<(), AppError> {
          if title.is_empty() || title.len() > 255 {
              return Err(AppError::Validation("workspace.invalid_title".to_string()));
          }
          let now = now_ms();
          sqlx::query!(
              "UPDATE workspace_documents SET title = ?, updated_at = ? WHERE id = ?",
              title, now, id
          )
          .execute(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;
          Ok(())
      }

      /// 写入或更新文档某个 role 的 asset 内容（UPSERT）
      pub async fn upsert_text_asset(
          &self,
          document_id: &str,
          role: &str,
          content: &str,
          language: Option<&str>,
      ) -> Result<String, AppError> {
          let id = Uuid::new_v4().to_string();
          let now = now_ms();

          sqlx::query!(
              "INSERT INTO workspace_text_assets (id, document_id, role, language, content, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(document_id, role) DO UPDATE SET content = excluded.content,
               language = excluded.language, updated_at = excluded.updated_at",
              id, document_id, role, language, content, now, now
          )
          .execute(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          // 同步更新文档 updated_at
          sqlx::query!(
              "UPDATE workspace_documents SET updated_at = ? WHERE id = ?",
              now, document_id
          )
          .execute(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          Ok(id)
      }

      /// 删除文档（级联删除 workspace_text_assets + llm_tasks，由 ON DELETE CASCADE 保证）
      pub async fn delete_document(&self, id: &str) -> Result<(), AppError> {
          let affected = sqlx::query!("DELETE FROM workspace_documents WHERE id = ?", id)
              .execute(&self.pool)
              .await
              .map_err(|e| AppError::Storage(e.to_string()))?
              .rows_affected();

          if affected == 0 {
              return Err(AppError::NotFound(format!("document {id}")));
          }
          Ok(())
      }

      /// 列出某文件夹下的所有文档（含 has_* flags）
      pub async fn list_documents_in_folder(
          &self,
          folder_id: Option<&str>,
      ) -> Result<Vec<DocumentSummary>, AppError> {
          let rows = sqlx::query_as!(
              WorkspaceDocumentRow,
              "SELECT id, folder_id, title, file_path, content_text, source_type, recording_id,
                      created_at, updated_at
               FROM workspace_documents WHERE folder_id IS ? ORDER BY updated_at DESC",
              folder_id
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          let mut summaries = Vec::with_capacity(rows.len());
          for doc in rows {
              let (has_transcript, has_summary, has_meeting_brief) =
                  self.fetch_asset_flags(&doc.id).await?;
              summaries.push(DocumentSummary {
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
          Ok(summaries)
      }

      async fn fetch_asset_flags(&self, doc_id: &str) -> Result<(bool, bool, bool), AppError> {
          let roles = sqlx::query!(
              "SELECT role FROM workspace_text_assets WHERE document_id = ?",
              doc_id
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          let has_transcript    = roles.iter().any(|r| r.role == "transcript");
          let has_summary       = roles.iter().any(|r| r.role == "summary");
          let has_meeting_brief = roles.iter().any(|r| r.role == "meeting_brief");
          Ok((has_transcript, has_summary, has_meeting_brief))
      }
  }

  // ─── FTS5 全文搜索 ────────────────────────────────────────────────────────

  impl WorkspaceManager {
      /// FTS5 全文搜索，返回高亮 snippet（最多 20 条）
      pub async fn search_documents(&self, query: &str) -> Result<Vec<SearchResult>, AppError> {
          if query.trim().is_empty() {
              return Ok(vec![]);
          }
          // FTS5 snippet()：高亮标签用 <mark>，窗口 64 token
          // bm25() 排名：rank 越小越相关（负数），ORDER BY rank ASC
          let rows = sqlx::query!(
              r#"SELECT
                  d.id as document_id,
                  d.title,
                  d.folder_id,
                  d.updated_at,
                  snippet(workspace_fts, 1, '<mark>', '</mark>', '…', 64) as snippet,
                  workspace_fts.rank
               FROM workspace_fts
               JOIN workspace_documents d ON workspace_fts.rowid = d.rowid
               WHERE workspace_fts MATCH ?
               ORDER BY rank
               LIMIT 20"#,
              query
          )
          .fetch_all(&self.pool)
          .await
          .map_err(|e| AppError::Storage(e.to_string()))?;

          Ok(rows
              .into_iter()
              .map(|r| SearchResult {
                  document_id: r.document_id,
                  title: r.title,
                  snippet: r.snippet.unwrap_or_default(),
                  rank: r.rank.unwrap_or(0.0),
                  folder_id: r.folder_id,
                  updated_at: r.updated_at,
              })
              .collect())
      }
  }

  // ─── 辅助函数 ─────────────────────────────────────────────────────────────

  fn now_ms() -> i64 {
      std::time::SystemTime::now()
          .duration_since(std::time::UNIX_EPOCH)
          .unwrap_or_default()
          .as_millis() as i64
  }

  fn validate_folder_name(name: &str) -> Result<(), AppError> {
      if name.is_empty() {
          return Err(AppError::Validation("workspace.invalid_name".to_string()));
      }
      let invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|'];
      if name.chars().any(|c| invalid_chars.contains(&c)) {
          return Err(AppError::Validation("workspace.invalid_name".to_string()));
      }
      Ok(())
  }

  /// 从扁平列表递归构建树（root level = parent_id IS NULL）
  fn build_folder_tree(
      rows: Vec<WorkspaceFolder>,
      count_map: &std::collections::HashMap<String, u32>,
      parent_id: Option<&str>,
  ) -> Result<Vec<FolderNode>, AppError> {
      let mut nodes = Vec::new();
      for row in rows.iter().filter(|r| r.parent_id.as_deref() == parent_id) {
          let children = build_folder_tree(rows.clone(), count_map, Some(&row.id))?;
          nodes.push(FolderNode {
              id: row.id.clone(),
              name: row.name.clone(),
              parent_id: row.parent_id.clone(),
              folder_kind: row.folder_kind.clone(),
              is_system: row.is_system,
              document_count: count_map.get(&row.id).copied().unwrap_or(0),
              children,
          });
      }
      Ok(nodes)
  }
  ```

- [ ] **Step 3.2: Commit**

  ```
  feat(workspace): implement WorkspaceManager with folder/document CRUD and FTS5 search
  ```

---

### Task 4: `workspace/exporter.rs` — SRT/VTT/MD/TXT 导出

**Files:**
- Create: `src-tauri/src/workspace/exporter.rs`

- [ ] **Step 4.1: 时间戳格式化辅助函数**

  SRT 用 `HH:MM:SS,mmm`（逗号分隔毫秒），VTT 用 `HH:MM:SS.mmm`（点分隔毫秒）。

  ```rust
  // src-tauri/src/workspace/exporter.rs

  use crate::error::AppError;
  use sqlx::SqlitePool;
  use std::path::Path;
  use tokio::fs;

  /// 将毫秒整数转为 SRT 时间戳格式：HH:MM:SS,mmm
  pub fn ms_to_srt_timestamp(ms: i64) -> String {
      let total_secs = ms / 1000;
      let millis     = ms % 1000;
      let hours      = total_secs / 3600;
      let minutes    = (total_secs % 3600) / 60;
      let secs       = total_secs % 60;
      format!("{:02}:{:02}:{:02},{:03}", hours, minutes, secs, millis)
  }

  /// 将毫秒整数转为 VTT 时间戳格式：HH:MM:SS.mmm
  pub fn ms_to_vtt_timestamp(ms: i64) -> String {
      let total_secs = ms / 1000;
      let millis     = ms % 1000;
      let hours      = total_secs / 3600;
      let minutes    = (total_secs % 3600) / 60;
      let secs       = total_secs % 60;
      format!("{:02}:{:02}:{:02}.{:03}", hours, minutes, secs, millis)
  }
  ```

- [ ] **Step 4.2: SRT 导出**

  从 `transcription_segments` 表读取时间戳，通过 `workspace_documents.recording_id` 关联。

  ```rust
  pub async fn export_as_srt(
      pool: &SqlitePool,
      document_id: &str,
      target_path: &Path,
  ) -> Result<(), AppError> {
      let recording_id = sqlx::query!(
          "SELECT recording_id FROM workspace_documents WHERE id = ?",
          document_id
      )
      .fetch_optional(pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?
      .and_then(|r| r.recording_id)
      .ok_or_else(|| AppError::Validation("document has no associated recording".to_string()))?;

      let segments = sqlx::query!(
          "SELECT start_ms, end_ms, text FROM transcription_segments
           WHERE recording_id = ? ORDER BY start_ms ASC",
          recording_id
      )
      .fetch_all(pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      let mut srt = String::new();
      for (i, seg) in segments.iter().enumerate() {
          srt.push_str(&format!(
              "{}\n{} --> {}\n{}\n\n",
              i + 1,
              ms_to_srt_timestamp(seg.start_ms as i64),
              ms_to_srt_timestamp(seg.end_ms as i64),
              seg.text.trim()
          ));
      }

      fs::write(target_path, srt).await.map_err(|e| AppError::Io(e.to_string()))
  }
  ```

- [ ] **Step 4.3: VTT 导出**

  与 SRT 相同逻辑，首行固定为 `WEBVTT`，时间戳用点分隔毫秒。

  ```rust
  pub async fn export_as_vtt(
      pool: &SqlitePool,
      document_id: &str,
      target_path: &Path,
  ) -> Result<(), AppError> {
      let recording_id = sqlx::query!(
          "SELECT recording_id FROM workspace_documents WHERE id = ?",
          document_id
      )
      .fetch_optional(pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?
      .and_then(|r| r.recording_id)
      .ok_or_else(|| AppError::Validation("document has no associated recording".to_string()))?;

      let segments = sqlx::query!(
          "SELECT start_ms, end_ms, text FROM transcription_segments
           WHERE recording_id = ? ORDER BY start_ms ASC",
          recording_id
      )
      .fetch_all(pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      let mut vtt = String::from("WEBVTT\n\n");
      for (i, seg) in segments.iter().enumerate() {
          vtt.push_str(&format!(
              "{}\n{} --> {}\n{}\n\n",
              i + 1,
              ms_to_vtt_timestamp(seg.start_ms as i64),
              ms_to_vtt_timestamp(seg.end_ms as i64),
              seg.text.trim()
          ));
      }

      fs::write(target_path, vtt).await.map_err(|e| AppError::Io(e.to_string()))
  }
  ```

- [ ] **Step 4.4: Markdown 和 TXT 导出**

  从 `workspace_text_assets` 读取优先级最高的 asset 内容。

  ```rust
  /// 导出为 Markdown（保留原始 asset 内容，有多个 role 时按优先级选择）
  pub async fn export_as_markdown(
      pool: &SqlitePool,
      document_id: &str,
      target_path: &Path,
  ) -> Result<(), AppError> {
      let content = fetch_best_text(pool, document_id).await?;
      fs::write(target_path, content).await.map_err(|e| AppError::Io(e.to_string()))
  }

  /// 导出为纯文本（去掉 Markdown 标记——简单替换即可，不引入额外 crate）
  pub async fn export_as_txt(
      pool: &SqlitePool,
      document_id: &str,
      target_path: &Path,
  ) -> Result<(), AppError> {
      let content = fetch_best_text(pool, document_id).await?;
      // 简单去除 Markdown 标题 '#'、粗体 '**'、下划线 '__'
      let plain = content
          .lines()
          .map(|l| l.trim_start_matches('#').trim())
          .collect::<Vec<_>>()
          .join("\n");
      let plain = plain.replace("**", "").replace("__", "");
      fs::write(target_path, plain).await.map_err(|e| AppError::Io(e.to_string()))
  }

  /// 按优先级取最佳文本 asset：document_text > transcript > meeting_brief > summary
  async fn fetch_best_text(pool: &SqlitePool, document_id: &str) -> Result<String, AppError> {
      let row = sqlx::query!(
          r#"SELECT content FROM workspace_text_assets
             WHERE document_id = ?
             ORDER BY CASE role
                 WHEN 'document_text' THEN 0
                 WHEN 'transcript'    THEN 1
                 WHEN 'meeting_brief' THEN 2
                 WHEN 'summary'       THEN 3
                 ELSE 99 END
             LIMIT 1"#,
          document_id
      )
      .fetch_optional(pool)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      row.map(|r| r.content)
          .ok_or_else(|| AppError::NotFound(format!("no text asset for document {document_id}")))
  }
  ```

- [ ] **Step 4.5: Commit**

  ```
  feat(workspace): implement exporter for SRT/VTT/MD/TXT with timestamp formatting
  ```

---

### Task 5: `workspace/parser.rs` — PDF/DOCX/TXT/MD 文件解析

**Files:**
- Create: `src-tauri/src/workspace/parser.rs`
- Modify: `src-tauri/Cargo.toml`

- [ ] **Step 5.1: 添加 Cargo 依赖**

  在 `src-tauri/Cargo.toml` 的 `[dependencies]` 中添加：

  ```toml
  pdf-extract = "0.7"
  docx-rs     = "0.4"
  ```

- [ ] **Step 5.2: 实现 parser.rs**

  ```rust
  // src-tauri/src/workspace/parser.rs

  use crate::error::AppError;
  use crate::workspace::document::ParsedDocument;
  use std::collections::HashMap;
  use std::path::Path;

  /// 根据文件扩展名分发到对应解析器
  pub fn parse_file(file_path: &Path) -> Result<ParsedDocument, AppError> {
      let ext = file_path
          .extension()
          .and_then(|e| e.to_str())
          .map(|e| e.to_lowercase())
          .unwrap_or_default();

      match ext.as_str() {
          "pdf"        => parse_pdf(file_path),
          "docx"       => parse_docx(file_path),
          "txt" | "md" => parse_text(file_path),
          _            => Err(AppError::Workspace(format!("unsupported file type: .{ext}"))),
      }
  }

  /// PDF 文本提取（pdf-extract crate）
  fn parse_pdf(path: &Path) -> Result<ParsedDocument, AppError> {
      let bytes = std::fs::read(path).map_err(|e| AppError::Io(e.to_string()))?;
      let text  = pdf_extract::extract_text_from_mem(&bytes)
          .map_err(|e| AppError::Workspace(format!("pdf parse error: {e}")))?;

      let title = path
          .file_stem()
          .and_then(|s| s.to_str())
          .unwrap_or("Untitled")
          .to_string();

      let mut metadata = HashMap::new();
      metadata.insert("source".to_string(), "pdf".to_string());
      metadata.insert("file_path".to_string(), path.to_string_lossy().to_string());

      Ok(ParsedDocument { title, text, metadata })
  }

  /// DOCX 段落文本提取（docx-rs crate，只读段落，忽略表格/图片）
  fn parse_docx(path: &Path) -> Result<ParsedDocument, AppError> {
      use docx_rs::*;
      let bytes = std::fs::read(path).map_err(|e| AppError::Io(e.to_string()))?;
      let docx  = read_docx(&bytes)
          .map_err(|e| AppError::Workspace(format!("docx parse error: {e:?}")))?;

      // 递归提取所有段落文本
      let mut lines = Vec::new();
      for child in &docx.document.children {
          if let DocumentChild::Paragraph(para) = child {
              let mut line = String::new();
              for run in &para.children {
                  if let ParagraphChild::Run(r) = run {
                      for rc in &r.children {
                          if let RunChild::Text(t) = rc {
                              line.push_str(&t.text);
                          }
                      }
                  }
              }
              if !line.is_empty() {
                  lines.push(line);
              }
          }
      }
      let text  = lines.join("\n");
      let title = path
          .file_stem()
          .and_then(|s| s.to_str())
          .unwrap_or("Untitled")
          .to_string();

      let mut metadata = HashMap::new();
      metadata.insert("source".to_string(), "docx".to_string());

      Ok(ParsedDocument { title, text, metadata })
  }

  /// TXT/MD 直接读取（UTF-8）
  fn parse_text(path: &Path) -> Result<ParsedDocument, AppError> {
      let text  = std::fs::read_to_string(path).map_err(|e| AppError::Io(e.to_string()))?;
      let ext   = path.extension().and_then(|e| e.to_str()).unwrap_or("txt").to_lowercase();
      let title = path
          .file_stem()
          .and_then(|s| s.to_str())
          .unwrap_or("Untitled")
          .to_string();

      let mut metadata = HashMap::new();
      metadata.insert("source".to_string(), ext);

      Ok(ParsedDocument { title, text, metadata })
  }
  ```

- [ ] **Step 5.3: Commit**

  ```
  feat(workspace): implement file parser for PDF/DOCX/TXT/MD with pdf-extract and docx-rs
  ```

---

### Task 6: `commands/workspace.rs` — Tauri IPC 命令层

**Files:**
- Create: `src-tauri/src/commands/workspace.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 6.1: 文件夹命令**

  ```rust
  // src-tauri/src/commands/workspace.rs

  use crate::error::AppError;
  use crate::state::AppState;
  use crate::workspace::document::*;
  use crate::workspace::{exporter, parser};
  use tauri::State;

  // ─── 文件夹命令 ──────────────────────────────────────────────────────────

  #[tauri::command]
  #[specta::specta]
  pub async fn list_folder_tree(
      state: State<'_, AppState>,
  ) -> Result<Vec<FolderNode>, AppError> {
      state.workspace_manager.list_folders().await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn create_folder(
      state: State<'_, AppState>,
      name: String,
      parent_id: Option<String>,
  ) -> Result<FolderNode, AppError> {
      state.workspace_manager
          .create_folder(&name, parent_id.as_deref())
          .await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn rename_folder(
      state: State<'_, AppState>,
      id: String,
      name: String,
  ) -> Result<(), AppError> {
      state.workspace_manager.rename_folder(&id, &name).await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn delete_folder(
      state: State<'_, AppState>,
      id: String,
  ) -> Result<(), AppError> {
      state.workspace_manager.delete_folder(&id).await
  }
  ```

- [ ] **Step 6.2: 文档命令**

  ```rust
  // ─── 文档命令 ────────────────────────────────────────────────────────────

  #[tauri::command]
  #[specta::specta]
  pub async fn list_documents_in_folder(
      state: State<'_, AppState>,
      folder_id: Option<String>,
  ) -> Result<Vec<DocumentSummary>, AppError> {
      state.workspace_manager
          .list_documents_in_folder(folder_id.as_deref())
          .await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn get_document(
      state: State<'_, AppState>,
      id: String,
  ) -> Result<DocumentDetail, AppError> {
      state.workspace_manager.get_document(&id).await
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn create_document(
      state: State<'_, AppState>,
      title: String,
      folder_id: Option<String>,
      content: String,
  ) -> Result<DocumentSummary, AppError> {
      let summary = state.workspace_manager
          .create_document(&title, folder_id.as_deref(), "note", None)
          .await?;

      if !content.is_empty() {
          state.workspace_manager
              .upsert_text_asset(&summary.id, "document_text", &content, None)
              .await?;
      }
      Ok(summary)
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn update_document(
      state: State<'_, AppState>,
      id: String,
      title: Option<String>,
      role: Option<String>,
      content: Option<String>,
  ) -> Result<(), AppError> {
      if let Some(t) = &title {
          state.workspace_manager.update_document_title(&id, t).await?;
      }
      if let (Some(r), Some(c)) = (&role, &content) {
          state.workspace_manager.upsert_text_asset(&id, r, c, None).await?;
      }
      Ok(())
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn delete_document(
      state: State<'_, AppState>,
      id: String,
  ) -> Result<(), AppError> {
      state.workspace_manager.delete_document(&id).await
  }
  ```

- [ ] **Step 6.3: 搜索、导出、导入命令**

  ```rust
  // ─── 搜索 ────────────────────────────────────────────────────────────────

  #[tauri::command]
  #[specta::specta]
  pub async fn search_workspace(
      state: State<'_, AppState>,
      query: String,
  ) -> Result<Vec<SearchResult>, AppError> {
      state.workspace_manager.search_documents(&query).await
  }

  // ─── 导出 ────────────────────────────────────────────────────────────────

  /// format: "md" | "txt" | "srt" | "vtt"
  #[tauri::command]
  #[specta::specta]
  pub async fn export_document(
      state: State<'_, AppState>,
      id: String,
      format: String,
      target_path: String,
  ) -> Result<(), AppError> {
      let path = std::path::Path::new(&target_path);
      match format.as_str() {
          "md"  => exporter::export_as_markdown(&state.pool, &id, path).await,
          "txt" => exporter::export_as_txt(&state.pool, &id, path).await,
          "srt" => exporter::export_as_srt(&state.pool, &id, path).await,
          "vtt" => exporter::export_as_vtt(&state.pool, &id, path).await,
          _     => Err(AppError::Validation(format!("unknown export format: {format}"))),
      }
  }

  // ─── 导入 ────────────────────────────────────────────────────────────────

  /// 解析 PDF/DOCX/TXT/MD 文件并写入 workspace_documents + workspace_text_assets
  #[tauri::command]
  #[specta::specta]
  pub async fn import_file_to_workspace(
      state: State<'_, AppState>,
      file_path: String,
      folder_id: Option<String>,
  ) -> Result<DocumentSummary, AppError> {
      let path   = std::path::Path::new(&file_path);
      let parsed = tokio::task::spawn_blocking({
          let path = path.to_path_buf();
          move || parser::parse_file(&path)
      })
      .await
      .map_err(|e| AppError::Io(e.to_string()))??;

      let summary = state.workspace_manager
          .create_document(&parsed.title, folder_id.as_deref(), "import", None)
          .await?;

      state.workspace_manager
          .upsert_text_asset(&summary.id, "document_text", &parsed.text, None)
          .await?;

      Ok(summary)
  }
  ```

- [ ] **Step 6.4: 注册命令到 `commands/mod.rs` 和 `lib.rs`**

  在 `src-tauri/src/commands/mod.rs` 中添加：
  ```rust
  pub mod workspace;
  ```

  在 `src-tauri/src/lib.rs` 的 `tauri::Builder` handler 列表中追加所有 workspace 命令：
  ```rust
  .invoke_handler(tauri::generate_handler![
      // ... 已有命令 ...
      commands::workspace::list_folder_tree,
      commands::workspace::create_folder,
      commands::workspace::rename_folder,
      commands::workspace::delete_folder,
      commands::workspace::list_documents_in_folder,
      commands::workspace::get_document,
      commands::workspace::create_document,
      commands::workspace::update_document,
      commands::workspace::delete_document,
      commands::workspace::search_workspace,
      commands::workspace::export_document,
      commands::workspace::import_file_to_workspace,
  ])
  ```

  同时将 `WorkspaceManager` 加入 `AppState`（`src-tauri/src/state.rs`）：
  ```rust
  pub struct AppState {
      // ... 已有字段 ...
      pub workspace_manager: Arc<WorkspaceManager>,
      pub pool: SqlitePool,  // 供 exporter 直接使用
  }
  ```

- [ ] **Step 6.5: Commit**

  ```
  feat(commands): add workspace IPC commands for folder/doc CRUD, search, export, import
  ```

---

### Task 7: TDD — 后端单元测试

**Files:**
- Modify: `src-tauri/src/workspace/manager.rs`（追加 `#[cfg(test)]` 模块）
- Modify: `src-tauri/src/workspace/parser.rs`（追加 `#[cfg(test)]` 模块）
- Modify: `src-tauri/src/workspace/exporter.rs`（追加 `#[cfg(test)]` 模块）

- [ ] **Step 7.1: manager.rs 测试 — 递归文件夹删除**

  在 `manager.rs` 末尾追加测试模块，使用 `sqlx::SqlitePool::connect(":memory:")` 创建内存数据库并运行 migration。

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;

      async fn setup_pool() -> SqlitePool {
          let pool = SqlitePool::connect(":memory:").await.unwrap();
          sqlx::migrate!("src/storage/migrations").run(&pool).await.unwrap();
          pool
      }

      #[tokio::test]
      async fn test_recursive_folder_delete_removes_child_documents() {
          let pool    = setup_pool().await;
          let manager = WorkspaceManager::new(pool);

          // 创建父文件夹
          let parent = manager.create_folder("parent", None).await.unwrap();
          // 创建子文件夹
          let child  = manager.create_folder("child", Some(&parent.id)).await.unwrap();
          // 在子文件夹创建文档
          let doc = manager.create_document("test doc", Some(&child.id), "note", None).await.unwrap();

          // 删除父文件夹
          manager.delete_folder(&parent.id).await.unwrap();

          // 验证：子文件夹和文档均被删除
          let result = manager.get_document(&doc.id).await;
          assert!(matches!(result, Err(AppError::NotFound(_))));

          let child_folders = manager.list_folders().await.unwrap();
          assert!(child_folders.is_empty());
      }

      #[tokio::test]
      async fn test_system_folder_cannot_be_deleted() {
          let pool    = setup_pool().await;
          let manager = WorkspaceManager::new(pool.clone());

          // 手动插入系统文件夹（is_system=1）
          sqlx::query!(
              "INSERT INTO workspace_folders (id, parent_id, name, folder_kind, is_system, created_at)
               VALUES ('sys-1', NULL, 'Inbox', 'inbox', 1, 0)"
          )
          .execute(&pool)
          .await
          .unwrap();

          let result = manager.delete_folder("sys-1").await;
          assert!(matches!(result, Err(AppError::Validation(_))));
      }

      #[tokio::test]
      async fn test_fts5_search_returns_correct_result() {
          let pool    = setup_pool().await;
          let manager = WorkspaceManager::new(pool.clone());

          // 创建文档
          let doc = manager.create_document("Meeting Notes", None, "note", None).await.unwrap();
          // 写入 asset（trigger 自动同步 content_text → FTS5）
          manager.upsert_text_asset(&doc.id, "document_text", "The team decided to launch v3 next quarter", None).await.unwrap();

          // 搜索
          let results = manager.search_documents("launch v3").await.unwrap();
          assert!(!results.is_empty());
          assert_eq!(results[0].document_id, doc.id);
          assert!(results[0].snippet.contains("launch") || results[0].snippet.contains("v3"));
      }

      #[tokio::test]
      async fn test_duplicate_folder_name_rejected() {
          let pool    = setup_pool().await;
          let manager = WorkspaceManager::new(pool);

          manager.create_folder("Alpha", None).await.unwrap();
          let err = manager.create_folder("Alpha", None).await;
          assert!(matches!(err, Err(AppError::Validation(ref s)) if s.contains("duplicate_name")));
      }
  }
  ```

- [ ] **Step 7.2: exporter.rs 测试 — SRT/VTT 时间戳格式**

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;

      #[test]
      fn test_ms_to_srt_timestamp_basic() {
          // 0ms
          assert_eq!(ms_to_srt_timestamp(0), "00:00:00,000");
          // 1500ms = 1s500ms
          assert_eq!(ms_to_srt_timestamp(1500), "00:00:01,500");
          // 1h23m45s678ms
          let ms = (1 * 3600 + 23 * 60 + 45) * 1000 + 678;
          assert_eq!(ms_to_srt_timestamp(ms), "01:23:45,678");
      }

      #[test]
      fn test_ms_to_vtt_timestamp_uses_dot_separator() {
          assert_eq!(ms_to_vtt_timestamp(0),    "00:00:00.000");
          assert_eq!(ms_to_vtt_timestamp(1500),  "00:00:01.500");
          let ms = (1 * 3600 + 23 * 60 + 45) * 1000 + 678;
          assert_eq!(ms_to_vtt_timestamp(ms), "01:23:45.678");
      }

      #[test]
      fn test_srt_and_vtt_differ_only_in_separator() {
          let ms = 90_061_234_i64; // 25h01m01s234ms（边界值）
          let srt = ms_to_srt_timestamp(ms);
          let vtt = ms_to_vtt_timestamp(ms);
          assert!(srt.contains(',') && !srt.contains('.'));
          assert!(vtt.contains('.') && !vtt.contains(','));
      }
  }
  ```

- [ ] **Step 7.3: parser.rs 测试 — TXT/MD 内联字符串**

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use std::io::Write;

      fn write_temp_file(ext: &str, content: &str) -> tempfile::NamedTempFile {
          let mut f = tempfile::Builder::new().suffix(ext).tempfile().unwrap();
          f.write_all(content.as_bytes()).unwrap();
          f
      }

      #[test]
      fn test_parse_txt_returns_content() {
          let f   = write_temp_file(".txt", "Hello, EchoNote!\nSecond line.");
          let doc = parse_file(f.path()).unwrap();
          assert_eq!(doc.text, "Hello, EchoNote!\nSecond line.");
          assert_eq!(doc.metadata["source"], "txt");
      }

      #[test]
      fn test_parse_md_preserves_markdown() {
          let md  = "# Title\n\n**Bold** text and `code`.";
          let f   = write_temp_file(".md", md);
          let doc = parse_file(f.path()).unwrap();
          assert_eq!(doc.text, md);
          assert_eq!(doc.metadata["source"], "md");
      }

      #[test]
      fn test_parse_unsupported_extension_returns_error() {
          let f   = write_temp_file(".xyz", "data");
          let err = parse_file(f.path());
          assert!(matches!(err, Err(AppError::Workspace(_))));
      }

      #[test]
      #[ignore = "requires test PDF file"]
      fn test_parse_pdf_extracts_text() {
          let path = std::path::Path::new("tests/fixtures/sample.pdf");
          let doc  = parse_file(path).unwrap();
          assert!(!doc.text.is_empty());
          assert_eq!(doc.metadata["source"], "pdf");
      }

      #[test]
      #[ignore = "requires test DOCX file"]
      fn test_parse_docx_extracts_paragraphs() {
          let path = std::path::Path::new("tests/fixtures/sample.docx");
          let doc  = parse_file(path).unwrap();
          assert!(!doc.text.is_empty());
          assert_eq!(doc.metadata["source"], "docx");
      }
  }
  ```

  > 注：`tempfile` crate 需要加入 `[dev-dependencies]`：`tempfile = "3"`

- [ ] **Step 7.4: 运行测试验证通过**

  ```bash
  cd src-tauri && cargo test workspace -- --nocapture
  ```

- [ ] **Step 7.5: Commit**

  ```
  test(workspace): add unit tests for manager CRUD/FTS5, exporter timestamps, and parser
  ```

---

### Task 8: `store/workspace.ts` — Zustand Store

**Files:**
- Create: `src/store/workspace.ts`

- [ ] **Step 8.1: 定义 store 类型和 actions**

  ```typescript
  // src/store/workspace.ts
  import { create } from 'zustand'
  import { commands } from '@/lib/bindings'
  import type { FolderNode, DocumentSummary, DocumentDetail, SearchResult } from '@/lib/bindings'

  interface WorkspaceState {
    // 状态
    folders:        FolderNode[]
    currentFolderId: string | null
    documents:      DocumentSummary[]
    currentDoc:     DocumentDetail | null
    searchQuery:    string
    searchResults:  SearchResult[]
    isSearching:    boolean

    // 文件夹 actions
    loadFolderTree:  () => Promise<void>
    selectFolder:    (id: string | null) => Promise<void>
    createFolder:    (name: string, parentId?: string) => Promise<void>
    renameFolder:    (id: string, name: string) => Promise<void>
    deleteFolder:    (id: string) => Promise<void>

    // 文档 actions
    openDocument:    (id: string) => Promise<void>
    createDocument:  (title: string, folderId?: string, content?: string) => Promise<void>
    updateDocument:  (id: string, opts: { title?: string; role?: string; content?: string }) => Promise<void>
    deleteDocument:  (id: string) => Promise<void>

    // 搜索 actions
    setSearchQuery:  (q: string) => void
    search:          (q: string) => Promise<void>
    clearSearch:     () => void

    // 导入/导出
    importFile:      (filePath: string, folderId?: string) => Promise<void>
    exportDocument:  (id: string, format: 'md' | 'txt' | 'srt' | 'vtt', targetPath: string) => Promise<void>
  }

  export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
    folders:         [],
    currentFolderId: null,
    documents:       [],
    currentDoc:      null,
    searchQuery:     '',
    searchResults:   [],
    isSearching:     false,

    loadFolderTree: async () => {
      const folders = await commands.listFolderTree()
      set({ folders })
    },

    selectFolder: async (id) => {
      set({ currentFolderId: id, currentDoc: null })
      const documents = await commands.listDocumentsInFolder(id ?? null)
      set({ documents })
    },

    createFolder: async (name, parentId) => {
      await commands.createFolder(name, parentId ?? null)
      await get().loadFolderTree()
    },

    renameFolder: async (id, name) => {
      await commands.renameFolder(id, name)
      await get().loadFolderTree()
    },

    deleteFolder: async (id) => {
      await commands.deleteFolder(id)
      await get().loadFolderTree()
      if (get().currentFolderId === id) set({ currentFolderId: null, documents: [] })
    },

    openDocument: async (id) => {
      const doc = await commands.getDocument(id)
      set({ currentDoc: doc })
    },

    createDocument: async (title, folderId, content = '') => {
      const summary = await commands.createDocument(title, folderId ?? null, content)
      set((s) => ({ documents: [summary, ...s.documents] }))
      await get().openDocument(summary.id)
    },

    updateDocument: async (id, { title, role, content }) => {
      await commands.updateDocument(id, title ?? null, role ?? null, content ?? null)
      if (get().currentDoc?.id === id) await get().openDocument(id)
    },

    deleteDocument: async (id) => {
      await commands.deleteDocument(id)
      set((s) => ({
        documents: s.documents.filter((d) => d.id !== id),
        currentDoc: s.currentDoc?.id === id ? null : s.currentDoc,
      }))
    },

    setSearchQuery: (q) => set({ searchQuery: q }),

    search: async (q) => {
      if (!q.trim()) { set({ searchResults: [], isSearching: false }); return }
      set({ isSearching: true })
      try {
        const results = await commands.searchWorkspace(q)
        set({ searchResults: results })
      } finally {
        set({ isSearching: false })
      }
    },

    clearSearch: () => set({ searchQuery: '', searchResults: [] }),

    importFile: async (filePath, folderId) => {
      const summary = await commands.importFileToWorkspace(filePath, folderId ?? null)
      set((s) => ({ documents: [summary, ...s.documents] }))
    },

    exportDocument: async (id, format, targetPath) => {
      await commands.exportDocument(id, format, targetPath)
    },
  }))
  ```

- [ ] **Step 8.2: Commit**

  ```
  feat(store): add useWorkspaceStore with folder/doc CRUD, search, import/export actions
  ```

---

### Task 9: `components/workspace/WorkspacePanel.tsx` — 可折叠文件夹树

**Files:**
- Create: `src/components/workspace/WorkspacePanel.tsx`
- Create: `src/components/workspace/FolderTreeNode.tsx`

- [ ] **Step 9.1: 递归 FolderTreeNode 组件**

  ```tsx
  // src/components/workspace/FolderTreeNode.tsx
  import { useState } from 'react'
  import { ChevronRight, Folder, FolderOpen, MoreHorizontal, Plus, Pencil, Trash2 } from 'lucide-react'
  import { cn } from '@/lib/utils'
  import type { FolderNode } from '@/lib/bindings'
  import {
    ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger,
  } from '@/components/ui/context-menu'

  interface Props {
    node:           FolderNode
    depth:          number
    selectedId:     string | null
    onSelect:       (id: string) => void
    onCreateChild:  (parentId: string) => void
    onRename:       (id: string, currentName: string) => void
    onDelete:       (id: string) => void
  }

  export function FolderTreeNode({ node, depth, selectedId, onSelect, onCreateChild, onRename, onDelete }: Props) {
    const [expanded, setExpanded] = useState(depth === 0)
    const isSelected = node.id === selectedId
    const hasChildren = node.children.length > 0

    return (
      <div>
        <ContextMenu>
          <ContextMenuTrigger>
            <div
              className={cn(
                'flex items-center gap-1 px-2 py-1 rounded cursor-pointer select-none text-sm',
                'hover:bg-bg-hover',
                isSelected && 'bg-accent-muted text-accent',
              )}
              style={{ paddingLeft: `${depth * 12 + 8}px` }}
              onClick={() => { onSelect(node.id); if (hasChildren) setExpanded((e) => !e) }}
            >
              {hasChildren ? (
                <ChevronRight
                  size={14}
                  className={cn('transition-transform shrink-0', expanded && 'rotate-90')}
                />
              ) : (
                <span className="w-3.5 shrink-0" />
              )}
              {expanded && hasChildren ? (
                <FolderOpen size={14} className="shrink-0 text-accent" />
              ) : (
                <Folder size={14} className="shrink-0 text-text-secondary" />
              )}
              <span className="truncate flex-1">{node.name}</span>
              {node.document_count > 0 && (
                <span className="text-xs text-text-muted ml-auto">{node.document_count}</span>
              )}
            </div>
          </ContextMenuTrigger>
          <ContextMenuContent>
            {!node.is_system && (
              <>
                <ContextMenuItem onClick={() => onCreateChild(node.id)}>
                  <Plus size={14} className="mr-2" /> 新建子文件夹
                </ContextMenuItem>
                <ContextMenuItem onClick={() => onRename(node.id, node.name)}>
                  <Pencil size={14} className="mr-2" /> 重命名
                </ContextMenuItem>
                <ContextMenuItem
                  onClick={() => onDelete(node.id)}
                  className="text-status-error focus:text-status-error"
                >
                  <Trash2 size={14} className="mr-2" /> 删除
                </ContextMenuItem>
              </>
            )}
            {node.is_system && (
              <ContextMenuItem disabled>系统文件夹（不可修改）</ContextMenuItem>
            )}
          </ContextMenuContent>
        </ContextMenu>

        {expanded && node.children.map((child) => (
          <FolderTreeNode
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
            onCreateChild={onCreateChild}
            onRename={onRename}
            onDelete={onDelete}
          />
        ))}
      </div>
    )
  }
  ```

- [ ] **Step 9.2: WorkspacePanel 组件**

  包含搜索框、文件夹树、底部新建按钮，以及重命名/新建弹窗（使用 shadcn `Dialog` + `Input`）。

  ```tsx
  // src/components/workspace/WorkspacePanel.tsx
  import { useEffect, useState } from 'react'
  import { Plus, Search } from 'lucide-react'
  import { useWorkspaceStore } from '@/store/workspace'
  import { FolderTreeNode } from './FolderTreeNode'
  import { Input } from '@/components/ui/input'
  import { Button } from '@/components/ui/button'
  import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
  import { SearchBar } from './SearchBar'

  export function WorkspacePanel() {
    const { folders, currentFolderId, loadFolderTree, selectFolder, createFolder, renameFolder, deleteFolder } =
      useWorkspaceStore()

    const [dialog, setDialog] = useState<
      | { mode: 'create'; parentId?: string }
      | { mode: 'rename'; id: string; currentName: string }
      | null
    >(null)
    const [inputVal, setInputVal] = useState('')

    useEffect(() => { loadFolderTree() }, [])

    const handleConfirm = async () => {
      if (!dialog || !inputVal.trim()) return
      if (dialog.mode === 'create') {
        await createFolder(inputVal.trim(), dialog.parentId)
      } else {
        await renameFolder(dialog.id, inputVal.trim())
      }
      setDialog(null)
      setInputVal('')
    }

    return (
      <div className="flex flex-col h-full text-text-primary">
        {/* 搜索框 */}
        <div className="p-2 border-b border-border">
          <SearchBar />
        </div>

        {/* 文件夹树 */}
        <div className="flex-1 overflow-y-auto py-1">
          {folders.map((node) => (
            <FolderTreeNode
              key={node.id}
              node={node}
              depth={0}
              selectedId={currentFolderId}
              onSelect={(id) => selectFolder(id)}
              onCreateChild={(parentId) => { setDialog({ mode: 'create', parentId }); setInputVal('') }}
              onRename={(id, name) => { setDialog({ mode: 'rename', id, currentName: name }); setInputVal(name) }}
              onDelete={(id) => deleteFolder(id)}
            />
          ))}
        </div>

        {/* 底部：新建根文件夹 */}
        <div className="p-2 border-t border-border">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-text-secondary hover:text-text-primary"
            onClick={() => { setDialog({ mode: 'create' }); setInputVal('') }}
          >
            <Plus size={14} /> 新建文件夹
          </Button>
        </div>

        {/* 重命名/新建弹窗 */}
        <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{dialog?.mode === 'create' ? '新建文件夹' : '重命名文件夹'}</DialogTitle>
            </DialogHeader>
            <Input
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
              placeholder="文件夹名称"
              autoFocus
            />
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDialog(null)}>取消</Button>
              <Button onClick={handleConfirm}>确认</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    )
  }
  ```

- [ ] **Step 9.3: Commit**

  ```
  feat(ui): add WorkspacePanel with recursive FolderTreeNode and context menu
  ```

---

### Task 10: `components/workspace/WorkspaceMain.tsx` — 文档列表与文档详情

**Files:**
- Create: `src/components/workspace/WorkspaceMain.tsx`

- [ ] **Step 10.1: 文档列表视图（选中文件夹时）**

  ```tsx
  // src/components/workspace/WorkspaceMain.tsx
  import { useEffect } from 'react'
  import { useParams } from '@tanstack/react-router'  // TanStack Router
  import { useWorkspaceStore } from '@/store/workspace'
  import { DocumentView } from './DocumentView'
  import { FileText, Import, Plus } from 'lucide-react'
  import { Button } from '@/components/ui/button'
  import { open } from '@tauri-apps/plugin-dialog'

  export function WorkspaceMain() {
    const { folderId, docId } = useParams({ strict: false }) as { folderId?: string; docId?: string }
    const {
      documents, currentDoc, currentFolderId,
      selectFolder, openDocument, createDocument, importFile,
    } = useWorkspaceStore()

    // URL 参数驱动状态同步
    useEffect(() => {
      if (folderId && folderId !== currentFolderId) selectFolder(folderId)
    }, [folderId])

    useEffect(() => {
      if (docId) openDocument(docId)
    }, [docId])

    // 文档详情视图
    if (currentDoc) {
      return <DocumentView doc={currentDoc} />
    }

    // 文档列表视图
    return (
      <div className="flex flex-col h-full">
        {/* 工具栏 */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
          <Button size="sm" variant="ghost" className="gap-1"
            onClick={() => createDocument('新建文档', currentFolderId ?? undefined)}
          >
            <Plus size={14} /> 新建文档
          </Button>
          <Button size="sm" variant="ghost" className="gap-1"
            onClick={async () => {
              const selected = await open({ multiple: false, filters: [
                { name: 'Documents', extensions: ['pdf', 'docx', 'txt', 'md'] }
              ]})
              if (typeof selected === 'string') {
                await importFile(selected, currentFolderId ?? undefined)
              }
            }}
          >
            <Import size={14} /> 导入文件
          </Button>
        </div>

        {/* 文档列表 */}
        <div className="flex-1 overflow-y-auto p-4">
          {documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
              <FileText size={40} />
              <p className="text-sm">此文件夹为空</p>
            </div>
          ) : (
            <div className="grid gap-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="p-3 rounded border border-border hover:bg-bg-hover cursor-pointer"
                  onClick={() => openDocument(doc.id)}
                >
                  <div className="font-medium text-sm truncate">{doc.title}</div>
                  <div className="flex gap-2 mt-1 text-xs text-text-muted">
                    {doc.has_transcript    && <span className="bg-bg-secondary px-1 rounded">转写</span>}
                    {doc.has_summary       && <span className="bg-bg-secondary px-1 rounded">摘要</span>}
                    {doc.has_meeting_brief && <span className="bg-bg-secondary px-1 rounded">会议纪要</span>}
                    <span className="ml-auto">{new Date(doc.updated_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 10.2: Commit**

  ```
  feat(ui): add WorkspaceMain with document list view and folder-driven navigation
  ```

---

### Task 11: `components/workspace/DocumentView.tsx` — 文档详情标签页视图

**Files:**
- Create: `src/components/workspace/DocumentView.tsx`

- [ ] **Step 11.1: 标签页切换与导出下拉**

  标签页包含：转写原文（transcript）/ AI 摘要（summary）/ 会议纪要（meeting_brief）/ 翻译（translation）。导出下拉菜单调用 `export_document` 命令。

  ```tsx
  // src/components/workspace/DocumentView.tsx
  import { useState } from 'react'
  import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
  import {
    DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  } from '@/components/ui/dropdown-menu'
  import { Button } from '@/components/ui/button'
  import { Download, ChevronDown } from 'lucide-react'
  import { save } from '@tauri-apps/plugin-dialog'
  import { useWorkspaceStore } from '@/store/workspace'
  import type { DocumentDetail } from '@/lib/bindings'

  const ASSET_TABS = [
    { role: 'transcript',    label: '转写原文' },
    { role: 'summary',       label: 'AI 摘要' },
    { role: 'meeting_brief', label: '会议纪要' },
    { role: 'translation',   label: '翻译' },
  ] as const

  const EXPORT_FORMATS = [
    { format: 'md',  label: 'Markdown (.md)' },
    { format: 'txt', label: '纯文本 (.txt)' },
    { format: 'srt', label: '字幕 SRT (.srt)' },
    { format: 'vtt', label: '字幕 VTT (.vtt)' },
  ] as const

  interface Props { doc: DocumentDetail }

  export function DocumentView({ doc }: Props) {
    const { exportDocument } = useWorkspaceStore()
    const assetMap = Object.fromEntries(doc.assets.map((a) => [a.role, a]))

    const availableTabs = ASSET_TABS.filter((t) => assetMap[t.role])
    const defaultTab = availableTabs[0]?.role ?? 'transcript'

    const handleExport = async (format: string) => {
      const ext = format === 'srt' ? 'srt' : format === 'vtt' ? 'vtt' : format === 'txt' ? 'txt' : 'md'
      const path = await save({
        defaultPath: `${doc.title}.${ext}`,
        filters: [{ name: ext.toUpperCase(), extensions: [ext] }],
      })
      if (path) await exportDocument(doc.id, format as any, path)
    }

    return (
      <div className="flex flex-col h-full">
        {/* 顶栏：标题 + 导出 */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border">
          <h2 className="font-semibold text-sm flex-1 truncate">{doc.title}</h2>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline" className="gap-1">
                <Download size={14} /> 导出 <ChevronDown size={12} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {EXPORT_FORMATS.map(({ format, label }) => (
                <DropdownMenuItem key={format} onClick={() => handleExport(format)}>
                  {label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* 标签页内容 */}
        {availableTabs.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
            此文档暂无内容
          </div>
        ) : (
          <Tabs defaultValue={defaultTab} className="flex flex-col flex-1 min-h-0">
            <TabsList className="px-4 pt-2 border-b border-border bg-transparent justify-start gap-1 h-auto">
              {availableTabs.map(({ role, label }) => (
                <TabsTrigger
                  key={role}
                  value={role}
                  className="text-xs px-3 py-1.5 data-[state=active]:bg-accent-muted data-[state=active]:text-accent"
                >
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>
            {availableTabs.map(({ role }) => (
              <TabsContent key={role} value={role} className="flex-1 overflow-y-auto p-4 mt-0">
                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans text-text-primary">
                  {assetMap[role]?.content ?? ''}
                </pre>
              </TabsContent>
            ))}
          </Tabs>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 11.2: Commit**

  ```
  feat(ui): add DocumentView with asset tabs, export dropdown menu
  ```

---

### Task 12: `components/workspace/SearchBar.tsx` — 全文搜索栏

**Files:**
- Create: `src/components/workspace/SearchBar.tsx`

- [ ] **Step 12.1: debounce 搜索 + 高亮结果列表**

  使用 `use-debounce` 包（需确认已在 `package.json` 中，否则执行 `npm install use-debounce`）。搜索结果中的 `<mark>` 标签直接用 `dangerouslySetInnerHTML` 渲染（snippet 内容来自 Rust FTS5，不含用户可控 HTML，XSS 风险可控）。

  ```tsx
  // src/components/workspace/SearchBar.tsx
  import { useEffect, useRef } from 'react'
  import { useDebounce } from 'use-debounce'
  import { Search, X } from 'lucide-react'
  import { Input } from '@/components/ui/input'
  import { useWorkspaceStore } from '@/store/workspace'

  export function SearchBar() {
    const { searchQuery, searchResults, isSearching, setSearchQuery, search, clearSearch, openDocument } =
      useWorkspaceStore()

    const [debouncedQuery] = useDebounce(searchQuery, 300)

    useEffect(() => {
      if (debouncedQuery.trim()) {
        search(debouncedQuery)
      } else {
        clearSearch()
      }
    }, [debouncedQuery])

    const inSearch = !!searchQuery.trim()

    return (
      <div className="relative">
        {/* 输入框 */}
        <div className="relative flex items-center">
          <Search size={14} className="absolute left-2.5 text-text-muted pointer-events-none" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索文档…"
            className="pl-8 pr-8 h-7 text-sm bg-bg-input border-border"
          />
          {inSearch && (
            <button
              onClick={clearSearch}
              className="absolute right-2 text-text-muted hover:text-text-primary"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* 搜索结果下拉 */}
        {inSearch && (
          <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-bg-secondary border border-border rounded shadow-lg max-h-72 overflow-y-auto">
            {isSearching && (
              <div className="p-2 text-xs text-text-muted">搜索中…</div>
            )}
            {!isSearching && searchResults.length === 0 && (
              <div className="p-2 text-xs text-text-muted">无匹配结果</div>
            )}
            {searchResults.map((r) => (
              <div
                key={r.document_id}
                className="px-3 py-2 hover:bg-bg-hover cursor-pointer"
                onClick={() => { openDocument(r.document_id); clearSearch() }}
              >
                <div className="text-sm font-medium truncate">{r.title}</div>
                <div
                  className="text-xs text-text-muted mt-0.5 line-clamp-2 [&_mark]:bg-accent-muted [&_mark]:text-accent [&_mark]:rounded-sm [&_mark]:px-0.5"
                  dangerouslySetInnerHTML={{ __html: r.snippet }}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 12.2: Commit**

  ```
  feat(ui): add SearchBar with 300ms debounce, FTS5 highlight rendering
  ```

---

### Task 13: 路由接入与最终集成

**Files:**
- Modify: `src/router.tsx`（或 TanStack Router 路由文件）

- [ ] **Step 13.1: 注册 workspace 路由**

  根据规格，workspace 路由支持可选的 `folderId` 和 `docId` 参数：

  ```typescript
  // 在路由定义文件中添加（TanStack Router 风格）
  const workspaceRoute = createRoute({
    path: '/workspace',
    component: () => (
      <Shell
        panel={<WorkspacePanel />}
        main={<WorkspaceMain />}
      />
    ),
  })

  const workspaceFolderRoute = createRoute({
    path: '/workspace/$folderId',
    component: () => (
      <Shell
        panel={<WorkspacePanel />}
        main={<WorkspaceMain />}
      />
    ),
  })

  const workspaceDocRoute = createRoute({
    path: '/workspace/$folderId/$docId',
    component: () => (
      <Shell
        panel={<WorkspacePanel />}
        main={<WorkspaceMain />}
      />
    ),
  })
  ```

- [ ] **Step 13.2: 确认 AppState 初始化**

  在 `src-tauri/src/lib.rs` 的 `setup` hook 中初始化 `WorkspaceManager`，确保在数据库 migration 完成后构建：

  ```rust
  let workspace_manager = Arc::new(WorkspaceManager::new(pool.clone()));
  ```

- [ ] **Step 13.3: 端到端冒烟测试**

  手动验证以下流程：
  - 启动应用 → migration `0003` 执行成功（检查无 panic）
  - WorkspacePanel 加载 → 显示 Inbox / Events / Batch Tasks 系统文件夹
  - 创建用户文件夹 → 树形结构更新
  - 右键系统文件夹 → 显示"系统文件夹不可修改"禁用菜单项
  - 创建文档 → 文档列表出现新条目
  - 搜索关键词 → 300ms 后显示高亮结果，点击跳转到文档
  - 导入 TXT 文件 → 文档出现，content 标签页显示原文
  - 导出为 MD → 文件保存到指定路径

- [ ] **Step 13.4: Final Commit**

  ```
  feat(workspace): wire M6 workspace routes, integrate WorkspacePanel/Main into Shell layout
  ```

---

## 依赖汇总

### Rust（`src-tauri/Cargo.toml`）

```toml
# 已有依赖（M1/M2 引入）
sqlx    = { version = "0.8", features = ["sqlite", "runtime-tokio", "macros"] }
uuid    = { version = "1", features = ["v4"] }
serde   = { version = "1", features = ["derive"] }
tokio   = { version = "1", features = ["full"] }

# M6 新增
pdf-extract = "0.7"
docx-rs     = "0.4"

# dev-dependencies
[dev-dependencies]
tempfile = "3"
```

### TypeScript（`package.json`）

```json
{
  "dependencies": {
    "use-debounce": "^10.0.0"
  }
}
```

---

## 文件路径速查

| 文件 | 任务 |
|------|------|
| `src-tauri/src/storage/migrations/0003_workspace_assets.sql` | Task 1 |
| `src-tauri/src/workspace/document.rs` | Task 2 |
| `src-tauri/src/workspace/manager.rs` | Task 3 |
| `src-tauri/src/workspace/exporter.rs` | Task 4 |
| `src-tauri/src/workspace/parser.rs` | Task 5 |
| `src-tauri/src/commands/workspace.rs` | Task 6 |
| `src/store/workspace.ts` | Task 8 |
| `src/components/workspace/WorkspacePanel.tsx` | Task 9 |
| `src/components/workspace/FolderTreeNode.tsx` | Task 9 |
| `src/components/workspace/WorkspaceMain.tsx` | Task 10 |
| `src/components/workspace/DocumentView.tsx` | Task 11 |
| `src/components/workspace/SearchBar.tsx` | Task 12 |
