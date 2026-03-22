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
5. 字幕模式：逐段时间轴编辑器，支持原文 + 翻译对齐，导出 SRT / VTT / LRC

---

## 架构概览

```
Workspace 路由
├── WorkspaceFileTree.tsx         ← 左侧文件夹树（完全重写）
│   ├── FolderNode（递归）
│   └── 右键 ContextMenu
└── 文档页 /workspace/$documentId
    ├── 文档头部（[📄 文档] [🎬 字幕] 模式切换）
    │   ├── 内联标题 input
    │   ├── 元信息行（日期 · 时长 · 所属文件夹）
    │   ├── AiPanel.tsx（悬浮 Popover）          ← 新增
    │   └── 紧凑 AudioPlayer
    ├── 文档模式（默认）
    │   ├── EditableAsset.tsx（双模式改造）
    │   └── AiInlineToolbar.tsx（选中工具条）     ← 新增
    └── 字幕模式
        └── SubtitleEditor.tsx                   ← 新增
            ├── 固定播放条（带段落跳转）
            ├── 工具栏（语言切换 + 导出按钮）
            └── SegmentTable（逐行时间编辑）
```

**后端新增文件：**
- `src-tauri/src/commands/workspace.rs`（已存在，需扩充）
- `src-tauri/src/commands/subtitle.rs`（新增，字幕命令）
- `src-tauri/src/storage/migrations/0003_segment_translations.sql`（新增 migration）

**前端新增 / 改造文件：**
- `src/components/workspace/WorkspaceFileTree.tsx`（完全重写）
- `src/components/workspace/EditableAsset.tsx`（双模式改造）
- `src/components/workspace/AiPanel.tsx`（新增）
- `src/components/workspace/AiInlineToolbar.tsx`（新增）
- `src/components/workspace/SubtitleEditor.tsx`（新增）

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

> **specta 递归类型注意事项：** specta v2 对 `Vec<FolderNode>` 递归结构支持有限，可能需要用 `Box<Vec<FolderNode>>` 或在编译时加 `#[specta(inline)]`。若 `cargo check` 报类型导出错误，备选方案是扁平化返回：返回 `Vec<FlatFolder>` + `Vec<DocumentSummary>`，由前端代码组装树，手工在 `bindings.ts` 中添加 `FolderNode` 类型。优先尝试递归结构，遇到问题再扁平化。

```rust
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
   - 查询目标文件夹名称，向上递归遍历 `parent_id` 链，拼接路径（`sanitize_filename` 每段）
   - 例：文件夹层级 `工作会议 > Q1` → `folder_path = "工作会议/Q1"`
   - 遍历 `workspace_text_assets`，对每条记录：
     - 计算新路径：`{vault_path}/notes/{folder_path}/{document_title}/{role}.md`
     - 用 `tokio::fs::rename` 移动文件；目标目录若不存在先 `create_dir_all`
     - 若目标路径已有同名文件，追加 `_{uuid_suffix}` 避免覆盖
     - 更新 `workspace_text_assets.file_path`
3. 若 vault 未配置，仅更新 DB

> `rename_document` 有同样的文件重命名逻辑：新路径 = `{vault_path}/notes/{folder_path}/{new_title}/{role}.md`，冲突时加后缀。

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

**`delete_document`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn delete_document(
    document_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), AppError>
```

- 查询 `workspace_text_assets.file_path`，若 vault 已配置则删除磁盘上的 `.md` 文件（失败不报错）
- 删除 `workspace_documents` 记录（DB CASCADE 会自动删除 `workspace_text_assets`）
- **注意：** 此命令只删文档，不删录音。若需同时删录音，使用现有的 `delete_recording(also_delete_document=true)`

### 1.4 修改现有命令

**`ensure_document_for_recording`**（`commands/workspace.rs`）

- 在函数内部先调用 `ensure_system_folders_inner(&pool).await?` 获取 `inbox_id`（提取为内部非 command 函数复用）
- 修改现有 INSERT 语句，加入 `folder_id` 列：

