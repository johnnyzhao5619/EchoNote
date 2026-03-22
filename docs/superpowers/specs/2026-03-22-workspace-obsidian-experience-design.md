# EchoNote — Workspace Obsidian 体验改造设计规格

**日期**：2026-03-22
**读者**：负责具体实现的 Rust / React 开发者
**状态**：已确认，待实现

---

## 目标

将 EchoNote 的 workspace 从「平铺录音列表 + 基础文本编辑器」改造为类 Obsidian 的文档管理体验，核心改进：

1. 文件夹树形侧边栏（含系统文件夹 inbox / batch_task）
2. Markdown 读写双模式编辑器（预览 / 编辑切换）
3. Obsidian 风格文档页布局（内联标题编辑、紧凑播放条、元信息一行）
4. 文档级 AI 悬浮面板 + 选中文字内联工具条

---

## 架构概览

```
Workspace 路由
├── WorkspaceFileTree.tsx      ← 左侧文件夹树（完全重写）
│   ├── FolderNode（递归）
│   └── 右键 ContextMenu
└── 文档页 /workspace/$documentId
    ├── 文档头部
    │   ├── 内联标题 input
    │   ├── 元信息行（日期 · 时长 · 所属文件夹）
    │   ├── AiPanel.tsx（悬浮 Popover）         ← 新增
    │   └── 紧凑 AudioPlayer
    └── 内容区
        ├── EditableAsset.tsx（双模式改造）
        └── AiInlineToolbar.tsx（选中工具条）    ← 新增
```

**后端新增文件：**
- `src-tauri/src/commands/workspace.rs`（已存在，需扩充）

**前端新增 / 改造文件：**
- `src/components/workspace/WorkspaceFileTree.tsx`（完全重写）
- `src/components/workspace/EditableAsset.tsx`（双模式改造）
- `src/components/workspace/AiPanel.tsx`（新增）
- `src/components/workspace/AiInlineToolbar.tsx`（新增）

---

## 不在本次范围内

- 文件夹/文档拖拽排序
- 全文搜索 UI（Cmd+Shift+F）
- 批量转写命令新增
- 时长 bug（已通过 `onLoadedMetadata` 修复，无需再实现）
- `AiTaskBar.tsx` 删除（本次保留兼容，下一步迭代删除）

---

## Task 1：后端 — 系统文件夹 + 文件夹 CRUD

### 1.1 背景（DB schema 无需改动）

`workspace_folders` 表已有以下字段：

| 字段 | 说明 |
|------|------|
| `id` | UUID v4 |
| `name` | 文件夹名 |
| `parent_id` | 父文件夹 id，NULL 表示顶级 |
| `folder_kind` | `inbox \| batch_task \| user \| system_root` |
| `is_system` | BOOLEAN，系统文件夹不可改名/删除 |
| `created_at` | Unix 毫秒 |

`workspace_documents` 表已有 `folder_id` 关联文件夹。

### 1.2 Rust 类型定义

```rust
// src-tauri/src/commands/workspace.rs

#[derive(Debug, serde::Serialize, serde::Deserialize, specta::Type)]
pub struct SystemFolderIds {
    pub inbox_id: String,
    pub batch_task_id: String,
}

#[derive(Debug, serde::Serialize, serde::Deserialize, specta::Type)]
pub struct DocumentSummary {
    pub id: String,
    pub title: String,
    pub source_type: String,            // "recording" | "batch_task" | "import"
    pub recording_id: Option<String>,
    pub created_at: i64,                // Unix ms
}

#[derive(Debug, serde::Serialize, serde::Deserialize, specta::Type)]
pub struct FolderNode {
    pub id: String,
    pub name: String,
    pub folder_kind: String,            // "inbox" | "batch_task" | "user" | "system_root"
    pub is_system: bool,
    pub children: Vec<FolderNode>,      // 递归子文件夹
    pub documents: Vec<DocumentSummary>,
}
```

### 1.3 新增命令

