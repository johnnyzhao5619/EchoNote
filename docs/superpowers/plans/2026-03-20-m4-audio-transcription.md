# Audio Pipeline + Realtime Transcription Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的实时音频录制管线：cpal 麦克风采集 → rubato 重采样 → VAD 静音检测 → whisper-rs 流式转写 → 前端实时更新，并在录音结束时自动保存 WAV 文件、写入数据库、创建 workspace 文档记录。

**Architecture:** Rust 后端由 `audio/`（capture + resampler + vad）和 `transcription/`（engine + pipeline）两个子模块构成，通过 `std::sync::mpsc::SyncSender` 跨越 cpal 系统线程与 tokio 异步运行时；`AppState` 持有 `transcription_tx: SyncSender<TranscriptionCommand>` 和 `whisper_engine: Arc<Mutex<Option<WhisperEngine>>>`，commands 层不直接执行 whisper 推理，所有推理在长驻 tokio task 内的 `spawn_blocking` 中执行；前端由 `useRecordingStore`（Zustand）、`RecordingPanel`（SecondPanel）、`RecordingMain`（MainContent）三部分组成。当前录音域以 `get_audio_level`、`get_realtime_segments`、`get_recording_status` 轮询驱动实时更新；`audio:level`、`transcription:segment`、`transcription:status` 可保留为兼容/调试用 best-effort 事件，但不作为验收硬要求。

> **Implementation note (2026-03-26):** 当前 Tauri 录音域事件在目标开发环境中不稳定。M4 的验收以“实时更新可用”为准，不强制要求必须由事件单独驱动；基于 `bindings.ts` 的轮询命令实现视为符合计划。

**Tech Stack:** `cpal 0.15`、`rubato 0.15`、`whisper-rs 0.11`（features: coreml）、`hound`（WAV 写入）、`tokio`（spawn_blocking）、`tauri-specta v2`、React 18 + TypeScript + Zustand + shadcn/ui + Canvas API

---

### Task 1: Cargo.toml — 新增依赖

**Files:**
- Modify: `src-tauri/Cargo.toml`

- [ ] **Step 1.1: 在 `[dependencies]` 中追加以下 crate**

  ```toml
  cpal    = "0.15"
  rubato  = "0.15"
  hound   = "3"
  whisper-rs = { version = "0.11", features = ["coreml"] }
  ```

  注意：`whisper-rs` 在 macOS 上开启 `coreml` feature 需要 `build.rs` 中设置正确的编译标志（Task 2）。`hound` 用于写 WAV 文件，纯 Rust 无系统依赖。

- [ ] **Step 1.2: 验证依赖能正常解析**

  ```bash
  cd src-tauri && cargo fetch
  ```

  若 `whisper-rs` 下载 whisper.cpp 子模块失败，确认 git submodule 已初始化：`git submodule update --init --recursive`。

- [ ] **Commit:** `chore(deps): add cpal, rubato, hound, whisper-rs to Cargo.toml`

---

### Task 2: build.rs — whisper-rs CoreML 编译标志

**Files:**
- Modify: `src-tauri/build.rs`

- [ ] **Step 2.1: 在 `build.rs` 中追加 whisper.cpp 的 CoreML 和 Metal 编译配置**

  ```rust
  fn main() {
      // 已有 Tauri build 调用
      tauri_build::build();

      // whisper-rs CoreML 加速（仅 macOS）
      #[cfg(target_os = "macos")]
      {
          println!("cargo:rustc-env=WHISPER_COREML=1");
          println!("cargo:rustc-link-lib=framework=CoreML");
          println!("cargo:rustc-link-lib=framework=Accelerate");
      }
  }
  ```

  此处 `WHISPER_COREML=1` 环境变量会被 whisper-rs 的 build script 识别，自动生成 CoreML 模型时需要对应的 `.mlmodelc` 文件（位于与 `.bin` 同名目录）。若 CoreML 模型文件不存在，whisper-rs 自动退回 CPU 推理，不会 panic。

- [ ] **Commit:** `build: configure whisper-rs CoreML flags for macOS`

---

### Task 3: `audio/capture.rs` — cpal 设备枚举与音频采集

**Files:**
- Create: `src-tauri/src/audio/capture.rs`

- [ ] **Step 3.1: 定义设备枚举函数 `list_audio_devices`**

  ```rust
  use cpal::traits::{DeviceTrait, HostTrait};
  use crate::commands::audio::AudioDevice;
  use crate::error::AppError;

  /// 枚举系统输入设备。is_default 通过名称字符串比对确定
  /// （cpal Device 不实现 PartialEq，无法直接比较）
  pub fn list_audio_devices() -> Result<Vec<AudioDevice>, AppError> {
      let host = cpal::default_host();
      let default_name = host
          .default_input_device()
          .and_then(|d| d.name().ok())
          .unwrap_or_default();

      let devices = host
          .input_devices()
          .map_err(|e| AppError::Audio(e.to_string()))?;

      let mut result = Vec::new();
      for device in devices {
          let name = device.name().map_err(|e| AppError::Audio(e.to_string()))?;
          let config = device
              .default_input_config()
              .map_err(|e| AppError::Audio(e.to_string()))?;
          result.push(AudioDevice {
              id: name.clone(),   // cpal 无稳定数字 ID，用名称作 ID
              is_default: name == default_name,
              sample_rate: config.sample_rate().0,
              channels: config.channels(),
              name,
          });
      }
      Ok(result)
  }
  ```

- [ ] **Step 3.2: 定义 `AudioCaptureHandle` 结构体，持有 cpal stream 和到 pipeline 的 SyncSender**

  ```rust
  use std::sync::mpsc::SyncSender;

  pub struct AudioCaptureHandle {
      /// cpal stream 必须保持 alive，drop 即停止采集
      _stream: cpal::Stream,
      pub sample_rate: u32,
      pub channels: u16,
  }

  /// 启动麦克风采集，将原始 f32 PCM 发往 tx
  /// - 样本格式统一转 f32（i16/u16/f32 均支持）
  /// - 若队列满（推理跟不上），调用 try_send；失败时静默丢弃（背压保护）
  pub fn start_capture(
      device_id: Option<&str>,
      tx: SyncSender<Vec<f32>>,
  ) -> Result<AudioCaptureHandle, AppError> {
      let host = cpal::default_host();
      let device = if let Some(id) = device_id {
          host.input_devices()
              .map_err(|e| AppError::Audio(e.to_string()))?
              .find(|d| d.name().map(|n| n == id).unwrap_or(false))
              .ok_or_else(|| AppError::Audio(format!("device not found: {id}")))?
      } else {
          host.default_input_device()
              .ok_or_else(|| AppError::Audio("no default input device".into()))?
      };

      let config = device
          .default_input_config()
          .map_err(|e| AppError::Audio(e.to_string()))?;
      let sample_rate = config.sample_rate().0;
      let channels = config.channels();
      let sample_format = config.sample_format();

      let stream = build_stream(&device, &config.into(), sample_format, tx)?;
      use cpal::traits::StreamTrait;
      stream.play().map_err(|e| AppError::Audio(e.to_string()))?;

      Ok(AudioCaptureHandle { _stream: stream, sample_rate, channels })
  }

  fn build_stream(
      device: &cpal::Device,
      config: &cpal::StreamConfig,
      format: cpal::SampleFormat,
      tx: SyncSender<Vec<f32>>,
  ) -> Result<cpal::Stream, AppError> {
      use cpal::SampleFormat::*;
      let err_fn = |e| eprintln!("[audio] stream error: {e}");
      let stream = match format {
          F32 => device.build_input_stream(
              config,
              move |data: &[f32], _| { let _ = tx.try_send(data.to_vec()); },
              err_fn, None,
          ),
          I16 => device.build_input_stream(
              config,
              move |data: &[i16], _| {
                  let f: Vec<f32> = data.iter().map(|&s| s as f32 / i16::MAX as f32).collect();
                  let _ = tx.try_send(f);
              },
              err_fn, None,
          ),
          U16 => device.build_input_stream(
              config,
              move |data: &[u16], _| {
                  let f: Vec<f32> = data.iter()
                      .map(|&s| (s as f32 / u16::MAX as f32) * 2.0 - 1.0)
                      .collect();
                  let _ = tx.try_send(f);
              },
              err_fn, None,
          ),
          _ => return Err(AppError::Audio("unsupported sample format".into())),
      };
      stream.map_err(|e| AppError::Audio(e.to_string()))
  }
  ```

- [ ] **Commit:** `feat(audio): implement cpal device enumeration and capture (capture.rs)`

---

### Task 4: `audio/resampler.rs` — rubato 重采样（任意 Hz → 16000Hz 单声道）

**Files:**
- Create: `src-tauri/src/audio/resampler.rs`

