// src-tauri/src/commands/audio.rs

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::State;

use crate::audio;
use crate::error::AppError;
use crate::state::AppState;

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
    // cpal 枚举是快速同步操作，在 spawn_blocking 中执行以免阻塞 tokio scheduler
    tokio::task::spawn_blocking(audio::list_audio_devices)
        .await
        .map_err(|e| AppError::Audio(format!("spawn_blocking: {e}")))?
}