**`ensure_system_folders`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn ensure_system_folders(
    state: tauri::State<'_, AppState>,
) -> Result<SystemFolderIds, AppError>
```

- 幂等：若 `inbox` / `batch_task` 文件夹已存在，直接返回 id
- 若不存在，创建并写入 DB（`is_system=true`）
- 在 app 启动时（`lib.rs` setup hook）调用一次

**`list_folders_with_documents`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn list_folders_with_documents(
    state: tauri::State<'_, AppState>,
) -> Result<Vec<FolderNode>, AppError>
```

- 查询所有文件夹 + 每个文件夹下的 documents
- 在内存中组装递归树（顶层节点 `parent_id IS NULL`，系统文件夹置顶）
- 返回顺序：`inbox` → `batch_task` → 用户文件夹（按 `created_at` 升序）

**`create_folder`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn create_folder(
    parent_id: Option<String>,
    name: String,
    state: tauri::State<'_, AppState>,
) -> Result<String, AppError>   // 返回新文件夹 id
```

- `name` 不可为空，否则返回 `AppError::Validation`
- `folder_kind` = `"user"`，`is_system` = `false`

**`rename_folder`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn rename_folder(
    folder_id: String,
    name: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), AppError>
```

- 若 `is_system=true` 则返回 `AppError::Validation("cannot rename system folder")`

**`delete_folder`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn delete_folder(
    folder_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), AppError>
```

- 若 `is_system=true` 则返回 `AppError::Validation`
- 删除前：将该文件夹（及所有子文件夹）下的文档 `folder_id` 更新为 `inbox_id`
- 递归删除子文件夹记录
- 删除文件夹本身

**`move_document_to_folder`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn move_document_to_folder(
    document_id: String,
    folder_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), AppError>
```

操作步骤：
1. 更新 DB `workspace_documents.folder_id = folder_id`
2. 若 `vault_path` 已在 settings 中配置：
   - 读取 `workspace_text_assets` 中该 document 的 `file_path`
   - 计算新路径：`{vault_path}/{folder_path}/{document_title}.md`
   - 用 `std::fs::rename` 移动文件
   - 更新 `workspace_text_assets.file_path`
3. 若 vault 未配置，仅更新 DB

**`rename_document`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn rename_document(
    document_id: String,
    title: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), AppError>
```

- 更新 `workspace_documents.title`
- 若 vault 已配置，重命名磁盘上的 `.md` 文件并更新 `file_path`

### 1.4 修改现有命令

**`ensure_document_for_recording`**（`commands/workspace.rs`）

- 创建新 document 时，查询 `inbox_id`（通过 `ensure_system_folders` 或直接查 DB）
- 设置 `folder_id = inbox_id`

**`create_batch_task_document`**（若存在）

- 创建时设置 `folder_id = batch_task_id`（`source_type = 'batch_task'`）

### 1.5 注册到 `lib.rs`

在 `tauri::Builder` 的 `invoke_handler` 中添加：

```rust
ensure_system_folders,
list_folders_with_documents,
create_folder,
rename_folder,
delete_folder,
move_document_to_folder,
rename_document,
```

在 `setup` hook 中调用：

```rust
app.state::<AppState>()
    .db
    .ensure_system_folders()
    .await?;
```

---

## Task 2：前端 — WorkspaceFileTree 重写

### 2.1 Store 扩展（`src/store/models.ts` 或新建 `src/store/workspace.ts`）

```ts
interface WorkspaceStore {
  folderTree: FolderNode[];
  expandedFolderIds: Set<string>;
  selectedDocumentId: string | null;
  systemFolderIds: SystemFolderIds | null;

