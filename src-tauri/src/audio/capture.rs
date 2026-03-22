// src-tauri/src/audio/capture.rs

use cpal::traits::{DeviceTrait, HostTrait};
use crate::commands::audio::AudioDevice;
use crate::error::AppError;
use std::sync::mpsc::SyncSender;

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

pub struct AudioCaptureHandle {
    /// cpal stream 必须保持 alive，drop 即停止采集
    _stream: cpal::Stream,
    pub sample_rate: u32,
    pub channels: u16,
}

impl AudioCaptureHandle {
    /// 先 pause 再 drop stream。
    /// 在 macOS 上，调用 StreamTrait::pause() 会触发 AudioOutputUnitStop，
    /// 立即释放麦克风使用权（系统状态栏图标消失）。
    /// 仅调用 drop() 不够——CoreAudio 可能延迟数秒才真正停止回调。
    pub fn stop(self) {
        use cpal::traits::StreamTrait;
        let _ = self._stream.pause(); // 通知 CoreAudio 立即停止
        // _stream 在此析构，释放 CoreAudio 资源
    }
}

/// 查询设备的默认采样率和声道数（不创建 stream，可在主线程调用）
pub fn get_device_config(device_id: Option<&str>) -> Result<(u32, usize), AppError> {
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
    Ok((config.sample_rate().0, config.channels() as usize))
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
    eprintln!("[capture] device format: {:?} @ {}Hz x{}ch",
        format, config.sample_rate.0, config.channels);
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
        I32 => device.build_input_stream(
            config,
            move |data: &[i32], _| {
                let f: Vec<f32> = data.iter().map(|&s| s as f32 / i32::MAX as f32).collect();
                let _ = tx.try_send(f);
            },
            err_fn, None,
        ),
        I64 => device.build_input_stream(
            config,
            move |data: &[i64], _| {
                let f: Vec<f32> = data.iter().map(|&s| s as f32 / i64::MAX as f32).collect();
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
        U32 => device.build_input_stream(
            config,
            move |data: &[u32], _| {
                let f: Vec<f32> = data.iter()
                    .map(|&s| (s as f64 / u32::MAX as f64 * 2.0 - 1.0) as f32)
                    .collect();
                let _ = tx.try_send(f);
            },
            err_fn, None,
        ),
        _ => {
            eprintln!("[capture] unsupported sample format: {:?}", format);
            return Err(AppError::Audio(format!("unsupported sample format: {format:?}")));
        }
    };
    stream.map_err(|e| AppError::Audio(e.to_string()))
}
