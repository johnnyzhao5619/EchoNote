# Workspace Authoring Hard-Cut Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Workspace 从“可搜索的文档查看页”硬切换为“统一承载手动文档、导入文档、录音文档的可编辑树形工作台”，补齐新建即编辑、导入即接管、左侧树导航三条闭环。

**Architecture:** 保留现有 `WorkspaceManager`、`workspace_text_assets`、`SearchBar`、路由骨架与 Zustand store 作为基础，但把文档主流程重构为单一作者模型：所有文档都通过 `DocumentView` 的同一编辑能力承载，`document_text` 作为手动文档和导入文档的主正文资产，录音文档复用同一资产展示与编辑基础设施。前端以 `WorkspacePanel` 的递归树作为唯一导航入口，`WorkspaceMain` 只负责文件夹级文档列表与入口动作，`DocumentView` 负责标题、正文、AI 资产和导出。

**Tech Stack:** Tauri 2.x、Rust + sqlx + SQLite FTS5、React 18 + TypeScript、TanStack Router、Zustand、shadcn/ui、Vitest、cargo test

---

### Task 1: 现状审计与陈旧实现清理

**Files:**
- Inspect: `src/components/workspace/DocumentView.tsx`
- Inspect: `src/components/workspace/EditableAsset.tsx`
- Inspect: `src/components/workspace/WorkspaceMain.tsx`
- Inspect: `src/components/workspace/WorkspacePanel.tsx`
- Inspect: `src/components/workspace/FolderTreeNode.tsx`
- Inspect: `src/store/workspace.ts`
- Inspect: `src-tauri/src/commands/workspace.rs`
- Inspect: `src-tauri/src/workspace/manager.rs`
- Modify: `src/components/workspace/`

**Step 1: 写一个失败的审计测试，锁定“新建文档进入只读查看器”的当前错误行为**

在 `src/components/workspace/__tests__/DocumentView.test.tsx` 或新建更贴近行为的测试文件中，写用例验证：
- 新建 `source_type='note'` 且仅有 `document_text` 资产的文档打开后，页面应出现可编辑正文入口，而不是只读 `<pre>`
- 标题区域应允许进入编辑或至少具备后续可扩展的编辑插槽

**Step 2: 运行测试确认 FAIL**

Run: `npm test -- DocumentView`
Expected: FAIL，原因是当前 `DocumentView` 只渲染只读 tabs/`<pre>`

**Step 3: 审计并删除失效或重复的 Workspace 旧心智代码**

- 删除或重写会把 Workspace 继续拉回“只读查看器”心智的组件分支
- 若存在未再使用的旧列表/旧树/旧占位状态代码，同步清理
- 不保留第二套文档查看逻辑；编辑与查看只能有一套主路径

**Step 4: 跑测试确保清理后基础仍可编译**

Run: `npm run typecheck`
Expected: PASS

**Step 5: Commit**

```bash
git add src/components/workspace src/store/workspace.ts
git commit -m "refactor(workspace): remove stale read-only document flow"
```

### Task 2: 新建文档闭环改造

**Files:**
- Modify: `src/components/workspace/WorkspaceMain.tsx`
- Modify: `src/components/workspace/DocumentView.tsx`
- Modify: `src/components/workspace/EditableAsset.tsx`
- Modify: `src/store/workspace.ts`
- Modify: `src/components/workspace/__tests__/WorkspaceMain.test.tsx`
- Modify: `src/components/workspace/__tests__/DocumentView.test.tsx`

**Step 1: 写失败测试，定义“新建即编辑”**

补两类测试：
- `WorkspaceMain`：点击“新建文档”后，不只是在列表里插入摘要，而是导航到新文档详情
- `DocumentView`：`source_type='note'` 且存在 `document_text` 资产时，正文区域默认可编辑或一键进入编辑

**Step 2: 运行测试确认 FAIL**

Run: `npm test -- WorkspaceMain DocumentView`
Expected: FAIL，原因是当前只会创建并打开只读详情

**Step 3: 实现最小改造**

