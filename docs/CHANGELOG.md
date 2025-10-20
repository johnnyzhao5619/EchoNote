# Changelog

## Unreleased
### Changed
- 调整 `TimelineManager.get_timeline_events` 的分页策略：历史事件继续遵循 `page/page_size`，但第一页始终返回完整的未来事件列表，并新增 `future_total_count` 字段，便于前端与调度器依赖未来事件数据时保持兼容。
- 优化时间线搜索结果的自动任务加载逻辑，通过批量查询减少数据库往返次数。
- 数据库连接初始化时改为对 SQLCipher 密钥使用参数绑定，并在必要时回退到安全的引用方案，避免字符串拼接导致的注入风险。