```sql
INSERT INTO workspace_documents
  (id, title, source_type, recording_id, folder_id, created_at, updated_at)
VALUES (?, ?, 'recording', ?, ?, ?, ?)
-- 对应绑定：&doc_id, &title, &recording_id, &inbox_id, created_at, now
```

**`create_batch_task_document`**（若存在）

- 创建时设置 `folder_id = batch_task_id`（`source_type = 'batch_task'`）

### 1.5 注册到 `lib.rs`

在 `collect_commands![]` 宏中添加（与现有命令格式一致）：

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

在 `app.manage(state)` 之后，用 spawn async task 初始化系统文件夹（与现有引擎加载模式一致）：

```rust
// 在 app.manage() 之后
let app_handle = app.handle().clone();
tauri::async_runtime::spawn(async move {
    let state = app_handle.state::<AppState>();
    if let Err(e) = workspace_cmds::init_system_folders(&state.db.pool).await {
        log::error!("Failed to init system folders: {e}");
    }
});
```

其中 `init_system_folders` 是从 `ensure_system_folders` 提取的内部函数（`pub(crate) async fn init_system_folders(pool: &SqlitePool) -> Result<SystemFolderIds, AppError>`），不是 command 本身。

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
  deleteDocument: (documentId: string) => Promise<void>;
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

**新增 npm 依赖（Task 2-5 合计，统一在 Task 2 开始前安装）：**

```bash
npm install react-markdown remark-gfm @radix-ui/react-context-menu textarea-caret
npm install --save-dev @types/textarea-caret
```

- `react-markdown` + `remark-gfm`：Markdown 渲染（Task 3）
- `@radix-ui/react-context-menu`：右键菜单（Task 2）
- `textarea-caret`：计算 textarea 内光标/选区的像素位置（Task 5）

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

**获取选区位置（`textarea` 专用，不能用 `window.getSelection()`）：**

`textarea` 内容不在 DOM 树中，`window.getSelection()` 对其无效。使用 `textarea-caret` 库计算光标像素位置：

```ts
import getCaretCoordinates from 'textarea-caret';

const getToolbarPosition = (el: HTMLTextAreaElement) => {
  const { selectionStart, selectionEnd } = el;
  if (selectionStart === selectionEnd) return null;   // 无选区

  // 取选区起始位置作为工具条定位点
  const caret = getCaretCoordinates(el, selectionStart);
  const rect = el.getBoundingClientRect();

  return {
    top: rect.top + caret.top - el.scrollTop - 36, // 工具条高度 36px，显示在上方
    left: rect.left + caret.left,
  };
};
```

边界情况处理：
- 选区靠近顶部（`top < 0`）时，工具条改为显示在选区下方（`top + caret.height + 4`）
- 选区靠近右侧时，`left` 需 clamp 到视口宽度内
- `textarea` 滚动时需重新计算（`el.scrollTop` 已在公式中减去）

### 5.3 AiTaskBar.tsx 兼容处理

本次迭代**保留** `AiTaskBar.tsx`，不删除。但文档页不再主动渲染它，功能由 `AiPanel` 接管。下一步迭代再正式删除。

---

## 实现顺序总结

| Task | 内容 | 前置依赖 |
|------|------|---------|
| Task 1 | 后端：系统文件夹 + CRUD 命令（含 `delete_document`）+ `list_folders_with_documents` + 修改 `ensure_document_for_recording` | 无 |
| Task 2 | 前端：`WorkspaceFileTree` 重写（文件夹树 + 右键菜单）| Task 1（需要后端命令） |
| Task 3 | 前端：`EditableAsset` Markdown 双模式（安装 `react-markdown`）| 无（**可与 Task 2 并行**） |
| Task 4 | 前端：文档页布局重构（Obsidian 风格头部、内联标题编辑、模式切换按钮）| Task 1（需要 `rename_document`）、Task 3 |
| Task 5 | 前端：`AiPanel` + `AiInlineToolbar` | Task 3（需要 `insertAtCursor` ref）、Task 4（头部按钮） |
| Task 6 | 后端：字幕命令（migration + `get_segments_with_translations` + `update_segment_timing` + `update_segment_translation` + `align_translation_to_segments` + `export_subtitle`）| Task 1（需要 AppState/DB 模式） |
| Task 7 | 前端：`SubtitleEditor.tsx`（字幕模式整页，逐段编辑 + 播放同步 + 导出）| Task 4（模式切换入口）、Task 6（后端命令） |