  loadFolderTree: () => Promise<void>;
  toggleFolder: (folderId: string) => void;
  createFolder: (parentId: string | null, name: string) => Promise<void>;
  renameFolder: (folderId: string, name: string) => Promise<void>;
  deleteFolder: (folderId: string) => Promise<void>;
  moveDocument: (documentId: string, folderId: string) => Promise<void>;
  renameDocument: (documentId: string, title: string) => Promise<void>;
}
```

- `loadFolderTree` 调用 `list_folders_with_documents` 后刷新 store
- 每次文件夹/文档操作后重新调用 `loadFolderTree`（数据量小，全量刷新即可）

### 2.2 WorkspaceFileTree.tsx 重写

**文件：** `src/components/workspace/WorkspaceFileTree.tsx`

**结构：**

```
WorkspaceFileTree
└── FolderItem（递归）
    ├── 文件夹行（chevron + icon + name + count badge）
    └── 展开时
        ├── DocumentItem（多个）
        └── FolderItem（子文件夹，递归）
```

**FolderItem 行为：**
- 点击行 → `toggleFolder(id)`
- 右键 → ContextMenu（见下）
- 系统文件夹用不同颜色/图标区分（`is_system` = true 时图标用 Inbox/Archive，用户文件夹用 Folder）

**DocumentItem 行为：**
- 点击 → `navigate({ to: '/workspace/$documentId', params: { documentId: doc.id } })`
- 右键 → ContextMenu（见下）
- 当前选中文档高亮

**右键 ContextMenu（文件夹）：**

```
新建子文件夹
重命名          ← is_system=true 时禁用（灰色，不可点）
删除            ← is_system=true 时禁用；点击弹 confirm dialog
```

**右键 ContextMenu（文档）：**

```
重命名
移动到…         ← 弹出文件夹选择器（简单 Select 下拉）
删除            ← 弹 confirm dialog
```

**底部操作区：**

```tsx
<button onClick={() => createFolder(null, '新建文件夹')}>
  + 新建文件夹
</button>
```

**样式要求：**
- 整体与 Obsidian 左侧 file explorer 对齐
- 缩进：每层 `pl-4`（16px）
- 文件夹行高 `h-7`，字号 `text-sm`
- 文档行高 `h-6`，字号 `text-sm text-text-secondary`
- 分隔线：系统文件夹与用户文件夹之间 `<hr className="my-2 border-border" />`
- 选中文档：`bg-accent/20 text-accent`

**依赖：**
- `@radix-ui/react-context-menu`（若已安装则复用，否则安装）
- Zustand store

### 2.3 侧边栏集成

在 `src/components/layout/SecondPanel.tsx` 或对应侧边栏组件中：
- 替换现有平铺录音列表为 `<WorkspaceFileTree />`
- 在侧边栏 mount 时调用 `loadFolderTree()`

---

## Task 3：前端 — EditableAsset Markdown 双模式编辑器

### 3.1 依赖安装

```bash
npm install react-markdown remark-gfm
```

### 3.2 EditableAsset.tsx 改造

**文件：** `src/components/workspace/EditableAsset.tsx`

**新增 props / state：**

```ts
type EditMode = 'view' | 'edit';
const [mode, setMode] = useState<EditMode>('view');
```

**View 模式（默认）：**

```tsx
<div
  className="prose prose-sm max-w-none cursor-text"
  onClick={() => setMode('edit')}
>
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {content}
  </ReactMarkdown>
</div>
```

- 点击内容区 → 切换到 Edit 模式

**Edit 模式：**

```tsx
<textarea
  className="w-full font-mono text-sm leading-relaxed resize-none focus:outline-none bg-transparent"
  style={{ fontFamily: 'Monaco, Menlo, monospace' }}
  value={content}
  onChange={handleChange}  // 保留 1.5s 防抖自动保存
  autoFocus
/>
```

**右上角切换按钮：**

```tsx
<button onClick={() => setMode(mode === 'view' ? 'edit' : 'view')}>
  {mode === 'view' ? '编辑' : '预览'}
</button>
```

**样式原则（Obsidian 风格）：**

```css
/* 内容容器 */
.content-area {
  max-width: 48rem;   /* max-w-3xl */
  margin: 0 auto;
  padding: 0 2rem;
  font-size: 15px;
  line-height: 1.75;
}

