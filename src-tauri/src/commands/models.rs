// src-tauri/src/commands/models.rs

use crate::error::AppError;
use crate::models::registry::{check_required_models, list_all_variants};
use crate::models::{DownloadCommand, ModelVariant};
use crate::state::AppState;
use tauri::State;

fn model_dir_from_vault(vault_path: &str) -> std::path::PathBuf {
    std::path::Path::new(vault_path)
        .parent()
        .unwrap_or(std::path::Path::new(vault_path))
        .join("models")
}

/// 列出所有模型变体及其下载/激活状态
#[tauri::command]
#[specta::specta]
pub async fn list_model_variants(
    state: State<'_, AppState>,
) -> Result<Vec<ModelVariant>, AppError> {
    let config = state.config.read().await;
    let model_dir = model_dir_from_vault(&config.vault_path);

    Ok(list_all_variants(
        &state.model_config,
        &model_dir,
        &config.active_whisper_model,
        &config.active_llm_model,
    ))
}

/// 触发后台下载（非阻塞），立即返回
#[tauri::command]
#[specta::specta]
pub async fn download_model(
    variant_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    state
        .download_tx
        .send(DownloadCommand::Start { variant_id })
        .await
        .map_err(|_| AppError::ChannelClosed)
}

/// 取消正在进行的下载
#[tauri::command]
#[specta::specta]
pub async fn cancel_download(
    variant_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    state
        .download_tx
        .send(DownloadCommand::Cancel { variant_id })
        .await
        .map_err(|_| AppError::ChannelClosed)
}

/// 删除已下载的模型文件
#[tauri::command]
#[specta::specta]
pub async fn delete_model(
    variant_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    use crate::models::registry::{model_file_path, parse_variant_id};

    let (model_type, variant_name) = parse_variant_id(&variant_id)
        .ok_or_else(|| AppError::Model(format!("无效 variant_id: {variant_id}")))?;

    let config = state.config.read().await;
    let model_dir = model_dir_from_vault(&config.vault_path);

    let cfg = match model_type {
        "whisper" => state.model_config.whisper.variants.get(variant_name),
        "llm" => state.model_config.llm.variants.get(variant_name),
        _ => None,
    }
    .ok_or_else(|| AppError::NotFound(variant_id.clone()))?;

    let path = model_file_path(&model_dir, model_type, variant_name, &cfg.url);

    if path.exists() {
        tokio::fs::remove_file(&path)
            .await
            .map_err(|e| AppError::Io(e.to_string()))?;
    }
    Ok(())
}

/// 切换激活模型（持久化到 AppConfig，下次推理时生效）
#[tauri::command]
#[specta::specta]
pub async fn set_active_model(
    variant_id: String,
    state: State<'_, AppState>,
) -> Result<(), AppError> {
    use crate::models::registry::parse_variant_id;

    let (model_type, _) = parse_variant_id(&variant_id)
        .ok_or_else(|| AppError::Model(format!("无效 variant_id: {variant_id}")))?;

    let serialized = {
        let mut config = state.config.write().await;
        match model_type {
            "whisper" => config.active_whisper_model = variant_id,
            "llm" => config.active_llm_model = variant_id,
            _ => return Err(AppError::Model(format!("未知 model_type: {model_type}"))),
        }
        serde_json::to_string(&*config)
            .map_err(|e| AppError::Storage(e.to_string()))?
    };

    state
        .db
        .save_setting("app_config", &serialized)
        .await
        .map_err(|e| AppError::Storage(e.to_string()))?;

    Ok(())
}

/// 启动时检测缺失模型（供 lib.rs 在窗口就绪后调用）
#[allow(dead_code)]
pub async fn missing_required_models(state: &AppState) -> Vec<String> {
    let config = state.config.read().await;
    let model_dir = model_dir_from_vault(&config.vault_path);
    check_required_models(
        &state.model_config,
        &model_dir,
        &config.active_whisper_model,
        &config.active_llm_model,
    )
}