**并行建议：**
- Task 1 完成后，Task 2、Task 3、Task 6 可同时开发（三者互不依赖）
- Task 7 依赖 Task 4 和 Task 6，需最后实现

---

## Task 6：后端 — 字幕系统

### 6.1 数据库 Migration

新建文件：`src-tauri/src/storage/migrations/0003_segment_translations.sql`

```sql
CREATE TABLE segment_translations (
    id          TEXT PRIMARY KEY,
    segment_id  INTEGER NOT NULL REFERENCES transcription_segments(id) ON DELETE CASCADE,
    language    TEXT NOT NULL,    -- 语言代码：'en' | 'ja' | 'ko' | 'fr' | 'de' | 'es' | 'ru'
    text        TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    UNIQUE(segment_id, language)  -- 每段每语言一条记录
);
CREATE INDEX idx_seg_translations ON segment_translations(segment_id, language);
```

> **Migration 集成：** 检查现有 `src-tauri/src/storage/` 目录中 migration 的执行方式（`sqlx::migrate!` 宏），按照同样模式添加新文件。

### 6.2 Rust 类型定义

新建文件：`src-tauri/src/commands/subtitle.rs`

```rust
use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;
use crate::error::AppError;
use crate::state::AppState;

/// 一个转写段落及其翻译
// Note: transcription_segments.id is INTEGER AUTOINCREMENT, not UUID
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct SegmentRow {
    pub id: i64,
    pub recording_id: String,
    pub start_ms: i64,
    pub end_ms: i64,
    pub text: String,           // 原文
    pub translated_text: Option<String>,  // 指定语言的译文（无则 None）
}

/// 字幕导出格式
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(rename_all = "snake_case")]
pub enum SubtitleFormat {
    Srt,
    Vtt,
    Lrc,
}

/// 字幕内容语言
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
#[serde(tag = "type", content = "data", rename_all = "snake_case")]
pub enum SubtitleLanguage {
    Original,                   // 原文
    Translation(String),        // 翻译，值为语言代码如 "en"
}
```

### 6.3 新增命令

**`get_segments_with_translations`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn get_segments_with_translations(
    recording_id: String,
    language: Option<String>,   // None = 只返回原文
    state: State<'_, AppState>,
) -> Result<Vec<SegmentRow>, AppError>
```

- 查询 `transcription_segments` 按 `start_ms` 排序
- 若 `language` 有值，LEFT JOIN `segment_translations` 填入 `translated_text`
- 返回完整段落列表

**`update_segment_timing`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn update_segment_timing(
    segment_id: String,
    start_ms: i64,
    end_ms: i64,
    state: State<'_, AppState>,
) -> Result<(), AppError>
```

- 校验 `start_ms < end_ms`，否则返回 `AppError::Validation`
- 更新 `transcription_segments`

**`update_segment_translation`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn update_segment_translation(
    segment_id: String,
    language: String,
    text: String,
    state: State<'_, AppState>,
) -> Result<(), AppError>
```

- UPSERT `segment_translations(segment_id, language)` → `text`

**`align_translation_to_segments`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn align_translation_to_segments(
    document_id: String,
    language: String,           // 语言代码，如 "en"
    state: State<'_, AppState>,
) -> Result<(), AppError>
```

对齐算法（方案 C — 比例映射）：

1. 查询 `workspace_documents.recording_id`，获取对应 `recording_id`
2. 查询 `transcription_segments WHERE recording_id = ?` 按 `start_ms` 排序，得 N 段

边界处理：
- 若 N = 0（无转写段落），直接返回 Ok(())
- 若查不到 role='translation' 的 asset，返回 AppError::Validation("no translation asset found")
- 若 M = 0（翻译内容分割后为空），直接返回 Ok(())
- 比例映射公式中 N > 0 且 M > 0 才执行