/* View 模式 Markdown 渲染 */
h1 { font-size: 1.5rem; font-weight: 700; margin: 1.5rem 0 0.5rem; }
h2 { font-size: 1.25rem; font-weight: 600; margin: 1.25rem 0 0.5rem; }
h3 { font-size: 1.1rem; font-weight: 600; margin: 1rem 0 0.25rem; }
strong { font-weight: 700; }
ul { list-style-type: disc; padding-left: 1.5rem; }
ol { list-style-type: decimal; padding-left: 1.5rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid var(--border); padding: 0.375rem 0.75rem; }
```

**保留行为：**
- 1.5s 防抖自动保存（现有逻辑保持不变）
- `AiInlineToolbar` 集成（见 Task 5）

---

## Task 4：前端 — 文档页布局重构

### 4.1 文档头部设计

**目标布局：**

```
┌────────────────────────────────────────────────────────────┐
│ 🎙  [Recording 2026-03-21 20:37]    [✨ AI 工具 ▾]  [🗑]  │
│ 2026-03-21 · 27:13 · 收件箱 >                              │
│ ▶ 0:00 ──────────────────────────────────── 27:13          │
└────────────────────────────────────────────────────────────┘
```

**标题行：**
- 左侧：source 图标（麦克风/文档）
- 标题：`<input>` 默认 `readOnly`，点击 → `readOnly=false`，失焦 → 调用 `rename_document` 并设回 `readOnly`
- 右侧：`<AiPanel />` 按钮 + 删除按钮

**元信息行：**

```tsx
<div className="text-xs text-text-muted flex gap-2">
  <span>{formatDate(document.created_at)}</span>
  <span>·</span>
  <span>{formatDuration(duration)}</span>
  <span>·</span>
  <button
    className="hover:underline"
    onClick={() => {/* 跳转到文件夹（展开对应 folder）*/}}
  >
    {folderName}
  </button>
</div>
```

**紧凑播放条：**
- 现有 `AudioPlayer.tsx` 直接复用，去掉多余 padding，使整体更紧凑
- 播放条高度控制在 `h-10` 以内

**内容区：**
- Section 分隔：`<hr className="border-border my-3" />`（细线，不是大间距）
- Section 标题：`<span className="text-xs uppercase tracking-widest text-text-muted">`
- 移除旧 `AiTaskBar` 的独立渲染位置（功能迁移到 `AiPanel`）

### 4.2 内联标题编辑实现

```tsx
const [titleEditing, setTitleEditing] = useState(false);
const [titleValue, setTitleValue] = useState(document.title);

<input
  value={titleValue}
  readOnly={!titleEditing}
  onClick={() => setTitleEditing(true)}
  onBlur={async () => {
    setTitleEditing(false);
    if (titleValue !== document.title) {
      await invoke('rename_document', { documentId: document.id, title: titleValue });
      // 刷新 store
    }
  }}
  className={cn(
    "bg-transparent font-semibold text-lg focus:outline-none",
    titleEditing && "border-b border-accent"
  )}
/>
```

---

## Task 5：前端 — AiPanel + AiInlineToolbar

### 5.1 AiPanel.tsx（新增）

**文件：** `src/components/workspace/AiPanel.tsx`

**触发：** 文档头部右侧「✨ AI 工具」按钮，使用 Radix `Popover` 组件

**面板内容：**

```
┌─────────────────────────────────┐
│  生成摘要                        │
│  会议纪要                        │
│  翻译 ▾  [英文 ▾]               │
│  ─────────────────────────────  │
│  [生成结果流式预览区...]          │
│                [插入到光标位置]   │
└─────────────────────────────────┘
```

**支持翻译语言：**

```ts
const TRANSLATION_LANGUAGES = [
  { value: 'en', label: '英文' },
  { value: 'ja', label: '日文' },
  { value: 'ko', label: '韩文' },
  { value: 'fr', label: '法文' },
  { value: 'de', label: '德文' },
  { value: 'es', label: '西班牙文' },
  { value: 'ru', label: '俄文' },
] as const;
```

**组件 Props：**

```ts
interface AiPanelProps {
  documentId: string;
  transcriptContent: string;
  onInsertAtCursor: (text: string) => void;  // 调用 textarea.setRangeText()
}
```

**生成流程：**
1. 用户点击「生成摘要」/「会议纪要」/「翻译」
2. 调用现有 LLM 命令（复用当前 AI 任务逻辑）
3. 结果通过 `StreamingText` 组件在面板内流式预览（复用 `src/components/workspace/StreamingText.tsx` 或等效组件）
4. 生成完成后，照旧写入对应 role asset（保持现有行为）
5. 「插入到光标位置」按钮：调用 `onInsertAtCursor(generatedText)`

**`onInsertAtCursor` 实现：**

```ts
// 在 EditableAsset.tsx 中暴露 ref
const textareaRef = useRef<HTMLTextAreaElement>(null);

