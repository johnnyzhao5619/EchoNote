# Workspace Obsidian Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform EchoNote workspace from a flat recording list + basic editor into an Obsidian-like document management experience with folder tree, Markdown dual-mode editor, AI floating panel, and subtitle editor.

**Architecture:** Backend gains folder CRUD commands + subtitle commands (migration 0003); frontend gains WorkspaceFileTree rewrite, EditableAsset Markdown mode, AiPanel, AiInlineToolbar, and SubtitleEditor. Tasks 1, 3, and 6 can run in parallel after Task 1 unblocks; Task 7 requires Tasks 4 and 6.

**Tech Stack:** Rust/Tauri 2 + sqlx SQLite, React/TypeScript, TanStack Router, Zustand, react-markdown, remark-gfm, @radix-ui/react-context-menu, textarea-caret, lucide-react.

---

## File Map

### New files
- `src-tauri/src/storage/migrations/0003_segment_translations.sql`
- `src-tauri/src/commands/subtitle.rs`
- `src/store/workspace.ts`
- `src/components/workspace/AiPanel.tsx`
- `src/components/workspace/AiInlineToolbar.tsx`
- `src/components/workspace/SubtitleEditor.tsx`

### Modified files
- `src-tauri/src/commands/workspace.rs` — add 8 new commands + `init_system_folders` helper
- `src-tauri/src/commands/mod.rs` — add `pub mod subtitle;`
- `src-tauri/src/lib.rs` — register new commands + spawn system-folder init
- `src/components/workspace/WorkspaceFileTree.tsx` — full rewrite
- `src/components/workspace/EditableAsset.tsx` — add Markdown dual-mode
- `src/routes/workspace.$documentId.tsx` — Obsidian-style layout + mode switch
- `package.json` — add react-markdown, remark-gfm, @radix-ui/react-context-menu, textarea-caret

---

## Task 1: Backend — Folder CRUD + System Folders + Document Commands

**Files:**
- Modify: `src-tauri/src/commands/workspace.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/lib.rs`
- Test: `src-tauri/src/storage/db.rs` (existing test file, add new tests)

### Step 1.1: Write failing tests for system folder init

- [ ] Open `src-tauri/src/storage/db.rs`, add after existing tests:

```rust
#[tokio::test]
async fn test_init_system_folders_idempotent() {
    use crate::commands::workspace;
    let db = Db::open("sqlite::memory:").await.unwrap();
    // First call creates folders
    let ids1 = workspace::init_system_folders(&db.pool).await.unwrap();
    // Second call returns same ids (idempotent)
    let ids2 = workspace::init_system_folders(&db.pool).await.unwrap();
    assert_eq!(ids1.inbox_id, ids2.inbox_id);
    assert_eq!(ids1.batch_task_id, ids2.batch_task_id);

    // Verify folders exist in DB
    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM workspace_folders WHERE is_system = 1"
    )
    .fetch_one(&db.pool)
    .await
    .unwrap();
    assert_eq!(count.0, 2, "should have 2 system folders");
}

#[tokio::test]
async fn test_list_folders_empty() {
    use crate::commands::workspace;
    let db = Db::open("sqlite::memory:").await.unwrap();
    workspace::init_system_folders(&db.pool).await.unwrap();
    let nodes = workspace::list_folders_tree(&db.pool).await.unwrap();
    // inbox and batch_task at top level, no documents
    assert_eq!(nodes.len(), 2);
    assert!(nodes.iter().any(|n| n.folder_kind == "inbox"));
    assert!(nodes.iter().any(|n| n.folder_kind == "batch_task"));
}
```

