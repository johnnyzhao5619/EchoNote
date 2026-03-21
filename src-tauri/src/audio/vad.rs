// src-tauri/src/audio/vad.rs

use std::time::{Duration, Instant};

/// 连续 N 块 RMS < threshold → 判定为静音段
const SILENCE_BLOCKS: usize = 6;
/// audio:level 最小发送间隔
const LEVEL_EMIT_INTERVAL: Duration = Duration::from_millis(100);
/// 静音上下文前导：静音结束后附带最多 1s 的前导帧（按 chunk 粒度）
const CONTEXT_CHUNKS: usize = 2; // 约 1s（500ms chunk × 2）

// ── 自适应 VAD 阈值参数 ─────────────────────────────────────────
/// 噪底估计滑动窗口大小（静音帧数）
const NOISE_FLOOR_WINDOW: usize = 50;
/// 语音阈值 = 噪底 × NOISE_FLOOR_MULTIPLIER
const NOISE_FLOOR_MULTIPLIER: f32 = 4.0;
/// 自适应阈值下界（防止极安静环境过灵敏）
const ADAPTIVE_MIN: f32 = 0.003;
/// 自适应阈值上界（防止嘈杂环境过滤所有语音）
const ADAPTIVE_MAX: f32 = 0.040;

pub struct VadFilter {
    /// 冷启动阈值（< NOISE_FLOOR_WINDOW 静音帧时使用）
    threshold: f32,
    /// 当前自适应阈值（稳定后替换 threshold）
    pub(crate) adaptive_threshold: f32,
    /// 噪底乘数（固定 4.0）
    base_multiplier: f32,
    /// 静音帧 RMS 滑动窗口（仅 rms < effective_threshold 时才追加）
    rms_history: std::collections::VecDeque<f32>,
    silence_count: usize,
    /// 最近 CONTEXT_CHUNKS 帧缓存，用于静音结束时补充上下文
    context_buf: std::collections::VecDeque<Vec<f32>>,
    last_level_emit: Instant,
    /// 音频电平回调（在 std::thread 中调用，回调内部应快速完成）
    on_level: Box<dyn Fn(f32) + Send + 'static>,
    /// 诊断用：已处理帧数（用于控制日志频率）
    chunk_count: u64,
}

impl VadFilter {
    /// `threshold`: 冷启动阈值（也是 `set_threshold()` 手动覆盖的目标值）
    /// `on_level`: 每隔 100ms 调用一次，传入归一化 RMS [0.0, 1.0]
    pub fn new(threshold: f32, on_level: impl Fn(f32) + Send + 'static) -> Self {
        Self {
            threshold,
            adaptive_threshold: threshold,
            base_multiplier: NOISE_FLOOR_MULTIPLIER,
            rms_history: std::collections::VecDeque::with_capacity(NOISE_FLOOR_WINDOW + 1),
            silence_count: 0,
            context_buf: std::collections::VecDeque::with_capacity(CONTEXT_CHUNKS + 1),
            last_level_emit: Instant::now()
                .checked_sub(LEVEL_EMIT_INTERVAL)
                .unwrap_or_else(Instant::now),
            on_level: Box::new(on_level),
            chunk_count: 0,
        }
    }

    /// P25 噪底估计，收集够 NOISE_FLOOR_WINDOW 帧后更新 adaptive_threshold
    fn update_noise_floor(&mut self) {
        if self.rms_history.len() < NOISE_FLOOR_WINDOW {
            return;
        }
        let mut sorted: Vec<f32> = self.rms_history.iter().copied().collect();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        // P25：index 12（= 50 × 0.25 = 12.5，向下取整）
        let p25 = sorted[NOISE_FLOOR_WINDOW / 4];
        self.adaptive_threshold = (p25 * self.base_multiplier).clamp(ADAPTIVE_MIN, ADAPTIVE_MAX);
    }