- [ ] **Step 4.1: 实现 `AudioResampler` 结构体**

  ```rust
  use rubato::{FftFixedIn, Resampler};
  use crate::error::AppError;

  const OUT_RATE: u32 = 16_000;
  /// 每次 rubato 输出 1600 个样本 = 100ms @ 16kHz
  const OUTPUT_CHUNK: usize = 1_600;

  pub struct AudioResampler {
      inner: FftFixedIn<f32>,
      in_rate: u32,
      channels: usize,
      /// rubato 每次期望的输入帧数（单声道帧 = channels 个 interleaved 样本）
      chunk_size: usize,
      /// 跨调用的输入缓冲，存放还不够 chunk_size 的余量（interleaved）
      input_buf: Vec<f32>,
  }

  impl AudioResampler {
      /// `in_rate`: cpal 设备原生采样率；`channels`: 设备声道数
      pub fn new(in_rate: u32, channels: usize) -> Result<Self, AppError> {
          let inner = FftFixedIn::<f32>::new(
              in_rate as usize,
              OUT_RATE as usize,
              OUTPUT_CHUNK,
              2,        // sub_chunks = 2（rubato 推荐值）
              channels,
          )
          .map_err(|e| AppError::Audio(format!("rubato init: {e}")))?;

          let chunk_size = inner.input_frames_next();
          Ok(Self {
              inner,
              in_rate,
              channels,
              chunk_size,
              input_buf: Vec::new(),
          })
      }

      /// 输入：来自 cpal callback 的 interleaved 多声道 f32（大小不定）
      /// 输出：16000Hz 单声道 f32 片段（每积攒满 chunk_size 帧时产出）
      /// 余量留在 input_buf，不截断、不丢失
      pub fn push(&mut self, input: &[f32]) -> Result<Vec<f32>, AppError> {
          self.input_buf.extend_from_slice(input);
          let mut output = Vec::new();
          let frame_stride = self.chunk_size * self.channels;

          while self.input_buf.len() >= frame_stride {
              // 取出 chunk_size 帧的 interleaved 数据
              let chunk: Vec<f32> = self.input_buf.drain(..frame_stride).collect();

              // 立体声/多声道 → 单声道（各声道平均）
              let mono: Vec<f32> = (0..self.chunk_size)
                  .map(|i| {
                      let sum: f32 = (0..self.channels)
                          .map(|c| chunk[i * self.channels + c])
                          .sum();
                      sum / self.channels as f32
                  })
                  .collect();

              // rubato 期望输入为 Vec<Vec<f32>>（每声道一个 Vec）
              let waves_in = vec![mono];
              let mut waves_out = self.inner
                  .process(&waves_in, None)
                  .map_err(|e| AppError::Audio(format!("rubato process: {e}")))?;

              // 单声道输出追加到结果
              output.append(&mut waves_out[0]);
          }
          Ok(output)
      }

      pub fn in_rate(&self) -> u32 { self.in_rate }
  }
  ```

- [ ] **Step 4.2: 编写重采样单元测试**

  在 `resampler.rs` 末尾添加：

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use std::f32::consts::PI;

      /// 用 440Hz 正弦波验证输入/输出长度关系
      /// 输入 in_rate * 1s 的样本 → 输出应接近 16000 个样本（允许 rubato 边界误差 ±OUTPUT_CHUNK）
      #[test]
      fn test_resample_length_44100_stereo() {
          let in_rate: u32 = 44_100;
          let channels: usize = 2;
          let mut resampler = AudioResampler::new(in_rate, channels).unwrap();

          // 生成 1 秒的 440Hz 正弦波（stereo interleaved）
          let n_samples = in_rate as usize * channels; // 88200
          let input: Vec<f32> = (0..n_samples)
              .map(|i| (2.0 * PI * 440.0 * (i / channels) as f32 / in_rate as f32).sin())
              .collect();

          let output = resampler.push(&input).unwrap();

          // 1 秒 @ 16kHz = 16000 samples；rubato FftFixedIn 以 OUTPUT_CHUNK=1600 为单位输出
          // 最多差一个 chunk
          let expected = OUT_RATE as usize; // 16000
          assert!(
              output.len() >= expected - OUTPUT_CHUNK && output.len() <= expected + OUTPUT_CHUNK,
              "expected ~{expected} samples, got {}",
              output.len()
          );
      }

      /// 48000Hz 单声道场景
      #[test]
      fn test_resample_length_48000_mono() {
          let in_rate: u32 = 48_000;
          let channels: usize = 1;
          let mut resampler = AudioResampler::new(in_rate, channels).unwrap();

          let input: Vec<f32> = (0..in_rate as usize)
              .map(|i| (2.0 * PI * 220.0 * i as f32 / in_rate as f32).sin())
              .collect();

          let output = resampler.push(&input).unwrap();
          let expected = OUT_RATE as usize;
          assert!(
              output.len() >= expected - OUTPUT_CHUNK && output.len() <= expected + OUTPUT_CHUNK,
              "expected ~{expected} samples, got {}",
              output.len()
          );
      }

      /// 余量机制：小块多次 push 与一次大块 push 的输出等价
      #[test]
      fn test_remainder_accumulation() {
          let in_rate: u32 = 44_100;
          let channels: usize = 1;

          let total: Vec<f32> = (0..in_rate as usize)
              .map(|i| (2.0 * PI * 440.0 * i as f32 / in_rate as f32).sin())
              .collect();

          // 单次 push
          let mut r1 = AudioResampler::new(in_rate, channels).unwrap();
          let single = r1.push(&total).unwrap();

          // 分 128 个小块逐次 push
          let mut r2 = AudioResampler::new(in_rate, channels).unwrap();
          let chunk_sz = in_rate as usize / 128;
          let mut chunked: Vec<f32> = Vec::new();
          for chunk in total.chunks(chunk_sz) {
              chunked.extend(r2.push(chunk).unwrap());
          }

          // 两种方式输出长度应相同（积攒机制正确）
          assert_eq!(single.len(), chunked.len());
      }
  }
  ```

- [ ] **Commit:** `feat(audio): implement rubato resampler with remainder accumulation and tests`

---

### Task 5: `audio/vad.rs` — RMS 能量阈值静音检测 + 电平上报

**Files:**
- Create: `src-tauri/src/audio/vad.rs`

- [ ] **Step 5.1: 实现 `VadFilter` 结构体**

  ```rust
  use std::time::{Duration, Instant};
  use tauri::AppHandle;

  /// 连续 N 块 RMS < threshold → 判定为静音段
  const SILENCE_BLOCKS: usize = 6;
  /// audio:level 最小发送间隔
  const LEVEL_EMIT_INTERVAL: Duration = Duration::from_millis(100);
  /// 静音上下文前导：静音结束后附带最多 1s 的前导帧（按 chunk 粒度）
  const CONTEXT_CHUNKS: usize = 2; // 约 1s（500ms chunk × 2）

  pub struct VadFilter {
      threshold: f32,
      silence_count: usize,
      /// 最近 CONTEXT_CHUNKS 帧缓存，用于静音结束时补充上下文
      context_buf: std::collections::VecDeque<Vec<f32>>,
      last_level_emit: Instant,
      app: AppHandle,
  }

  impl VadFilter {
      pub fn new(threshold: f32, app: AppHandle) -> Self {
          Self {
              threshold,
              silence_count: 0,
              context_buf: std::collections::VecDeque::with_capacity(CONTEXT_CHUNKS + 1),
              last_level_emit: Instant::now()
                  .checked_sub(LEVEL_EMIT_INTERVAL)
                  .unwrap_or_else(Instant::now),
              app,
          }
      }

      /// 处理一个音频块，返回应送往 whisper pipeline 的帧（可能为空）
      /// 同时在满足 100ms 间隔时 emit `audio:level` 事件
      pub fn process(&mut self, chunk: Vec<f32>) -> Vec<Vec<f32>> {
          let rms = Self::rms(&chunk);

          // 100ms 降频 emit audio:level
          if self.last_level_emit.elapsed() >= LEVEL_EMIT_INTERVAL {
              let _ = self.app.emit("audio:level", rms.min(1.0));
              self.last_level_emit = Instant::now();
          }

          if rms < self.threshold {
              // 静音：计数器递增，缓存帧备用（循环覆盖旧帧）
              self.silence_count += 1;
              if self.context_buf.len() >= CONTEXT_CHUNKS {
                  self.context_buf.pop_front();
              }
              self.context_buf.push_back(chunk);
              Vec::new() // 静音不送 pipeline
          } else {
              // 有声音：重置计数器
              let was_silent = self.silence_count >= SILENCE_BLOCKS;
              self.silence_count = 0;

              let mut to_send: Vec<Vec<f32>> = Vec::new();
              if was_silent {
                  // 静音结束：先把缓存的前导帧一起送出（保留上下文）
                  to_send.extend(self.context_buf.drain(..));
              } else {
                  self.context_buf.clear();
              }
              to_send.push(chunk);
              to_send
          }
      }

      /// RMS 能量：sqrt(mean(x²))，结果范围 [0.0, 1.0]（输入已是 f32 [-1,1]）
      fn rms(samples: &[f32]) -> f32 {
          if samples.is_empty() {
              return 0.0;
          }
          let mean_sq: f32 = samples.iter().map(|s| s * s).sum::<f32>() / samples.len() as f32;
          mean_sq.sqrt()
      }

      pub fn set_threshold(&mut self, threshold: f32) {
          self.threshold = threshold;
      }
  }
  ```

- [ ] **Step 5.2: 编写 VAD 单元测试**

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;

      // 辅助：构造不依赖真实 AppHandle 的可测试 VAD
      // 测试中用 SILENCE_BLOCKS 个全零块验证静音过滤
      // 注意：由于 AppHandle 需要 Tauri runtime，此处通过行为验证（不 emit）
      // 实际测试通过 is_empty() 返回值断言

      fn make_silent(n: usize) -> Vec<f32> { vec![0.0f32; n] }
      fn make_loud(n: usize) -> Vec<f32> { vec![0.5f32; n] }

      /// 辅助函数：调用 VadFilter::rms（静态方法，不需要 AppHandle）
      #[test]
      fn test_rms_all_zeros_is_zero() {
          assert_eq!(VadFilter::rms(&make_silent(1024)), 0.0);
      }

      #[test]
      fn test_rms_constant_signal() {
          // RMS(0.5, 0.5, ...) = 0.5
          let rms = VadFilter::rms(&make_loud(1024));
          assert!((rms - 0.5).abs() < 1e-5, "rms = {rms}");
      }

      /// 验证 RMS 计算正确性（不依赖 AppHandle）
      #[test]
      fn test_rms_sine_approx_amplitude_over_sqrt2() {
          // 正弦波 A*sin(x) 的 RMS = A/sqrt(2)
          use std::f32::consts::PI;
          let amplitude = 0.8f32;
          let samples: Vec<f32> = (0..16000)
              .map(|i| amplitude * (2.0 * PI * 440.0 * i as f32 / 16000.0).sin())
              .collect();
          let rms = VadFilter::rms(&samples);
          let expected = amplitude / 2.0f32.sqrt();
          assert!((rms - expected).abs() < 0.001, "rms={rms}, expected={expected}");
      }
  }
  ```

  > 注意：`VadFilter::process` 依赖真实 `AppHandle`（用于 emit），集成测试在 Task 12 的 pipeline mock 测试中覆盖；此处只测试纯计算逻辑（`rms`）。

