use std::sync::Arc;
use tokio::sync::Mutex;

/// AppState 是注入所有 Tauri commands 的共享状态。
/// M1 阶段只有结构骨架，无实际业务字段。
/// 后续里程碑逐步添加 transcription_tx / llm_tx / model_tx 等 channel sender。
#[derive(Clone)]
pub struct AppState {
    pub inner: Arc<AppStateInner>,
}

pub struct AppStateInner {
    /// 当前选中主题名称（对应 resources/themes/*.json 的 name 字段）
    pub current_theme: Mutex<String>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(AppStateInner {
                current_theme: Mutex::new("Tokyo Night".to_string()),
            }),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_app_state_default_theme() {
        let state = AppState::new();
        let theme = state.inner.current_theme.lock().await;
        assert_eq!(*theme, "Tokyo Night");
    }
}
