# Adaptive VAD + Pause-Based Segmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复实时转录无文字输出的问题——通过自适应 VAD 阈值自动适配不同麦克风，并用停顿检测驱动实时转录，同时用双缓冲异步推理保证音频不被阻断。

**Architecture:** VadFilter 新增滑动窗口 P25 噪声基底估算，动态更新阈值；Pipeline 引入双缓冲（active_buf 积累 + 后台 tokio::spawn 推理），800ms 停顿触发 flush，推理结果通过 tokio::sync::mpsc 回传主循环写入 segments_cache。

**Tech Stack:** Rust (whisper-rs, tokio, std::sync::mpsc), React + Zustand (TypeScript)

---

## 文件职责映射

| 文件 | 操作 | 职责变化 |
|------|------|---------|
| `src-tauri/src/transcription/engine.rs` | Modify | 增加 `compression_ratio_thold(2.4)` 幻觉抑制 |
| `src-tauri/src/audio/vad.rs` | Modify | 新增自适应阈值字段 + P25 噪声基底算法 |
| `src-tauri/src/transcription/pipeline.rs` | Modify | 双缓冲结构、async run_inference、800ms 停顿触发、Stop 同步等待 |
| `src/components/recording/RecordingPanel.tsx` | Modify | VAD 默认阈值 0.010→0.008，clamp 0.020→0.015 |
| `src/store/recording.ts` | Modify | segments 轮询 500ms→300ms（tickCount % 5 → % 3） |
| `src/components/recording/RecordingMain.tsx` | Modify | 线性波形增益，VAD 阈值参考线，校准期状态文字 |

---

## Task 1: engine.rs — 幻觉抑制补全

**文件:**
- Modify: `src-tauri/src/transcription/engine.rs:55-63`

### 背景知识

`compression_ratio_thold` 是 whisper.cpp 的默认参数（值 2.4），用于检测重复文本幻觉（如 "谢谢谢谢谢谢"）。现有 `engine.rs` 已设置 `no_speech_thold` 和 `logprob_thold`，但遗漏了此参数。`whisper_rs::FullParams` 提供 `set_compression_ratio_thold(f32)` 方法。

- [ ] **Step 1.1: 在 `transcribe()` 中现有参数后追加新参数**

在 `engine.rs` 第 59 行（`params.set_logprob_thold(-1.0);`）之后添加：

```rust
// compression_ratio_thold：输出压缩比超过此值时丢弃（幻觉通常产生高度重复文本）
params.set_compression_ratio_thold(2.4);
```

- [ ] **Step 1.2: 验证编译通过**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo check 2>&1 | tail -5
```

期望输出：`Finished` 或无错误。

- [ ] **Step 1.3: Commit**

```bash
cd /Users/weijiazhao/Dev/EchoNote
git add src-tauri/src/transcription/engine.rs
git commit -m "fix(engine): add compression_ratio_thold=2.4 to suppress repetition hallucinations"
```

---

## Task 2: vad.rs — 自适应噪声基底阈值

**文件:**
- Modify: `src-tauri/src/audio/vad.rs`

### 背景知识

**算法：** 维护一个最多 50 帧的 RMS 历史滑动窗口（仅静音帧）。当历史满 50 帧后，计算 P25（第 25 百分位数 = 排序后第 12 个元素），乘以 4.0 得到自适应阈值，再 clamp 到 [0.003, 0.040]。

- 仅静音帧（`rms < adaptive_threshold`）进入历史，防止语音峰值污染估算
- `set_threshold()` 重置自适应（手动 override）
- 冷启动期（历史 < 50 帧）使用初始阈值

**新增字段：**
```rust
rms_history: std::collections::VecDeque<f32>,  // 容量上限 NOISE_FLOOR_WINDOW=50
adaptive_threshold: f32,                        // 当前动态阈值，初始 = new() 的 threshold 参数
```

**常量：**
```rust
const NOISE_FLOOR_WINDOW: usize = 50;    // 需要多少帧静音才进入稳定期
const NOISE_FLOOR_MULTIPLIER: f32 = 4.0; // noise_floor × 4.0 = speech threshold
const ADAPTIVE_MIN: f32 = 0.003;         // 极安静环境下限（防过敏感）
const ADAPTIVE_MAX: f32 = 0.040;         // 极嘈杂环境上限（防过滤所有语音）
```

- [ ] **Step 2.1: 在 `mod tests` 中写 4 个失败测试**

在 `vad.rs` 的 `mod tests { use super::*; ... }` 内追加以下测试。此时 `VadFilter` 还没有 `adaptive_threshold` 字段，**测试会编译失败**（这是 TDD 预期行为）：

```rust
    #[test]
    fn test_adaptive_threshold_converges_after_50_silence_frames() {
        // 初始阈值设为 0.100（远高于语音），让静音帧能进入历史
        // 静音帧 RMS = 0.005（值 0.005 时 RMS = 0.005）
        let mut vad = VadFilter::new(0.100, |_| {});
        let silence_frame: Vec<f32> = vec![0.005f32; 800];
        for _ in 0..50 {
            let _ = vad.process(silence_frame.clone());
        }
        // noise_floor ≈ 0.005, adaptive_threshold ≈ 0.005 * 4.0 = 0.020
        assert!(
            (vad.adaptive_threshold - 0.020).abs() < 0.003,
            "expected adaptive_threshold ≈ 0.020, got {}", vad.adaptive_threshold
        );
    }

    #[test]
    fn test_adaptive_threshold_clamp_lower_bound() {
        let mut vad = VadFilter::new(0.100, |_| {});
        // 极安静：RMS ≈ 0.0001，noise_floor * 4.0 = 0.0004，应被 clamp 到 0.003
        let near_zero: Vec<f32> = vec![0.0001f32; 800];
        for _ in 0..50 {
            let _ = vad.process(near_zero.clone());
        }
        assert!(
            vad.adaptive_threshold >= 0.003,
            "adaptive_threshold below lower bound: {}", vad.adaptive_threshold
        );
    }

    #[test]
    fn test_adaptive_threshold_clamp_upper_bound() {
        // 初始阈值 0.100，噪声 RMS = 0.020（< 0.100，视为静音）
        // noise_floor ≈ 0.020，0.020 * 4.0 = 0.080，应被 clamp 到 0.040
        let mut vad = VadFilter::new(0.100, |_| {});
        let noisy_frame: Vec<f32> = vec![0.020f32; 800];
        for _ in 0..50 {
            let _ = vad.process(noisy_frame.clone());
        }
        assert!(
            vad.adaptive_threshold <= 0.040,
            "adaptive_threshold above upper bound: {}", vad.adaptive_threshold
        );
    }

    #[test]
    fn test_voice_frames_do_not_pollute_noise_history() {
        // 初始阈值 0.010；静音帧 RMS=0.002（<0.010），语音帧 RMS=0.500（>0.010）
        let mut vad = VadFilter::new(0.010, |_| {});
        let silence_frame: Vec<f32> = vec![0.002f32; 800];
        let voice_frame: Vec<f32> = vec![0.500f32; 800];

        // 先 30 帧静音
        for _ in 0..30 {
            let _ = vad.process(silence_frame.clone());
        }
        // 20 帧语音（不应进入 rms_history）
        for _ in 0..20 {
            let _ = vad.process(voice_frame.clone());
        }
        // 再 20 帧静音，共 50 帧静音 → 进入稳定期
        for _ in 0..20 {
            let _ = vad.process(silence_frame.clone());
        }
        // noise_floor ≈ 0.002，threshold ≈ 0.008；若语音帧污染了历史则会远高于此
        assert!(
            vad.adaptive_threshold < 0.030,
            "voice frames polluted noise history: adaptive_threshold = {}", vad.adaptive_threshold
        );
    }