- `createDocument` 后返回新文档 id，并在 store 内统一负责打开/导航后的状态刷新
- `DocumentView` 不再把 `document_text` 当成普通只读 tab；它是 note/import 文档的主正文
- 复用 `EditableAsset`，不要在 `DocumentView` 中再实现第二套文本编辑器
- 若正文为空，显示“点击开始编写”而不是“此文档暂无内容”

**Step 4: 运行测试确认 PASS**

Run: `npm test -- WorkspaceMain DocumentView`
Expected: PASS

**Step 5: Commit**

```bash
git add src/components/workspace src/store/workspace.ts
git commit -m "feat(workspace): make new documents immediately editable"
```

### Task 3: 导入文档闭环改造

**Files:**
- Modify: `src/components/workspace/WorkspaceMain.tsx`
- Modify: `src/store/workspace.ts`
- Modify: `src-tauri/src/commands/workspace.rs`
- Modify: `src-tauri/src/workspace/manager.rs`
- Test: `src/components/workspace/__tests__/WorkspaceMain.test.tsx`
- Test: `src/store/__tests__/workspace.test.ts`
- Test: `src-tauri/src/workspace/manager.rs`

**Step 1: 写失败测试，定义“导入即接管”**

补测试覆盖：
- 前端点击“导入文件”成功后，应打开被导入的新文档，而不是只把文档摘要插进列表
- store 的 `importFile` 在成功后应同步 `documents`、`currentDoc`、路由所需数据
- 若解析后写入的是 `document_text` 资产，`get_document` 返回时应能直接进入编辑主视图

**Step 2: 运行测试确认 FAIL**

Run: `npm test -- WorkspaceMain workspace.test`
Run: `cargo test import_file_to_workspace -- --test-threads=1`
Expected: FAIL，原因是当前导入只追加列表，不自动接管后续工作流

**Step 3: 实现最小改造**

- `importFileToWorkspace` 继续复用现有解析逻辑，不新增第二套导入管线
- `importFile` 成功后统一打开文档详情，并聚焦到 `document_text`
- 导入失败要返回明确错误，不允许静默无反馈
- 不使用 mock 内容或占位数据伪装“导入成功”

**Step 4: 运行测试确认 PASS**

Run: `npm test -- WorkspaceMain workspace.test`
Run: `cargo test import_file_to_workspace -- --test-threads=1`
Expected: PASS

**Step 5: Commit**

```bash
git add src/components/workspace src/store/workspace.ts src-tauri/src/commands/workspace.rs src-tauri/src/workspace/manager.rs
git commit -m "feat(workspace): open imported files in editable document flow"
```

### Task 4: 左侧树形导航语义修正

**Files:**
- Modify: `src/components/workspace/WorkspacePanel.tsx`
- Modify: `src/components/workspace/FolderTreeNode.tsx`
- Modify: `src/store/workspace.ts`
- Test: `src/components/workspace/__tests__/WorkspacePanel.test.tsx`
- Test: `src/routes/__tests__/-workspace-routing.test.tsx`

**Step 1: 写失败测试，锁定树形结构而非平面列表**

至少覆盖：
- 存在父子文件夹时，子节点必须在 UI 中以层级缩进和展开状态出现
- 选择文件夹不应强制改变展开状态
- 展开/折叠与进入文件夹是两个独立动作
- 当前路由对应文件夹必须在树中高亮，且其祖先链自动展开

**Step 2: 运行测试确认 FAIL**

Run: `npm test -- WorkspacePanel workspace-routing`
Expected: FAIL，原因是当前点击节点同时承担选择与折叠，且默认展开策略过于粗糙

**Step 3: 实现最小改造**

- 为 `FolderTreeNode` 分离“展开按钮”和“选择文件夹”点击区域
- 把展开状态提升到可维护位置，避免递归节点内部各自维护导致祖先链无法可靠恢复
- 不再让“文档数量 badge”承担层级表达功能
- 空树、单层树、多层树共用一套节点组件，不新增平行实现

**Step 4: 运行测试确认 PASS**

Run: `npm test -- WorkspacePanel workspace-routing`
Expected: PASS

**Step 5: Commit**

