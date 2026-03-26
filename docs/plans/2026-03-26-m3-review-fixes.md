# M3 Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 M3 审查确认的 3 个阻塞问题：模型完整性误判、首次启动缺模型不弹引导、取消下载不真正停止后台传输。

**Architecture:** 后端统一恢复“模型文件存在且大小匹配”这一完整性判定，并把下载取消语义落实到下载循环本身，避免 UI 与后台状态分叉。前端恢复以 `models:*` Tauri 事件为单一事实来源，去掉额外轮询旁路，确保首次启动引导、下载进度和错误处理都沿同一条状态链流转。

**Tech Stack:** Rust (`tokio`, `reqwest`, `wiremock`, `tauri`), React 18 + TypeScript + Zustand + Vitest, tauri-specta bindings

---

### Task 1: 恢复后端模型完整性判定

**Files:**
- Modify: `src-tauri/src/models/registry.rs`

**Step 1: 写失败测试，覆盖残缺文件误判场景**

在 `src-tauri/src/models/registry.rs` 的 `#[cfg(test)]` 中新增：
- `build_variant_size_mismatch_is_not_downloaded`
- `check_required_models_size_mismatch_is_missing`

测试要点：
- 创建与 URL 文件名一致、但大小小于 `size_bytes` 的假模型文件
- `build_variant(...).is_downloaded` 必须为 `false`
- `check_required_models(...)` 必须返回对应 `variant_id`

**Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test models::registry::tests::build_variant_size_mismatch_is_not_downloaded models::registry::tests::check_required_models_size_mismatch_is_missing -- --exact
```

Expected:
- 至少一个测试 FAIL，因为当前实现使用 `path.exists()`

**Step 3: 写最小实现**

在 `src-tauri/src/models/registry.rs` 中：
- 让 `build_variant` 改回使用 `file_matches_size`
- 让 `check_required_models` 对激活模型使用 `file_matches_size`
- 不新增重复判定逻辑，直接复用现有辅助函数

**Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test models::registry -- --nocapture
```

Expected:
- `models::registry::*` 全部 PASS

**Step 5: Commit**

```bash
git add src-tauri/src/models/registry.rs
git commit -m "fix(models): restore size-based model integrity checks"
```

### Task 2: 恢复前端事件驱动的首次启动引导与下载状态

**Files:**
- Modify: `src/store/models.ts`
- Modify: `src/App.tsx`
- Modify: `src/components/models/ModelRequiredDialog.tsx`
- Create: `src/store/__tests__/models.test.ts`

**Step 1: 写失败测试，覆盖事件驱动行为**

在 `src/store/__tests__/models.test.ts` 中新增至少 3 个测试：
- `setupListeners_opens_required_dialog_on_models_required`
- `setupListeners_updates_download_progress_on_models_progress`
- `setupListeners_clears_download_and_sets_error_on_models_error`

测试结构：
- mock `@tauri-apps/api/event` 的 `listen`
- mock `@/lib/bindings` 的 `commands`
- 调用 `useModelsStore.getState()._setupListeners()`
- 手动触发注册下来的事件回调
- 断言 `requiredMissing` / `isRequiredDialogOpen` / `downloads` / `lastError` 变化正确

**Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote
npm test -- src/store/__tests__/models.test.ts
```

Expected:
- FAIL，因为当前 store 未注册这些事件监听

**Step 3: 写最小实现**

在 `src/store/models.ts` 中：
- 恢复 `listen('models:required' | 'models:progress' | 'models:downloaded' | 'models:error')`
- 去掉仅在下载中才工作的轮询逻辑
- `models:error` 事件里写入 `lastError`
- 保留 `loadVariants` / `startDownload` / `cancelDownload` / `deleteModel` / `setActive`
- 若 `get_download_error` 不再有调用方，删掉相关死代码依赖链

在 `src/App.tsx` 中：
- 保持全局挂载 `_setupListeners()`
- 不再依赖轮询副作用提供首次启动状态

在 `src/components/models/ModelRequiredDialog.tsx` 中：
- 保持事件触发后才 `loadVariants()`
- 确认对话框仍不可点遮罩关闭

**Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote
npm test -- src/store/__tests__/models.test.ts
```