- [ ] Run tests to confirm they fail:
```bash
cd src-tauri && cargo test test_init_system_folders_idempotent test_list_folders_empty -- --test-threads=1 2>&1 | tail -20
```
Expected: FAIL (functions don't exist yet)

### Step 1.2: Implement `init_system_folders` and types in workspace.rs

- [ ] Add the following to `src-tauri/src/commands/workspace.rs` (after existing imports):

```rust
use sqlx::SqlitePool;

#[derive(Debug, serde::Serialize, serde::Deserialize, specta::Type, Clone)]
pub struct SystemFolderIds {
    pub inbox_id: String,
    pub batch_task_id: String,
}

#[derive(Debug, serde::Serialize, serde::Deserialize, specta::Type, Clone)]
pub struct DocumentSummary {
    pub id: String,
    pub title: String,
    pub source_type: String,
    pub recording_id: Option<String>,
    pub created_at: i64,
}

/// specta note: Vec<FolderNode> is recursive. If `cargo check` emits a type-export
/// error, change children to `Vec<FlatFolder>` and assemble the tree on the frontend.
#[derive(Debug, serde::Serialize, serde::Deserialize, specta::Type, Clone)]
pub struct FolderNode {
    pub id: String,
    pub name: String,
    pub folder_kind: String,
    pub is_system: bool,
    pub children: Vec<FolderNode>,
    pub documents: Vec<DocumentSummary>,
}

/// Internal helper — not a Tauri command. Called from lib.rs setup and reused
/// inside ensure_document_for_recording.
pub async fn init_system_folders(pool: &SqlitePool) -> Result<SystemFolderIds, crate::error::AppError> {
    let now = chrono::Utc::now().timestamp_millis();

    // inbox
    let inbox_id: Option<String> = sqlx::query_scalar(
        "SELECT id FROM workspace_folders WHERE folder_kind = 'inbox' AND is_system = 1 LIMIT 1"
    )
    .fetch_optional(pool)
    .await?;

    let inbox_id = if let Some(id) = inbox_id {
        id
    } else {
        let id = uuid::Uuid::new_v4().to_string();
        sqlx::query(
            "INSERT INTO workspace_folders (id, name, folder_kind, is_system, created_at)
             VALUES (?, '收件箱', 'inbox', 1, ?)"
        )
        .bind(&id)
        .bind(now)
        .execute(pool)
        .await?;
        id
    };

    // batch_task
    let batch_id: Option<String> = sqlx::query_scalar(
        "SELECT id FROM workspace_folders WHERE folder_kind = 'batch_task' AND is_system = 1 LIMIT 1"
    )
    .fetch_optional(pool)
    .await?;

    let batch_task_id = if let Some(id) = batch_id {
        id
    } else {
        let id = uuid::Uuid::new_v4().to_string();
        sqlx::query(
            "INSERT INTO workspace_folders (id, name, folder_kind, is_system, created_at)
             VALUES (?, '批量任务', 'batch_task', 1, ?)"
        )
        .bind(&id)
        .bind(now)
        .execute(pool)
        .await?;
        id
    };

    Ok(SystemFolderIds { inbox_id, batch_task_id })
}

/// Internal helper for list_folders_with_documents — builds recursive tree from flat rows.
pub async fn list_folders_tree(pool: &SqlitePool) -> Result<Vec<FolderNode>, crate::error::AppError> {
    // All folders
    let folder_rows: Vec<(String, String, String, bool, Option<String>)> = sqlx::query_as(
        "SELECT id, name, folder_kind, is_system, parent_id FROM workspace_folders ORDER BY is_system DESC, created_at ASC"
    )
    .fetch_all(pool)
    .await?;

    // All documents
    let doc_rows: Vec<(String, String, String, Option<String>, i64, Option<String>)> = sqlx::query_as(
        "SELECT id, title, source_type, recording_id, created_at, folder_id
         FROM workspace_documents ORDER BY created_at DESC"
    )
    .fetch_all(pool)
    .await?;

    // Build folder map
    use std::collections::HashMap;
    let mut nodes: HashMap<String, FolderNode> = folder_rows
        .iter()
        .map(|(id, name, kind, is_sys, _)| {
            (id.clone(), FolderNode {
                id: id.clone(),
                name: name.clone(),
                folder_kind: kind.clone(),
                is_system: *is_sys,
                children: vec![],
                documents: vec![],
            })
        })
        .collect();

    // Attach documents to folders
    for (id, title, source_type, recording_id, created_at, folder_id) in &doc_rows {
        let doc = DocumentSummary {
            id: id.clone(),
            title: title.clone(),
            source_type: source_type.clone(),
            recording_id: recording_id.clone(),
            created_at: *created_at,
        };
        if let Some(fid) = folder_id {
            if let Some(node) = nodes.get_mut(fid) {
                node.documents.push(doc);
            }
        }
    }

    // Build tree (collect children, then return top-level)
    let parent_map: HashMap<String, Option<String>> = folder_rows
        .iter()
        .map(|(id, _, _, _, parent)| (id.clone(), parent.clone()))
        .collect();

    let child_ids: Vec<String> = folder_rows
        .iter()
        .filter(|(id, _, _, _, _)| parent_map[id].is_some())
        .map(|(id, _, _, _, _)| id.clone())
        .collect();

    // Collect children into parents
    let mut children_map: HashMap<String, Vec<FolderNode>> = HashMap::new();
    for cid in &child_ids {
        if let Some(node) = nodes.remove(cid) {
            let parent_id = parent_map[cid].clone().unwrap();
            children_map.entry(parent_id).or_default().push(node);
        }
    }
    for (parent_id, children) in children_map {
        if let Some(parent) = nodes.get_mut(&parent_id) {
            parent.children = children;
        }
    }

    // Return top-level nodes: system folders first, then user folders
    let mut top: Vec<FolderNode> = nodes.into_values().collect();
    top.sort_by(|a, b| {
        b.is_system.cmp(&a.is_system)
            .then(a.folder_kind.cmp(&b.folder_kind))
    });
    Ok(top)
}
```

### Step 1.3: Implement Tauri commands in workspace.rs

- [ ] Add these commands after the helper functions:

```rust
#[tauri::command]
#[specta::specta]
pub async fn ensure_system_folders(
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<SystemFolderIds, crate::error::AppError> {
    init_system_folders(&state.db.pool).await
}

#[tauri::command]
#[specta::specta]
pub async fn list_folders_with_documents(
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<Vec<FolderNode>, crate::error::AppError> {
    list_folders_tree(&state.db.pool).await
}

#[tauri::command]
#[specta::specta]
pub async fn create_folder(
    parent_id: Option<String>,
    name: String,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<String, crate::error::AppError> {
    if name.trim().is_empty() {
        return Err(crate::error::AppError::Validation("folder name cannot be empty".into()));
    }
    let now = chrono::Utc::now().timestamp_millis();
    let id = uuid::Uuid::new_v4().to_string();
    sqlx::query(
        "INSERT INTO workspace_folders (id, parent_id, name, folder_kind, is_system, created_at)
         VALUES (?, ?, ?, 'user', 0, ?)"
    )
    .bind(&id)
    .bind(&parent_id)
    .bind(&name)
    .bind(now)
    .execute(&state.db.pool)
    .await?;
    Ok(id)
}

#[tauri::command]
#[specta::specta]
pub async fn rename_folder(
    folder_id: String,
    name: String,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<(), crate::error::AppError> {
    let is_system: Option<bool> = sqlx::query_scalar(
        "SELECT is_system FROM workspace_folders WHERE id = ?"
    )
    .bind(&folder_id)
    .fetch_optional(&state.db.pool)
    .await?;
    match is_system {
        None => return Err(crate::error::AppError::NotFound(folder_id)),
        Some(true) => return Err(crate::error::AppError::Validation("cannot rename system folder".into())),
        Some(false) => {}
    }
    sqlx::query("UPDATE workspace_folders SET name = ? WHERE id = ?")
        .bind(&name)
        .bind(&folder_id)
        .execute(&state.db.pool)
        .await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn delete_folder(
    folder_id: String,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<(), crate::error::AppError> {
    let is_system: Option<bool> = sqlx::query_scalar(
        "SELECT is_system FROM workspace_folders WHERE id = ?"
    )
    .bind(&folder_id)
    .fetch_optional(&state.db.pool)
    .await?;
    match is_system {
        None => return Err(crate::error::AppError::NotFound(folder_id)),
        Some(true) => return Err(crate::error::AppError::Validation("cannot delete system folder".into())),
        Some(false) => {}
    }
    // Move documents from this folder (and descendants) to inbox
    let ids = init_system_folders(&state.db.pool).await?;
    sqlx::query(
        "UPDATE workspace_documents SET folder_id = ?
         WHERE folder_id IN (
           WITH RECURSIVE sub(id) AS (
             SELECT id FROM workspace_folders WHERE id = ?
             UNION ALL
             SELECT f.id FROM workspace_folders f JOIN sub ON f.parent_id = sub.id
           )
           SELECT id FROM sub
         )"
    )
    .bind(&ids.inbox_id)
    .bind(&folder_id)
    .execute(&state.db.pool)
    .await?;
    // Delete folder (CASCADE deletes children)
    sqlx::query("DELETE FROM workspace_folders WHERE id = ?")
        .bind(&folder_id)
        .execute(&state.db.pool)
        .await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn move_document_to_folder(
    document_id: String,
    folder_id: String,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<(), crate::error::AppError> {
    sqlx::query("UPDATE workspace_documents SET folder_id = ? WHERE id = ?")
        .bind(&folder_id)
        .bind(&document_id)
        .execute(&state.db.pool)
        .await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn rename_document(
    document_id: String,
    title: String,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<(), crate::error::AppError> {
    let now = chrono::Utc::now().timestamp_millis();
    sqlx::query("UPDATE workspace_documents SET title = ?, updated_at = ? WHERE id = ?")
        .bind(&title)
        .bind(now)
        .bind(&document_id)
        .execute(&state.db.pool)
        .await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn delete_document(
    document_id: String,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<(), crate::error::AppError> {
    sqlx::query("DELETE FROM workspace_documents WHERE id = ?")
        .bind(&document_id)
        .execute(&state.db.pool)
        .await?;
    Ok(())
}
```

### Step 1.4: Modify `ensure_document_for_recording` to set folder_id

- [ ] In `src-tauri/src/commands/workspace.rs`, find the existing `ensure_document_for_recording` function (around line 108). Change the INSERT statement to include `folder_id`:

Old:
```rust
    let now = chrono::Utc::now().timestamp();
    let doc_id = uuid::Uuid::new_v4().to_string();

    let mut tx = state.db.pool.begin().await?;

    sqlx::query(
        "INSERT INTO workspace_documents (id, title, source_type, recording_id, created_at, updated_at)
         VALUES (?, ?, 'recording', ?, ?, ?)",
    )
    .bind(&doc_id)
    .bind(&title)
    .bind(&recording_id)
    .bind(created_at)
    .bind(now)
    .execute(&mut *tx)
    .await?;
```

New (add inbox_id lookup before tx):
```rust
    let inbox_id = init_system_folders(&state.db.pool).await?.inbox_id;
    let now = chrono::Utc::now().timestamp_millis();
    let doc_id = uuid::Uuid::new_v4().to_string();

    let mut tx = state.db.pool.begin().await?;

    sqlx::query(
        "INSERT INTO workspace_documents (id, title, source_type, recording_id, folder_id, created_at, updated_at)
         VALUES (?, ?, 'recording', ?, ?, ?, ?)",
    )
    .bind(&doc_id)
    .bind(&title)
    .bind(&recording_id)
    .bind(&inbox_id)
    .bind(created_at)
    .bind(now)
    .execute(&mut *tx)
    .await?;
```

Also update the `asset` INSERT timestamps to use `timestamp_millis()` for consistency. And fix the `now` in `save` calls to use `timestamp_millis()` as well.

### Step 1.5: Register commands in mod.rs and lib.rs

- [ ] In `src-tauri/src/commands/mod.rs`, add:
```rust
pub mod subtitle;
```

- [ ] In `src-tauri/src/lib.rs`, add imports at top:
```rust
use commands::{..., subtitle as subtitle_cmds};
```

- [ ] In the `collect_commands![]` macro, add:
```rust
workspace_cmds::ensure_system_folders,
workspace_cmds::list_folders_with_documents,
workspace_cmds::create_folder,
workspace_cmds::rename_folder,
workspace_cmds::delete_folder,
workspace_cmds::move_document_to_folder,
workspace_cmds::rename_document,
workspace_cmds::delete_document,
```

- [ ] After `app.manage(...)` (line ~314 in lib.rs), add system folder init spawn:
```rust
let app_handle_folders = app.handle().clone();
tauri::async_runtime::spawn(async move {
    let state = app_handle_folders.state::<crate::state::AppState>();
    if let Err(e) = workspace_cmds::init_system_folders(&state.db.pool).await {
        log::error!("Failed to init system folders: {e}");
    }
});
```

### Step 1.6: Run tests and cargo check

- [ ] Run tests:
```bash
cd src-tauri && cargo test -- --test-threads=1 2>&1 | tail -30
```
Expected: all tests pass including new ones.

- [ ] Run cargo check to regenerate bindings:
```bash
cd src-tauri && cargo check 2>&1 | grep -E "(error|warning.*unused)" | head -20
```
Expected: no errors. `src/lib/bindings.ts` gets regenerated with new commands.

> **specta recursive type note:** If `cargo check` reports a TypeScript export error on `FolderNode.children`, add `#[specta(inline)]` to the `children` field. If that still fails, change `children: Vec<FolderNode>` to `children: serde_json::Value` with `#[specta(type = "unknown[]")]` and manually add the type to bindings.ts.

### Step 1.7: Commit

- [ ] Commit:
```bash
git add src-tauri/src/commands/workspace.rs src-tauri/src/commands/mod.rs src-tauri/src/lib.rs src-tauri/src/storage/db.rs
git commit -m "feat(backend): add folder CRUD, system folders, delete_document commands"
```

---

## Task 2: Frontend — Install npm deps + WorkspaceFileTree Rewrite

**Files:**
- Modify: `package.json`
- Create: `src/store/workspace.ts`
- Modify: `src/components/workspace/WorkspaceFileTree.tsx` (full rewrite)

**Depends on:** Task 1 (backend commands + updated bindings.ts)

### Step 2.1: Install npm dependencies

- [ ] Run:
```bash
cd /Users/weijiazhao/Dev/EchoNote && npm install react-markdown remark-gfm @radix-ui/react-context-menu textarea-caret
npm install --save-dev @types/textarea-caret
```
Expected: packages added to package.json, no peer-dep errors.

### Step 2.2: Create workspace store

- [ ] Create `src/store/workspace.ts`:

```ts
// src/store/workspace.ts
import { create } from "zustand";
import { commands } from "@/lib/bindings";
import type { FolderNode, SystemFolderIds } from "@/lib/bindings";

interface WorkspaceStore {
  folderTree: FolderNode[];
  expandedFolderIds: Set<string>;
  systemFolderIds: SystemFolderIds | null;

  loadFolderTree: () => Promise<void>;
  toggleFolder: (folderId: string) => void;
  createFolder: (parentId: string | null, name: string) => Promise<void>;
  renameFolder: (folderId: string, name: string) => Promise<void>;
  deleteFolder: (folderId: string) => Promise<void>;
  moveDocument: (documentId: string, folderId: string) => Promise<void>;
  renameDocument: (documentId: string, title: string) => Promise<void>;
  deleteDocument: (documentId: string) => Promise<void>;
}

export const useWorkspaceStore = create<WorkspaceStore>((set, get) => ({
  folderTree: [],
  expandedFolderIds: new Set(),
  systemFolderIds: null,

  loadFolderTree: async () => {
    const [treeResult, sysResult] = await Promise.all([
      commands.listFoldersWithDocuments(),
      commands.ensureSystemFolders(),
    ]);
    if (treeResult.status === "ok") {
      set({ folderTree: treeResult.data });
      // Auto-expand system folders on first load
      const { expandedFolderIds } = get();
      if (expandedFolderIds.size === 0) {
        const sysIds = new Set(
          treeResult.data.filter((n) => n.is_system).map((n) => n.id)
        );
        set({ expandedFolderIds: sysIds });
      }
    }
    if (sysResult.status === "ok") {
      set({ systemFolderIds: sysResult.data });
    }
  },

  toggleFolder: (folderId) => {
    set((s) => {
      const next = new Set(s.expandedFolderIds);
      if (next.has(folderId)) next.delete(folderId);
      else next.add(folderId);
      return { expandedFolderIds: next };
    });
  },

  createFolder: async (parentId, name) => {
    const result = await commands.createFolder(parentId, name);
    if (result.status === "ok") {
      await get().loadFolderTree();
      // Auto-expand new folder's parent
      if (parentId) {
        set((s) => {
          const next = new Set(s.expandedFolderIds);
          next.add(parentId);
          return { expandedFolderIds: next };
        });
      }
    }
  },

  renameFolder: async (folderId, name) => {
    const result = await commands.renameFolder(folderId, name);
    if (result.status === "ok") await get().loadFolderTree();
  },

  deleteFolder: async (folderId) => {
    const result = await commands.deleteFolder(folderId);
    if (result.status === "ok") await get().loadFolderTree();
  },

  moveDocument: async (documentId, folderId) => {
    const result = await commands.moveDocumentToFolder(documentId, folderId);
    if (result.status === "ok") await get().loadFolderTree();
  },

  renameDocument: async (documentId, title) => {
    const result = await commands.renameDocument(documentId, title);
    if (result.status === "ok") await get().loadFolderTree();
  },

  deleteDocument: async (documentId) => {
    const result = await commands.deleteDocument(documentId);
    if (result.status === "ok") await get().loadFolderTree();
  },
}));
```

### Step 2.3: Rewrite WorkspaceFileTree.tsx

- [ ] Replace entire content of `src/components/workspace/WorkspaceFileTree.tsx`:

```tsx
// src/components/workspace/WorkspaceFileTree.tsx
import { useEffect, useState, useCallback } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import * as ContextMenu from "@radix-ui/react-context-menu";
import {
  ChevronRight, ChevronDown, Inbox, Archive, Folder,
  FileText, Plus
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspace";
import type { FolderNode, DocumentSummary } from "@/lib/bindings";

// ─── Folder item (recursive) ───────────────────────────────────────────────

function FolderItem({ node, depth }: { node: FolderNode; depth: number }) {
  const navigate = useNavigate();
  const routerState = useRouterState();
  const currentDocumentId: string | null =
    routerState.matches
      .map((m) => (m.params as Record<string, string>).documentId)
      .find(Boolean) ?? null;

  const {
    expandedFolderIds, toggleFolder, folderTree,
    createFolder, renameFolder, deleteFolder,
    moveDocument, renameDocument, deleteDocument,
  } = useWorkspaceStore();

  const [showDeleteFolderConfirm, setShowDeleteFolderConfirm] = useState(false);
  const [showDeleteDocConfirm, setShowDeleteDocConfirm] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(node.name);
  const [renamingDocId, setRenamingDocId] = useState<string | null>(null);
  const [renameDocValue, setRenameDocValue] = useState("");
  const [movingDocId, setMovingDocId] = useState<string | null>(null);

  const isExpanded = expandedFolderIds.has(node.id);

  const FolderIcon = node.folder_kind === "inbox"
    ? Inbox
    : node.folder_kind === "batch_task"
      ? Archive
      : Folder;

  // Flatten all folders for move-to select
  const allFolders = flattenTree(folderTree);

  return (
    <div>
      {/* Folder row */}
      <ContextMenu.Root>
        <ContextMenu.Trigger asChild>
          <div
            className={cn(
              "flex items-center gap-1.5 h-7 px-2 rounded cursor-pointer select-none",
              "hover:bg-bg-tertiary text-text-secondary hover:text-text-primary",
              "text-sm font-medium transition-colors"
            )}
            style={{ paddingLeft: `${8 + depth * 16}px` }}
            onClick={() => toggleFolder(node.id)}
          >
            {isExpanded
              ? <ChevronDown className="w-3.5 h-3.5 shrink-0" />
              : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
            <FolderIcon className="w-3.5 h-3.5 shrink-0 text-accent-primary/80" />
            {renaming ? (
              <input
                className="flex-1 bg-bg-secondary border border-accent-primary rounded px-1 text-sm focus:outline-none"
                value={renameValue}
                autoFocus
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={() => { setRenaming(false); renameFolder(node.id, renameValue); }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") { setRenaming(false); renameFolder(node.id, renameValue); }
                  if (e.key === "Escape") setRenaming(false);
                }}
              />
            ) : (
              <span className="flex-1 truncate">{node.name}</span>
            )}
            <span className="text-xs text-text-muted shrink-0">
              {node.documents.length + countAllDocs(node)}
            </span>
          </div>
        </ContextMenu.Trigger>

        <ContextMenu.Portal>
          <ContextMenu.Content className={cn(
            "bg-bg-primary border border-border-default rounded-md shadow-lg py-1 z-50 min-w-36",
            "text-sm text-text-primary"
          )}>
            <ContextMenu.Item
              className="px-3 py-1.5 hover:bg-bg-secondary cursor-pointer"
              onSelect={() => createFolder(node.id, "新建文件夹")}
            >
              新建子文件夹
            </ContextMenu.Item>
            <ContextMenu.Item
              className={cn(
                "px-3 py-1.5 cursor-pointer",
                node.is_system ? "opacity-40 cursor-not-allowed" : "hover:bg-bg-secondary"
              )}
              disabled={node.is_system}
              onSelect={() => { if (!node.is_system) { setRenaming(true); setRenameValue(node.name); } }}
            >
              重命名
            </ContextMenu.Item>
            <ContextMenu.Item
              className={cn(
                "px-3 py-1.5 cursor-pointer text-status-error",
                node.is_system ? "opacity-40 cursor-not-allowed" : "hover:bg-status-error/10"
              )}
              disabled={node.is_system}
              onSelect={() => { if (!node.is_system) setShowDeleteFolderConfirm(true); }}
            >
              删除
            </ContextMenu.Item>
          </ContextMenu.Content>
        </ContextMenu.Portal>
      </ContextMenu.Root>

      {/* Expanded content */}
      {isExpanded && (
        <div>
          {node.documents.map((doc) => (
            <ContextMenu.Root key={doc.id}>
              <ContextMenu.Trigger asChild>
                <button
                  className={cn(
                    "w-full text-left flex items-center gap-1.5 h-6 text-sm truncate transition-colors",
                    "hover:bg-bg-tertiary rounded",
                    currentDocumentId === doc.id
                      ? "bg-accent-primary/15 text-accent-primary"
                      : "text-text-secondary"
                  )}
                  style={{ paddingLeft: `${8 + (depth + 1) * 16}px`, paddingRight: "8px" }}
                  onClick={() => navigate({ to: "/workspace/$documentId", params: { documentId: doc.id } })}
                >
                  <FileText className="w-3 h-3 shrink-0" />
                  {renamingDocId === doc.id ? (
                    <input
                      className="flex-1 bg-bg-secondary border border-accent-primary rounded px-1 text-sm focus:outline-none"
                      value={renameDocValue}
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setRenameDocValue(e.target.value)}
                      onBlur={() => { setRenamingDocId(null); renameDocument(doc.id, renameDocValue); }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") { setRenamingDocId(null); renameDocument(doc.id, renameDocValue); }
                        if (e.key === "Escape") setRenamingDocId(null);
                      }}
                    />
                  ) : (
                    <span className="truncate">{doc.title}</span>
                  )}
                </button>
              </ContextMenu.Trigger>

              <ContextMenu.Portal>
                <ContextMenu.Content className="bg-bg-primary border border-border-default rounded-md shadow-lg py-1 z-50 min-w-36 text-sm text-text-primary">
                  <ContextMenu.Item
                    className="px-3 py-1.5 hover:bg-bg-secondary cursor-pointer"
                    onSelect={() => { setRenamingDocId(doc.id); setRenameDocValue(doc.title); }}
                  >
                    重命名
                  </ContextMenu.Item>
                  <ContextMenu.Item
                    className="px-3 py-1.5 hover:bg-bg-secondary cursor-pointer"
                    onSelect={() => setMovingDocId(doc.id)}
                  >
                    移动到…
                  </ContextMenu.Item>
                  <ContextMenu.Item
                    className="px-3 py-1.5 hover:bg-status-error/10 cursor-pointer text-status-error"
                    onSelect={() => setShowDeleteDocConfirm(doc.id)}
                  >
                    删除
                  </ContextMenu.Item>
                </ContextMenu.Content>
              </ContextMenu.Portal>
            </ContextMenu.Root>
          ))}

          {/* Child folders (recursive) */}
          {node.children.map((child) => (
            <FolderItem key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}

      {/* Delete folder confirm dialog */}
      {showDeleteFolderConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-primary border border-border-default rounded-lg shadow-xl p-5 max-w-xs w-full mx-4">
            <p className="text-sm text-text-primary mb-4">
              删除文件夹「{node.name}」？其中的文档将移回收件箱。
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteFolderConfirm(false)}
                className="px-3 py-1.5 text-sm rounded border border-border-default hover:bg-bg-secondary"
              >取消</button>
              <button
                onClick={() => { deleteFolder(node.id); setShowDeleteFolderConfirm(false); }}
                className="px-3 py-1.5 text-sm rounded bg-status-error text-white hover:opacity-90"
              >删除</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete doc confirm */}
      {showDeleteDocConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-primary border border-border-default rounded-lg shadow-xl p-5 max-w-xs w-full mx-4">
            <p className="text-sm text-text-primary mb-4">
              永久删除该文档？（录音文件不受影响）
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteDocConfirm(null)}
                className="px-3 py-1.5 text-sm rounded border border-border-default hover:bg-bg-secondary"
              >取消</button>
              <button
                onClick={() => { deleteDocument(showDeleteDocConfirm!); setShowDeleteDocConfirm(null); }}
                className="px-3 py-1.5 text-sm rounded bg-status-error text-white hover:opacity-90"
              >删除</button>
            </div>
          </div>
        </div>
      )}

      {/* Move doc dialog */}
      {movingDocId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-primary border border-border-default rounded-lg shadow-xl p-5 max-w-xs w-full mx-4">
            <p className="text-sm font-medium text-text-primary mb-3">移动到文件夹</p>
            <select
              className="w-full text-sm border border-border-default rounded px-2 py-1.5 bg-bg-secondary mb-4"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) {
                  moveDocument(movingDocId, e.target.value);
                  setMovingDocId(null);
                }
              }}
            >
              <option value="" disabled>选择文件夹…</option>
              {allFolders.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
            <div className="flex justify-end">
              <button
                onClick={() => setMovingDocId(null)}
                className="px-3 py-1.5 text-sm rounded border border-border-default hover:bg-bg-secondary"
              >取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function flattenTree(nodes: FolderNode[]): Array<{ id: string; name: string }> {
  const result: Array<{ id: string; name: string }> = [];
  function walk(n: FolderNode) {
    result.push({ id: n.id, name: n.name });
    n.children.forEach(walk);
  }
  nodes.forEach(walk);
  return result;
}

function countAllDocs(node: FolderNode): number {
  return node.children.reduce((sum, c) => sum + c.documents.length + countAllDocs(c), 0);
}

// ─── Main component ─────────────────────────────────────────────────────────

export function WorkspaceFileTree() {
  const { folderTree, loadFolderTree, createFolder } = useWorkspaceStore();

  useEffect(() => {
    loadFolderTree();
    const timer = setInterval(loadFolderTree, 5000);
    return () => clearInterval(timer);
  }, [loadFolderTree]);

  const systemFolders = folderTree.filter((n) => n.is_system);
  const userFolders = folderTree.filter((n) => !n.is_system);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-3 py-2 flex items-center justify-between border-b border-border-default">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          文件
        </span>
        <button
          onClick={() => createFolder(null, "新建文件夹")}
          className="p-0.5 rounded hover:bg-bg-tertiary text-text-muted hover:text-text-primary"
          title="新建文件夹"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1 px-1">
        {systemFolders.map((node) => (
          <FolderItem key={node.id} node={node} depth={0} />
        ))}

        {userFolders.length > 0 && (
          <hr className="my-2 border-border-default" />
        )}
        {userFolders.map((node) => (
          <FolderItem key={node.id} node={node} depth={0} />
        ))}
      </div>
    </div>
  );
}
```

### Step 2.4: Update workspace.tsx to trigger tree load

- [ ] Verify `src/routes/workspace.tsx` calls `setSecondPanelContent(<WorkspaceFileTree />)` — it already does, no change needed. The store's `loadFolderTree` is called inside the component's `useEffect`.

### Step 2.5: Manual test in dev

- [ ] Run dev server:
```bash
npm run tauri dev
```
- Open workspace → verify folder tree appears with 收件箱 and 批量任务
- Right-click folder → verify menu appears
- Create new folder → verify it appears
- Click a recording document → verify navigation works

### Step 2.6: Commit

```bash
git add src/store/workspace.ts src/components/workspace/WorkspaceFileTree.tsx package.json package-lock.json
git commit -m "feat(frontend): rewrite WorkspaceFileTree with folder tree and context menus"
```

---

## Task 3: Frontend — EditableAsset Markdown Dual-Mode

**Files:**
- Modify: `src/components/workspace/EditableAsset.tsx`

**Can run in parallel with Task 2.**

### Step 3.1: Write test for EditableAsset

The existing component is presentational with Tauri calls. We test by verifying the view/edit mode toggle behavior manually. Skip automated tests for this UI component.

### Step 3.2: Add Markdown dual-mode to EditableAsset.tsx

- [ ] Replace content of `src/components/workspace/EditableAsset.tsx`:

```tsx
// src/components/workspace/EditableAsset.tsx
import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { commands } from "@/lib/bindings";
import { ChevronDown, ChevronRight, Check, Loader2, Eye, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EditableAssetHandle {
  insertAtCursor: (text: string) => void;
  getTextareaRef: () => HTMLTextAreaElement | null;
}

interface EditableAssetProps {
  documentId: string;
  role: string;
  label: string;
  initialContent: string;
  onSaved?: () => void;
}

type SaveState = "idle" | "saving" | "saved";
type EditMode = "view" | "edit";

export const EditableAsset = forwardRef<EditableAssetHandle, EditableAssetProps>(
  function EditableAsset({ documentId, role, label, initialContent, onSaved }, ref) {
    const [open, setOpen] = useState(true);
    const [content, setContent] = useState(initialContent);
    const [saveState, setSaveState] = useState<SaveState>("idle");
    const [mode, setMode] = useState<EditMode>("view");
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastSavedRef = useRef(initialContent);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      insertAtCursor: (text: string) => {
        const el = textareaRef.current;
        if (!el) return;
        // Switch to edit mode first
        setMode("edit");
        setTimeout(() => {
          if (!textareaRef.current) return;
          const start = textareaRef.current.selectionStart;
          const end = textareaRef.current.selectionEnd;
          textareaRef.current.setRangeText(text, start, end, "end");
          textareaRef.current.dispatchEvent(new Event("input", { bubbles: true }));
        }, 50);
      },
      getTextareaRef: () => textareaRef.current,
    }));

    useEffect(() => {
      if (content === lastSavedRef.current) {
        setContent(initialContent);
        lastSavedRef.current = initialContent;
      }
    }, [initialContent]);

    const save = useCallback(
      async (text: string) => {
        if (text === lastSavedRef.current) return;
        setSaveState("saving");
        const result = await commands.updateDocumentAsset(documentId, role, text);
        if (result.status === "ok") {
          lastSavedRef.current = text;
          setSaveState("saved");
          onSaved?.();
          setTimeout(() => setSaveState("idle"), 2000);
        } else {
          setSaveState("idle");
        }
      },
      [documentId, role, onSaved]
    );

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const text = e.target.value;
      setContent(text);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => save(text), 1500);
    };

    // Handle synthetic input events from insertAtCursor
    const handleInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
      const text = (e.target as HTMLTextAreaElement).value;
      setContent(text);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => save(text), 1500);
    };

    useEffect(() => {
      return () => { if (timerRef.current) clearTimeout(timerRef.current); };
    }, []);

    // Auto-focus textarea when switching to edit
    useEffect(() => {
      if (mode === "edit") textareaRef.current?.focus();
    }, [mode]);

    return (
      <section className="flex flex-col gap-2">
        {/* Section header */}
        <div className="flex items-center justify-between">
          <button
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wide hover:text-text-primary transition-colors"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            {label}
          </button>

          <div className="flex items-center gap-2">
            {saveState === "saving" && (
              <span className="flex items-center gap-1 text-xs text-text-muted">
                <Loader2 className="w-3 h-3 animate-spin" />保存中…
              </span>
            )}
            {saveState === "saved" && (
              <span className="flex items-center gap-1 text-xs text-status-success">
                <Check className="w-3 h-3" />已保存
              </span>
            )}
            {open && (
              <button
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors px-1.5 py-0.5 rounded hover:bg-bg-tertiary"
                onClick={() => setMode(mode === "view" ? "edit" : "view")}
              >
                {mode === "view"
                  ? <><Pencil className="w-3 h-3" />编辑</>
                  : <><Eye className="w-3 h-3" />预览</>}
              </button>
            )}
          </div>
        </div>

        {/* Content area */}
        {open && (
          <>
            {mode === "view" ? (
              <div
                className={cn(
                  "prose prose-sm max-w-none cursor-text min-h-[80px]",
                  "text-text-primary leading-relaxed",
                  "[&_h1]:text-xl [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2",
                  "[&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1",
                  "[&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1",
                  "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
                  "[&_table]:border-collapse [&_th]:border [&_th]:border-border-default [&_th]:px-3 [&_th]:py-1",
                  "[&_td]:border [&_td]:border-border-default [&_td]:px-3 [&_td]:py-1",
                  "[&_code]:bg-bg-tertiary [&_code]:px-1 [&_code]:rounded [&_code]:text-xs",
                  "[&_blockquote]:border-l-4 [&_blockquote]:border-accent-primary/50 [&_blockquote]:pl-3 [&_blockquote]:text-text-muted"
                )}
                onClick={() => setMode("edit")}
              >
                {content ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                ) : (
                  <p className="text-text-muted text-sm">点击编辑…</p>
                )}
              </div>
            ) : (
              <textarea
                ref={textareaRef}
                value={content}
                onChange={handleChange}
                onInput={handleInput}
                className={cn(
                  "w-full min-h-[120px] text-sm text-text-primary leading-relaxed",
                  "rounded-md bg-bg-secondary border border-border-default p-3",
                  "resize-y focus:outline-none focus:ring-1 focus:ring-accent-primary",
                  "placeholder:text-text-muted font-mono"
                )}
                placeholder={`在此输入 ${label}…（支持 Markdown）`}
                spellCheck={false}
              />
            )}
          </>
        )}
      </section>
    );
  }
);
```

### Step 3.3: Verify build

```bash
npm run build 2>&1 | grep -E "error|Error" | head -20
```
Expected: no errors.

### Step 3.4: Commit

```bash
git add src/components/workspace/EditableAsset.tsx
git commit -m "feat(frontend): add Markdown dual-mode to EditableAsset"
```

---

## Task 4: Frontend — Document Page Layout Refactor

**Files:**
- Modify: `src/routes/workspace.$documentId.tsx`

**Depends on:** Task 1 (rename_document command), Task 3 (EditableAsset forwardRef handle)

### Step 4.1: Refactor workspace.$documentId.tsx

- [ ] Replace the entire file `src/routes/workspace.$documentId.tsx`:

```tsx
// src/routes/workspace.$documentId.tsx
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "@tanstack/react-router";
import { commands } from "@/lib/bindings";
import type { DocumentAsset, RecordingItem } from "@/lib/bindings";
import { formatDuration, formatDate } from "@/lib/format";
import { AudioPlayer } from "@/components/workspace/AudioPlayer";
import { EditableAsset, type EditableAssetHandle } from "@/components/workspace/EditableAsset";
import { AiPanel } from "@/components/workspace/AiPanel";
import { SubtitleEditor } from "@/components/workspace/SubtitleEditor";
import { Mic, Clock, Trash2, Sparkles, Captions } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspace";

export const Route = createFileRoute("/workspace/$documentId")({
  component: DocumentPage,
});

const ROLE_META: Record<string, { label: string; order: number }> = {
  transcript:    { label: "转写原文",  order: 0 },
  document_text: { label: "文档正文",  order: 1 },
  summary:       { label: "摘要",      order: 2 },
  meeting_brief: { label: "会议纪要",  order: 3 },
  translation:   { label: "翻译",      order: 4 },
  decisions:     { label: "决策",      order: 5 },
  action_items:  { label: "行动项",    order: 6 },
  next_steps:    { label: "下一步",    order: 7 },
};

type DocMode = "document" | "subtitle";

function DocumentPage() {
  const { documentId } = Route.useParams();
  const navigate = useNavigate();
  const { loadFolderTree, folderTree } = useWorkspaceStore();

  const [assets, setAssets] = useState<DocumentAsset[]>([]);
  const [recording, setRecording] = useState<RecordingItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [alsoDeleteDoc, setAlsoDeleteDoc] = useState(true);
  const [mode, setMode] = useState<DocMode>("document");
  const [titleEditing, setTitleEditing] = useState(false);
  const [titleValue, setTitleValue] = useState("");

  // Refs to each asset panel so AiPanel can insert text
  const assetRefs = useRef<Record<string, EditableAssetHandle | null>>({});

  const sortAssets = useCallback((raw: DocumentAsset[]) =>
    [...raw].sort((a, b) => {
      const ao = ROLE_META[a.role]?.order ?? 99;
      const bo = ROLE_META[b.role]?.order ?? 99;
      return ao - bo;
    }), []);

  const loadData = useCallback(async () => {
    const [assetsResult, recordingsResult] = await Promise.all([
      commands.getDocumentAssets(documentId),
      commands.listRecordings(),
    ]);
    if (assetsResult.status === "ok") setAssets(sortAssets(assetsResult.data));
    if (recordingsResult.status === "ok") {
      const rec = recordingsResult.data.find((r) => r.document_id === documentId);
      setRecording(rec ?? null);
      if (rec) setTitleValue(rec.title);
    }
    setLoading(false);
  }, [documentId, sortAssets]);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll for new assets after AI tasks
  useEffect(() => {
    const timer = setInterval(async () => {
      const result = await commands.getDocumentAssets(documentId);
      if (result.status === "ok") setAssets(sortAssets(result.data));
    }, 3000);
    return () => clearInterval(timer);
  }, [documentId, sortAssets]);

  // Folder name for meta row
  const folderName = useCallback(() => {
    function findFolder(nodes: typeof folderTree, docId: string): string | null {
      for (const node of nodes) {
        if (node.documents.some((d) => d.id === docId)) return node.name;
        const found = findFolder(node.children, docId);
        if (found) return found;
      }
      return null;
    }
    return findFolder(folderTree, documentId) ?? "收件箱";
  }, [folderTree, documentId]);

  // Transcript content for AiPanel
  const transcriptContent = assets.find((a) => a.role === "transcript")?.content ?? "";

  // insertAtCursor: target first visible asset textarea in edit mode
  const handleInsertAtCursor = useCallback((text: string) => {
    const firstRef = Object.values(assetRefs.current)[0];
    firstRef?.insertAtCursor(text);
  }, []);

  const handleTitleBlur = async () => {
    setTitleEditing(false);
    if (recording && titleValue !== recording.title) {
      await commands.renameDocument(documentId, titleValue);
      loadFolderTree();
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        Loading...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Document header */}
      <div className="shrink-0 px-6 py-4 border-b border-border-default">
        {/* Title row */}
        <div className="flex items-center gap-2 min-w-0">
          <Mic className="w-4 h-4 shrink-0 text-accent-primary" />
          <input
            value={titleValue}
            readOnly={!titleEditing}
            onClick={() => setTitleEditing(true)}
            onBlur={handleTitleBlur}
            onChange={(e) => setTitleValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
            className={cn(
              "flex-1 bg-transparent font-semibold text-base text-text-primary focus:outline-none truncate",
              titleEditing && "border-b border-accent-primary pb-0.5"
            )}
          />
          {/* Mode switch */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setMode("document")}
              className={cn(
                "px-2 py-1 text-xs rounded transition-colors",
                mode === "document"
                  ? "bg-accent-primary/15 text-accent-primary"
                  : "text-text-muted hover:text-text-primary hover:bg-bg-tertiary"
              )}
            >
              📄 文档
            </button>
            {recording?.file_path && (
              <button
                onClick={() => setMode("subtitle")}
                className={cn(
                  "px-2 py-1 text-xs rounded transition-colors",
                  mode === "subtitle"
                    ? "bg-accent-primary/15 text-accent-primary"
                    : "text-text-muted hover:text-text-primary hover:bg-bg-tertiary"
                )}
              >
                🎬 字幕
              </button>
            )}
          </div>
          {/* AI Panel trigger */}
          <AiPanel
            documentId={documentId}
            transcriptContent={transcriptContent}
            onInsertAtCursor={handleInsertAtCursor}
          />
          {/* Delete */}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0 p-1.5 rounded text-text-muted hover:text-status-error hover:bg-status-error/10 transition-colors"
            title="删除录音"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* Meta row */}
        {recording && (
          <div className="flex items-center gap-2 mt-1 text-xs text-text-muted">
            <span>{formatDate(recording.created_at)}</span>
            <span>·</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(recording.duration_ms)}
            </span>
            <span>·</span>
            <span>{folderName()}</span>
          </div>
        )}

        {/* Audio player — hidden in subtitle mode */}
        {recording?.file_path && mode === "document" && (
          <div className="mt-2">
            <AudioPlayer
              key={recording.file_path}
              filePath={recording.file_path}
              durationMs={recording.duration_ms}
            />
          </div>
        )}
      </div>

      {/* Content area */}
      {mode === "document" ? (
        <div className="flex-1 px-6 py-4 flex flex-col gap-4 overflow-y-auto">
          {assets.length === 0 ? (
            <p className="text-sm text-text-muted">
              暂无内容。录音结束后转写内容会自动显示，或点击右上角 AI 工具生成摘要。
            </p>
          ) : (
            assets.map((asset) => {
              const meta = ROLE_META[asset.role] ?? { label: asset.role, order: 99 };
              return (
                <EditableAsset
                  key={asset.id}
                  ref={(el) => { assetRefs.current[asset.role] = el; }}
                  documentId={documentId}
                  role={asset.role}
                  label={meta.label}
                  initialContent={asset.content}
                  onSaved={loadData}
                />
              );
            })
          )}
        </div>
      ) : (
        recording?.file_path && (
          <SubtitleEditor
            recordingId={recording.id}
            filePath={recording.file_path}
            durationMs={recording.duration_ms}
          />
        )
      )}

      {/* Delete dialog */}
      {showDeleteConfirm && recording && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-primary border border-border-default rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h2 className="text-base font-semibold text-text-primary mb-2">删除录音</h2>
            <p className="text-sm text-text-secondary mb-4">
              「{recording.title}」将被永久删除，音频文件也会从磁盘移除。
            </p>
            <label className="flex items-center gap-2 mb-5 cursor-pointer">
              <input
                type="checkbox"
                checked={alsoDeleteDoc}
                onChange={(e) => setAlsoDeleteDoc(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-text-primary">同时删除工作台文档（转写、摘要等内容）</span>
            </label>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-sm rounded-md border border-border-default text-text-primary hover:bg-bg-secondary"
              >取消</button>
              <button
                onClick={async () => {
                  const result = await commands.deleteRecording(recording.id, alsoDeleteDoc);
                  if (result.status === "ok") navigate({ to: "/workspace" });
                  setShowDeleteConfirm(false);
                }}
                className="px-4 py-2 text-sm rounded-md bg-status-error text-white hover:opacity-90"
              >删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

> **Note:** `AiPanel` and `SubtitleEditor` are stub-imported here. Create them as empty stubs before building (see Tasks 5 and 7).

### Step 4.2: Create stub files for AiPanel and SubtitleEditor

- [ ] Create `src/components/workspace/AiPanel.tsx` (stub):
```tsx
// Stub — replaced in Task 5
export function AiPanel(_props: { documentId: string; transcriptContent: string; onInsertAtCursor: (t: string) => void }) {
  return null;
}
```

- [ ] Create `src/components/workspace/SubtitleEditor.tsx` (stub):
```tsx
// Stub — replaced in Task 7
export function SubtitleEditor(_props: { recordingId: string; filePath: string; durationMs: number }) {
  return <div className="flex-1 flex items-center justify-center text-text-muted text-sm">字幕编辑器（开发中）</div>;
}
```

### Step 4.3: Verify build

```bash
npm run build 2>&1 | grep -E "^.*error" | head -20
```
Expected: no errors.

### Step 4.4: Commit

```bash
git add src/routes/workspace.\$documentId.tsx src/components/workspace/AiPanel.tsx src/components/workspace/SubtitleEditor.tsx
git commit -m "feat(frontend): Obsidian-style document page layout with mode switch and inline title"
```

---

## Task 5: Frontend — AiPanel + AiInlineToolbar

**Files:**
- Modify: `src/components/workspace/AiPanel.tsx` (replace stub)
- Create: `src/components/workspace/AiInlineToolbar.tsx`
- Modify: `src/components/workspace/EditableAsset.tsx` (add AiInlineToolbar integration)

**Depends on:** Task 3 (EditableAsset textarea ref), Task 4 (AiPanel stub exists)

### Step 5.1: Implement AiPanel.tsx

- [ ] Replace `src/components/workspace/AiPanel.tsx`:

```tsx
// src/components/workspace/AiPanel.tsx
import { useState, useRef } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Sparkles, X, Loader2, Check } from "lucide-react";
import { commands } from "@/lib/bindings";
import { cn } from "@/lib/utils";