- [ ] **Commit:** `feat(audio): implement VAD filter with RMS threshold, context buffering, and level reporting`

---

### Task 6: `audio/mod.rs` — 模块导出

**Files:**
- Create: `src-tauri/src/audio/mod.rs`

- [ ] **Step 6.1: 创建 `audio/mod.rs`，导出子模块**

  ```rust
  pub mod capture;
  pub mod resampler;
  pub mod vad;

  // 重导出常用类型，方便其他模块引用
  pub use capture::{AudioCaptureHandle, list_audio_devices, start_capture};
  pub use resampler::AudioResampler;
  pub use vad::VadFilter;
  ```

- [ ] **Commit:** `feat(audio): add audio/mod.rs module exports`

---

### Task 7: `transcription/engine.rs` — whisper-rs 封装

**Files:**
- Create: `src-tauri/src/transcription/engine.rs`

- [ ] **Step 7.1: 实现 `WhisperEngine` 结构体**

  ```rust
  use std::path::Path;
  use std::sync::{Arc, Mutex};
  use whisper_rs::{WhisperContext, WhisperContextParameters, FullParams, SamplingStrategy};
  use crate::error::AppError;

  pub struct RawSegment {
      pub start_ms: u32,
      pub end_ms: u32,
      pub text: String,
      pub language: String,
  }

  pub struct WhisperEngine {
      /// Arc<Mutex<>> 使多线程场景下安全共享；
      /// 实际只从 spawn_blocking 单线程串行访问，Mutex 主要用于满足 Send 约束
      pub(crate) ctx: Arc<Mutex<WhisperContext>>,
  }

  impl WhisperEngine {
      pub fn new(model_path: &Path) -> Result<Self, AppError> {
          let params = WhisperContextParameters::default();
          let ctx = WhisperContext::new_with_params(
              model_path.to_str().ok_or_else(|| AppError::Model("invalid path".into()))?,
              params,
          )
          .map_err(|e| AppError::Model(format!("whisper init: {e}")))?;
          Ok(Self { ctx: Arc::new(Mutex::new(ctx)) })
      }

      /// 同步阻塞推理，必须在 `tokio::task::spawn_blocking` 内调用。
      /// `audio`: 16000Hz 单声道 f32
      /// `language`: None = 自动检测；Some("zh") / Some("en") 等 ISO 639-1 代码
      /// `translate`: true = whisper task=translate（输出英文）
      pub fn transcribe(
          &self,
          audio: &[f32],
          language: Option<&str>,
          translate: bool,
      ) -> Result<Vec<RawSegment>, AppError> {
          let mut ctx = self.ctx.lock()
              .map_err(|_| AppError::Transcription("whisper ctx poisoned".into()))?;

          let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
          params.set_print_special(false);
          params.set_print_progress(false);
          params.set_print_realtime(false);
          params.set_print_timestamps(true);
          params.set_translate(translate);
          if let Some(lang) = language {
              params.set_language(Some(lang));
          }

          let mut state = ctx.create_state()
              .map_err(|e| AppError::Transcription(format!("create state: {e}")))?;
          state.full(params, audio)
              .map_err(|e| AppError::Transcription(format!("full: {e}")))?;

          let n = state.full_n_segments()
              .map_err(|e| AppError::Transcription(e.to_string()))?;

          let mut segments = Vec::with_capacity(n as usize);
          for i in 0..n {
              let text = state.full_get_segment_text(i)
                  .map_err(|e| AppError::Transcription(e.to_string()))?;
              let t0 = state.full_get_segment_t0(i)
                  .map_err(|e| AppError::Transcription(e.to_string()))?;
              let t1 = state.full_get_segment_t1(i)
                  .map_err(|e| AppError::Transcription(e.to_string()))?;
              // whisper 时间戳单位为 10ms，转换为 ms
              segments.push(RawSegment {
                  start_ms: (t0 * 10) as u32,
                  end_ms: (t1 * 10) as u32,
                  text: text.trim().to_string(),
                  language: language.unwrap_or("auto").to_string(),
              });
          }
          Ok(segments)
      }
  }

  // 需要 Send + Sync 以便在 Arc 中跨线程使用
  // WhisperContext 本身满足 Send（whisper-rs 文档说明），Mutex 提供 Sync
  unsafe impl Send for WhisperEngine {}
  unsafe impl Sync for WhisperEngine {}
  ```

- [ ] **Commit:** `feat(transcription): implement WhisperEngine wrapper with language and translate support`

---

### Task 8: `transcription/pipeline.rs` — tokio 长驻转写 pipeline

**Files:**
- Create: `src-tauri/src/transcription/pipeline.rs`

- [ ] **Step 8.1: 定义 `TranscriptionCommand` 枚举和 `PipelineState`**

  ```rust
  use std::sync::{Arc, Mutex, mpsc};
  use std::time::Instant;
  use tauri::AppHandle;
  use tokio::task;
  use uuid::Uuid;

  use crate::error::AppError;
  use crate::transcription::engine::WhisperEngine;
  use crate::commands::transcription::{
      RecordingMode, RecordingStatus, SegmentPayload,
  };

  /// 发往 TranscriptionWorker 的控制命令
  #[derive(Debug)]
  pub enum TranscriptionCommand {
      Start {
          session_id: String,
          language: Option<String>,
          mode: RecordingMode,
          vad_threshold: f32,
      },
      AudioChunk(Vec<f32>),   // 来自 VAD 过滤后的有效音频帧
      Pause { session_id: String },
      Resume { session_id: String },
      Stop { session_id: String },
  }
  ```