    /// 处理一个音频块，返回应送往 whisper pipeline 的帧（可能为空）
    /// 同时在满足 100ms 间隔时通过回调发送 RMS 电平
    pub fn process(&mut self, chunk: Vec<f32>) -> Vec<Vec<f32>> {
        let rms = Self::rms(&chunk);
        self.chunk_count += 1;

        // 有效阈值：冷启动期用初始 threshold，稳定后用 adaptive_threshold
        let effective = if self.rms_history.len() < NOISE_FLOOR_WINDOW {
            self.threshold
        } else {
            self.adaptive_threshold
        };

        // 诊断日志：前 10 帧 + 每 50 帧打印一次
        if self.chunk_count <= 10 || self.chunk_count % 50 == 0 {
            let verdict = if rms >= effective { "VOICE" } else { "silent" };
            let phase = if self.rms_history.len() < NOISE_FLOOR_WINDOW { "cold" } else { "adapted" };
            let noise_floor = if self.rms_history.len() >= 4 {
                let mut s: Vec<f32> = self.rms_history.iter().copied().collect();
                s.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
                s[s.len() / 4]
            } else {
                0.0
            };
            eprintln!("[vad] chunk #{}: rms={:.5}, noise_floor={:.5}, threshold={:.5}({}) → {}",
                self.chunk_count, rms, noise_floor, effective, phase, verdict);
        }

        // 100ms 降频回调
        if self.last_level_emit.elapsed() >= LEVEL_EMIT_INTERVAL {
            (self.on_level)(rms.min(1.0));
            self.last_level_emit = Instant::now();
        }

        if rms < effective {
            // 静音帧：追加到噪底历史（维持滑动窗口）
            if self.rms_history.len() >= NOISE_FLOOR_WINDOW {
                self.rms_history.pop_front();
            }
            self.rms_history.push_back(rms);
            self.update_noise_floor();

            // 更新静音计数和上下文缓存
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
    pub fn rms(samples: &[f32]) -> f32 {
        if samples.is_empty() {
            return 0.0;
        }
        let mean_sq: f32 = samples.iter().map(|s| s * s).sum::<f32>() / samples.len() as f32;
        mean_sq.sqrt()
    }

    /// 手动覆盖阈值；同时重置 adaptive_threshold 和噪底历史
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

    // ── 原有测试（保留）─────────────────────────────────────────

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

    // ── 新增：自适应阈值测试 ─────────────────────────────────────

    #[test]
    fn test_adaptive_threshold_cold_start_uses_initial() {
        // 冷启动期（< 50 静音帧）adaptive_threshold 保持初始值不变
        let mut vad = VadFilter::new(0.008, |_| {});
        for _ in 0..10 {
            vad.process(vec![0.003f32; 1600]); // rms=0.003 < 0.008 → 静音
        }
        assert_eq!(vad.adaptive_threshold, 0.008,
            "cold-start should not change adaptive_threshold");
    }

    #[test]
    fn test_adaptive_threshold_converges_after_50_silence_frames() {
        // 50 帧 rms=0.005 → 噪底 P25=0.005 → adaptive=0.005×4=0.020
        let mut vad = VadFilter::new(0.008, |_| {});
        let silence_chunk: Vec<f32> = vec![0.005f32; 1600];
        for _ in 0..50 {
            vad.process(silence_chunk.clone());
        }
        let expected = (0.005f32 * 4.0).clamp(ADAPTIVE_MIN, ADAPTIVE_MAX);
        assert!(
            (vad.adaptive_threshold - expected).abs() < 0.001,
            "adaptive_threshold={}, expected={}", vad.adaptive_threshold, expected
        );
    }

    #[test]
    fn test_adaptive_threshold_clamp_min() {
        // 极安静（rms=0.0003）→ 0.0003×4=0.0012 < ADAPTIVE_MIN → clamp 到 0.003
        let mut vad = VadFilter::new(0.008, |_| {});
        for _ in 0..50 {
            vad.process(vec![0.0003f32; 1600]);
        }
        assert!(vad.adaptive_threshold >= ADAPTIVE_MIN,
            "must not go below ADAPTIVE_MIN, got {}", vad.adaptive_threshold);
        assert!((vad.adaptive_threshold - ADAPTIVE_MIN).abs() < 0.001);
    }

    #[test]
    fn test_adaptive_threshold_clamp_max() {
        // 嘈杂（rms=0.015）→ 0.015×4=0.060 > ADAPTIVE_MAX → clamp 到 0.040
        // 初始阈值设 0.030 使 rms=0.015 判定为静音进入 history
        let mut vad = VadFilter::new(0.030, |_| {});
        for _ in 0..50 {
            vad.process(vec![0.015f32; 1600]);
        }
        assert!(vad.adaptive_threshold <= ADAPTIVE_MAX,
            "must not exceed ADAPTIVE_MAX, got {}", vad.adaptive_threshold);
        assert!((vad.adaptive_threshold - ADAPTIVE_MAX).abs() < 0.001);
    }

    #[test]
    fn test_set_threshold_resets_adaptive_and_history() {
        // set_threshold 应重置 adaptive_threshold 和 rms_history
        let mut vad = VadFilter::new(0.008, |_| {});
        for _ in 0..50 {
            vad.process(vec![0.004f32; 1600]);
        }
        assert_ne!(vad.adaptive_threshold, 0.008); // 已收敛
        vad.set_threshold(0.015);
        assert_eq!(vad.adaptive_threshold, 0.015);
        assert!(vad.rms_history.is_empty());
    }

    #[test]
    fn test_speech_frames_not_added_to_history() {
        // 语音帧（rms > threshold）不应进入 rms_history
        let mut vad = VadFilter::new(0.008, |_| {});
        for _ in 0..60 {
            vad.process(vec![0.050f32; 1600]); // rms=0.050 > 0.008
        }
        assert!(vad.rms_history.is_empty(),
            "speech frames must not populate rms_history, len={}", vad.rms_history.len());
    }

    #[test]
    fn test_silence_frames_fill_history_up_to_window() {
        // 静音帧持续累积到 NOISE_FLOOR_WINDOW，之后维持滑动窗口大小
        let mut vad = VadFilter::new(0.020, |_| {});
        for _ in 0..30 {
            vad.process(vec![0.005f32; 1600]);
        }
        assert_eq!(vad.rms_history.len(), 30);

        for _ in 0..30 {
            vad.process(vec![0.005f32; 1600]);
        }
        // 超过窗口大小后，长度应保持在 NOISE_FLOOR_WINDOW
        assert_eq!(vad.rms_history.len(), NOISE_FLOOR_WINDOW);
    }
}