```bash
git add src/components/workspace src/store/workspace.ts src/routes/__tests__/-workspace-routing.test.tsx
git commit -m "feat(workspace): restore true tree navigation semantics"
```

### Task 5: 文档详情统一为单一路径

**Files:**
- Modify: `src/components/workspace/DocumentView.tsx`
- Modify: `src/components/workspace/EditableAsset.tsx`
- Modify: `src/components/workspace/AiTaskBar.tsx`
- Test: `src/components/workspace/__tests__/DocumentView.test.tsx`

**Step 1: 写失败测试，定义 note/import/recording 的统一详情规则**

补测试覆盖：
- `note`/`import` 文档：`document_text` 为主正文资产
- `recording` 文档：`transcript` 为主内容，但 `summary`、`meeting_brief`、`translation` 继续在同页协同呈现
- 无正文时显示可操作空状态，而不是不可写死文案

**Step 2: 运行测试确认 FAIL**

Run: `npm test -- DocumentView`
Expected: FAIL

**Step 3: 实现最小改造**

- `DocumentView` 只保留一套正文与资产渲染逻辑
- `EditableAsset` 成为正文与 AI 资产的基础编辑单元
- 若 `AiTaskBar` 已接入，放在同一详情页上下文中，而不是做独立页面心智
- 删除只读 `<pre>` 方案，避免未来再次分叉

**Step 4: 运行测试确认 PASS**

Run: `npm test -- DocumentView`
Expected: PASS

**Step 5: Commit**

```bash
git add src/components/workspace
git commit -m "refactor(workspace): unify document detail around editable assets"
```

### Task 6: 端到端状态流与回归测试

**Files:**
- Modify: `src/store/__tests__/workspace.test.ts`
- Modify: `src/components/workspace/__tests__/WorkspaceMain.test.tsx`
- Modify: `src/components/workspace/__tests__/WorkspacePanel.test.tsx`
- Modify: `src/components/workspace/__tests__/DocumentView.test.tsx`
- Modify: `src/routes/__tests__/-workspace-routing.test.tsx`

**Step 1: 写失败测试，补齐本轮验收缺口**

需要明确覆盖：
- 新建文档后进入编辑态
- 导入文档后打开并可继续编辑
- 多层文件夹能正确渲染树形结构与展开链
- 搜索进入文档后左侧树状态仍正确

**Step 2: 运行测试确认 FAIL**

Run: `npm test -- workspace`
Expected: FAIL

**Step 3: 补齐最小实现或测试夹具，移除空壳断言**

- 删除只验证按钮存在、不验证结果闭环的空洞测试
- 测试命名改成行为导向，避免继续围绕“组件渲染成功”写低价值用例

**Step 4: 运行完整验证**

Run: `npm test`
Expected: PASS

Run: `npm run typecheck`
Expected: PASS

Run: `cargo test`
Expected: PASS

**Step 5: Commit**

```bash
git add src/components/workspace/__tests__ src/store/__tests__/workspace.test.ts src/routes/__tests__/-workspace-routing.test.tsx
git commit -m "test(workspace): cover authoring, import, and tree navigation flows"
```

### Task 7: 文档同步与收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-03-20-echonote-v3-tauri-rewrite-design.md`
- Modify: `CHANGELOG.md`

**Step 1: 写一个失败检查清单**

列出本轮实现前后需要同步的文档事实：
- Workspace 变为可编辑工作台
- 路由层级与树导航语义
- `source_type='note'`

**Step 2: 人工检查现有文档确认不一致**

Run: `rg -n "manual|/workspace/:docId|文档树|导入" docs/superpowers/specs/2026-03-20-echonote-v3-tauri-rewrite-design.md CHANGELOG.md`
Expected: 能看到待更新旧描述

**Step 3: 更新文档**

- 规格文档同步真实交互模型
- `CHANGELOG.md` 记录 Workspace authoring hard cut

**Step 4: 运行最终验证**

Run: `npm run typecheck && npm test && cargo test`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-03-20-echonote-v3-tauri-rewrite-design.md CHANGELOG.md
git commit -m "docs(workspace): document authoring-first hard cut"
```