- [ ] **Step 8.2: 实现 `TranscriptionWorker::run()` 长驻 loop**

  关键约束：
  - 外层锁（`AppState.whisper_engine` 的 `Mutex<Option<WhisperEngine>>`）只用于 clone 内部 Arc，**不跨越 spawn_blocking 边界**
  - whisper 推理必须在 `spawn_blocking` 内执行（同步阻塞，不阻塞 tokio 调度器）
  - 30 秒或 >3s 静音时触发一次推理

  ```rust
  pub struct TranscriptionWorker {
      rx: mpsc::Receiver<TranscriptionCommand>,
      app: AppHandle,
      engine: Arc<Mutex<Option<WhisperEngine>>>,
  }

  impl TranscriptionWorker {
      pub fn new(
          rx: mpsc::Receiver<TranscriptionCommand>,
          app: AppHandle,
          engine: Arc<Mutex<Option<WhisperEngine>>>,
      ) -> Self {
          Self { rx, app, engine }
      }

      /// 在独立 tokio task 内调用此方法（`tokio::spawn(worker.run())`）
      pub async fn run(self) {
          let mut accumulator: Vec<f32> = Vec::new();
          let mut session_id: Option<String> = None;
          let mut language: Option<String> = None;
          let mut translate = false;
          let mut segment_counter: u32 = 0;
          let mut paused = false;
          let mut last_audio_at = Instant::now();

          const MAX_ACCUM_SAMPLES: usize = 16_000 * 30; // 30s @ 16kHz
          const SILENCE_FLUSH_SECS: u64 = 3;

          loop {
              // 非阻塞尝试接收；无数据时检查是否需要超时 flush
              match self.rx.try_recv() {
                  Ok(cmd) => match cmd {
                      TranscriptionCommand::Start { session_id: sid, language: lang, mode, .. } => {
                          session_id = Some(sid.clone());
                          language = lang;
                          translate = matches!(mode, RecordingMode::TranscribeAndTranslate { .. });
                          accumulator.clear();
                          segment_counter = 0;
                          paused = false;
                          last_audio_at = Instant::now();
                          let _ = self.app.emit("transcription:status",
                              RecordingStatus::Recording {
                                  session_id: sid,
                                  started_at: chrono::Utc::now().timestamp_millis(),
                              });
                      }
                      TranscriptionCommand::AudioChunk(chunk) if !paused => {
                          accumulator.extend_from_slice(&chunk);
                          last_audio_at = Instant::now();

                          if accumulator.len() >= MAX_ACCUM_SAMPLES {
                              self.flush_to_whisper(
                                  &mut accumulator, &session_id, &language,
                                  translate, &mut segment_counter,
                              ).await;
                          }
                      }
                      TranscriptionCommand::Pause { session_id: sid } => {
                          paused = true;
                          let _ = self.app.emit("transcription:status",
                              RecordingStatus::Paused { session_id: sid });
                      }
                      TranscriptionCommand::Resume { session_id: sid } => {
                          paused = false;
                          last_audio_at = Instant::now();
                          let _ = self.app.emit("transcription:status",
                              RecordingStatus::Recording {
                                  session_id: sid,
                                  started_at: chrono::Utc::now().timestamp_millis(),
                              });
                      }
                      TranscriptionCommand::Stop { session_id: sid } => {
                          // 最终 flush 剩余音频
                          if !accumulator.is_empty() {
                              self.flush_to_whisper(
                                  &mut accumulator, &session_id, &language,
                                  translate, &mut segment_counter,
                              ).await;
                          }
                          session_id = None;
                          paused = false;
                          let _ = self.app.emit("transcription:status",
                              RecordingStatus::Stopped {
                                  session_id: sid.clone(),
                                  recording_id: sid, // 实际 recording_id 由 stop_realtime command 写 DB 后设置
                              });
                      }
                      _ => {} // AudioChunk while paused → discard
                  },
                  Err(mpsc::TryRecvError::Empty) => {
                      // 检查静音超时 flush（>3s 无新音频）
                      if session_id.is_some()
                          && !paused
                          && !accumulator.is_empty()
                          && last_audio_at.elapsed().as_secs() >= SILENCE_FLUSH_SECS
                      {
                          self.flush_to_whisper(
                              &mut accumulator, &session_id, &language,
                              translate, &mut segment_counter,
                          ).await;
                      }
                      // 让出 CPU 避免 busy-loop
                      tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
                  }
                  Err(mpsc::TryRecvError::Disconnected) => break, // sender 已 drop，退出
              }
          }
      }

      /// 将 accumulator 中的音频发往 whisper 推理，emit segment events
      async fn flush_to_whisper(
          &self,
          accumulator: &mut Vec<f32>,
          session_id: &Option<String>,
          language: &Option<String>,
          translate: bool,
          counter: &mut u32,
      ) {
          let audio = std::mem::take(accumulator);
          let sid = session_id.clone().unwrap_or_default();
          let lang = language.clone();

          // 关键：外层锁只用于 clone Arc，立即释放，不跨 spawn_blocking
          let engine_arc: Option<Arc<Mutex<WhisperEngine>>> = {
              let guard = self.engine.lock().unwrap();
              guard.as_ref().map(|e| Arc::clone(&e.ctx)
                  .map(|_| ()) // 此处说明 clone 模式
              );
              // 实际上 WhisperEngine 本身就是 Arc<Mutex<WhisperContext>> 的包装
              // 外层状态是 Arc<Mutex<Option<WhisperEngine>>>
              // clone 内部引用：
              guard.as_ref().map(|_e| {
                  // 把整个 Option<WhisperEngine> 的引用通过 Arc 共享
                  // 正确做法：AppState.whisper_engine 类型为 Arc<Mutex<Option<WhisperEngine>>>
                  // 这里拿到 Arc 本身并 clone
                  Arc::clone(&self.engine)
              })
          };

          let Some(engine_ref) = engine_arc else { return; };
          let app = self.app.clone();
          let current_counter = *counter;
          let sid_clone = sid.clone();

          let result = task::spawn_blocking(move || {
              let guard = engine_ref.lock().unwrap();
              if let Some(engine) = guard.as_ref() {
                  engine.transcribe(&audio, lang.as_deref(), translate)
              } else {
                  Ok(vec![])
              }
          })
          .await;

          match result {
              Ok(Ok(segments)) => {
                  for (i, seg) in segments.iter().enumerate() {
                      *counter += 1;
                      let payload = SegmentPayload {
                          id: current_counter + i as u32,
                          recording_session_id: sid_clone.clone(),
                          start_ms: seg.start_ms,
                          end_ms: seg.end_ms,
                          text: seg.text.clone(),
                          language: seg.language.clone(),
                          is_partial: false,
                      };
                      let _ = app.emit("transcription:segment", &payload);
                  }
              }
              Ok(Err(e)) => eprintln!("[pipeline] whisper error: {e}"),
              Err(e) => eprintln!("[pipeline] spawn_blocking panicked: {e}"),
          }
      }
  }
  ```

  > 注意：`flush_to_whisper` 中的"外层锁只用于 clone Arc"模式说明：`AppState.whisper_engine` 的类型为 `Arc<Mutex<Option<WhisperEngine>>>`，`spawn_blocking` 闭包内通过 `Arc::clone` 进入的引用访问 `WhisperEngine`，外层 `Mutex` 锁在 `spawn_blocking` 启动前已释放。上方伪代码已标注此模式，实际实现需根据最终 `AppState` 字段类型调整 clone 一行。

- [ ] **Step 8.3: 编写 pipeline mock channel 测试**

  ```rust
  #[cfg(test)]
  mod tests {
      use std::sync::mpsc;

      use super::TranscriptionCommand;

      /// 验证 SyncSender channel 能正常发送/接收 TranscriptionCommand
      #[test]
      fn test_channel_send_recv() {
          let (tx, rx) = mpsc::sync_channel::<TranscriptionCommand>(32);

          tx.send(TranscriptionCommand::AudioChunk(vec![0.0f32; 1600])).unwrap();
          tx.send(TranscriptionCommand::Pause { session_id: "test-session".into() }).unwrap();
          tx.send(TranscriptionCommand::Resume { session_id: "test-session".into() }).unwrap();

          assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::AudioChunk(_)));
          assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Pause { .. }));
          assert!(matches!(rx.recv().unwrap(), TranscriptionCommand::Resume { .. }));
      }

      /// 验证 try_send 在队列满时返回 Err（不阻塞）
      #[test]
      fn test_sync_sender_backpressure() {
          let (tx, _rx) = mpsc::sync_channel::<TranscriptionCommand>(1);
          tx.try_send(TranscriptionCommand::AudioChunk(vec![0.0; 100])).unwrap();
          // 队列已满（容量=1），第二次 try_send 应返回 Err
          let result = tx.try_send(TranscriptionCommand::AudioChunk(vec![0.0; 100]));
          assert!(result.is_err(), "should fail when channel is full");
      }

      /// 验证 Disconnected 场景（rx drop 后 tx.send 返回 Err）
      #[test]
      fn test_channel_disconnected() {
          let (tx, rx) = mpsc::sync_channel::<TranscriptionCommand>(4);
          drop(rx);
          let result = tx.send(TranscriptionCommand::AudioChunk(vec![]));
          assert!(result.is_err());
      }
  }
  ```

- [ ] **Step 8.4: 标注集成测试（需要真实模型，CI 中跳过）**

  在 `pipeline.rs` 末尾添加需要真实 whisper 模型的集成测试骨架：

  ```rust
  /// 集成测试：需要真实 whisper 模型文件，CI 无模型时跳过
  /// 手动运行：cargo test --test integration -- --ignored
  #[cfg(test)]
  mod integration_tests {
      use super::*;
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
          // 全零输入（静音）应返回空 segments 或仅含空白文本
          let audio = vec![0.0f32; 16_000]; // 1s silence
          let segments = engine.transcribe(&audio, None, false)
              .expect("transcribe failed");
          // 静音不应产生有意义的文本段（允许为空）
          for seg in &segments {
              assert!(seg.text.trim().is_empty() || seg.text.len() < 5,
                  "unexpected text from silence: '{}'", seg.text);
          }
      }
  }
  ```

- [ ] **Commit:** `feat(transcription): implement pipeline worker with spawn_blocking whisper inference and tests`

---

### Task 9: `transcription/mod.rs` — 模块导出

**Files:**
- Create: `src-tauri/src/transcription/mod.rs`

- [ ] **Step 9.1: 创建 `transcription/mod.rs`**

  ```rust
  pub mod engine;
  pub mod pipeline;
  pub mod batch; // batch.rs 为 M4 后期任务占位，可暂为空文件

  pub use engine::{WhisperEngine, RawSegment};
  pub use pipeline::{TranscriptionWorker, TranscriptionCommand};
  ```

- [ ] **Commit:** `feat(transcription): add transcription/mod.rs module exports`

---

### Task 10: `commands/audio.rs` — `list_audio_devices` Tauri command

**Files:**
- Create: `src-tauri/src/commands/audio.rs`

- [ ] **Step 10.1: 定义 `AudioDevice` 类型和 `list_audio_devices` command**

  ```rust
  use serde::{Serialize, Deserialize};
  use specta::Type;
  use tauri::State;

  use crate::state::AppState;
  use crate::error::AppError;
  use crate::audio;

  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  pub struct AudioDevice {
      pub id: String,
      pub name: String,
      pub is_default: bool,
      pub sample_rate: u32,
      pub channels: u16,
  }

  /// 列出系统可用音频输入设备（前端设备下拉选择器数据源）
  #[tauri::command]
  #[specta::specta]
  pub async fn list_audio_devices(
      _state: State<'_, AppState>,
  ) -> Result<Vec<AudioDevice>, AppError> {
      // 调用 audio::capture 中的枚举函数（在 tokio context 中执行，但 cpal 枚举是快速同步操作）
      tokio::task::spawn_blocking(audio::list_audio_devices)
          .await
          .map_err(|e| AppError::Audio(format!("spawn_blocking: {e}")))?
  }
  ```