const insertAtCursor = (text: string) => {
  const el = textareaRef.current;
  if (!el) return;
  const start = el.selectionStart;
  const end = el.selectionEnd;
  el.setRangeText(text, start, end, 'end');
  // 触发 onChange 以更新 state 并启动防抖保存
  el.dispatchEvent(new Event('input', { bubbles: true }));
};
```

### 5.2 AiInlineToolbar.tsx（新增）

**文件：** `src/components/workspace/AiInlineToolbar.tsx`

**触发条件：** Edit 模式下，`textarea` 的 `mouseup` / `keyup` 事件中检测 `selectionStart !== selectionEnd`

**位置：** 跟随选区位置（绝对定位，`top = selectionRect.top - toolbarHeight`，`left = selectionRect.left`）

**工具条内容：**

```
[翻译 ▾] [生成摘要] [复制]
```

**行为：**
- 「翻译」：下拉选语言后执行，结果显示在小弹窗（`Popover`），可「插入」或「取消」
- 「生成摘要」：对选中内容执行摘要，结果显示在小弹窗
- 「复制」：`navigator.clipboard.writeText(selectedText)`
- 工具条在选区消失时隐藏

**组件 Props：**

```ts
interface AiInlineToolbarProps {
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onInsert: (text: string) => void;
}
```

**获取选区位置：**

```ts
const getSelectionRect = () => {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  return selection.getRangeAt(0).getBoundingClientRect();
};
```

注意：`textarea` 内的选区不直接支持 `window.getSelection()`，需通过在 textarea 上创建隐藏 mirror div 或使用 `getBoundingClientRect` + caret position 库（如 `textarea-caret`）计算位置。

### 5.3 AiTaskBar.tsx 兼容处理

本次迭代**保留** `AiTaskBar.tsx`，不删除。但文档页不再主动渲染它，功能由 `AiPanel` 接管。下一步迭代再正式删除。

---

## 实现顺序总结

| Task | 内容 | 前置依赖 |
|------|------|---------|
| Task 1 | 后端：系统文件夹 + CRUD 命令 + `list_folders_with_documents` + 修改 `ensure_document_for_recording` | 无 |
| Task 2 | 前端：`WorkspaceFileTree` 重写（文件夹树 + 右键菜单）| Task 1（需要后端命令） |
| Task 3 | 前端：`EditableAsset` Markdown 双模式（安装 `react-markdown`）| 无（可并行） |
| Task 4 | 前端：文档页布局重构（Obsidian 风格头部、内联标题编辑）| Task 1（需要 `rename_document`）、Task 3 |
| Task 5 | 前端：`AiPanel` + `AiInlineToolbar` | Task 3（需要 `insertAtCursor` ref）、Task 4（头部按钮） |

---

## 附录：关键约定

- 所有 Tauri 命令返回 `Result<T, AppError>`，前端从 `bindings.ts` 引入类型
- ID 为 UUID v4 字符串，由 Rust 生成
- 时间戳为 Unix 毫秒整数（`i64`）
- 轮询替代事件：参见项目 memory `feedback_tauri_events.md`，`AppHandle::emit()` 在 macOS dev 不可靠，文件夹树状态刷新使用命令轮询而非事件推送
- specta 类型变更后需重新运行 `cargo build` 生成 `bindings.ts`
