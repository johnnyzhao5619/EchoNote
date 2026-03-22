// src-tauri/src/llm/streaming.rs
//
// 同步 token callback → tokio unbounded channel → Tauri event 桥接。
//
// 设计原则：
//   - 发送端（TokenSender）可安全地在 spawn_blocking 闭包中（非 tokio 线程）调用
//   - unbounded channel 保证 send 不阻塞，不会因 emit 延迟而拖慢推理循环
//   - 转发 task 在 channel 关闭（发送端 drop）时自动退出

use tauri::{AppHandle, Emitter};
use tokio::sync::mpsc::{self, UnboundedReceiver, UnboundedSender};
use tokio::task::JoinHandle;

use crate::llm::TokenPayload;

/// 同步发送端——在 spawn_blocking 中使用
#[derive(Clone)]
pub struct TokenSender(UnboundedSender<String>);

impl TokenSender {
    /// 发送一个 token。若接收侧已关闭（任务被取消），返回 false 通知推理循环停止。
    pub fn send(&self, token: String) -> bool {
        self.0.send(token).is_ok()
    }
}

/// 创建 token 桥接：
///
/// 返回 `(TokenSender, JoinHandle)`:
/// - `TokenSender` 传入 spawn_blocking 闭包，在 token_cb 中调用 `sender.send(token)`
/// - `JoinHandle` 由 worker 持有，转发 task 在 channel 关闭时自动结束
pub fn make_token_bridge(
    app: AppHandle,
    task_id: String,
) -> (TokenSender, JoinHandle<()>) {
    let (tx, mut rx): (UnboundedSender<String>, UnboundedReceiver<String>) =
        mpsc::unbounded_channel();

    let handle = tokio::spawn(async move {
        while let Some(token) = rx.recv().await {
            let payload = TokenPayload {
                task_id: task_id.clone(),
                token,
            };
            // emit 失败（窗口已关闭）时静默忽略，不 panic
            app.emit("llm:token", payload).ok();
        }
    });

    (TokenSender(tx), handle)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_sender_send_returns_false_after_drop() {
        let (tx, rx) = tokio::sync::mpsc::unbounded_channel::<String>();
        let sender = TokenSender(tx);
        // rx 立即 drop，模拟接收侧关闭
        drop(rx);
        assert!(!sender.send("hello".to_string()));
    }
}
