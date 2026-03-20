use serde::Serialize;

#[derive(Debug, thiserror::Error, Serialize, specta::Type)]
#[serde(tag = "kind", content = "message")]
pub enum AppError {
    #[error("audio error: {0}")]
    Audio(String),

    #[error("transcription error: {0}")]
    Transcription(String),

    #[error("llm error: {0}")]
    Llm(String),

    #[error("storage error: {0}")]
    Storage(String),

    #[error("io error: {0}")]
    Io(String),

    #[error("model error: {0}")]
    Model(String),

    #[error("workspace error: {0}")]
    Workspace(String),

    #[error("not found: {0}")]
    NotFound(String),

    #[error("validation: {0}")]
    Validation(String),

    #[error("channel closed")]
    ChannelClosed,
}

impl AppError {
    pub fn channel<E: std::fmt::Display>(_e: E) -> Self {
        AppError::ChannelClosed
    }

    pub fn io<E: std::fmt::Display>(e: E) -> Self {
        AppError::Io(e.to_string())
    }

    pub fn storage<E: std::fmt::Display>(e: E) -> Self {
        AppError::Storage(e.to_string())
    }
}

// 让 Tauri 能序列化错误返回给前端
impl From<AppError> for tauri::ipc::InvokeError {
    fn from(e: AppError) -> Self {
        tauri::ipc::InvokeError::from_serde_json(
            serde_json::to_value(&e).unwrap_or_default()
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_app_error_display_audio() {
        let err = AppError::Audio("microphone not found".to_string());
        assert_eq!(err.to_string(), "audio error: microphone not found");
    }

    #[test]
    fn test_app_error_display_channel_closed() {
        let err = AppError::ChannelClosed;
        assert_eq!(err.to_string(), "channel closed");
    }

    #[test]
    fn test_app_error_serde_round_trip() {
        let err = AppError::NotFound("recording-123".to_string());
        let json = serde_json::to_string(&err).unwrap();
        assert!(json.contains("\"kind\":\"NotFound\""));
        assert!(json.contains("recording-123"));
    }
}