```

- [ ] **Step 2.2: 确认测试编译失败（字段不存在）**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test --lib -- vad 2>&1 | tail -15
```

期望：编译错误，类似 `error[E0609]: no field 'adaptive_threshold' on type 'VadFilter'`。

- [ ] **Step 2.3: 实现自适应阈值**

将 `vad.rs` 替换为以下完整内容：

```rust
// src-tauri/src/audio/vad.rs

use std::collections::VecDeque;
use std::time::{Duration, Instant};

/// 连续 N 块 RMS < threshold → 判定为静音段（用于上下文帧重注）
const SILENCE_BLOCKS: usize = 6;
/// audio:level 最小发送间隔
const LEVEL_EMIT_INTERVAL: Duration = Duration::from_millis(100);
/// 静音上下文前导：静音结束后附带最多 1s 的前导帧
const CONTEXT_CHUNKS: usize = 2; // 约 1s（500ms chunk × 2）

/// 自适应阈值参数
/// 需要积累多少帧静音样本才进入稳定期
const NOISE_FLOOR_WINDOW: usize = 50;
/// noise_floor × multiplier = 自适应阈值
const NOISE_FLOOR_MULTIPLIER: f32 = 4.0;
/// 自适应阈值下限（防止极安静环境过于敏感）
const ADAPTIVE_MIN: f32 = 0.003;
/// 自适应阈值上限（防止极嘈杂环境过滤所有语音）
const ADAPTIVE_MAX: f32 = 0.040;

pub struct VadFilter {
    /// 初始阈值（set_threshold() 重置时同步更新）
    threshold: f32,
    /// 当前动态阈值，初始 = threshold，稳定后由噪声基底自动更新
    /// pub(crate) 而非 pub：仅诊断测试需要读取，外部不应直接修改（用 set_threshold() override）
    pub(crate) adaptive_threshold: f32,
    /// 静音帧 RMS 历史（仅静音帧写入），容量 NOISE_FLOOR_WINDOW
    rms_history: VecDeque<f32>,
    silence_count: usize,
    /// 最近 CONTEXT_CHUNKS 帧缓存，用于静音结束时补充上下文
    context_buf: VecDeque<Vec<f32>>,
    last_level_emit: Instant,
    /// 音频电平回调（在 std::thread 中调用，回调内部应快速完成）
    on_level: Box<dyn Fn(f32) + Send + 'static>,
    /// 诊断用：已处理帧数
    chunk_count: u64,
}

impl VadFilter {
    /// `threshold`: 初始 VAD 阈值（冷启动期使用）；稳定后被噪声基底自适应覆盖
    /// `on_level`: 每隔 100ms 调用一次，传入归一化 RMS [0.0, 1.0]
    pub fn new(threshold: f32, on_level: impl Fn(f32) + Send + 'static) -> Self {
        Self {
            threshold,
            adaptive_threshold: threshold,
            rms_history: VecDeque::with_capacity(NOISE_FLOOR_WINDOW + 1),
            silence_count: 0,
            context_buf: VecDeque::with_capacity(CONTEXT_CHUNKS + 1),
            last_level_emit: Instant::now()
                .checked_sub(LEVEL_EMIT_INTERVAL)
                .unwrap_or_else(Instant::now),
            on_level: Box::new(on_level),
            chunk_count: 0,
        }
    }

    /// 处理一个音频块，返回应送往 whisper pipeline 的帧（可能为空）
    pub fn process(&mut self, chunk: Vec<f32>) -> Vec<Vec<f32>> {
        let rms = Self::rms(&chunk);
        self.chunk_count += 1;

        // 诊断日志：前 10 帧 + 每 50 帧一次
        if self.chunk_count <= 10 || self.chunk_count % 50 == 0 {
            let verdict = if rms >= self.adaptive_threshold { "VOICE" } else { "silent" };
            let stable = if self.rms_history.len() >= NOISE_FLOOR_WINDOW { "adapted" } else { "cold" };
            eprintln!(
                "[vad] chunk #{}: rms={:.5}, threshold={:.4}({}) → {}",
                self.chunk_count, rms, self.adaptive_threshold, stable, verdict
            );
        }

        // 100ms 降频回调
        if self.last_level_emit.elapsed() >= LEVEL_EMIT_INTERVAL {
            (self.on_level)(rms.min(1.0));
            self.last_level_emit = Instant::now();
        }

        if rms < self.adaptive_threshold {
            // 静音帧：更新噪声基底历史
            self.silence_count += 1;
            self.update_noise_floor(rms);

            // 循环覆盖旧帧
            if self.context_buf.len() >= CONTEXT_CHUNKS {
                self.context_buf.pop_front();
            }
            self.context_buf.push_back(chunk);
            Vec::new()
        } else {
            // 语音帧：重置静音计数
            let was_silent = self.silence_count >= SILENCE_BLOCKS;
            self.silence_count = 0;

            let mut to_send: Vec<Vec<f32>> = Vec::new();
            if was_silent {
                to_send.extend(self.context_buf.drain(..));
            } else {
                self.context_buf.clear();
            }
            to_send.push(chunk);
            to_send
        }
    }

    /// 仅在静音帧时调用：将 rms 写入历史，满 NOISE_FLOOR_WINDOW 后更新自适应阈值
    fn update_noise_floor(&mut self, rms: f32) {
        if self.rms_history.len() >= NOISE_FLOOR_WINDOW {
            self.rms_history.pop_front();
        }
        self.rms_history.push_back(rms);

        if self.rms_history.len() >= NOISE_FLOOR_WINDOW {
            // P25：排序后取第 25 百分位（index = window_size / 4）
            let mut sorted: Vec<f32> = self.rms_history.iter().copied().collect();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let p25_idx = NOISE_FLOOR_WINDOW / 4; // 50 / 4 = 12
            let noise_floor = sorted[p25_idx];
            self.adaptive_threshold = (noise_floor * NOISE_FLOOR_MULTIPLIER)
                .clamp(ADAPTIVE_MIN, ADAPTIVE_MAX);
        }
    }

    /// RMS 能量：sqrt(mean(x²))
    pub fn rms(samples: &[f32]) -> f32 {
        if samples.is_empty() {
            return 0.0;
        }
        let mean_sq: f32 = samples.iter().map(|s| s * s).sum::<f32>() / samples.len() as f32;
        mean_sq.sqrt()
    }

    /// 手动设置阈值（重置自适应，清除历史）
    pub fn set_threshold(&mut self, threshold: f32) {
        self.threshold = threshold;
        self.adaptive_threshold = threshold;
        self.rms_history.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_silent(n: usize) -> Vec<f32> { vec![0.0f32; n] }
    fn make_loud(n: usize) -> Vec<f32> { vec![0.5f32; n] }

    #[test]
    fn test_rms_all_zeros_is_zero() {
        assert_eq!(VadFilter::rms(&make_silent(1024)), 0.0);
    }

    #[test]
    fn test_rms_constant_signal() {
        let rms = VadFilter::rms(&make_loud(1024));
        assert!((rms - 0.5).abs() < 1e-5, "rms = {rms}");
    }

    #[test]
    fn test_rms_sine_approx_amplitude_over_sqrt2() {
        use std::f32::consts::PI;
        let amplitude = 0.8f32;
        let samples: Vec<f32> = (0..16000)
            .map(|i| amplitude * (2.0 * PI * 440.0 * i as f32 / 16000.0).sin())
            .collect();
        let rms = VadFilter::rms(&samples);
        let expected = amplitude / 2.0f32.sqrt();
        assert!((rms - expected).abs() < 0.001, "rms={rms}, expected={expected}");
    }

    #[test]
    fn test_vad_no_apphandle_needed() {
        let received = std::sync::Arc::new(std::sync::Mutex::new(Vec::<f32>::new()));
        let r = std::sync::Arc::clone(&received);
        let mut vad = VadFilter::new(0.3, move |rms| {
            r.lock().unwrap().push(rms);
        });
        for _ in 0..5 {
            vad.process(make_loud(1600));
        }
        let _ = received.lock().unwrap().len();
    }

    #[test]
    fn test_adaptive_threshold_converges_after_50_silence_frames() {
        let mut vad = VadFilter::new(0.100, |_| {});
        let silence_frame: Vec<f32> = vec![0.005f32; 800];
        for _ in 0..50 {
            let _ = vad.process(silence_frame.clone());
        }
        // noise_floor ≈ 0.005, adaptive_threshold ≈ 0.005 * 4.0 = 0.020
        assert!(
            (vad.adaptive_threshold - 0.020).abs() < 0.003,
            "expected adaptive_threshold ≈ 0.020, got {}", vad.adaptive_threshold
        );
    }

    #[test]
    fn test_adaptive_threshold_clamp_lower_bound() {
        let mut vad = VadFilter::new(0.100, |_| {});
        let near_zero: Vec<f32> = vec![0.0001f32; 800];
        for _ in 0..50 {
            let _ = vad.process(near_zero.clone());
        }
        assert!(
            vad.adaptive_threshold >= 0.003,
            "adaptive_threshold below lower bound: {}", vad.adaptive_threshold
        );
    }

    #[test]
    fn test_adaptive_threshold_clamp_upper_bound() {
        let mut vad = VadFilter::new(0.100, |_| {});
        let noisy_frame: Vec<f32> = vec![0.020f32; 800];
        for _ in 0..50 {
            let _ = vad.process(noisy_frame.clone());
        }
        assert!(
            vad.adaptive_threshold <= 0.040,
            "adaptive_threshold above upper bound: {}", vad.adaptive_threshold
        );
    }

    #[test]
    fn test_voice_frames_do_not_pollute_noise_history() {
        let mut vad = VadFilter::new(0.010, |_| {});
        let silence_frame: Vec<f32> = vec![0.002f32; 800];
        let voice_frame: Vec<f32> = vec![0.500f32; 800];

        for _ in 0..30 {
            let _ = vad.process(silence_frame.clone());
        }
        for _ in 0..20 {
            let _ = vad.process(voice_frame.clone());
        }
        for _ in 0..20 {
            let _ = vad.process(silence_frame.clone());
        }
        assert!(
            vad.adaptive_threshold < 0.030,
            "voice frames polluted noise history: adaptive_threshold = {}", vad.adaptive_threshold
        );
    }
}
```

