// src-tauri/src/models/mod.rs

pub mod registry;
pub mod downloader;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use specta::Type;

// ── TOML 反序列化结构 ─────────────────────────────────────────

#[derive(Debug, Deserialize, Clone)]
pub struct ModelsToml {
    pub whisper: ModelGroup,
    pub llm: ModelGroup,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ModelGroup {
    pub default_variant: String,
    pub variants: HashMap<String, VariantConfig>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct VariantConfig {
    pub url: String,
    pub sha256: String,
    pub size_bytes: u64,
    pub description: String,
}

// ── IPC 数据类型（tauri-specta 导出到前端）────────────────────

/// 下载进度推送 Payload（`models:progress` 事件）
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct DownloadProgressPayload {
    pub variant_id: String,
    pub downloaded_bytes: u64,
    pub total_bytes: Option<u64>,
    /// bytes/sec，基于最近 5 秒滑动窗口均值
    pub speed_bps: u64,
    /// 预计剩余秒数；total_bytes 未知时为 None
    pub eta_secs: Option<u64>,
}

/// 单个模型变体的完整状态（`list_model_variants` 返回值）
#[derive(Debug, Serialize, Deserialize, Clone, Type)]
pub struct ModelVariant {
    /// 格式："whisper/base" 或 "llm/qwen2.5-3b-q4"
    pub variant_id: String,
    /// "whisper" | "llm"
    pub model_type: String,
    pub name: String,
    pub description: String,
    pub size_bytes: u64,
    /// 格式化后的大小字符串，如 "142 MB"
    pub size_display: String,
    pub is_downloaded: bool,
    /// 当前已加载（激活）的模型
    pub is_active: bool,
    /// SHA256 是否已配置（false = 占位符，禁止下载）
    pub sha256_valid: bool,
}

// ── 内部 channel 消息 ─────────────────────────────────────────

#[derive(Debug)]
pub enum DownloadCommand {
    Start { variant_id: String },
    Cancel { variant_id: String },
}

// ── 辅助函数 ──────────────────────────────────────────────────

/// 将字节数格式化为人类可读字符串，如 "142 MB"、"1.4 GB"
pub fn format_size(bytes: u64) -> String {
    const GB: u64 = 1_073_741_824;
    const MB: u64 = 1_048_576;
    const KB: u64 = 1_024;
    if bytes >= GB {
        format!("{:.1} GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.0} MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.0} KB", bytes as f64 / KB as f64)
    } else {
        format!("{} B", bytes)
    }
}