3. 查询 `workspace_text_assets WHERE document_id = ? AND role = 'translation'` 的 `content`
4. 将 content 按句子分割（正则 `[。.!?！？\n]+` 为分隔符），过滤空串，得 M 句
5. 比例映射：`segment[i] → translated_sentences[min(round(i * M / N), M-1)]`
6. 批量 UPSERT 到 `segment_translations`

> 此命令在 LLM 翻译任务完成后由前端主动调用（或在 `AiPanel` 翻译完成回调中触发）。

**`export_subtitle`**

```rust
#[tauri::command]
#[specta::specta]
pub async fn export_subtitle(
    recording_id: String,
    format: SubtitleFormat,
    language: SubtitleLanguage,
    state: State<'_, AppState>,
) -> Result<String, AppError>   // 返回导出文件的绝对路径
```

- 查询段落列表（原文 or 译文）
- 按格式生成内容字符串
- 对 recording_title 执行文件名 sanitize（使用已有的 `sanitize_filename` 函数）
- 写到 `{recordings_path}/{sanitized_title}.{ext}`，已存在则覆盖（V1 策略）
- V2 可引入 Tauri dialog API 让用户选择保存位置，本次不实现
- 返回写入路径（前端可用 Tauri 打开文件对话框或通知用户）

**SRT 格式示例：**
```
1
00:00:00,000 --> 00:00:03,200
你好，今天我们来讨论

2
00:00:03,210 --> 00:00:05,800
关于这个项目的进展
```

**VTT 格式示例：**
```
WEBVTT

00:00:00.000 --> 00:00:03.200
你好，今天我们来讨论
```

**LRC 格式示例：**
```
[00:00.00]你好，今天我们来讨论
[00:03.21]关于这个项目的进展
```

### 6.4 注册到 `lib.rs`

```rust
subtitle_cmds::get_segments_with_translations,
subtitle_cmds::update_segment_timing,
subtitle_cmds::update_segment_translation,
subtitle_cmds::align_translation_to_segments,
subtitle_cmds::export_subtitle,
```

并在 `src-tauri/src/commands/mod.rs` 中声明 `pub mod subtitle;`。

---

## Task 7：前端 — SubtitleEditor 字幕模式

### 7.1 模式切换集成（修改 `workspace.$documentId.tsx`）

在文档页头部增加模式切换按钮：

```tsx
type DocMode = 'document' | 'subtitle';
const [mode, setMode] = useState<DocMode>('document');

// 头部按钮
<button onClick={() => setMode('document')} className={mode === 'document' ? 'active' : ''}>
  📄 文档
</button>
<button onClick={() => setMode('subtitle')} className={mode === 'subtitle' ? 'active' : ''}>
  🎬 字幕
</button>

// 内容区
{mode === 'document' ? <DocumentContent ... /> : <SubtitleEditor recordingId={recording.id} filePath={filePath} durationMs={durationMs} />}
```

字幕模式下隐藏 `EditableAsset` 列表，整页渲染 `SubtitleEditor`。

字幕模式下：
- 隐藏父级 AudioPlayer 组件（避免双 audio 元素冲突）
- SubtitleEditor 自带完整播放条（内含独立 `<audio>` 元素）
- SubtitleEditor Props 增加 `filePath: string`（WAV 文件绝对路径）和 `durationMs: number`

### 7.2 SubtitleEditor.tsx

**文件：** `src/components/workspace/SubtitleEditor.tsx`

**Props：**
```ts
interface SubtitleEditorProps {
  recordingId: string;
  filePath: string;       // WAV 文件绝对路径，内部用 convertFileSrc(filePath) 转换（与 AudioPlayer 相同方式）
  durationMs: number;
}
```

**State：**
```ts
const [segments, setSegments] = useState<SegmentRow[]>([]);
const [language, setLanguage] = useState<string | null>(null);  // null = 仅原文
const [currentSegmentId, setCurrentSegmentId] = useState<string | null>(null);
const audioRef = useRef<HTMLAudioElement>(null);
```

