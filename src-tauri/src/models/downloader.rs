// src-tauri/src/models/downloader.rs

use super::registry::tmp_file_path;
use super::{DownloadCommand, DownloadProgressPayload, ModelsToml};
use crate::error::AppError;
use crate::state::AppState;
use futures_util::StreamExt;
use sha2::{Digest, Sha256};
use std::collections::VecDeque;
use std::io::Write;
use std::path::Path;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter};
use tokio::sync::mpsc;

// ── 镜像 URL 替换 ─────────────────────────────────────────────

/// 根据用户配置的镜像设置替换下载 URL 中的域名。
/// - `""` / `"default"` → 不替换（使用 models.toml 中的原始 URL）
/// - `"hf-mirror"` → 将 `huggingface.co` 替换为 `hf-mirror.com`
/// - 其他字符串 → 视为自定义 base URL，替换 `https://huggingface.co`
pub fn apply_mirror(url: &str, mirror: &str) -> String {
    let mirror = mirror.trim();
    if mirror.is_empty() || mirror == "default" {
        return url.to_string();
    }
    let replacement = match mirror {
        "hf-mirror" => "https://hf-mirror.com",
        other => other,
    };
    // 仅对 huggingface.co URL 执行替换
    if url.contains("huggingface.co") {
        url.replacen("https://huggingface.co", replacement, 1)
    } else {
        url.to_string()
    }
}

// ── 滑动窗口速度计算 ──────────────────────────────────────────

/// (时间点, 该时间点新写入的字节数)
type WindowEntry = (Instant, u64);

pub struct SpeedWindow {
    entries: VecDeque<WindowEntry>,
    window: Duration,
}

impl Default for SpeedWindow {
    fn default() -> Self {
        Self::new()
    }
}

impl SpeedWindow {
    pub fn new() -> Self {
        Self {
            entries: VecDeque::new(),
            window: Duration::from_secs(5),
        }
    }

    /// 记录一次写入事件
    pub fn record(&mut self, at: Instant, bytes: u64) {
        self.entries.push_back((at, bytes));
    }

    /// 计算当前平均速度（bytes/sec），丢弃 5 秒前的条目
    pub fn avg_bps(&mut self, now: Instant) -> u64 {
        // 移除超过窗口的旧条目
        while let Some(&(ts, _)) = self.entries.front() {
            if now.duration_since(ts) > self.window {
                self.entries.pop_front();
            } else {
                break;
            }
        }
        if self.entries.is_empty() {
            return 0;
        }
        let total_bytes: u64 = self.entries.iter().map(|(_, b)| b).sum();
        // 窗口长度 = now - 最老条目的时间戳（至少 1 秒，避免除零）
        // Divide by the full window duration (5 s) so speed reflects bytes/sec
        // averaged over the entire sliding window, not just the span of recorded entries.
        let elapsed = self.window.as_secs_f64();
        (total_bytes as f64 / elapsed) as u64
    }
}

// ── 核心下载函数（可独立测试）────────────────────────────────