const TRANSLATION_LANGUAGES = [
  { value: "en", label: "英文" },
  { value: "ja", label: "日文" },
  { value: "ko", label: "韩文" },
  { value: "fr", label: "法文" },
  { value: "de", label: "德文" },
  { value: "es", label: "西班牙文" },
  { value: "ru", label: "俄文" },
] as const;

interface AiPanelProps {
  documentId: string;
  transcriptContent: string;
  onInsertAtCursor: (text: string) => void;
}

type TaskType = "summary" | "meeting_brief" | "translation" | null;

export function AiPanel({ documentId, transcriptContent, onInsertAtCursor }: AiPanelProps) {
  const [open, setOpen] = useState(false);
  const [activeTask, setActiveTask] = useState<TaskType>(null);
  const [targetLang, setTargetLang] = useState("en");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [generatedText, setGeneratedText] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startTask = async (task: "summary" | "meeting_brief" | "translation") => {
    setActiveTask(task);
    setStatus("running");
    setGeneratedText("");

    // LlmTaskRequest uses snake_case field names (specta generates bindings.ts with snake_case)
    const result = await commands.submitLlmTask({
      document_id: documentId,
      task_type: task === "translation"
        ? { type: "translation", data: { target_language: targetLang } }
        : { type: task as "summary" | "meeting_brief" },
      text_role_hint: null,
    });

    if (result.status !== "ok") {
      setStatus("error");
      return;
    }
    const tid = result.data;
    setTaskId(tid);

    // Poll for completion
    pollRef.current = setInterval(async () => {
      const tasks = await commands.listDocumentLlmTasks(documentId);
      if (tasks.status !== "ok") return;
      const t = tasks.data.find((x: any) => x.id === tid);
      if (!t) return;
      if (t.status === "completed") {
        clearInterval(pollRef.current!);
        setStatus("done");
        // Fetch updated asset content
        const assets = await commands.getDocumentAssets(documentId);
        if (assets.status === "ok") {
          const roleMap: Record<string, string> = {
            summary: "summary",
            meeting_brief: "meeting_brief",
            translation: "translation",
          };
          const asset = assets.data.find((a: any) => a.role === roleMap[task]);
          setGeneratedText(asset?.content ?? "");
        }
      } else if (t.status === "failed") {
        clearInterval(pollRef.current!);
        setStatus("error");
      }
    }, 1500);
  };

  const handleInsert = () => {
    onInsertAtCursor(generatedText);
    setOpen(false);
    setStatus("idle");
    setGeneratedText("");
  };

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          className={cn(
            "shrink-0 flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors",
            "text-text-muted hover:text-text-primary hover:bg-bg-tertiary"
          )}
        >
          <Sparkles className="w-3.5 h-3.5" />
          AI 工具
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={8}
          className={cn(
            "bg-bg-primary border border-border-default rounded-lg shadow-xl p-4",
            "w-72 z-50"
          )}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-text-primary">AI 工具</span>
            <Popover.Close asChild>
              <button className="text-text-muted hover:text-text-primary">
                <X className="w-3.5 h-3.5" />
              </button>
            </Popover.Close>
          </div>

          {/* Task buttons */}
          <div className="flex flex-col gap-1.5 mb-3">
            <button
              onClick={() => startTask("summary")}
              disabled={status === "running"}
              className="text-left px-3 py-2 text-sm rounded hover:bg-bg-secondary text-text-primary disabled:opacity-50 transition-colors"
            >
              生成摘要
            </button>
            <button
              onClick={() => startTask("meeting_brief")}
              disabled={status === "running"}
              className="text-left px-3 py-2 text-sm rounded hover:bg-bg-secondary text-text-primary disabled:opacity-50 transition-colors"
            >
              会议纪要
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={() => startTask("translation")}
                disabled={status === "running"}
                className="flex-1 text-left px-3 py-2 text-sm rounded hover:bg-bg-secondary text-text-primary disabled:opacity-50 transition-colors"
              >
                翻译
              </button>
              <select
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                className="text-xs border border-border-default rounded px-1.5 py-1 bg-bg-secondary text-text-primary"
              >
                {TRANSLATION_LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Status / preview */}
          {status === "running" && (
            <div className="flex items-center gap-2 text-xs text-text-muted py-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              生成中…
            </div>
          )}
          {status === "done" && generatedText && (
            <div className="mt-2">
              <div className="text-xs text-text-muted mb-1">预览</div>
              <div className="text-sm text-text-primary bg-bg-secondary rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {generatedText.slice(0, 300)}{generatedText.length > 300 ? "…" : ""}
              </div>
              <button
                onClick={handleInsert}
                className="mt-2 w-full px-3 py-1.5 text-xs bg-accent-primary text-white rounded hover:opacity-90"
              >
                插入到光标位置
              </button>
            </div>
          )}
          {status === "error" && (
            <p className="text-xs text-status-error mt-1">生成失败，请重试。</p>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
```

> **Note:** `@radix-ui/react-popover` is needed. Install if not present:
```bash
npm install @radix-ui/react-popover
```

### Step 5.2: Create AiInlineToolbar.tsx

- [ ] Create `src/components/workspace/AiInlineToolbar.tsx`:

```tsx
// src/components/workspace/AiInlineToolbar.tsx
import { useState, useEffect } from "react";
import getCaretCoordinates from "textarea-caret";
import { cn } from "@/lib/utils";

const TRANSLATION_LANGUAGES = [
  { value: "en", label: "英文" },
  { value: "ja", label: "日文" },
  { value: "ko", label: "韩文" },
  { value: "fr", label: "法文" },
  { value: "de", label: "德文" },
  { value: "es", label: "西班牙文" },
  { value: "ru", label: "俄文" },
] as const;

interface AiInlineToolbarProps {
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onInsert: (text: string) => void;
}

interface ToolbarPosition {
  top: number;
  left: number;
}

export function AiInlineToolbar({ textareaRef, onInsert }: AiInlineToolbarProps) {
  const [position, setPosition] = useState<ToolbarPosition | null>(null);
  const [selectedText, setSelectedText] = useState("");
  const [showLangMenu, setShowLangMenu] = useState(false);

  const updatePosition = () => {
    const el = textareaRef.current;
    if (!el) return;
    const { selectionStart, selectionEnd } = el;
    if (selectionStart === selectionEnd) {
      setPosition(null);
      return;
    }
    setSelectedText(el.value.substring(selectionStart, selectionEnd));

    const caret = getCaretCoordinates(el, selectionStart);
    const rect = el.getBoundingClientRect();
    const TOOLBAR_H = 36;

    let top = rect.top + caret.top - el.scrollTop - TOOLBAR_H - 4;
    const left = Math.min(rect.left + caret.left, window.innerWidth - 180);

    // If too close to top, show below selection
    if (top < 0) {
      const caretEnd = getCaretCoordinates(el, selectionEnd);
      top = rect.top + caretEnd.top - el.scrollTop + caretEnd.height + 4;
    }

    setPosition({ top, left });
  };

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const handle = () => updatePosition();
    el.addEventListener("mouseup", handle);
    el.addEventListener("keyup", handle);
    return () => {
      el.removeEventListener("mouseup", handle);
      el.removeEventListener("keyup", handle);
    };
  }, [textareaRef]);

  // Hide toolbar on click outside
  useEffect(() => {
    const hide = (e: MouseEvent) => {
      const el = textareaRef.current;
      if (el && !el.contains(e.target as Node)) setPosition(null);
    };
    document.addEventListener("mousedown", hide);
    return () => document.removeEventListener("mousedown", hide);
  }, [textareaRef]);

  if (!position) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(selectedText).catch(() => {});
    setPosition(null);
  };

  return (
    <div
      className={cn(
        "fixed z-50 flex items-center gap-1 px-2 py-1",
        "bg-bg-primary border border-border-default rounded-lg shadow-lg",
        "text-xs text-text-primary"
      )}
      style={{ top: position.top, left: position.left }}
      onMouseDown={(e) => e.preventDefault()} // prevent textarea blur
    >
      <div className="relative">
        <button
          className="px-2 py-0.5 rounded hover:bg-bg-secondary flex items-center gap-1"
          onClick={() => setShowLangMenu((v) => !v)}
        >
          翻译 ▾
        </button>
        {showLangMenu && (
          <div className="absolute top-full left-0 mt-1 bg-bg-primary border border-border-default rounded shadow-lg z-10">
            {TRANSLATION_LANGUAGES.map((l) => (
              <button
                key={l.value}
                className="block w-full text-left px-3 py-1.5 hover:bg-bg-secondary text-xs"
                onClick={() => {
                  // For inline translate, just copy selection with language note
                  // Full LLM call would need documentId — simplified version
                  onInsert(`[翻译(${l.label}): ${selectedText}]`);
                  setShowLangMenu(false);
                  setPosition(null);
                }}
              >
                {l.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        className="px-2 py-0.5 rounded hover:bg-bg-secondary"
        onClick={handleCopy}
      >
        复制
      </button>
    </div>
  );
}
```

### Step 5.3: Integrate AiInlineToolbar into EditableAsset

- [ ] In `src/components/workspace/EditableAsset.tsx`, add import and render the toolbar inside Edit mode:

Add import:
```tsx
import { AiInlineToolbar } from "@/components/workspace/AiInlineToolbar";
```

Inside the Edit mode block, wrap textarea and toolbar in a relative div:
```tsx
) : (
  <div className="relative">
    <textarea
      ref={textareaRef}
      {/* existing props */}
    />
    <AiInlineToolbar
      textareaRef={textareaRef}
      onInsert={(text) => {
        const el = textareaRef.current;
        if (!el) return;
        const start = el.selectionStart;
        const end = el.selectionEnd;
        el.setRangeText(text, start, end, "end");
        el.dispatchEvent(new Event("input", { bubbles: true }));
      }}
    />
  </div>
)}
```

### Step 5.4: Verify build and manual test

```bash
npm run build 2>&1 | grep -E "^.*error" | head -20
```

Manual test:
- Open a document → click "AI 工具" → verify popover opens
- Click "生成摘要" → verify loading spinner appears
- In Edit mode, select text in textarea → verify inline toolbar appears above selection

### Step 5.5: Commit

```bash
git add src/components/workspace/AiPanel.tsx src/components/workspace/AiInlineToolbar.tsx src/components/workspace/EditableAsset.tsx
git commit -m "feat(frontend): add AiPanel popover and AiInlineToolbar"
```

---

## Task 6: Backend — Subtitle System

**Files:**
- Create: `src-tauri/src/storage/migrations/0003_segment_translations.sql`
- Create: `src-tauri/src/commands/subtitle.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/src/storage/db.rs` (add test)

**Can run in parallel with Tasks 2, 3 after Task 1.**

### Step 6.1: Write failing test for subtitle migration

- [ ] In `src-tauri/src/storage/db.rs`, add:

```rust
#[tokio::test]
async fn test_segment_translations_table_created() {
    let db = Db::open("sqlite::memory:").await.unwrap();
    let row: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='segment_translations'"
    )
    .fetch_one(&db.pool)
    .await
    .unwrap();
    assert_eq!(row.0, 1, "segment_translations table should exist after migration 0003");
}

#[tokio::test]
async fn test_segment_translations_unique_constraint() {
    let db = Db::open("sqlite::memory:").await.unwrap();
    let now = 1_700_000_000_000_i64;

    // Need a recording first
    sqlx::query(
        "INSERT INTO recordings (id, title, file_path, duration_ms, created_at, updated_at)
         VALUES ('rec1', 'Test', '/tmp/test.wav', 1000, ?, ?)"
    ).bind(now).bind(now).execute(&db.pool).await.unwrap();

    // Need a segment
    sqlx::query(
        "INSERT INTO transcription_segments (recording_id, start_ms, end_ms, text)
         VALUES ('rec1', 0, 1000, 'hello')"
    ).execute(&db.pool).await.unwrap();

    let seg_id: i64 = sqlx::query_scalar("SELECT id FROM transcription_segments LIMIT 1")
        .fetch_one(&db.pool).await.unwrap();

    let trans_id = uuid::Uuid::new_v4().to_string();
    sqlx::query(
        "INSERT INTO segment_translations (id, segment_id, language, text, created_at)
         VALUES (?, ?, 'en', 'hello', ?)"
    ).bind(&trans_id).bind(seg_id).bind(now).execute(&db.pool).await.unwrap();

    // Duplicate should fail
    let dup_id = uuid::Uuid::new_v4().to_string();
    let result = sqlx::query(
        "INSERT INTO segment_translations (id, segment_id, language, text, created_at)
         VALUES (?, ?, 'en', 'world', ?)"
    ).bind(&dup_id).bind(seg_id).bind(now).execute(&db.pool).await;
    assert!(result.is_err(), "duplicate (segment_id, language) should fail");
}
```

- [ ] Run to confirm fail:
```bash
cd src-tauri && cargo test test_segment_translations -- --test-threads=1 2>&1 | tail -10
```

### Step 6.2: Create migration file

- [ ] Create `src-tauri/src/storage/migrations/0003_segment_translations.sql`:

```sql
CREATE TABLE segment_translations (
    id          TEXT PRIMARY KEY,
    segment_id  INTEGER NOT NULL REFERENCES transcription_segments(id) ON DELETE CASCADE,
    language    TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    UNIQUE(segment_id, language)
);
CREATE INDEX idx_seg_translations ON segment_translations(segment_id, language);
```

### Step 6.3: Create subtitle.rs

- [ ] Create `src-tauri/src/commands/subtitle.rs`:

```rust
// src-tauri/src/commands/subtitle.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;
use crate::error::AppError;
use crate::state::AppState;

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct SegmentRow {
    pub id: i64,
    pub recording_id: String,
    pub start_ms: i64,
    pub end_ms: i64,
    pub text: String,
    pub translated_text: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(rename_all = "snake_case")]
pub enum SubtitleFormat {
    Srt,
    Vtt,
    Lrc,
}

#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(tag = "type", content = "data", rename_all = "snake_case")]
pub enum SubtitleLanguage {
    Original,
    Translation(String),
}

#[tauri::command]
#[specta::specta]
pub async fn get_segments_with_translations(
    recording_id: String,
    language: Option<String>,
    state: State<'_, AppState>,
) -> Result<Vec<SegmentRow>, AppError> {
    if let Some(ref lang) = language {
        let rows: Vec<(i64, String, i64, i64, String, Option<String>)> = sqlx::query_as(
            "SELECT ts.id, ts.recording_id, ts.start_ms, ts.end_ms, ts.text, st.text
             FROM transcription_segments ts
             LEFT JOIN segment_translations st
               ON st.segment_id = ts.id AND st.language = ?
             WHERE ts.recording_id = ?
             ORDER BY ts.start_ms"
        )
        .bind(lang)
        .bind(&recording_id)
        .fetch_all(&state.db.pool)
        .await?;

        Ok(rows.into_iter().map(|(id, recording_id, start_ms, end_ms, text, translated_text)| {
            SegmentRow { id, recording_id, start_ms, end_ms, text, translated_text }
        }).collect())
    } else {
        let rows: Vec<(i64, String, i64, i64, String)> = sqlx::query_as(
            "SELECT id, recording_id, start_ms, end_ms, text
             FROM transcription_segments
             WHERE recording_id = ?
             ORDER BY start_ms"
        )
        .bind(&recording_id)
        .fetch_all(&state.db.pool)
        .await?;

        Ok(rows.into_iter().map(|(id, recording_id, start_ms, end_ms, text)| {
            SegmentRow { id, recording_id, start_ms, end_ms, text, translated_text: None }
        }).collect())
    }
}

#[tauri::command]
#[specta::specta]
pub async fn update_segment_timing(
    segment_id: i64,
    start_ms: i64,
    end_ms: i64,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    if start_ms >= end_ms {
        return Err(AppError::Validation("start_ms must be less than end_ms".into()));
    }
    sqlx::query("UPDATE transcription_segments SET start_ms = ?, end_ms = ? WHERE id = ?")
        .bind(start_ms)
        .bind(end_ms)
        .bind(segment_id)
        .execute(&state.db.pool)
        .await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn update_segment_translation(
    segment_id: i64,
    language: String,
    text: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    let now = chrono::Utc::now().timestamp_millis();
    let id = uuid::Uuid::new_v4().to_string();
    sqlx::query(
        "INSERT INTO segment_translations (id, segment_id, language, text, created_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(segment_id, language) DO UPDATE SET text = excluded.text"
    )
    .bind(&id)
    .bind(segment_id)
    .bind(&language)
    .bind(&text)
    .bind(now)
    .execute(&state.db.pool)
    .await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn align_translation_to_segments(
    document_id: String,
    language: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    // Get recording_id from document
    let recording_id: Option<String> = sqlx::query_scalar(
        "SELECT recording_id FROM workspace_documents WHERE id = ?"
    )
    .bind(&document_id)
    .fetch_optional(&state.db.pool)
    .await?
    .flatten();

    let recording_id = recording_id.ok_or_else(|| AppError::NotFound(document_id.clone()))?;

    // Get segments
    let segment_ids: Vec<i64> = sqlx::query_scalar(
        "SELECT id FROM transcription_segments WHERE recording_id = ? ORDER BY start_ms"
    )
    .bind(&recording_id)
    .fetch_all(&state.db.pool)
    .await?;

    let n = segment_ids.len();
    if n == 0 { return Ok(()); }

    // Get translation content
    let content: Option<String> = sqlx::query_scalar(
        "SELECT content FROM workspace_text_assets WHERE document_id = ? AND role = 'translation'"
    )
    .bind(&document_id)
    .fetch_optional(&state.db.pool)
    .await?;

    let content = content.ok_or_else(|| AppError::Validation("no translation asset found".into()))?;

    // Split into sentences
    let sentences: Vec<&str> = regex::Regex::new(r"[。.!?！？\n]+")
        .unwrap()
        .split(&content)
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();

    let m = sentences.len();
    if m == 0 { return Ok(()); }

    // Proportional mapping: segment[i] → sentences[min(round(i * m / n), m-1)]
    let now = chrono::Utc::now().timestamp_millis();
    let mut tx = state.db.pool.begin().await?;
    for (i, seg_id) in segment_ids.iter().enumerate() {
        let j = ((i * m + n / 2) / n).min(m - 1);
        let text = sentences[j];
        let id = uuid::Uuid::new_v4().to_string();
        sqlx::query(
            "INSERT INTO segment_translations (id, segment_id, language, text, created_at)
             VALUES (?, ?, ?, ?, ?)
             ON CONFLICT(segment_id, language) DO UPDATE SET text = excluded.text"
        )
        .bind(&id)
        .bind(seg_id)
        .bind(&language)
        .bind(text)
        .bind(now)
        .execute(&mut *tx)
        .await?;
    }
    tx.commit().await?;
    Ok(())
}

#[tauri::command]
#[specta::specta]
pub async fn export_subtitle(
    recording_id: String,
    format: SubtitleFormat,
    language: SubtitleLanguage,
    state: State<'_, AppState>,
) -> Result<String, AppError> {
    // Fetch segments — both branches return (start_ms, end_ms, text) tuples (3-tuple, no id needed for output)
    // Use i64 for start/end, String for text
    let rows: Vec<(i64, i64, String)> = match &language {
        SubtitleLanguage::Original => {
            sqlx::query_as(
                "SELECT start_ms, end_ms, text
                 FROM transcription_segments
                 WHERE recording_id = ? ORDER BY start_ms"
            )
            .bind(&recording_id)
            .fetch_all(&state.db.pool)
            .await?
        }
        SubtitleLanguage::Translation(lang) => {
            sqlx::query_as(
                "SELECT ts.start_ms, ts.end_ms, COALESCE(st.text, ts.text)
                 FROM transcription_segments ts
                 LEFT JOIN segment_translations st ON st.segment_id = ts.id AND st.language = ?
                 WHERE ts.recording_id = ? ORDER BY ts.start_ms"
            )
            .bind(lang)
            .bind(&recording_id)
            .fetch_all(&state.db.pool)
            .await?
        }
    };

    // Get recording title + recordings_path
    let (title,): (String,) = sqlx::query_as(
        "SELECT title FROM recordings WHERE id = ?"
    )
    .bind(&recording_id)
    .fetch_one(&state.db.pool)
    .await?;

    let recordings_path = {
        let cfg = state.config.read().await;
        cfg.recordings_path.clone()
    };

    let safe_title = super::workspace::sanitize_filename(&title);
    let ext = match format { SubtitleFormat::Srt => "srt", SubtitleFormat::Vtt => "vtt", SubtitleFormat::Lrc => "lrc" };
    let output_path = std::path::Path::new(&recordings_path).join(format!("{}.{}", safe_title, ext));

    // Build content
    let mut content = String::new();
    if matches!(format, SubtitleFormat::Vtt) {
        content.push_str("WEBVTT\n\n");
    }

    for (idx, (start_ms, end_ms, text)) in rows.into_iter().enumerate() {
        match format {
            SubtitleFormat::Srt => {
                content.push_str(&format!(
                    "{}\n{} --> {}\n{}\n\n",
                    idx + 1,
                    fmt_srt(start_ms),
                    fmt_srt(end_ms),
                    text
                ));
            }
            SubtitleFormat::Vtt => {
                content.push_str(&format!(
                    "{} --> {}\n{}\n\n",
                    fmt_vtt(start_ms),
                    fmt_vtt(end_ms),
                    text
                ));
            }
            SubtitleFormat::Lrc => {
                content.push_str(&format!("[{}]{}\n", fmt_lrc(start_ms), text));
            }
        }
    }

    tokio::fs::create_dir_all(output_path.parent().unwrap()).await?;
    tokio::fs::write(&output_path, &content).await?;

    Ok(output_path.to_string_lossy().to_string())
}

fn fmt_srt(ms: i64) -> String {
    let h = ms / 3_600_000;
    let m = (ms % 3_600_000) / 60_000;
    let s = (ms % 60_000) / 1_000;
    let millis = ms % 1_000;
    format!("{:02}:{:02}:{:02},{:03}", h, m, s, millis)
}

fn fmt_vtt(ms: i64) -> String {
    let h = ms / 3_600_000;
    let m = (ms % 3_600_000) / 60_000;
    let s = (ms % 60_000) / 1_000;
    let millis = ms % 1_000;
    format!("{:02}:{:02}:{:02}.{:03}", h, m, s, millis)
}

fn fmt_lrc(ms: i64) -> String {
    let m = ms / 60_000;
    let s = (ms % 60_000) / 1_000;
    let cs = (ms % 1_000) / 10;
    format!("{:02}:{:02}.{:02}", m, s, cs)
}
```

### Step 6.4: Fix sanitize_filename visibility

- [ ] In `src-tauri/src/commands/workspace.rs`, change `fn sanitize_filename` to `pub(crate) fn sanitize_filename` so subtitle.rs can use it.

### Step 6.5: Register subtitle commands in lib.rs

- [ ] In `src-tauri/src/lib.rs`, update the import line:
```rust
use commands::{settings, theme, models as model_cmds, audio as audio_cmds, transcription as transcription_cmds, workspace as workspace_cmds, llm as llm_cmds, subtitle as subtitle_cmds};
```

- [ ] Add to `collect_commands![]`:
```rust
subtitle_cmds::get_segments_with_translations,
subtitle_cmds::update_segment_timing,
subtitle_cmds::update_segment_translation,
subtitle_cmds::align_translation_to_segments,
subtitle_cmds::export_subtitle,
```

### Step 6.6: Run tests + cargo check

```bash
cd src-tauri && cargo test -- --test-threads=1 2>&1 | tail -20
```
Expected: all tests pass including new subtitle tests.

```bash
cd src-tauri && cargo check 2>&1 | grep error | head -20
```

### Step 6.7: Commit

```bash
git add src-tauri/src/storage/migrations/0003_segment_translations.sql \
        src-tauri/src/commands/subtitle.rs \
        src-tauri/src/commands/mod.rs \
        src-tauri/src/commands/workspace.rs \
        src-tauri/src/lib.rs \
        src-tauri/src/storage/db.rs \
        src/lib/bindings.ts
git commit -m "feat(backend): add subtitle system with segment translations and export commands"
```

---

## Task 7: Frontend — SubtitleEditor

**Files:**
- Modify: `src/components/workspace/SubtitleEditor.tsx` (replace stub)

**Depends on:** Task 4 (mode switch integration), Task 6 (backend commands + bindings.ts)

### Step 7.1: Replace SubtitleEditor stub

- [ ] Replace `src/components/workspace/SubtitleEditor.tsx`:

```tsx
// src/components/workspace/SubtitleEditor.tsx
import { useEffect, useState, useRef, useCallback } from "react";
import { commands } from "@/lib/bindings";
import type { SegmentRow, SubtitleLanguage } from "@/lib/bindings";
import { convertFileSrc } from "@tauri-apps/api/core";
import { Play, Pause } from "lucide-react";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";

interface SubtitleEditorProps {
  recordingId: string;
  filePath: string;
  durationMs: number;
}

const TRANSLATION_LANGUAGES = [
  { value: "en", label: "英文" },
  { value: "ja", label: "日文" },
  { value: "ko", label: "韩文" },
  { value: "fr", label: "法文" },
  { value: "de", label: "德文" },
  { value: "es", label: "西班牙文" },
  { value: "ru", label: "俄文" },
] as const;

const parseTime = (s: string): number => {
  const [m, rest] = s.split(":");
  return Math.round((parseInt(m, 10) * 60 + parseFloat(rest)) * 1000);
};

const formatTime = (ms: number): string => {
  const total = ms / 1000;
  const m = Math.floor(total / 60);
  const s = (total % 60).toFixed(2).padStart(5, "0");
  return `${m}:${s}`;
};

export function SubtitleEditor({ recordingId, filePath, durationMs }: SubtitleEditorProps) {
  const [segments, setSegments] = useState<SegmentRow[]>([]);
  const [language, setLanguage] = useState<string | null>(null);
  const [currentSegmentId, setCurrentSegmentId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(durationMs / 1000);
  const [src, setSrc] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const rowRefs = useRef<Record<number, HTMLTableRowElement | null>>({});

  // Load audio src
  useEffect(() => {
    convertFileSrc(filePath).then(setSrc).catch(() => {});
  }, [filePath]);

  // Load segments
  const loadSegments = useCallback(async () => {
    const result = await commands.getSegmentsWithTranslations(
      recordingId,
      language ?? undefined
    );
    if (result.status === "ok") setSegments(result.data);
  }, [recordingId, language]);

  useEffect(() => { loadSegments(); }, [loadSegments]);

  // Playback sync
  const handleTimeUpdate = () => {
    const currentMs = (audioRef.current?.currentTime ?? 0) * 1000;
    setCurrentTime(audioRef.current?.currentTime ?? 0);
    const active = segments.find((s) => s.start_ms <= currentMs && currentMs <= s.end_ms);
    const newId = active?.id ?? null;
    if (newId !== currentSegmentId) {
      setCurrentSegmentId(newId !== undefined ? Number(newId) : null);
      if (newId != null && rowRefs.current[Number(newId)]) {
        rowRefs.current[Number(newId)]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  };

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) audio.pause(); else audio.play().catch(() => {});
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const t = Number(e.target.value);
    if (audioRef.current) audioRef.current.currentTime = t;
    setCurrentTime(t);
  };

  const handleExport = async (format: "srt" | "vtt" | "lrc") => {
    const lang: SubtitleLanguage = language
      ? { type: "translation", data: language }
      : { type: "original" };
    const result = await commands.exportSubtitle(recordingId, format, lang);
    if (result.status === "ok") {
      alert(`已导出到：${result.data}`);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Hidden audio */}
      {src && (
        <audio
          ref={audioRef}
          src={src}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={() => {
            const d = audioRef.current?.duration;
            if (d && isFinite(d)) setAudioDuration(d);
          }}
          preload="metadata"
        />
      )}

      {/* Playback bar */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-border-default bg-bg-secondary">
        <button
          onClick={togglePlay}
          className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-accent-primary text-white hover:opacity-90"
        >
          {isPlaying ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current ml-0.5" />}
        </button>
        <span className="shrink-0 text-xs text-text-muted w-10 text-right tabular-nums">
          {formatDuration(Math.round(currentTime) * 1000)}
        </span>
        <input
          type="range" min={0} max={audioDuration || 1} step={0.1}
          value={currentTime} onChange={handleSeek}
          className="flex-1 h-1 accent-[var(--color-accent-primary)] cursor-pointer"
        />
        <span className="shrink-0 text-xs text-text-muted w-10 tabular-nums">
          {formatDuration(Math.round(audioDuration) * 1000)}
        </span>
      </div>

      {/* Toolbar */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-border-default">
        <select
          value={language ?? ""}
          onChange={(e) => setLanguage(e.target.value || null)}
          className="text-xs border border-border-default rounded px-2 py-1 bg-bg-secondary text-text-primary"
        >
          <option value="">原文</option>
          {TRANSLATION_LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>{l.label}</option>
          ))}
        </select>

        <div className="flex-1" />

        {["srt", "vtt", "lrc"].map((fmt) => (
          <button
            key={fmt}
            onClick={() => handleExport(fmt as "srt" | "vtt" | "lrc")}
            className="text-xs px-2 py-1 border border-border-default rounded hover:bg-bg-secondary text-text-muted hover:text-text-primary"
          >
            {fmt.toUpperCase()} ↓
          </button>
        ))}
      </div>

      {/* Segment table */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 bg-bg-secondary">
            <tr>
              <th className="text-left px-3 py-2 text-text-muted w-8">#</th>
              <th className="text-left px-2 py-2 text-text-muted w-24">开始</th>
              <th className="text-left px-2 py-2 text-text-muted w-24">结束</th>
              <th className="text-left px-2 py-2 text-text-muted">原文</th>
              {language && <th className="text-left px-2 py-2 text-text-muted">
                {TRANSLATION_LANGUAGES.find((l) => l.value === language)?.label ?? language}
              </th>}
            </tr>
          </thead>
          <tbody>
            {segments.map((seg, idx) => {
              const isActive = currentSegmentId === Number(seg.id);
              return (
                <tr
                  key={seg.id}
                  ref={(el) => { rowRefs.current[Number(seg.id)] = el; }}
                  className={cn(
                    "border-b border-border-default transition-colors",
                    isActive ? "bg-accent-primary/10" : "hover:bg-bg-tertiary"
                  )}
                >
                  <td
                    className="px-3 py-1 text-text-muted cursor-pointer"
                    onClick={() => { if (audioRef.current) audioRef.current.currentTime = seg.start_ms / 1000; }}
                  >
                    {isActive ? "▶" : idx + 1}
                  </td>
                  <td className="px-2 py-1">
                    <input
                      className="w-20 bg-transparent border-b border-transparent hover:border-border-default focus:border-accent-primary focus:outline-none tabular-nums"
                      defaultValue={formatTime(seg.start_ms)}
                      onBlur={(e) => {
                        const ms = parseTime(e.target.value);
                        if (!isNaN(ms)) commands.updateSegmentTiming(seg.id, ms, seg.end_ms);
                      }}
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      className="w-20 bg-transparent border-b border-transparent hover:border-border-default focus:border-accent-primary focus:outline-none tabular-nums"
                      defaultValue={formatTime(seg.end_ms)}
                      onBlur={(e) => {
                        const ms = parseTime(e.target.value);
                        if (!isNaN(ms)) commands.updateSegmentTiming(seg.id, seg.start_ms, ms);
                      }}
                    />
                  </td>
                  <td className="px-2 py-1">
                    {/* Original text is read-only — editing transcription_segments.text is out of scope */}
                    <span className="text-text-primary">{seg.text}</span>
                  </td>
                  {language && (
                    <td className="px-2 py-1">
                      <input
                        className="w-full bg-transparent border-b border-transparent hover:border-border-default focus:border-accent-primary focus:outline-none"
                        defaultValue={seg.translated_text ?? ""}
                        onBlur={(e) => {
                          commands.updateSegmentTranslation(seg.id, language, e.target.value);
                        }}
                      />
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {segments.length === 0 && (
          <div className="flex items-center justify-center h-32 text-text-muted text-sm">
            暂无转写段落
          </div>
        )}
      </div>
    </div>
  );
}
```

### Step 7.2: Install @radix-ui/react-popover if missing

```bash
npm ls @radix-ui/react-popover 2>/dev/null || npm install @radix-ui/react-popover
```

### Step 7.3: Build verification

```bash
npm run build 2>&1 | grep -E "error|Error" | head -20
```
Expected: no errors.

### Step 7.4: Manual test

- Run `npm run tauri dev`
- Open a document with a recording → click "🎬 字幕"
- Verify segment table loads
- Click a row number → audio jumps to that position
- Edit a time field → blur → verify timing saved
- Switch language → verify translated column appears
- Click SRT/VTT/LRC export buttons → verify file created

### Step 7.5: Commit

```bash
git add src/components/workspace/SubtitleEditor.tsx
git commit -m "feat(frontend): SubtitleEditor with segment timeline editing, playback sync, and export"
```

---

## Final Integration Check

After all 7 tasks are complete:

- [ ] Run full Rust test suite:
```bash
cd src-tauri && cargo test -- --test-threads=1 2>&1 | tail -30
```

- [ ] Run TypeScript build:
```bash
npm run build 2>&1 | tail -20
```

- [ ] Manual smoke test checklist:
  - [ ] Workspace sidebar shows folder tree with 收件箱 and 批量任务
  - [ ] New recordings appear in 收件箱 after transcription
  - [ ] Right-click folder → new sub-folder, rename, delete work
  - [ ] Right-click document → rename, move to folder, delete work
  - [ ] Document page shows Obsidian-style header with inline title edit
  - [ ] Click "编辑" toggle → textarea appears; click "预览" → markdown renders
  - [ ] AI 工具 popover opens, task buttons work
  - [ ] Select text in edit mode → inline toolbar appears
  - [ ] Switch to 字幕 mode → SubtitleEditor loads segments
  - [ ] Export SRT file → file created at recordings_path

- [ ] Final commit if any cleanup needed:
```bash
git commit -m "chore: workspace obsidian experience final integration"
```
