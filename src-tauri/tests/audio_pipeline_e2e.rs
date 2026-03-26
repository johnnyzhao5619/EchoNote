//! 端到端集成测试。
//! 需要真实麦克风和 whisper 模型文件，CI 环境中所有测试标注 #[ignore]。
//! 手动运行：cargo test --test audio_pipeline_e2e -- --ignored

#[test]
#[ignore = "requires microphone and whisper model at /tmp/ggml-base.bin"]
fn test_realtime_pipeline_5s() {
    // TODO: 构造真实 AppState，启动 capture + pipeline，录 5s，验证 segments 非空
}