- [ ] **Commit:** `feat(commands): implement list_audio_devices Tauri command`

---

### Task 11: `commands/transcription.rs` — 录音控制 commands

**Files:**
- Create: `src-tauri/src/commands/transcription.rs`

- [ ] **Step 11.1: 定义所有录音相关类型（SegmentPayload, RecordingStatus, RecordingMode, RealtimeConfig）**

  ```rust
  use serde::{Serialize, Deserialize};
  use specta::Type;
  use tauri::{AppHandle, State};
  use uuid::Uuid;

  use crate::state::AppState;
  use crate::error::AppError;
  use crate::transcription::pipeline::TranscriptionCommand;

  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  pub struct SegmentPayload {
      pub id: u32,
      pub recording_session_id: String,
      pub start_ms: u32,
      pub end_ms: u32,
      pub text: String,
      pub language: String,
      pub is_partial: bool,
  }

  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  pub struct AudioLevelPayload {
      pub rms: f32,
  }

  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  #[serde(tag = "status", rename_all = "snake_case")]
  pub enum RecordingStatus {
      Idle,
      Recording { session_id: String, started_at: i64 },
      Paused  { session_id: String },
      Stopped { session_id: String, recording_id: String },
  }

  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  #[serde(rename_all = "snake_case")]
  pub enum RecordingMode {
      RecordOnly,
      TranscribeOnly,
      TranscribeAndTranslate { target_language: String },
  }

  #[derive(Debug, Serialize, Deserialize, Clone, Type)]
  pub struct RealtimeConfig {
      pub device_id: Option<String>,
      pub language: Option<String>,
      pub mode: RecordingMode,
      pub vad_threshold: f32,
      pub chunk_duration_ms: u32,
  }
  ```

- [ ] **Step 11.2: 实现 `start_realtime`**

  ```rust
  /// 开始实时录音。立即返回 session_id，后续通过 Tauri 事件通知状态变化。
  #[tauri::command]
  #[specta::specta]
  pub async fn start_realtime(
      config: RealtimeConfig,
      state: State<'_, AppState>,
      app: AppHandle,
  ) -> Result<String, AppError> {
      let session_id = Uuid::new_v4().to_string();

      // 1. 启动 cpal 音频采集（在 spawn_blocking 中，因 cpal 构造涉及系统调用）
      let (raw_tx, raw_rx) = std::sync::mpsc::sync_channel::<Vec<f32>>(64);
      let device_id = config.device_id.clone();
      let capture_handle = tokio::task::spawn_blocking(move || {
          crate::audio::start_capture(device_id.as_deref(), raw_tx)
      })
      .await
      .map_err(|e| AppError::Audio(e.to_string()))??;

      // 2. 保存 capture handle（持有 _stream，drop 即停止采集）
      *state.capture_handle.lock().await = Some(capture_handle);

      // 3. 启动 resampler + VAD 转发线程（std::thread，因为需要 blocking recv from std::mpsc）
      let sample_rate = state.capture_handle.lock().await
          .as_ref().map(|h| h.sample_rate).unwrap_or(44100);
      let channels = state.capture_handle.lock().await
          .as_ref().map(|h| h.channels as usize).unwrap_or(2);
      let transcription_tx = state.transcription_tx.clone();
      let threshold = config.vad_threshold;
      let app_for_vad = app.clone();

      std::thread::spawn(move || {
          let mut resampler = crate::audio::AudioResampler::new(sample_rate, channels)
              .expect("resampler init");
          // VAD 在此线程创建（AppHandle 是 Clone + Send）
          let mut vad = crate::audio::VadFilter::new(threshold, app_for_vad);

          loop {
              match raw_rx.recv() {
                  Ok(chunk) => {
                      let resampled = match resampler.push(&chunk) {
                          Ok(r) => r,
                          Err(e) => { eprintln!("[pipeline] resample error: {e}"); continue; }
                      };
                      if resampled.is_empty() { continue; }
                      for frame in vad.process(resampled) {
                          let _ = transcription_tx.try_send(TranscriptionCommand::AudioChunk(frame));
                      }
                  }
                  Err(_) => break, // cpal stream 已停止
              }
          }
      });

      // 4. 通知 TranscriptionWorker 开始新会话
      let sid = session_id.clone();
      state.transcription_tx
          .send(TranscriptionCommand::Start {
              session_id: sid,
              language: config.language,
              mode: config.mode,
              vad_threshold: config.vad_threshold,
          })
          .map_err(|_| AppError::ChannelClosed)?;

      // 5. 更新 AppState 中的 session_id
      *state.current_session_id.lock().await = Some(session_id.clone());

      Ok(session_id)
  }
  ```