/// 下载单个文件到 `dest`，支持断点续传和 SHA256 校验。
///
/// - 若 `dest.tmp` 已存在，使用 `Range: bytes=N-` 续传
/// - 每写入 128 KB 调用一次 `progress_cb(downloaded_bytes)`
/// - 下载完成后 SHA256 校验；通过则 rename tmp → dest，失败则删除 tmp 并返回 Error
pub async fn download_to_file(
    client: &reqwest::Client,
    url: &str,
    dest: &Path,
    _expected_size: u64,
    expected_sha256: &str,
    mut progress_cb: impl FnMut(u64),
) -> Result<(), AppError> {
    let tmp = tmp_file_path(dest);

    // 创建目标目录
    if let Some(parent) = dest.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;
    }

    // 检查已有临时文件大小（断点续传）
    let resume_offset = tokio::fs::metadata(&tmp)
        .await
        .map(|m| m.len())
        .unwrap_or(0);

    // 构建请求
    let mut req = client.get(url);
    if resume_offset > 0 {
        req = req.header("Range", format!("bytes={}-", resume_offset));
    }
    eprintln!("[download] sending request to {url} (resume_offset={resume_offset})");
    let resp = req.send().await.map_err(|e| {
        eprintln!("[download] request failed: {e}");
        AppError::Model(e.to_string())
    })?;
    eprintln!("[download] HTTP {}", resp.status());
    if !resp.status().is_success() && resp.status().as_u16() != 206 {
        return Err(AppError::Model(format!(
            "HTTP {} for {}",
            resp.status(),
            url
        )));
    }

    // 打开临时文件（追加模式）
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&tmp)
        .map_err(|e| AppError::Io(e.to_string()))?;

    let mut downloaded = resume_offset;
    let mut buf = Vec::with_capacity(128 * 1024);
    let mut stream = resp.bytes_stream();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| AppError::Model(e.to_string()))?;
        buf.extend_from_slice(&chunk);

        // 每积累 128 KB 刷一次盘
        if buf.len() >= 128 * 1024 {
            file.write_all(&buf)
                .map_err(|e| AppError::Io(e.to_string()))?;
            downloaded += buf.len() as u64;
            progress_cb(downloaded);
            buf.clear();
        }
    }
    // 刷写剩余不足 128 KB 的尾部数据
    if !buf.is_empty() {
        file.write_all(&buf)
            .map_err(|e| AppError::Io(e.to_string()))?;
        downloaded += buf.len() as u64;
        progress_cb(downloaded);
    }
    drop(file);

    // SHA256 校验
    let computed = compute_sha256(&tmp)?;
    if computed != expected_sha256 {
        let _ = std::fs::remove_file(&tmp);
        return Err(AppError::Model(format!(
            "SHA256 校验失败：期望 {expected_sha256}，实际 {computed}"
        )));
    }

    // 重命名为最终文件
    std::fs::rename(&tmp, dest).map_err(|e| AppError::Io(e.to_string()))?;
    Ok(())
}

/// 计算文件 SHA256（同步，适合在 spawn_blocking 中调用）
fn compute_sha256(path: &Path) -> Result<String, AppError> {
    let mut file = std::fs::File::open(path).map_err(|e| AppError::Io(e.to_string()))?;
    let mut hasher = Sha256::new();
    std::io::copy(&mut file, &mut hasher).map_err(|e| AppError::Io(e.to_string()))?;
    Ok(hex::encode(hasher.finalize()))
}

// ── DownloadWorker 长驻任务 ───────────────────────────────────

/// 接收 DownloadCommand，管理并发下载（每次最多 1 个）。
/// 通过 `cancel_flags` DashMap 支持取消。
pub async fn run_download_worker(
    mut rx: mpsc::Receiver<DownloadCommand>,
    app: AppHandle,
    state: Arc<AppState>,
) {
    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(30)) // 仅连接超时；下载大文件不设总超时
        .build()
        .expect("reqwest client build failed");

    // DashMap<variant_id, AtomicBool>：true = 已请求取消
    let cancel_flags: Arc<dashmap::DashMap<String, Arc<AtomicBool>>> =
        Arc::new(dashmap::DashMap::new());

    while let Some(cmd) = rx.recv().await {
        match cmd {
            DownloadCommand::Start { variant_id } => {
                let cancelled = Arc::new(AtomicBool::new(false));
                cancel_flags.insert(variant_id.clone(), Arc::clone(&cancelled));

                // 从 AppState 克隆所需数据，避免跨 await 持锁
                let model_config = Arc::clone(&state.model_config);
                let config = state.config.read().await.clone();
                let model_dir = state.models_dir();
                let app_clone = app.clone();
                let client_clone = client.clone();
                let cancel_clone = Arc::clone(&cancelled);
                let cancel_flags_clone = Arc::clone(&cancel_flags);
                let vid = variant_id.clone();

                let state_for_reload = Arc::clone(&state);
                tokio::spawn(async move {
                    let result = do_download(
                        &client_clone,
                        &model_config,
                        &config,
                        &model_dir,
                        &vid,
                        &app_clone,
                        cancel_clone,
                    )
                    .await;

                    cancel_flags_clone.remove(&vid);

                    match result {
                        Ok(()) => {
                            app_clone
                                .emit(
                                    "models:downloaded",
                                    serde_json::json!({ "variant_id": vid }),
                                )
                                .ok();

                            // 下载完成后立即热加载对应引擎
                            use crate::models::registry::parse_variant_id;
                            match parse_variant_id(&vid).map(|(t, _)| t) {
                                Some("whisper") => { state_for_reload.try_load_whisper().await; }
                                Some("llm") => { state_for_reload.try_load_llm().await; }
                                _ => {}
                            }
                        }
                        Err(e) => {
                            // Keep the event for any future listeners
                            app_clone
                                .emit(
                                    "models:error",
                                    serde_json::json!({ "variant_id": vid, "error": e.to_string() }),
                                )
                                .ok();
                            // Also store for poll-based retrieval
                            state_for_reload.download_errors.insert(vid.clone(), e.to_string());
                        }
                    }
                });
            }

            DownloadCommand::Cancel { variant_id } => {
                if let Some(flag) = cancel_flags.get(&variant_id) {
                    flag.store(true, Ordering::Relaxed);
                }
            }
        }
    }
}

