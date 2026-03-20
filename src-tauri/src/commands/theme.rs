use crate::{error::AppError, state::AppState};
use serde::{Deserialize, Serialize};
use specta::Type;

/// 主题描述符，仅含元信息（不含完整 token 数据，token 由前端直接读取 JSON 文件）
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct ThemeInfo {
    pub name: String,
    pub r#type: String, // "dark" | "light"
}

/// 获取当前激活主题名称
#[tauri::command]
#[specta::specta]
pub async fn get_current_theme(
    state: tauri::State<'_, AppState>,
) -> Result<String, AppError> {
    let cfg = state.config.read().await;
    Ok(cfg.active_theme.clone())
}

/// 设置当前激活主题
#[tauri::command]
#[specta::specta]
pub async fn set_current_theme(
    name: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), AppError> {
    let partial = crate::config::PartialAppConfig {
        active_theme: Some(name),
        ..Default::default()
    };
    super::settings::update_config_inner(&state, partial).await
}

/// 列举内置主题信息
#[tauri::command]
#[specta::specta]
pub async fn list_builtin_themes() -> Result<Vec<ThemeInfo>, AppError> {
    Ok(vec![
        ThemeInfo { name: "Tokyo Night".to_string(),       r#type: "dark".to_string() },
        ThemeInfo { name: "Tokyo Night Storm".to_string(), r#type: "dark".to_string() },
        ThemeInfo { name: "Tokyo Night Light".to_string(), r#type: "light".to_string() },
    ])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_list_builtin_themes_returns_three() {
        let themes = list_builtin_themes().await.unwrap();
        assert_eq!(themes.len(), 3);
        assert!(themes.iter().any(|t| t.name == "Tokyo Night"));
        assert!(themes.iter().any(|t| t.name == "Tokyo Night Storm"));
        assert!(themes.iter().any(|t| t.name == "Tokyo Night Light"));
    }
}
