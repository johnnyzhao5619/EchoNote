use std::sync::Arc;
use tokio::sync::RwLock;
use crate::{config::AppConfig, storage::db::Db};

pub struct AppState {
    pub db: Arc<Db>,
    pub config: Arc<RwLock<AppConfig>>,
    // Other fields will be added in later milestones (worker channels, engines, etc.)
}