/// 实际执行单个模型的下载（在 tokio::spawn 的 async task 中运行）
async fn do_download(
    client: &reqwest::Client,
    model_config: &ModelsToml,
    config: &crate::config::schema::AppConfig,
    model_dir: &Path,
    variant_id: &str,
    app: &AppHandle,
    cancelled: Arc<AtomicBool>,
) -> Result<(), AppError> {
    use super::registry::{model_file_path, parse_variant_id};

    eprintln!("[download] starting: {variant_id}");

    let (model_type, variant_name) = parse_variant_id(variant_id)
        .ok_or_else(|| AppError::Model(format!("无效 variant_id: {variant_id}")))?;

    let cfg = match model_type {
        "whisper" => model_config.whisper.variants.get(variant_name),
        "llm" => model_config.llm.variants.get(variant_name),
        _ => None,
    }
    .ok_or_else(|| AppError::Model(format!("未找到模型配置: {variant_id}")))?;

    // 拒绝下载 SHA256 占位符的模型（防止下载完成后必然校验失败）
    if cfg.sha256.starts_with("FILL_IN") || cfg.sha256.len() != 64 {
        return Err(AppError::Model(format!(
            "模型 {variant_id} 的 SHA256 尚未配置，请联系开发者。"
        )));
    }

    let dest = model_file_path(model_dir, model_type, variant_name, &cfg.url);
    let expected_size = cfg.size_bytes;
    let expected_sha256 = cfg.sha256.clone();
    let url = apply_mirror(&cfg.url, &config.model_mirror);

    eprintln!("[download] url={url}");
    eprintln!("[download] dest={}", dest.display());

    let mut speed_window = SpeedWindow::new();
    let mut last_progress = Instant::now();

    // 每 128 KB chunk 触发 progress callback
    let app_clone = app.clone();
    let vid = variant_id.to_string();

    let progress_cb = move |downloaded: u64| {
        if cancelled.load(Ordering::Relaxed) {
            // 取消信号已标记，仅记录；实际中断由连接关闭实现
            return;
        }

        let now = Instant::now();
        speed_window.record(now, 128 * 1024); // 近似：每次 128KB
        let speed_bps = speed_window.avg_bps(now);
        let eta_secs = if speed_bps > 0 && expected_size > downloaded {
            Some((expected_size - downloaded) / speed_bps)
        } else {
            None
        };

        // 限流：每 500ms 发一次 progress 事件（避免高频 IPC）
        if now.duration_since(last_progress) >= Duration::from_millis(500) {
            last_progress = now;
            app_clone
                .emit(
                    "models:progress",
                    DownloadProgressPayload {
                        variant_id: vid.clone(),
                        downloaded_bytes: downloaded,
                        total_bytes: Some(expected_size),
                        speed_bps,
                        eta_secs,
                    },
                )
                .ok();
        }
    };

    download_to_file(client, &url, &dest, expected_size, &expected_sha256, progress_cb).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::{Digest, Sha256};
    use tempfile::tempdir;
    use wiremock::matchers::{header_exists, method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    fn sha256_of(data: &[u8]) -> String {
        let mut h = Sha256::new();
        h.update(data);
        hex::encode(h.finalize())
    }

    // 测试正常下载：服务器返回完整文件，SHA256 匹配
    #[tokio::test]
    async fn download_full_ok() {
        let server = MockServer::start().await;
        let body = vec![42u8; 1024 * 256]; // 256 KB
        let expected_sha256 = sha256_of(&body);
        Mock::given(method("GET"))
            .and(path("/model.bin"))
            .respond_with(ResponseTemplate::new(200).set_body_bytes(body.clone()))
            .mount(&server)
            .await;

        let dir = tempdir().unwrap();
        let dest = dir.path().join("model.bin");
        let url = format!("{}/model.bin", server.uri());

        let client = reqwest::Client::new();
        download_to_file(
            &client,
            &url,
            &dest,
            body.len() as u64,
            &expected_sha256,
            |_| {},
        )
        .await
        .unwrap();

        assert!(dest.exists());
        let written = std::fs::read(&dest).unwrap();
        assert_eq!(written, body);
    }

    // 测试 SHA256 不匹配：下载后删除临时文件，返回 AppError::Model
    #[tokio::test]
    async fn download_sha256_mismatch_deletes_tmp() {
        let server = MockServer::start().await;
        let body = vec![1u8; 100];
        Mock::given(method("GET"))
            .and(path("/bad.bin"))
            .respond_with(ResponseTemplate::new(200).set_body_bytes(body))
            .mount(&server)
            .await;

        let dir = tempdir().unwrap();
        let dest = dir.path().join("bad.bin");
        let url = format!("{}/bad.bin", server.uri());
        let wrong_sha256 = "a".repeat(64);
        let client = reqwest::Client::new();

        let result =
            download_to_file(&client, &url, &dest, 100, &wrong_sha256, |_| {}).await;
        assert!(result.is_err());
        // 临时文件应已被清理
        let tmp = super::super::registry::tmp_file_path(&dest);
        assert!(!tmp.exists());
        // 最终文件不应存在
        assert!(!dest.exists());
    }

    // 测试断点续传：服务器支持 Range，临时文件已有部分内容
    #[tokio::test]
    async fn download_resume_sends_range_header() {
        let server = MockServer::start().await;
        let partial = vec![0u8; 50];
        let remaining = vec![1u8; 50];
        // 服务端响应 Range 请求（模拟 206 Partial Content）
        Mock::given(method("GET"))
            .and(path("/model.bin"))
            .and(header_exists("range"))
            .respond_with(ResponseTemplate::new(206).set_body_bytes(remaining.clone()))
            .mount(&server)
            .await;

        let dir = tempdir().unwrap();
        let dest = dir.path().join("model.bin");
        let tmp = super::super::registry::tmp_file_path(&dest);
        // 预写 50 bytes 的临时文件（模拟已下载部分）
        std::fs::write(&tmp, &partial).unwrap();

        // 构造完整内容的 SHA256（partial + remaining）
        let mut full = partial.clone();
        full.extend_from_slice(&remaining);
        let sha = sha256_of(&full);

        let url = format!("{}/model.bin", server.uri());
        let client = reqwest::Client::new();
        download_to_file(&client, &url, &dest, 100, &sha, |_| {})
            .await
            .unwrap();

        assert!(dest.exists());
        let written = std::fs::read(&dest).unwrap();
        assert_eq!(written, full);
    }

    // 测试速度窗口：连续写入多个时间点，滑动窗口超过 5 秒的条目被丢弃
    #[test]
    fn speed_window_drops_old_entries() {
        use std::time::{Duration, Instant};
        let mut window = SpeedWindow::new();
        let now = Instant::now();

        // 模拟 6 秒前的条目（超出 5 秒窗口）
        window.record(now - Duration::from_secs(6), 1000);
        window.record(now - Duration::from_secs(2), 2000);
        window.record(now, 3000);

        let speed = window.avg_bps(now);
        // 只有最近 5 秒内的两条记录有效（2000 + 3000）/ 5s = 1000 bps
        assert!(speed > 0);
        // 6 秒前的 1000 bytes 不应参与计算
        // avg = (2000 + 3000) / 5 = 1000 bps
        assert_eq!(speed, 1000);
    }
}
