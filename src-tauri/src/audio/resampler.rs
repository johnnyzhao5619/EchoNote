// src-tauri/src/audio/resampler.rs

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
            1,        // rubato operates on mono; multi-channel input is downmixed before passing
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