- [ ] **Step 2.4: 运行测试，确认 4 个新测试 PASS**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test --lib -- vad 2>&1
```

期望：所有 `vad::tests::*` 测试 PASS，无编译错误。

- [ ] **Step 2.5: Commit**

```bash
cd /Users/weijiazhao/Dev/EchoNote
git add src-tauri/src/audio/vad.rs
git commit -m "feat(vad): adaptive noise floor threshold via P25 sliding window

- Add rms_history VecDeque (capacity 50, silence frames only)
- After 50 silence frames: adaptive_threshold = P25(history) * 4.0
- Clamp to [0.003, 0.040] for extreme environments
- Voice frames excluded from history to prevent pollution
- set_threshold() resets adaptation (manual override preserved)
- Enhanced diagnostic log shows cold/adapted state"
```

---

## Task 3: pipeline.rs — 双缓冲 + 异步推理 + 800ms 停顿触发

**文件:**
- Modify: `src-tauri/src/transcription/pipeline.rs`

### 背景知识

**双缓冲设计：** 引入 `active_buf` 替代旧 `accumulator`。检测到 800ms 停顿时（`last_audio_at.elapsed() >= 800ms`），将 `active_buf` 通过 `tokio::spawn` 发给后台 `run_inference` 任务，主循环继续积累新音频到清空后的 `active_buf`。

**结果回传：** `run_inference` 完成后通过 `tokio::sync::mpsc::Sender<InferenceResult>` 发送结果，主循环的 Step 1 通过 `try_recv()` 收取结果并写入 `segments_cache`。

**Stop 同步处理：** 若 `inference_in_flight=true`，Stop 先用 `tokio::time::timeout(30s, result_rx.recv())` 等待后台任务完成，再 flush 剩余 `active_buf`（同步 await）。

**关键常量变更：**
- `MAX_ACCUM_SAMPLES`: 30s → 25s（安全兜底，防截断）
- 新增 `PAUSE_FLUSH_MS = 800`（停顿触发阈值）
- 新增 `MIN_INFER_SAMPLES = 8_000`（最小推理长度 0.5s，防幻觉）
- 删除 `SILENCE_FLUSH_SECS`（被 PAUSE_FLUSH_MS 替代）

**`run()` 的 destructure 更新：** 原代码 `let Self { rx, app, engine, segments_cache } = self;` 需改为 `let Self { rx, app, engine, segments_cache, result_tx, result_rx } = self;`。

- [ ] **Step 3.1: 写 2 个失败测试**

在 `pipeline.rs` 末尾的 `mod tests` 内追加（此时 `InferenceResult` 不存在，编译失败）：

```rust
    #[test]
    fn test_inference_result_channel() {
        use tokio::sync::mpsc;
        use super::{InferenceResult};
        let (tx, mut rx) = mpsc::channel::<InferenceResult>(4);
        let result = InferenceResult {
            session_id: "sess-1".into(),
            segments: vec![],
        };
        tx.try_send(result).unwrap();
        let received = rx.try_recv().unwrap();
        assert_eq!(received.session_id, "sess-1");
        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_pipeline_constants() {
        use super::{PAUSE_FLUSH_MS, MIN_INFER_SAMPLES, MAX_ACCUM_SAMPLES};
        assert_eq!(PAUSE_FLUSH_MS, 800u64);
        assert_eq!(MIN_INFER_SAMPLES, 8_000usize);
        assert_eq!(MAX_ACCUM_SAMPLES, 16_000usize * 25);
    }
```

- [ ] **Step 3.2: 确认测试编译失败**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test --lib -- pipeline::tests 2>&1 | head -20
```

期望：编译错误，`InferenceResult` 和常量未定义。

- [ ] **Step 3.3: 实现双缓冲 + 异步推理**

将 `pipeline.rs` 替换为以下完整内容：

```rust
// src-tauri/src/transcription/pipeline.rs

use std::collections::HashMap;
use std::sync::{Arc, Mutex, mpsc};
use std::time::Instant;
use tauri::{AppHandle, Emitter};
use tokio::sync::mpsc as async_mpsc;
use tokio::task;

use crate::transcription::engine::WhisperEngine;
use crate::commands::transcription::{RecordingMode, RecordingStatus, SegmentPayload};

/// 发往 TranscriptionWorker 的控制命令
pub enum TranscriptionCommand {
    Start {
        session_id: String,
        language: Option<String>,
        mode: RecordingMode,
        vad_threshold: f32,
    },
    AudioChunk(Vec<f32>),
    Pause { session_id: String },
    Resume { session_id: String },
    /// done_tx: pipeline 完成 flush 后发送信号
    Stop { session_id: String, done_tx: tokio::sync::oneshot::Sender<()> },
}

/// 后台推理任务回传结果
pub struct InferenceResult {
    pub session_id: String,
    pub segments: Vec<SegmentPayload>,
}

/// 停顿时长：超过此值且 accumulator 非空 → 触发推理（中文句子边界）
pub const PAUSE_FLUSH_MS: u64 = 800;
/// 最小推理音频长度（0.5s @ 16kHz），短于此不推理（防止幻觉）
pub const MIN_INFER_SAMPLES: usize = 8_000;
/// 安全兜底：超过 25s 强制 flush（防止连续说话无停顿时无限积累）
pub const MAX_ACCUM_SAMPLES: usize = 16_000 * 25;

pub struct TranscriptionWorker {
    rx: mpsc::Receiver<TranscriptionCommand>,
    app: AppHandle,
    engine: Arc<Mutex<Option<WhisperEngine>>>,
    segments_cache: Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,
    /// 后台推理结果发送端（每次 spawn 时 clone）
    /// NOTE: try_send 若失败（通道满或 receiver drop），Stop 的 result_rx.recv() 会超时 30s。
    /// inference_in_flight 保证同一时刻至多一个 spawn，实践中不会触发此情况。
    result_tx: async_mpsc::Sender<InferenceResult>,
    /// 后台推理结果接收端（主循环 Step 1 轮询）
    result_rx: async_mpsc::Receiver<InferenceResult>,
}

impl TranscriptionWorker {
    pub fn new(
        rx: mpsc::Receiver<TranscriptionCommand>,
        app: AppHandle,
        engine: Arc<Mutex<Option<WhisperEngine>>>,
        segments_cache: Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,
    ) -> Self {
        // 容量 4：Whisper Mutex 串行保证实际至多 1 个结果在途
        let (result_tx, result_rx) = async_mpsc::channel(4);
        Self { rx, app, engine, segments_cache, result_tx, result_rx }
    }

    pub async fn run(self) {
        let Self { rx, app, engine, segments_cache, result_tx, mut result_rx } = self;

        let mut active_buf: Vec<f32> = Vec::new();
        let mut session_id: Option<String> = None;
        let mut language: Option<String> = None;
        let mut translate = false;
        let mut segment_counter: u32 = 0;
        let mut paused = false;
        let mut last_audio_at = Instant::now();
        let mut inference_in_flight = false;

        loop {
            // ── Step 1: 收取后台推理完成结果（非阻塞）────────────────────
            if let Ok(result) = result_rx.try_recv() {
                if let Ok(mut cache) = segments_cache.lock() {
                    cache.entry(result.session_id.clone()).or_default().extend(result.segments.clone());
                }
                for seg in &result.segments {
                    let _ = app.emit("transcription:segment", seg);
                }
                segment_counter += result.segments.len() as u32;
                inference_in_flight = false;
            }

            // ── Step 2: 处理控制命令（每次迭代处理一条）──────────────────
            match rx.try_recv() {
                Ok(cmd) => match cmd {
                    TranscriptionCommand::Start { session_id: sid, language: lang, mode, .. } => {
                        session_id = Some(sid.clone());
                        language = lang;
                        translate = matches!(mode, RecordingMode::TranscribeAndTranslate { .. });
                        active_buf.clear();
                        segment_counter = 0;
                        paused = false;
                        inference_in_flight = false;
                        last_audio_at = Instant::now();
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Recording {
                                session_id: sid,
                                started_at: chrono::Utc::now().timestamp_millis(),
                            });
                    }
                    TranscriptionCommand::AudioChunk(chunk) if !paused && session_id.is_some() => {
                        active_buf.extend_from_slice(&chunk);
                        last_audio_at = Instant::now();
                    }
                    TranscriptionCommand::Pause { session_id: sid } => {
                        paused = true;
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Paused { session_id: sid });
                    }
                    TranscriptionCommand::Resume { session_id: sid } => {
                        paused = false;
                        last_audio_at = Instant::now();
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Recording {
                                session_id: sid,
                                started_at: chrono::Utc::now().timestamp_millis(),
                            });
                    }
                    TranscriptionCommand::Stop { session_id: sid, done_tx } => {
                        // 1. 等待后台推理完成（最多 30s）
                        if inference_in_flight {
                            match tokio::time::timeout(
                                tokio::time::Duration::from_secs(30),
                                result_rx.recv(),
                            ).await {
                                Ok(Some(result)) => {
                                    if let Ok(mut cache) = segments_cache.lock() {
                                        cache.entry(result.session_id.clone())
                                            .or_default()
                                            .extend(result.segments.clone());
                                    }
                                    for seg in &result.segments {
                                        let _ = app.emit("transcription:segment", seg);
                                    }
                                    segment_counter += result.segments.len() as u32;
                                }
                                Ok(None) => eprintln!("[pipeline] result channel closed before stop"),
                                Err(_) => eprintln!("[pipeline] inference timeout on stop, proceeding"),
                            }
                            inference_in_flight = false;
                        }
                        // 2. Flush 剩余音频（同步 await，Stop 后全部数据写入 cache）
                        if !active_buf.is_empty() {
                            flush_to_whisper(
                                &mut active_buf, &session_id, &language,
                                translate, &mut segment_counter,
                                &app, &engine, &segments_cache,
                            ).await;
                        }
                        // 3. 重置状态
                        session_id = None;
                        paused = false;
                        inference_in_flight = false;
                        let _ = app.emit("transcription:status",
                            RecordingStatus::Stopped {
                                session_id: sid.clone(),
                                recording_id: sid,
                            });
                        let _ = done_tx.send(());
                    }
                    _ => {} // AudioChunk while paused → discard
                },
                Err(mpsc::TryRecvError::Empty) => {
                    // ── Step 3: 检查 flush 条件（仅当无推理任务在途时）──────
                    // NOTE: 当 AudioChunk 频繁到来时（每 500ms 一个），大多数循环迭代
                    // 实际上都落入 Empty 分支（50ms loop vs 500ms chunk），
                    // flush 检查在实践中会正常触发。
                    if session_id.is_some() && !paused && !inference_in_flight {
                        let pause_triggered = last_audio_at.elapsed().as_millis() as u64 >= PAUSE_FLUSH_MS
                            && active_buf.len() >= MIN_INFER_SAMPLES;
                        let safety_triggered = active_buf.len() >= MAX_ACCUM_SAMPLES;

                        if pause_triggered || safety_triggered {
                            let audio = std::mem::take(&mut active_buf);
                            let sid = session_id.clone().unwrap_or_default();
                            let lang = language.clone();
                            let snapshot = segment_counter;
                            let engine_arc = Arc::clone(&engine);
                            let tx = result_tx.clone();
                            inference_in_flight = true;
                            tokio::spawn(run_inference(audio, sid, lang, translate, snapshot, engine_arc, tx));
                        }
                    }
                    // ── Step 4: 50ms 休眠 ─────────────────────────────────
                    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
                }
                Err(mpsc::TryRecvError::Disconnected) => break,
            }
        }
    }
}

/// 后台推理任务：spawn_blocking 调用 Whisper，结果通过 result_tx 回传主循环
/// 无论成功或失败都发送（即使 segments 为空），确保 inference_in_flight 被主循环清除
async fn run_inference(
    audio: Vec<f32>,
    session_id: String,
    language: Option<String>,
    translate: bool,
    counter_snapshot: u32,
    engine: Arc<Mutex<Option<WhisperEngine>>>,
    result_tx: async_mpsc::Sender<InferenceResult>,
) {
    // 前置检查：engine 是否已加载
    {
        let guard = engine.lock().unwrap();
        if guard.is_none() {
            let _ = result_tx.try_send(InferenceResult { session_id, segments: vec![] });
            return;
        }
    }

    let sid_clone = session_id.clone();
    let lang_clone = language.clone();

    let result = task::spawn_blocking(move || {
        let guard = engine.lock().unwrap();
        if let Some(eng) = guard.as_ref() {
            eng.transcribe(&audio, lang_clone.as_deref(), translate)
        } else {
            Ok(vec![])
        }
    }).await;

    let segments = match result {
        Ok(Ok(raw_segs)) => {
            raw_segs.iter().enumerate().map(|(i, seg)| SegmentPayload {
                id: counter_snapshot + i as u32,
                recording_session_id: sid_clone.clone(),
                start_ms: seg.start_ms,
                end_ms: seg.end_ms,
                text: seg.text.clone(),
                language: seg.language.clone(),
                is_partial: false,
            }).collect()
        }
        Ok(Err(e)) => { eprintln!("[pipeline] whisper error: {e}"); vec![] }
        Err(e) => { eprintln!("[pipeline] spawn_blocking panicked: {e}"); vec![] }
    };

    // try_send：若通道满则静默失败（Whisper Mutex 串行保证通道不满）
    let _ = result_tx.try_send(InferenceResult { session_id, segments });
}

/// Stop 时的同步 flush：直接 await，保证 Stop 前所有音频写入 segments_cache
/// 复用逻辑与 run_inference 相同，但同步返回（无通道）
async fn flush_to_whisper(
    active_buf: &mut Vec<f32>,
    session_id: &Option<String>,
    language: &Option<String>,
    translate: bool,
    counter: &mut u32,
    app: &AppHandle,
    engine: &Arc<Mutex<Option<WhisperEngine>>>,
    segments_cache: &Arc<Mutex<HashMap<String, Vec<SegmentPayload>>>>,
) {
    let audio = std::mem::take(active_buf);
    if audio.is_empty() { return; }
    let sid = session_id.clone().unwrap_or_default();
    let lang = language.clone();

    {
        let guard = engine.lock().unwrap();
        if guard.is_none() { return; }
    }

    let engine_arc = Arc::clone(engine);
    let app_clone = app.clone();
    let current_counter = *counter;
    let sid_clone = sid.clone();
    let segments_cache_clone = Arc::clone(segments_cache);

    let result = task::spawn_blocking(move || {
        let guard = engine_arc.lock().unwrap();
        if let Some(eng) = guard.as_ref() {
            eng.transcribe(&audio, lang.as_deref(), translate)
        } else {
            Ok(vec![])
        }
    }).await;

    match result {
        Ok(Ok(segments)) => {
            let mut new_payloads = Vec::new();
            for (i, seg) in segments.iter().enumerate() {
                let payload = SegmentPayload {
                    id: current_counter + i as u32,
                    recording_session_id: sid_clone.clone(),
                    start_ms: seg.start_ms,
                    end_ms: seg.end_ms,
                    text: seg.text.clone(),
                    language: seg.language.clone(),
                    is_partial: false,
                };
                let _ = app_clone.emit("transcription:segment", &payload);
                new_payloads.push(payload);
            }
            // 循环外一次性更新 counter（避免循环内逐一 += 1 的语义混乱）
            *counter += segments.len() as u32;
            if let Ok(mut cache) = segments_cache_clone.lock() {
                cache.entry(sid_clone).or_default().extend(new_payloads);
            }
        }
        Ok(Err(e)) => eprintln!("[pipeline] whisper error: {e}"),
        Err(e) => eprintln!("[pipeline] spawn_blocking panicked: {e}"),
    }
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;
    use super::TranscriptionCommand;

    #[test]
    fn test_channel_send_recv() {
        let (tx, rx) = mpsc::sync_channel::<TranscriptionCommand>(32);

        tx.send(TranscriptionCommand::AudioChunk(vec![0.0f32; 1600])).unwrap();
        tx.send(TranscriptionCommand::Pause { session_id: "test-session".into() }).unwrap();
        tx.send(TranscriptionCommand::Resume { session_id: "test-session".into() }).unwrap();
        let (done_tx, _done_rx) = tokio::sync::oneshot::channel();
        tx.send(TranscriptionCommand::Stop { session_id: "test-session".into(), done_tx }).unwrap();

        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::AudioChunk(_)));
        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Pause { .. }));
        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Resume { .. }));
        assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Stop { .. }));
    }

    #[test]
    fn test_sync_sender_backpressure() {
        let (tx, _rx) = mpsc::sync_channel::<TranscriptionCommand>(1);
        tx.try_send(TranscriptionCommand::AudioChunk(vec![0.0; 100])).unwrap();
        let result = tx.try_send(TranscriptionCommand::AudioChunk(vec![0.0; 100]));
        assert!(result.is_err(), "should fail when channel is full");
    }

    #[test]
    fn test_channel_disconnected() {
        let (tx, rx) = mpsc::sync_channel::<TranscriptionCommand>(4);
        drop(rx);
        let result = tx.send(TranscriptionCommand::AudioChunk(vec![]));
        assert!(result.is_err());
    }

    #[test]
    fn test_inference_result_channel() {
        use tokio::sync::mpsc;
        use super::InferenceResult;
        let (tx, mut rx) = mpsc::channel::<InferenceResult>(4);
        let result = InferenceResult {
            session_id: "sess-1".into(),
            segments: vec![],
        };
        tx.try_send(result).unwrap();
        let received = rx.try_recv().unwrap();
        assert_eq!(received.session_id, "sess-1");
        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn test_pipeline_constants() {
        use super::{PAUSE_FLUSH_MS, MIN_INFER_SAMPLES, MAX_ACCUM_SAMPLES};
        assert_eq!(PAUSE_FLUSH_MS, 800u64);
        assert_eq!(MIN_INFER_SAMPLES, 8_000usize);
        assert_eq!(MAX_ACCUM_SAMPLES, 16_000usize * 25);
    }
}

#[cfg(test)]
mod integration_tests {
    use std::path::Path;
    use crate::transcription::engine::WhisperEngine;

    #[test]
    #[ignore = "requires whisper model file at /tmp/ggml-base.bin"]
    fn test_whisper_engine_transcribe_silence() {
        let model_path = Path::new("/tmp/ggml-base.bin");
        if !model_path.exists() {
            eprintln!("model not found, skipping");
            return;
        }
        let engine = WhisperEngine::new(model_path).expect("engine init failed");
        let audio = vec![0.0f32; 16_000];
        let segments = engine.transcribe(&audio, None, false)
            .expect("transcribe failed");
        for seg in &segments {
            assert!(seg.text.trim().is_empty() || seg.text.len() < 5,
                "unexpected text from silence: '{}'", seg.text);
        }
    }
}
```

- [ ] **Step 3.4: 运行测试，确认所有测试 PASS**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo test --lib -- pipeline 2>&1
```

期望：所有 `pipeline::tests::*` PASS，`integration_tests::*` 被 ignore（需要模型文件）。

- [ ] **Step 3.5: 完整编译检查**

```bash
cd /Users/weijiazhao/Dev/EchoNote/src-tauri
cargo check 2>&1 | tail -10
```

期望：`Finished` 无错误。

- [ ] **Step 3.6: Commit**

```bash
cd /Users/weijiazhao/Dev/EchoNote
git add src-tauri/src/transcription/pipeline.rs
git commit -m "feat(pipeline): double-buffer async inference with 800ms pause detection

- Replace accumulator with active_buf + tokio::spawn(run_inference)
- Pause trigger: 800ms silence + min 0.5s audio (vs old 3s block)
- Safety flush: 25s max accumulation (vs old 30s)
- run_inference: background task, returns via tokio::sync::mpsc
- Stop: waits for in-flight inference (30s timeout) before final flush
- Removes blocking flush_to_whisper from hot loop path"
```

---

## Task 4: Frontend — 波形修正 + 轮询优化 + VAD 默认值

### Task 4a: RecordingPanel.tsx — VAD 默认值

**文件:**
- Modify: `src/components/recording/RecordingPanel.tsx:42,53`

- [ ] **Step 4a.1: 修改默认阈值和 clamp 上限**

将第 42 行的默认值从 `0.010` 改为 `0.008`：

```tsx
// 旧
const [vadThreshold, setVadThreshold] = useState<number>(0.010)

// 新
const [vadThreshold, setVadThreshold] = useState<number>(0.008)
```

将第 53 行的 clamp 上限从 `0.020` 改为 `0.015`：

```tsx
// 旧
if (cfg.vad_threshold != null) setVadThreshold(Math.min(cfg.vad_threshold, 0.020))

// 新（0.015 是 iPhone mic 的实际语音 RMS 上界，超过此值会过滤所有语音）
if (cfg.vad_threshold != null) setVadThreshold(Math.min(cfg.vad_threshold, 0.015))
```

### Task 4b: store/recording.ts — segments 轮询频率

**文件:**
- Modify: `src/store/recording.ts:112`

- [ ] **Step 4b.1: 修改轮询频率**

将第 112 行（`// 每 5 次（500ms）` 注释处）修改：

```ts
// 旧（timer interval=100ms，% 5 → 每 500ms 一次）
// 每 5 次（500ms）轮询一次 segments
if (tickCount % 5 === 0 && currentSession) {

// 新（timer interval 保持 100ms 不变，% 3 → 每 300ms 一次）
// 每 3 次（300ms）轮询一次 segments（timer interval=100ms，勿修改 interval 本身）
if (tickCount % 3 === 0 && currentSession) {
```

### Task 4c: RecordingMain.tsx — 波形 + 校准文字

**文件:**
- Modify: `src/components/recording/RecordingMain.tsx:25-70,198-200`

- [ ] **Step 4c.1: 修改 AudioWaveform 接受 vadThreshold prop 并绘制阈值参考线**

将 `AudioWaveform` 函数替换为：

```tsx
function AudioWaveform({ level, vadThreshold }: { level: number; vadThreshold?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const historyRef = useRef<number[]>(new Array(120).fill(0))

  useEffect(() => {
    // 线性 10x 增益：iPhone mic 0.015 → 显示 15%；清晰语音 0.05 → 显示 50%
    // 避免 sqrt 放大导致 0.014 RMS 显示为 85%（误导 VAD 调试）
    const displayLevel = Math.min(1, level * 10)
    historyRef.current.push(displayLevel)
    if (historyRef.current.length > 120) historyRef.current.shift()

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { width, height } = canvas
    ctx.clearRect(0, 0, width, height)

    const accentColor = getComputedStyle(document.documentElement)
      .getPropertyValue('--color-accent-primary').trim() || '#7aa2f7'

    historyRef.current.forEach((lvl, i) => {
      const barHeight = Math.max(2, lvl * height * 0.9)
      const x = i * (width / historyRef.current.length)
      const y = (height - barHeight) / 2
      ctx.fillStyle = accentColor
      ctx.globalAlpha = 0.4 + lvl * 0.6
      ctx.fillRect(x, y, (width / historyRef.current.length) - 1, barHeight)
    })

    // VAD 阈值参考线（虚线）：仅在提供 vadThreshold 时绘制
    if (vadThreshold !== undefined) {
      const thresholdDisplay = Math.min(1, vadThreshold * 10)
      const thresholdY = (height - thresholdDisplay * height * 0.9) / 2
      ctx.setLineDash([4, 4])
      ctx.strokeStyle = accentColor
      ctx.globalAlpha = 0.5
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(0, thresholdY)
      ctx.lineTo(width, thresholdY)
      ctx.stroke()
      ctx.moveTo(0, height - thresholdY)
      ctx.lineTo(width, height - thresholdY)
      ctx.stroke()
      ctx.setLineDash([])
    }

    ctx.globalAlpha = 1
  }, [level, vadThreshold])

  return (
    <canvas
      ref={canvasRef}
      width={480}
      height={80}
      className="w-full rounded-md bg-bg-secondary"
    />
  )
}
```

- [ ] **Step 4c.2: 更新 AudioWaveform 调用，传入 vadThreshold**

将第 188 行的 `<AudioWaveform level={audioLevel} />` 改为：

```tsx
<AudioWaveform level={audioLevel} vadThreshold={config?.vad_threshold} />
```

- [ ] **Step 4c.3: 更新校准期状态文字**

将第 198-203 行（`{segments.length === 0 ? ...}` 的条件渲染部分）改为：

```tsx
{segments.length === 0 ? (
  <p className="text-text-muted text-center mt-8">
    {status === 'idle'
      ? 'Press Start Recording to begin'
      : status === 'recording' && elapsed < 5000
      ? 'Calibrating microphone...'
      : 'Listening...'}
  </p>
) : (
```

- [ ] **Step 4c.4: TypeScript 类型检查**

```bash
cd /Users/weijiazhao/Dev/EchoNote
npx tsc --noEmit 2>&1 | tail -20
```

期望：无类型错误。

- [ ] **Step 4c.5: Commit**

```bash
cd /Users/weijiazhao/Dev/EchoNote
git add src/components/recording/RecordingPanel.tsx \
        src/store/recording.ts \
        src/components/recording/RecordingMain.tsx
git commit -m "feat(frontend): VAD defaults, 300ms poll, linear waveform with threshold line

- RecordingPanel: default vadThreshold 0.010→0.008, clamp 0.020→0.015
- recording.ts: segments poll interval 500ms→300ms (tickCount % 5 → % 3)
- AudioWaveform: linear 10x gain (removes sqrt over-amplification)
- AudioWaveform: draw dashed VAD threshold reference line on canvas
- RecordingMain: show 'Calibrating microphone...' for first 5s"
```

---

## 验收标准

以下所有命令应无错误：

```bash
# Rust 全量测试
cd /Users/weijiazhao/Dev/EchoNote/src-tauri && cargo test --lib 2>&1

# TypeScript 类型检查
cd /Users/weijiazhao/Dev/EchoNote && npx tsc --noEmit 2>&1
```

行为验收（手动）：
1. 用 iPhone 麦克风录制中文语音 → 5-10s 后（第一次停顿后约 800ms）出现转录文字（不需等待 Stop）
2. 波形中可见 VAD 阈值参考线；波形高度与实际音量成线性比例
3. 录音开始 5s 内显示 "Calibrating microphone..."，之后显示 "Listening..."
4. 停止录音后所有 segments 仍完整保存
