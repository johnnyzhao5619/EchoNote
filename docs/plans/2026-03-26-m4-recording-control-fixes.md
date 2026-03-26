# M4 Recording Control Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 M4 录音链路中的启动失败未上抛、暂停仍写入音频、停止时 WAV/DB 不一致、录音状态查询失真四个阻塞问题，并补齐对应测试。

**Architecture:** 保持现有“录音域轮询为主、后台 worker 负责推理”的总体结构不变，只收紧 `commands/transcription.rs` 的控制语义和 `state.rs` 的状态表达。将设备配置解析、会话元数据、暂停闸门抽成单点状态，避免在 capture/resampler/command 三处重复维护录音真相。

**Tech Stack:** Rust, Tauri 2, tokio, std::sync::mpsc, cpal, rubato, hound, sqlx, specta

---

### Task 1: 建立录音会话状态与纯逻辑测试

**Files:**
- Modify: `src-tauri/src/state.rs`
- Modify: `src-tauri/src/commands/transcription.rs`

**Step 1: 写失败测试，锁定状态语义**

在 `src-tauri/src/commands/transcription.rs` 末尾新增测试模块，覆盖：
- `get_recording_status` 在无会话时返回 `Idle`
- 有活动会话且未暂停时返回 `Recording { started_at != 0 }`
- 有活动会话且暂停时返回 `Paused`
- `stop_realtime` 前置状态清理后会把会话元数据重置

优先抽纯函数，例如：

```rust
fn build_recording_status(meta: Option<&RecordingSessionMeta>) -> RecordingStatus
```

**Step 2: 运行失败测试**

运行：

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test commands::transcription::tests::test_build_recording_status -- --exact
```

预期：因 `RecordingSessionMeta` / helper 尚未存在而失败。

**Step 3: 写最小实现**

在 `src-tauri/src/state.rs` 中新增单一录音会话元数据结构，例如：
- `started_at_ms`
- `is_paused`
- `device_id`

在 `AppState` 中增加：
- `recording_meta: Arc<TokioMutex<Option<RecordingSessionMeta>>>`

在 `commands/transcription.rs` 中只通过这一处状态生成 `RecordingStatus`。

**Step 4: 重新跑测试**

运行同一条 `cargo test`，预期 PASS。

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/state.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/transcription.rs
git commit -m "test(recording): add recording status state model"
```

---

### Task 2: 修复启动阶段错误传播与设备参数硬编码

**Files:**
- Modify: `src-tauri/src/commands/transcription.rs`
- Modify: `src-tauri/src/audio/capture.rs`
- Test: `src-tauri/src/commands/transcription.rs`

**Step 1: 写失败测试**

新增纯逻辑测试，覆盖：
- 设备配置解析失败时返回 `AppError::Audio(...)`，而不是回退到 `44100/1`
- 启动前的准备阶段如果拿不到设备配置，不应产生会话 ID

建议抽函数：

```rust
fn resolve_input_config(device_cfg: Result<(u32, usize), AppError>) -> Result<(u32, usize), AppError>
```

**Step 2: 运行失败测试**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test commands::transcription::tests::test_resolve_input_config -- --exact
```

预期：当前实现因为存在硬编码 fallback 而失败。

**Step 3: 写最小实现**

实现要求：
- 去掉 `44100/1` fallback
- `start_realtime` 在进入后台线程前先同步获取真实设备配置；失败即返回 `AppError`
- 对 capture 启动增加一次“可确认失败”的握手，避免线程内部失败后 command 仍返回成功

握手通道只用于启动确认，不用于长期流式数据。

**Step 4: 重新跑测试**

运行同一条 `cargo test`，预期 PASS。

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/transcription.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/audio/capture.rs
git commit -m "fix(recording): fail fast on capture startup and device config errors"
```

---

### Task 3: 修复暂停语义，确保暂停期间不写 WAV / 不累积 PCM

**Files:**
- Modify: `src-tauri/src/commands/transcription.rs`
- Modify: `src-tauri/src/state.rs`
- Test: `src-tauri/src/commands/transcription.rs`

**Step 1: 写失败测试**

新增纯逻辑测试，覆盖：
- 当会话处于 paused 时，重采样后的 chunk 不写入 `pcm_cache`
- paused 恢复后重新开始写入

建议抽函数：

```rust
fn should_persist_pcm(meta: Option<&RecordingSessionMeta>) -> bool
```

**Step 2: 运行失败测试**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test commands::transcription::tests::test_should_persist_pcm -- --exact
```

预期：当前实现因为暂停时仍写 `pcm_cache` 而失败。

**Step 3: 写最小实现**

实现要求：
- `pause_realtime` / `resume_realtime` 同时更新 `recording_meta.is_paused`
- resampler 线程在写 `pcm_cache` 和发送 `AudioChunk` 前都读取同一份暂停状态
- 避免新增第二套暂停真相；不要同时维护多个布尔值来源

**Step 4: 重新跑测试**

运行同一条 `cargo test`，预期 PASS。

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/transcription.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/state.rs
git commit -m "fix(recording): stop persisting pcm while paused"
```

