use std::path::Path;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum FfmpegError {
    #[error("ffmpeg not found in PATH")]
    NotFound,
    #[error("ffmpeg conversion failed: {0}")]
    ConversionFailed(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

/// 检测系统 PATH 中是否存在 ffmpeg。
pub fn detect_ffmpeg() -> bool {
    let mut command = if cfg!(target_os = "windows") {
        std::process::Command::new("where")
    } else {
        std::process::Command::new("which")
    };

    command
        .arg("ffmpeg")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

/// 将媒体文件同步转码为 16kHz 单声道 WAV。
/// 调用方必须在 spawn_blocking 中调用此函数。
pub fn convert_to_wav(input: &Path, output: &Path) -> Result<(), FfmpegError> {
    if !detect_ffmpeg() {
        return Err(FfmpegError::NotFound);
    }

    let result = std::process::Command::new("ffmpeg")
        .args(["-y", "-i"])
        .arg(input)
        .args(["-ar", "16000", "-ac", "1", "-f", "wav"])
        .arg(output)
        .output()?;

    if result.status.success() {
        Ok(())
    } else {
        Err(FfmpegError::ConversionFailed(
            String::from_utf8_lossy(&result.stderr).to_string(),
        ))
    }
}

/// 仅 WAV 走直接解码路径，其他格式统一经 ffmpeg 转码。
pub fn needs_transcode(path: &Path) -> bool {
    let extension = path
        .extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| ext.to_ascii_lowercase());

    !matches!(extension.as_deref(), Some("wav"))
}

pub fn is_supported_format(path: &Path) -> bool {
    let extension = path
        .extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| ext.to_ascii_lowercase());

    matches!(
        extension.as_deref(),
        Some("wav" | "flac" | "mp3" | "mp4" | "m4a" | "mov" | "mkv" | "webm" | "ogg")
    )
}
