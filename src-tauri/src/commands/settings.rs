use crate::error::AppError;
use serde::{Deserialize, Serialize};
use specta::Type;

/// 应用配置骨架（M1 只含主题相关字段，后续里程碑扩充）
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct AppConfig {
    pub theme: String,
    pub language: String,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            theme: "Tokyo Night".to_string(),
            language: "en".to_string(),
        }
    }
}

/// 获取应用配置骨架（M1 返回默认值，M3+ 从磁盘读取）
#[tauri::command]
#[specta::specta]
pub async fn get_app_config() -> Result<AppConfig, AppError> {
    Ok(AppConfig::default())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_get_app_config_defaults() {
        let config = get_app_config().await.unwrap();
        assert_eq!(config.theme, "Tokyo Night");
        assert_eq!(config.language, "en");
    }
}