---

### Task 4: 修复停止事务顺序，保证 WAV 和数据库一致

**Files:**
- Modify: `src-tauri/src/commands/transcription.rs`
- Test: `src-tauri/src/commands/transcription.rs`

**Step 1: 写失败测试**

新增纯逻辑测试，覆盖：
- WAV 写入失败时，`stop_realtime` 路径应返回 `AppError::Io`
- 当 WAV 路径为空/写入失败时，不允许构造 DB insert payload

建议抽纯函数：

```rust
fn ensure_wav_written(result: Result<(), String>, wav_path: &Path) -> Result<String, AppError>
```

**Step 2: 运行失败测试**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test commands::transcription::tests::test_ensure_wav_written -- --exact
```

预期：当前实现因为把 WAV 失败当成 non-fatal 而失败。

**Step 3: 写最小实现**

实现要求：
- WAV 写入失败立即返回 `AppError::Io`
- 不再把空字符串写入 `recordings.file_path`
- 成功写 WAV 后再开始 DB 事务
- `current_session_id`、`recording_meta`、停止通道在成功/失败路径都要保持可恢复的状态清理

**Step 4: 重新跑测试**

运行同一条 `cargo test`，预期 PASS。

**Step 5: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/transcription.rs
git commit -m "fix(recording): require wav write before persisting recording"
```

---

### Task 5: 清理配置漂移与录音页默认值重复

**Files:**
- Modify: `src/components/recording/RecordingPanel.tsx`
- Modify: `src/components/recording/RecordingMain.tsx`

**Step 1: 写失败测试或先锁定行为**

当前前端无现成录音组件测试。若新增前端测试成本过高，本任务至少先清理硬编码重复：
- 去掉 `RecordingPanel` 对 `vad_threshold` 的静默 clamp
- 去掉 `RecordingMain` 中与 `AppConfig` 不一致的 `0.02` 默认阈值，改为只消费路由传入配置或后端默认

**Step 2: 实现最小改动**

要求：
- 配置展示值与保存值一致
- 不额外引入新 store / hook
- 避免同一默认值在 `schema.rs`、`RecordingPanel.tsx`、`RecordingMain.tsx` 三处重复

**Step 3: 验证**

```bash
cd /Users/weijiazhao/Dev/EchoNote
npm run typecheck
```

预期：PASS。

**Step 4: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/src/components/recording/RecordingPanel.tsx /Users/weijiazhao/Dev/EchoNote/src/components/recording/RecordingMain.tsx
git commit -m "refactor(recording): remove frontend vad threshold drift"
```

---

### Task 6: 补齐 M4 缺失测试资产并做全量回归

**Files:**
- Create: `src-tauri/tests/audio_pipeline_e2e.rs`
- Modify: `src-tauri/src/commands/transcription.rs`

**Step 1: 新增 ignored E2E 占位测试**

创建：
- `src-tauri/tests/audio_pipeline_e2e.rs`

内容保持真实约束：
- `#[ignore]`
- 需要真实麦克风和 whisper 模型
- 不引入 mock 数据

**Step 2: 运行后端验证**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test
cargo check
```

预期：全部通过，ignored 测试保留。

**Step 3: 运行前端验证**

```bash
cd /Users/weijiazhao/Dev/EchoNote
npm run typecheck
```

预期：PASS。

**Step 4: Commit**

```bash
git add /Users/weijiazhao/Dev/EchoNote/src-tauri/tests/audio_pipeline_e2e.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/commands/transcription.rs /Users/weijiazhao/Dev/EchoNote/src/components/recording/RecordingPanel.tsx /Users/weijiazhao/Dev/EchoNote/src/components/recording/RecordingMain.tsx /Users/weijiazhao/Dev/EchoNote/src-tauri/src/state.rs /Users/weijiazhao/Dev/EchoNote/src-tauri/src/audio/capture.rs
git commit -m "test(recording): add coverage for control flow fixes"
```

---

### 执行顺序

1. Task 1：先建立单点会话状态，给后续 start/pause/stop 提供统一真相。
2. Task 2：修复启动阶段的错误传播和硬编码设备参数。
3. Task 3：在统一状态上修复暂停语义。
4. Task 4：修复 stop 路径的 WAV/DB 一致性。
5. Task 5：收掉前端配置漂移，避免后续再出现“设置值”和“运行值”不一致。
6. Task 6：补齐缺失测试资产并做全量回归。

### 备注

- 当前录音域以轮询命令为主，计划不尝试恢复对 Tauri 事件的强依赖。
- 不新增 mock capture/whisper 层；后端测试以纯函数、状态构造和 ignored E2E 占位为主。
- 若在实现中发现 `recording_meta` 与现有字段可进一步合并，应优先合并，避免长期维护两套状态。