**Layout：**

```
┌────────────────────────────────────────────────────────────┐
│ ▶ 0:00 ──────────────────────────────────────── 27:13      │  ← 固定播放条
├────────────────────────────────────────────────────────────┤
│ [语言: 原文 ▾]  [翻译列: 英文 ▾]  [SRT ↓] [VTT ↓] [LRC ↓]│  ← 工具栏
├────┬──────────┬──────────┬──────────────────┬──────────────┤
│ #  │ 开始     │ 结束     │ 原文             │ 英文译文      │
├────┼──────────┼──────────┼──────────────────┼──────────────┤
│ ▶1 │[0:00.00] │[0:03.20] │[可编辑 input]    │[可编辑 input]│  ← 高亮行
│  2 │[0:03.21] │[0:05.80] │...               │...            │
└────┴──────────┴──────────┴──────────────────┴──────────────┘
```

**播放同步逻辑：**

```ts
// 挂载在 <audio> 的 onTimeUpdate
const handleTimeUpdate = () => {
  const currentMs = (audioRef.current?.currentTime ?? 0) * 1000;
  const active = segments.find(s => s.start_ms <= currentMs && currentMs <= s.end_ms);
  setCurrentSegmentId(active?.id ?? null);
  // 自动滚动到当前行（rowRef[active.id].scrollIntoView({ block: 'nearest' })）
};
```

**时间格编辑：**

```tsx
// 时间 input 格式：mm:ss.ss
// 失焦时解析并调用 update_segment_timing
const parseTime = (s: string): number => {
  const [m, rest] = s.split(':');
  return (parseInt(m) * 60 + parseFloat(rest)) * 1000;
};
const formatTime = (ms: number): string => {
  const total = ms / 1000;
  const m = Math.floor(total / 60);
  const s = (total % 60).toFixed(2).padStart(5, '0');
  return `${m}:${s}`;
};
```

注意：formatTime/parseTime 仅用于编辑器 UI 展示。后端 export_subtitle 直接将 start_ms/end_ms（i64 毫秒）
格式化为各标准时间字符串：
- SRT：00:mm:ss,mmm（HH:MM:SS,mmm，3位毫秒，逗号分隔）
- VTT：00:mm:ss.mmm（HH:MM:SS.mmm，3位毫秒，点分隔）
- LRC：[mm:ss.xx]（2位厘秒）
前端无需感知这些格式细节。

**点击行跳转：**
```ts
// 点击行号列或高亮区域 → 音频跳转
audioRef.current.currentTime = segment.start_ms / 1000;
```

**导出按钮：**
```ts
const handleExport = async (format: 'srt' | 'vtt' | 'lrc') => {
  const lang: SubtitleLanguage = language
    ? { type: 'translation', data: language }
    : { type: 'original' };
  const fmt = format as 'srt' | 'vtt' | 'lrc';
  const result = await commands.exportSubtitle(recordingId, fmt, lang);
  if (result.status === 'ok') {
    // 提示用户文件路径（toast 通知）
  }
};
```

**翻译列加载：**

```ts
// 切换 language 时重新拉取段落
useEffect(() => {
  commands.getSegmentsWithTranslations(recordingId, language ?? undefined)
    .then(r => { if (r.status === 'ok') setSegments(r.data); });
}, [recordingId, language]);
```

**翻译对齐触发（在 AiPanel 翻译完成后）：**

`AiPanel` 中检测翻译任务完成后，调用：
```ts
await commands.alignTranslationToSegments(documentId, targetLanguage);
```

---

## 附录：关键约定

- 所有 Tauri 命令返回 `Result<T, AppError>`，前端从 `bindings.ts` 引入类型
- ID 为 UUID v4 字符串，由 Rust 生成
- 时间戳为 Unix 毫秒整数（`i64`）
- 轮询替代事件：参见项目 memory `feedback_tauri_events.md`，`AppHandle::emit()` 在 macOS dev 不可靠，文件夹树状态刷新使用命令轮询而非事件推送
- specta 类型变更后需重新运行 `cargo build` 生成 `bindings.ts`
