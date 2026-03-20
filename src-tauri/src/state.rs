use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use crate::{config::AppConfig, models::{DownloadCommand, ModelsToml}, storage::db::Db};

pub struct AppState {
    pub db: Arc<Db>,
    pub config: Arc<RwLock<AppConfig>>,
    pub model_config: Arc<ModelsToml>,
    pub download_tx: mpsc::Sender<DownloadCommand>,
}