Expected:
- 新增 store 测试全部 PASS

**Step 5: Commit**

```bash
git add src/store/models.ts src/App.tsx src/components/models/ModelRequiredDialog.tsx src/store/__tests__/models.test.ts
git commit -m "fix(ui): restore event-driven model onboarding and progress state"
```

### Task 3: 让取消下载真正停止后台传输

**Files:**
- Modify: `src-tauri/src/error.rs`
- Modify: `src-tauri/src/models/downloader.rs`
- Modify: `src-tauri/src/commands/models.rs`
- Modify: `src-tauri/src/state.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/src/commands/settings.rs`

**Step 1: 写失败测试，覆盖取消后不能继续落盘**

在 `src-tauri/src/models/downloader.rs` 的 `#[cfg(test)]` 中新增：
- `download_cancelled_keeps_tmp_and_does_not_create_final_file`

测试要点：
- 启动 `wiremock` 服务，返回大于 `128 KB` 的内容
- 在 `progress_cb` 首次触发后翻转取消标志
- 下载函数必须以“取消”结束，而不是成功
- 最终文件不存在
- `.tmp` 文件保留且其大小小于完整文件大小

**Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test models::downloader::tests::download_cancelled_keeps_tmp_and_does_not_create_final_file -- --exact
```

Expected:
- FAIL，因为当前实现不会中止下载

**Step 3: 写最小实现**

在 `src-tauri/src/error.rs` 中：
- 增加可序列化的 `AppError::Cancelled`

在 `src-tauri/src/models/downloader.rs` 中：
- 让下载循环在读取 chunk 前/后检查取消标志
- 被取消时立即返回 `AppError::Cancelled`
- 保留 `.tmp`，不 rename 成最终文件
- `run_download_worker` 对 `Cancelled` 特判：不发 `models:error`，不发 `models:downloaded`
- 保持下载完成后才热加载引擎
- 若可顺便消除“每次最多 1 个下载”与实现不一致的问题，使用单活跃下载守卫一并修复；若会扩散改动，则在实现备注里明确保留为后续项

同步清理：
- 删除前端已不再使用的 `download_errors` 存储与 `get_download_error` 命令链路
- 更新相关测试初始化代码，确保 `AppState` 构造不再携带死字段

**Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test models::downloader -- --nocapture
```

Expected:
- `models::downloader::*` 全部 PASS

**Step 5: Commit**

```bash
git add src-tauri/src/error.rs src-tauri/src/models/downloader.rs src-tauri/src/commands/models.rs src-tauri/src/state.rs src-tauri/src/lib.rs src-tauri/src/commands/settings.rs
git commit -m "fix(models): abort cancelled downloads and remove stale polling path"
```

### Task 4: 全量回归验证

**Files:**
- Modify: `src/lib/bindings.ts` (由 Rust 侧测试/导出自动更新，如有变更则纳入提交)

**Step 1: 运行后端模型相关测试**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test models::registry
cargo test models::downloader
```

Expected:
- 所有模型相关测试 PASS

**Step 2: 运行前端新增测试与类型检查**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote
npm test -- src/store/__tests__/models.test.ts
npm run typecheck
```

Expected:
- PASS

**Step 3: 运行全量后端测试**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test
```

Expected:
- PASS

**Step 4: 运行定向 clippy，确保本次修复未引入新 warning**

Run:

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo clippy --tests -- src/models/registry.rs src/models/downloader.rs src/commands/models.rs src/error.rs
```

Expected:
- 若命令形式不支持文件过滤，则至少确认本次改动文件无新增 warning
- 记录当前仓库仍存在的非 M3 既有 clippy 问题，不在本次修复中扩散处理

**Step 5: Commit**

```bash
git add src/lib/bindings.ts
git commit -m "test(models): verify M3 review fixes"
```