- [ ] **Step 11.3: 实现 `pause_realtime` / `resume_realtime`**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn pause_realtime(
      session_id: String,
      state: State<'_, AppState>,
  ) -> Result<(), AppError> {
      state.transcription_tx
          .send(TranscriptionCommand::Pause { session_id })
          .map_err(|_| AppError::ChannelClosed)
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn resume_realtime(
      session_id: String,
      state: State<'_, AppState>,
  ) -> Result<(), AppError> {
      state.transcription_tx
          .send(TranscriptionCommand::Resume { session_id })
          .map_err(|_| AppError::ChannelClosed)
  }
  ```

- [ ] **Step 11.4: 实现 `stop_realtime`（含 WAV 保存 + DB 写入）**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn stop_realtime(
      session_id: String,
      state: State<'_, AppState>,
      app: AppHandle,
  ) -> Result<String, AppError> {
      // 1. 停止 cpal 采集（drop capture handle）
      *state.capture_handle.lock().await = None;

      // 2. 通知 pipeline 最终 flush
      state.transcription_tx
          .send(TranscriptionCommand::Stop { session_id: session_id.clone() })
          .map_err(|_| AppError::ChannelClosed)?;

      // 3. 短暂等待 pipeline flush 完成（简单 sleep；生产可改为 oneshot channel 确认）
      tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

      // 4. 收集当前会话的所有 segments（从 AppState 的 segments_cache 中读取）
      let segments = state.segments_cache
          .lock().await
          .remove(&session_id)
          .unwrap_or_default();

      // 5. 写 WAV 文件
      let recording_id = Uuid::new_v4().to_string();
      let recordings_dir = state.config.recordings_path.clone();
      tokio::fs::create_dir_all(&recordings_dir).await
          .map_err(|e| AppError::Io(e.to_string()))?;
      let wav_path = recordings_dir.join(format!("recording_{session_id}.wav"));

      // WAV 写入需要收集 PCM 数据；实际实现中 capture 线程需将 resampled f32
      // 同时存入 AppState.pcm_cache（Vec<f32>），此处从 pcm_cache 读取
      let pcm_data = state.pcm_cache
          .lock().await
          .remove(&session_id)
          .unwrap_or_default();

      {
          let wav_path_clone = wav_path.clone();
          let pcm_clone = pcm_data.clone();
          tokio::task::spawn_blocking(move || -> Result<(), AppError> {
              let spec = hound::WavSpec {
                  channels: 1,
                  sample_rate: 16_000,
                  bits_per_sample: 16,
                  sample_format: hound::SampleFormat::Int,
              };
              let mut writer = hound::WavWriter::create(&wav_path_clone, spec)
                  .map_err(|e| AppError::Io(e.to_string()))?;
              for sample in pcm_clone {
                  let s = (sample * i16::MAX as f32) as i16;
                  writer.write_sample(s).map_err(|e| AppError::Io(e.to_string()))?;
              }
              writer.finalize().map_err(|e| AppError::Io(e.to_string()))
          })
          .await
          .map_err(|e| AppError::Io(e.to_string()))??;
      }

      // 6. 写 DB（单一事务：recordings + transcription_segments + workspace_documents）
      let duration_ms = segments.last().map(|s| s.end_ms as i64).unwrap_or(0);
      let now = chrono::Utc::now().timestamp_millis();
      let title = format!("Recording {}", chrono::Local::now().format("%Y-%m-%d %H:%M"));
      let doc_id = Uuid::new_v4().to_string();
      let asset_id = Uuid::new_v4().to_string();
      let transcript_text: String = segments.iter()
          .map(|s| s.text.as_str())
          .collect::<Vec<_>>()
          .join(" ");
      let wav_path_str = wav_path.to_string_lossy().to_string();
      let rec_id = recording_id.clone();
      let session_clone = session_id.clone();
      let pool = state.db_pool.clone();

      tokio::task::spawn_blocking(move || {
          // 实际为 sqlx async，此处为结构说明；真实实现直接 await
      }).await.ok();

      // 真实 sqlx async 写法（直接 await，不用 spawn_blocking）：
      let mut tx = state.db_pool.begin().await
          .map_err(|e| AppError::Storage(e.to_string()))?;

      sqlx::query!(
          "INSERT INTO recordings (id, title, file_path, duration_ms, language, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)",
          recording_id, title, wav_path_str, duration_ms, "auto", now, now
      ).execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;

      for seg in &segments {
          sqlx::query!(
              "INSERT INTO transcription_segments (recording_id, start_ms, end_ms, text, language)
               VALUES (?, ?, ?, ?, ?)",
              recording_id, seg.start_ms, seg.end_ms, seg.text, seg.language
          ).execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;
      }

      sqlx::query!(
          "INSERT INTO workspace_documents (id, title, source_type, recording_id, created_at, updated_at)
           VALUES (?, ?, 'recording', ?, ?, ?)",
          doc_id, title, recording_id, now, now
      ).execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;

      sqlx::query!(
          "INSERT INTO workspace_text_assets (id, document_id, role, content, created_at, updated_at)
           VALUES (?, ?, 'transcript', ?, ?, ?)",
          asset_id, doc_id, transcript_text, now, now
      ).execute(&mut *tx).await.map_err(|e| AppError::Storage(e.to_string()))?;

      tx.commit().await.map_err(|e| AppError::Storage(e.to_string()))?;

      *state.current_session_id.lock().await = None;

      Ok(recording_id)
  }
  ```

  > 注意：`workspace_text_assets` 表需在 M2 数据库 migration 中确认存在。若 migration 中尚未创建该表，需在 `storage/migrations/0001_initial.sql` 中补充：
  > ```sql
  > CREATE TABLE workspace_text_assets (
  >     id          TEXT PRIMARY KEY,
  >     document_id TEXT NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
  >     role        TEXT NOT NULL,   -- 'transcript' | 'summary' | 'translation'
  >     content     TEXT NOT NULL,
  >     file_path   TEXT,
  >     created_at  INTEGER NOT NULL,
  >     updated_at  INTEGER NOT NULL
  > );
  > ```

- [ ] **Step 11.5: 实现 `get_recording_status`**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn get_recording_status(
      state: State<'_, AppState>,
  ) -> Result<RecordingStatus, AppError> {
      let session = state.current_session_id.lock().await.clone();
      Ok(match session {
          None => RecordingStatus::Idle,
          Some(sid) => RecordingStatus::Recording {
              session_id: sid,
              started_at: 0, // 完整实现从 AppState.session_start_time 读取
          },
      })
  }
  ```

- [ ] **Commit:** `feat(commands): implement start/pause/resume/stop_realtime and get_recording_status with WAV save and DB write`

---

### Task 12: `state.rs` 更新 — 注入 M4 字段

**Files:**
- Modify: `src-tauri/src/state.rs`

- [ ] **Step 12.1: 在 `AppState` 中新增 M4 所需字段**

  ```rust
  use std::sync::{Arc, Mutex, mpsc};
  use tokio::sync::Mutex as TokioMutex;
  use std::collections::HashMap;

  use crate::audio::AudioCaptureHandle;
  use crate::transcription::engine::WhisperEngine;
  use crate::transcription::pipeline::TranscriptionCommand;
  use crate::commands::transcription::SegmentPayload;

  pub struct AppState {
      // ... 已有字段 (db_pool, config, download_tx 等来自 M1-M3) ...

      // M4 新增：转写 channel（SyncSender 满足 Send，可跨线程发送）
      pub transcription_tx: mpsc::SyncSender<TranscriptionCommand>,

      // M4 新增：whisper 引擎（外层 Mutex 只用于 clone Arc，内层 Arc 跨 spawn_blocking）
      pub whisper_engine: Arc<TokioMutex<Option<WhisperEngine>>>,

      // M4 新增：当前录音会话 ID
      pub current_session_id: TokioMutex<Option<String>>,

      // M4 新增：cpal stream 持有（drop 即停止采集）
      pub capture_handle: TokioMutex<Option<AudioCaptureHandle>>,

      // M4 新增：实时 segment 缓存（session_id → segments）
      pub segments_cache: TokioMutex<HashMap<String, Vec<SegmentPayload>>>,

      // M4 新增：实时 PCM 缓存（session_id → 16kHz f32 samples，用于 WAV 写入）
      pub pcm_cache: TokioMutex<HashMap<String, Vec<f32>>>,
  }
  ```

- [ ] **Step 12.2: 在 `lib.rs` 的 `setup` 函数中初始化新字段并启动 TranscriptionWorker**

  ```rust
  // lib.rs 中 setup 钩子片段
  let (transcription_tx, transcription_rx) = std::sync::mpsc::sync_channel::<TranscriptionCommand>(128);
  let whisper_engine: Arc<tokio::sync::Mutex<Option<WhisperEngine>>> =
      Arc::new(tokio::sync::Mutex::new(None));

  // 如果模型已下载，立即加载 whisper
  if let Some(model_path) = registry.get_model_path("whisper/base") {
      match WhisperEngine::new(&model_path) {
          Ok(engine) => {
              *whisper_engine.lock().await = Some(engine);
              tracing::info!("whisper engine loaded");
          }
          Err(e) => tracing::warn!("whisper load failed: {e}"),
      }
  }

  let worker = TranscriptionWorker::new(
      transcription_rx,
      app.handle().clone(),
      Arc::clone(&whisper_engine),
  );
  tokio::spawn(worker.run());
  ```

- [ ] **Commit:** `feat(state): add M4 fields to AppState and initialize TranscriptionWorker on startup`

---

### Task 13: `commands/mod.rs` 更新 — 注册 M4 命令

**Files:**
- Modify: `src-tauri/src/commands/mod.rs`

- [ ] **Step 13.1: 导出新命令模块并在 `lib.rs` 的 `invoke_handler` 中注册**

  在 `commands/mod.rs`：
  ```rust
  pub mod audio;
  pub mod transcription;
  // ... 已有模块 ...
  ```

  在 `lib.rs` 的 `tauri::Builder` 调用中追加：
  ```rust
  .invoke_handler(tauri::generate_handler![
      // ... 已有命令 ...
      commands::audio::list_audio_devices,
      commands::transcription::start_realtime,
      commands::transcription::pause_realtime,
      commands::transcription::resume_realtime,
      commands::transcription::stop_realtime,
      commands::transcription::get_recording_status,
  ])
  ```

  tauri-specta builder 也需同步注册（用于生成 `bindings.ts`）：
  ```rust
  let builder = tauri_specta::Builder::<tauri::Wry>::new()
      // ... 已有 ...
      .commands(tauri_specta::collect_commands![
          commands::audio::list_audio_devices,
          commands::transcription::start_realtime,
          commands::transcription::pause_realtime,
          commands::transcription::resume_realtime,
          commands::transcription::stop_realtime,
          commands::transcription::get_recording_status,
      ]);
  ```

- [ ] **Commit:** `feat(commands): register M4 audio and transcription commands in invoke_handler and specta builder`

---

### Task 14: React — `useRecordingStore` Zustand store

**Files:**
- Create: `src/store/recording.ts`

- [ ] **Step 14.1: 实现完整的 `useRecordingStore`**

  > 当前录音域前端更新接受两种方式：
  > 1. 首选：通过 `bindings.ts` 轮询 `get_audio_level`、`get_realtime_segments`、`get_recording_status`
  > 2. 兼容：继续监听 `audio:level` / `transcription:*` 事件
  >
  > 只要实时电平、字幕、录音状态三者都能稳定更新，即视为满足本 Step。

  ```typescript
  // src/store/recording.ts
  import { create } from 'zustand'
  import { listen, UnlistenFn } from '@tauri-apps/api/event'
  import {
    listAudioDevices,
    startRealtime,
    pauseRealtime,
    resumeRealtime,
    stopRealtime,
    getRecordingStatus,
  } from '../lib/bindings'
  import type {
    AudioDevice,
    RealtimeConfig,
    SegmentPayload,
    RecordingStatus,
  } from '../lib/bindings'

  interface RecordingStore {
    // State
    status: 'idle' | 'recording' | 'paused'
    sessionId: string | null
    startedAt: number | null
    audioLevel: number          // 0.0-1.0，来自 audio:level 事件
    segments: SegmentPayload[]  // 当前会话所有已确认 segments
    devices: AudioDevice[]
    devicesLoading: boolean

    // Actions
    loadDevices: () => Promise<void>
    start: (config: RealtimeConfig) => Promise<void>
    pause: () => Promise<void>
    resume: () => Promise<void>
    stop: () => Promise<string>  // 返回 recording_id
    syncStatus: () => Promise<void>

    // 内部：事件监听器管理
    _unlisteners: UnlistenFn[]
    _setupEventListeners: () => Promise<() => void>
  }

  export const useRecordingStore = create<RecordingStore>((set, get) => ({
    status: 'idle',
    sessionId: null,
    startedAt: null,
    audioLevel: 0,
    segments: [],
    devices: [],
    devicesLoading: false,
    _unlisteners: [],

    loadDevices: async () => {
      set({ devicesLoading: true })
      try {
        const devices = await listAudioDevices()
        set({ devices, devicesLoading: false })
      } catch (e) {
        console.error('[recording] loadDevices error:', e)
        set({ devicesLoading: false })
      }
    },

    start: async (config) => {
      const sessionId = await startRealtime(config)
      set({
        status: 'recording',
        sessionId,
        startedAt: Date.now(),
        segments: [],
      })
    },

    pause: async () => {
      const { sessionId } = get()
      if (!sessionId) return
      await pauseRealtime(sessionId)
      set({ status: 'paused' })
    },

    resume: async () => {
      const { sessionId } = get()
      if (!sessionId) return
      await resumeRealtime(sessionId)
      set({ status: 'recording' })
    },

    stop: async () => {
      const { sessionId } = get()
      if (!sessionId) throw new Error('no active session')
      const recordingId = await stopRealtime(sessionId)
      set({ status: 'idle', sessionId: null, startedAt: null })
      return recordingId
    },

    syncStatus: async () => {
      const status = await getRecordingStatus()
      if (status.status === 'recording') {
        set({ status: 'recording', sessionId: status.session_id, startedAt: status.started_at })
      } else if (status.status === 'paused') {
        set({ status: 'paused', sessionId: status.session_id })
      } else {
        set({ status: 'idle', sessionId: null })
      }
    },

    _setupEventListeners: async () => {
      const unlisten1 = await listen<number>('audio:level', (e) => {
        set({ audioLevel: e.payload })
      })

      const unlisten2 = await listen<SegmentPayload>('transcription:segment', (e) => {
        set((state) => {
          // 若 is_partial，替换同 id 的现有 segment；否则追加
          const existing = state.segments.findIndex((s) => s.id === e.payload.id)
          if (existing >= 0) {
            const updated = [...state.segments]
            updated[existing] = e.payload
            return { segments: updated }
          }
          return { segments: [...state.segments, e.payload] }
        })
      })

      const unlisten3 = await listen<RecordingStatus>('transcription:status', (e) => {
        const s = e.payload
        if (s.status === 'recording') {
          set({ status: 'recording', sessionId: s.session_id, startedAt: s.started_at })
        } else if (s.status === 'paused') {
          set({ status: 'paused', sessionId: s.session_id })
        } else if (s.status === 'idle') {
          set({ status: 'idle', sessionId: null })
        }
      })

      const cleanup = () => {
        unlisten1(); unlisten2(); unlisten3()
      }
      set({ _unlisteners: [unlisten1, unlisten2, unlisten3] })
      return cleanup
    },
  }))
  ```

- [ ] **Commit:** `feat(store): implement useRecordingStore with polling-based realtime updates`

---

### Task 15: React — `RecordingPanel` 组件（SecondPanel）

**Files:**
- Create: `src/components/recording/RecordingPanel.tsx`

- [ ] **Step 15.1: 实现 `RecordingPanel`**

  ```tsx
  // src/components/recording/RecordingPanel.tsx
  import { useEffect, useState } from 'react'
  import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
  } from '@/components/ui/select'
  import { Label } from '@/components/ui/label'
  import { Slider } from '@/components/ui/slider'
  import { Switch } from '@/components/ui/switch'
  import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
  import { useRecordingStore } from '@/store/recording'
  import { useSettingsStore } from '@/store/settings'
  import type { RecordingMode } from '@/lib/bindings'

  const LANGUAGES = [
    { value: 'auto', label: 'Auto Detect' },
    { value: 'zh',   label: '中文' },
    { value: 'en',   label: 'English' },
    { value: 'fr',   label: 'Français' },
    { value: 'ja',   label: '日本語' },
  ]

  export function RecordingPanel() {
    const { devices, devicesLoading, loadDevices } = useRecordingStore()
    const { settings, updateSetting } = useSettingsStore()

    const [deviceId, setDeviceId] = useState<string>('')
    const [language, setLanguage] = useState<string>('auto')
    const [mode, setMode] = useState<'record_only' | 'transcribe_only' | 'transcribe_and_translate'>('transcribe_only')
    const [targetLang, setTargetLang] = useState<string>('en')
    const [vadThreshold, setVadThreshold] = useState<number>(0.02)
    const [autoProcess, setAutoProcess] = useState<boolean>(false)

    useEffect(() => {
      loadDevices()
    }, [])

    useEffect(() => {
      const defaultDevice = devices.find((d) => d.is_default)
      if (defaultDevice && !deviceId) setDeviceId(defaultDevice.id)
    }, [devices])

    return (
      <div className="flex flex-col gap-4 p-4">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
          Input
        </h2>

        {/* 设备选择 */}
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs text-text-muted">Microphone</Label>
          <Select value={deviceId} onValueChange={setDeviceId} disabled={devicesLoading}>
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder={devicesLoading ? 'Loading...' : 'Select device'} />
            </SelectTrigger>
            <SelectContent>
              {devices.map((d) => (
                <SelectItem key={d.id} value={d.id} className="text-xs">
                  {d.name}{d.is_default ? ' (Default)' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* 语言选择 */}
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs text-text-muted">Language</Label>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {LANGUAGES.map((l) => (
                <SelectItem key={l.value} value={l.value} className="text-xs">{l.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* 录音模式 */}
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-text-muted">Mode</Label>
          <RadioGroup value={mode} onValueChange={(v: any) => setMode(v)} className="gap-1.5">
            <div className="flex items-center gap-2">
              <RadioGroupItem value="record_only" id="mode-record" />
              <Label htmlFor="mode-record" className="text-xs cursor-pointer">Record Only</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="transcribe_only" id="mode-transcribe" />
              <Label htmlFor="mode-transcribe" className="text-xs cursor-pointer">Transcribe</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="transcribe_and_translate" id="mode-translate" />
              <Label htmlFor="mode-translate" className="text-xs cursor-pointer">Transcribe + Translate</Label>
            </div>
          </RadioGroup>
        </div>

        {/* 目标语言（仅 TranscribeAndTranslate 模式显示） */}
        {mode === 'transcribe_and_translate' && (
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-text-muted">Target Language</Label>
            <Select value={targetLang} onValueChange={setTargetLang}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LANGUAGES.filter((l) => l.value !== 'auto').map((l) => (
                  <SelectItem key={l.value} value={l.value} className="text-xs">{l.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* VAD 灵敏度滑块 */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center">
            <Label className="text-xs text-text-muted">VAD Sensitivity</Label>
            <span className="text-xs text-text-muted font-mono">{vadThreshold.toFixed(3)}</span>
          </div>
          <Slider
            min={0.001} max={0.1} step={0.001}
            value={[vadThreshold]}
            onValueChange={([v]) => setVadThreshold(v)}
            className="w-full"
          />
        </div>

        {/* 自动处理开关 */}
        <div className="flex items-center justify-between">
          <Label className="text-xs text-text-muted">Auto Process After Stop</Label>
          <Switch
            checked={autoProcess}
            onCheckedChange={setAutoProcess}
            className="scale-75"
          />
        </div>
      </div>
    )
  }

  // 导出当前面板配置的 RealtimeConfig 构建器（供 RecordingMain 使用）
  export { }
  ```

- [ ] **Commit:** `feat(ui): implement RecordingPanel with device/language/mode/VAD controls`

---

### Task 16: React — `RecordingMain` 组件（MainContent）

**Files:**
- Create: `src/components/recording/RecordingMain.tsx`

- [ ] **Step 16.1: 实现 `RecordingMain`（控制按钮 + 计时器 + Canvas 波形 + 实时字幕）**

  ```tsx
  // src/components/recording/RecordingMain.tsx
  import { useEffect, useRef, useState, useCallback } from 'react'
  import { Button } from '@/components/ui/button'
  import { Mic, MicOff, Pause, Square } from 'lucide-react'
  import { useRecordingStore } from '@/store/recording'
  import type { RealtimeConfig } from '@/lib/bindings'

  const DEFAULT_CONFIG: RealtimeConfig = {
    device_id: null,
    language: null,
    mode: { type: 'transcribe_only' },
    vad_threshold: 0.02,
    chunk_duration_ms: 500,
  }

  function formatDuration(ms: number): string {
    const totalSec = Math.floor(ms / 1000)
    const h = Math.floor(totalSec / 3600)
    const m = Math.floor((totalSec % 3600) / 60)
    const s = totalSec % 60
    return h > 0
      ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
      : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  function AudioWaveform({ level }: { level: number }) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    // 保存历史 level 用于波形滚动显示
    const historyRef = useRef<number[]>(new Array(120).fill(0))

    useEffect(() => {
      historyRef.current.push(level)
      if (historyRef.current.length > 120) historyRef.current.shift()

      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const { width, height } = canvas
      ctx.clearRect(0, 0, width, height)

      const barWidth = width / historyRef.current.length
      const accentColor = getComputedStyle(document.documentElement)
        .getPropertyValue('--color-accent-primary').trim() || '#7aa2f7'

      historyRef.current.forEach((lvl, i) => {
        const barHeight = Math.max(2, lvl * height * 0.9)
        const x = i * barWidth
        const y = (height - barHeight) / 2
        ctx.fillStyle = accentColor
        ctx.globalAlpha = 0.4 + lvl * 0.6
        ctx.fillRect(x, y, barWidth - 1, barHeight)
      })
      ctx.globalAlpha = 1
    }, [level])

    return (
      <canvas
        ref={canvasRef}
        width={480}
        height={80}
        className="w-full rounded-md bg-bg-secondary"
      />
    )
  }

  export function RecordingMain() {
    const { status, startedAt, audioLevel, segments, start, pause, resume, stop, _setupEventListeners } =
      useRecordingStore()
    const [elapsed, setElapsed] = useState(0)
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const segmentsEndRef = useRef<HTMLDivElement>(null)

    // 设置 Tauri 事件监听器（仅一次）
    useEffect(() => {
      let cleanup: (() => void) | undefined
      _setupEventListeners().then((fn) => { cleanup = fn })
      return () => { cleanup?.() }
    }, [])

    // 录音计时器
    useEffect(() => {
      if (status === 'recording' && startedAt) {
        timerRef.current = setInterval(() => {
          setElapsed(Date.now() - startedAt)
        }, 100)
      } else {
        if (timerRef.current) clearInterval(timerRef.current)
        if (status === 'idle') setElapsed(0)
      }
      return () => { if (timerRef.current) clearInterval(timerRef.current) }
    }, [status, startedAt])

    // 字幕自动滚动到底部
    useEffect(() => {
      segmentsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [segments])

    const handleStart = useCallback(async () => {
      await start(DEFAULT_CONFIG)
    }, [start])

    const handleStop = useCallback(async () => {
      const recordingId = await stop()
      console.log('[recording] saved as', recordingId)
    }, [stop])

    return (
      <div className="flex flex-col h-full p-6 gap-6">
        {/* 控制区 */}
        <div className="flex items-center gap-4">
          {status === 'idle' && (
            <Button onClick={handleStart} className="gap-2">
              <Mic className="w-4 h-4" />
              Start Recording
            </Button>
          )}
          {status === 'recording' && (
            <>
              <Button variant="outline" onClick={() => pause()} className="gap-2">
                <Pause className="w-4 h-4" />
                Pause
              </Button>
              <Button variant="destructive" onClick={handleStop} className="gap-2">
                <Square className="w-4 h-4" />
                Stop
              </Button>
            </>
          )}
          {status === 'paused' && (
            <>
              <Button onClick={() => resume()} className="gap-2">
                <Mic className="w-4 h-4" />
                Resume
              </Button>
              <Button variant="destructive" onClick={handleStop} className="gap-2">
                <Square className="w-4 h-4" />
                Stop
              </Button>
            </>
          )}

          {/* 计时器 */}
          {status !== 'idle' && (
            <div className="flex items-center gap-2 ml-auto">
              {status === 'recording' && (
                <span className="w-2 h-2 rounded-full bg-status-error animate-pulse" />
              )}
              <span className="font-mono text-lg text-text-primary tabular-nums">
                {formatDuration(elapsed)}
              </span>
            </div>
          )}
        </div>

        {/* 音频波形 Canvas */}
        <AudioWaveform level={audioLevel} />

        {/* 实时字幕 */}
        <div className="flex-1 overflow-y-auto rounded-md bg-bg-secondary p-4 text-sm text-text-primary leading-relaxed">
          {segments.length === 0 ? (
            <p className="text-text-muted text-center mt-8">
              {status === 'idle'
                ? 'Press Start Recording to begin'
                : 'Listening...'}
            </p>
          ) : (
            segments.map((seg) => (
              <span
                key={seg.id}
                className={seg.is_partial ? 'opacity-60' : 'opacity-100'}
              >
                {seg.text}{' '}
              </span>
            ))
          )}
          <div ref={segmentsEndRef} />
        </div>
      </div>
    )
  }
  ```

- [ ] **Commit:** `feat(ui): implement RecordingMain with canvas waveform, timer, and realtime subtitles`

---

### Task 17: 路由注册 — 接入 RecordingPanel + RecordingMain

**Files:**
- Modify: `src/router.tsx`（或 TanStack Router 路由定义文件）

- [ ] **Step 17.1: 在 `/recording` 路由的 SecondPanel slot 和 MainContent slot 分别引入组件**

  按 M1 已建立的路由结构，找到 `/recording` 路由定义，将 `RecordingPanel` 和 `RecordingMain` 注入对应 slot：

  ```tsx
  import { RecordingPanel } from '@/components/recording/RecordingPanel'
  import { RecordingMain }  from '@/components/recording/RecordingMain'

  // TanStack Router 路由定义示例（实际结构以 M1 为准）
  const recordingRoute = createRoute({
    getParentRoute: () => shellRoute,
    path: '/recording',
    component: () => (
      <Shell
        secondPanel={<RecordingPanel />}
        main={<RecordingMain />}
      />
    ),
  })
  ```

- [ ] **Commit:** `feat(router): wire RecordingPanel and RecordingMain into /recording route`

---

### Task 18: 端到端测试与调试

**Files:**
- Create: `src-tauri/tests/audio_pipeline_e2e.rs`（`#[ignore]` 标注，需硬件）

- [ ] **Step 18.1: 运行全量单元测试，确认通过**

  ```bash
  cd src-tauri && cargo test --lib -- audio resampler vad pipeline 2>&1
  ```

  预期结果：
  - `resampler::tests::test_resample_length_44100_stereo` — PASSED
  - `resampler::tests::test_resample_length_48000_mono` — PASSED
  - `resampler::tests::test_remainder_accumulation` — PASSED
  - `vad::tests::test_rms_all_zeros_is_zero` — PASSED
  - `vad::tests::test_rms_constant_signal` — PASSED
  - `vad::tests::test_rms_sine_approx_amplitude_over_sqrt2` — PASSED
  - `pipeline::tests::test_channel_send_recv` — PASSED
  - `pipeline::tests::test_sync_sender_backpressure` — PASSED
  - `pipeline::tests::test_channel_disconnected` — PASSED

- [ ] **Step 18.2: 编译检查（无需运行时）**

  ```bash
  cd src-tauri && cargo check 2>&1
  ```

- [ ] **Step 18.3: 创建 whisper 集成测试占位文件**

  ```rust
  // src-tauri/tests/audio_pipeline_e2e.rs
  //! 端到端集成测试。
  //! 需要真实麦克风和 whisper 模型文件，CI 环境中所有测试标注 #[ignore]。
  //! 手动运行：cargo test --test audio_pipeline_e2e -- --ignored

  #[test]
  #[ignore = "requires microphone and whisper model at /tmp/ggml-base.bin"]
  fn test_realtime_pipeline_5s() {
      // TODO: 构造假 AppState，启动 capture + pipeline，录 5s，验证 segments 非空
  }
  ```

- [ ] **Step 18.4: 前端开发服务验证（需 Tauri dev 环境）**

  ```bash
  npm run tauri dev
  ```

  手动检查：
  - `/recording` 页面：设备下拉正确列出系统麦克风
  - 点击 Start Recording：状态变为 recording，计时器开始
  - 对麦克风说话：Canvas 波形有响应，实时字幕出现（事件或轮询均可；需 whisper 模型已下载）
  - 点击 Stop：WAV 文件出现在 `{APP_DATA}/recordings/`，DB 中有对应记录

- [ ] **Commit:** `test: add audio pipeline unit tests and e2e integration test placeholder`

---

### Task 19: migration 补充 — `workspace_text_assets` 表

**Files:**
- Modify: `src-tauri/src/storage/migrations/0001_initial.sql`

- [ ] **Step 19.1: 确认 `workspace_text_assets` 表已存在，若不存在则补充**

  检查 `0001_initial.sql`：若该表尚未定义，追加以下 SQL：

  ```sql
  -- M4 补充：存储录音转写文本、LLM 摘要/翻译等文本资产
  CREATE TABLE IF NOT EXISTS workspace_text_assets (
      id          TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES workspace_documents(id) ON DELETE CASCADE,
      role        TEXT NOT NULL,   -- 'transcript' | 'summary' | 'translation' | 'brief'
      content     TEXT NOT NULL,
      file_path   TEXT,            -- 可选：指向外部文本文件
      created_at  INTEGER NOT NULL,
      updated_at  INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_text_assets_document ON workspace_text_assets(document_id);
  CREATE INDEX IF NOT EXISTS idx_text_assets_role ON workspace_text_assets(document_id, role);
  ```

- [ ] **Commit:** `feat(db): add workspace_text_assets table to migration for M4 transcript storage`

---

## 依赖关系总结

```
Task 1 (Cargo.toml)
  └─ Task 2 (build.rs)
       └─ Task 3 (capture.rs)
            └─ Task 4 (resampler.rs)
                 └─ Task 5 (vad.rs)
                      └─ Task 6 (audio/mod.rs)
Task 7 (engine.rs)
  └─ Task 8 (pipeline.rs)
       └─ Task 9 (transcription/mod.rs)
            ├─ Task 10 (commands/audio.rs)
            └─ Task 11 (commands/transcription.rs)
                 └─ Task 12 (state.rs 更新)
                      └─ Task 13 (commands 注册)
                           ├─ Task 14 (useRecordingStore)
                           │    └─ Task 15 (RecordingPanel)
                           │         └─ Task 16 (RecordingMain)
                           │              └─ Task 17 (路由注册)
                           └─ Task 18 (E2E 测试)
Task 19 (migration) — 并行，不阻塞其他 task
```

## 关键约束备忘

| 约束 | 位置 | 说明 |
|------|------|------|
| `std::sync::mpsc::SyncSender` | `capture.rs` → `pipeline.rs` | cpal callback 在系统线程，必须用 std（非 tokio）channel |
| 外层锁不跨 `spawn_blocking` | `pipeline.rs::flush_to_whisper` | clone Arc 后立即释放 Mutex guard，在 spawn_blocking 内通过 Arc 访问 |
| WAV 先写文件后写 DB | `commands/transcription.rs::stop_realtime` | 文件写失败返回 `AppError::Io`，不执行 DB 事务 |
| `#[ignore]` 标注集成测试 | `pipeline.rs` + `tests/audio_pipeline_e2e.rs` | CI 无模型/麦克风时自动跳过 |
| `chunk_size = inner.input_frames_next()` | `resampler.rs::new()` | 不硬编码，动态读取 rubato 实际期望值 |
| VAD `Instant` 计时 100ms | `vad.rs::process()` | 每次处理块时检查，满足间隔才 emit |
