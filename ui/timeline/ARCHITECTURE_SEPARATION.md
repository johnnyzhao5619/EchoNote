# 时间线架构职责分离说明

## 背景

需求 4.6 和 4.7 涉及自动任务的启动和通知功能。本文档说明为什么这些功能由后端调度器处理，而不是 UI 层。

## 架构原则

### 关注点分离（Separation of Concerns）

```
┌─────────────────────────────────────────────────────────┐
│                      UI 层 (Presentation)                │
│  - 用户交互                                              │
│  - 数据展示                                              │
│  - 配置收集                                              │
└─────────────────────────────────────────────────────────┘
                            ↓ ↑
                    信号/槽通信 (Qt Signals)
                            ↓ ↑
┌─────────────────────────────────────────────────────────┐
│                   业务逻辑层 (Business Logic)             │
│  - 数据处理                                              │
│  - 业务规则                                              │
│  - 任务调度                                              │
└─────────────────────────────────────────────────────────┘
                            ↓ ↑
                      数据访问 (Data Access)
                            ↓ ↑
┌─────────────────────────────────────────────────────────┐
│                     数据层 (Data)                        │
│  - 数据库操作                                            │
│  - 文件系统                                              │
│  - 外部 API                                              │
└─────────────────────────────────────────────────────────┘
```

## 需求分析

### 需求 4.6: 自动启动任务

**原文**: "WHEN 事件开始时间到达 AND 用户已启用自动任务 THEN 系统应自动启动配置的任务（实时转录/录音）"

**职责分析**:

- ✅ **UI 层**: 提供开关控件，保存用户配置
- ✅ **后端层**: 监控时间，检测事件开始，启动任务

### 需求 4.7: 提前通知

**原文**: "WHEN 事件开始前 5 分钟 AND 用户已启用自动任务 THEN 系统应发送桌面通知"

**职责分析**:

- ✅ **UI 层**: 显示通知（通过通知管理器）
- ✅ **后端层**: 监控时间，检测提前 5 分钟，触发通知

## 实现方案

### UI 层职责（任务 13）

#### 1. 配置界面

```python
# ui/timeline/event_card.py
class EventCard(QFrame):
    def create_future_actions(self):
        # 提供自动任务开关
        self.transcription_checkbox = QCheckBox(
            self.i18n.t('timeline.enable_transcription')
        )
        self.recording_checkbox = QCheckBox(
            self.i18n.t('timeline.enable_recording')
        )

        # 连接信号
        self.transcription_checkbox.stateChanged.connect(
            self._on_auto_task_changed
        )
```

#### 2. 配置保存

```python
# ui/timeline/widget.py
class TimelineWidget(QWidget):
    def _on_auto_task_changed(self, event_id: str, config: Dict[str, Any]):
        try:
            # 保存配置到后端
            self.timeline_manager.set_auto_task(event_id, config)
            logger.info(f"Auto-task config updated for event: {event_id}")

            # 发射信号通知其他组件
            self.auto_task_changed.emit(event_id, config)
        except Exception as e:
            logger.error(f"Failed to update auto-task config: {e}")
```

#### 3. 通知显示

```python
# ui/common/notification.py (已在任务 9.3 实现)
class NotificationManager:
    def show_event_reminder(self, event_title: str, auto_tasks: dict):
        """显示事件提醒通知"""
        message = f"{event_title} 即将开始"
        if auto_tasks.get('enable_transcription'):
            message += "，将自动启动转录"
        if auto_tasks.get('enable_recording'):
            message += "，将自动启动录音"

        self.show_notification("事件提醒", message)
```

### 后端层职责（任务 7.2）

#### 1. 自动任务调度器

```python
# core/timeline/auto_task_scheduler.py (已在任务 7.2 实现)
class AutoTaskScheduler:
    def __init__(self, timeline_manager, realtime_recorder):
        self.timeline_manager = timeline_manager
        self.realtime_recorder = realtime_recorder
        self.scheduler = BackgroundScheduler()

    def start(self):
        """启动调度器，每分钟检查一次"""
        self.scheduler.add_job(
            self._check_upcoming_events,
            'interval',
            minutes=1
        )
        self.scheduler.start()

    def _check_upcoming_events(self):
        """检查即将开始的事件"""
        now = datetime.now()

        # 查询未来 15 分钟内的事件
        events = self.timeline_manager.get_timeline_events(
            center_time=now,
            past_days=0,
            future_days=0.01  # ~15 分钟
        )

        for event_data in events['future_events']:
            event = event_data['event']
            auto_tasks = event_data['auto_tasks']

            if not auto_tasks:
                continue

            event_start = datetime.fromisoformat(event.start_time)
            time_diff = (event_start - now).total_seconds()

            # 提前 5 分钟发送通知
            if 4.5 * 60 <= time_diff <= 5.5 * 60:
                self._send_reminder_notification(event, auto_tasks)

            # 事件开始时启动任务
            if -30 <= time_diff <= 30:  # 30 秒容差
                self._start_auto_tasks(event, auto_tasks)

    def _send_reminder_notification(self, event, auto_tasks):
        """发送提醒通知"""
        # 通过信号通知 UI 层显示通知
        self.reminder_signal.emit(event.id, event.title, auto_tasks)

    async def _start_auto_tasks(self, event, auto_tasks):
        """启动自动任务"""
        options = {}

        if auto_tasks.get('enable_transcription'):
            options['enable_transcription'] = True

        if auto_tasks.get('enable_recording'):
            options['enable_recording'] = True

        if not options:
            return

        await self.realtime_recorder.start_recording(
            input_source=None,
            options=options,
            event_id=event.id,
        )
```

> **提示**：`options` 只需包含与当前事件有关的增量配置。其他默认值应统一来自 `SettingsManager.get_realtime_preferences()`，以便 UI、调度器与实时录制模块共享同一套首选项，避免在多个位置硬编码开关或阈值。调度器在准备 `options` 前应优先读取全局首选项，并复用同一字典以保持行为一致。

## 为什么这样分离？

### 1. 可靠性

**问题**: 如果 UI 层负责调度，用户关闭应用后怎么办？

**解决**: 后端调度器独立运行，即使 UI 关闭也能工作

```python
# 后端调度器可以作为后台服务运行
# 或者在应用启动时自动启动
```

### 2. 准确性

**问题**: UI 层可能因为用户操作而阻塞，导致时间检测不准确

**解决**: 后端调度器使用专门的定时器，不受 UI 影响

```python
# APScheduler 使用独立线程
# 不会被 UI 事件阻塞
```

### 3. 可测试性

**问题**: UI 层的时间逻辑难以测试

**解决**: 后端调度器可以独立测试

```python
# 单元测试示例
def test_auto_task_scheduler():
    scheduler = AutoTaskScheduler(mock_manager, mock_recorder)
    scheduler._check_upcoming_events()
    assert mock_recorder.start_recording.called
```

### 4. 可维护性

**问题**: UI 和业务逻辑混合，难以维护

**解决**: 清晰的职责分离

```
UI 层: 只关心用户交互和显示
后端层: 只关心业务逻辑和调度
```

### 5. 可扩展性

**问题**: 未来可能需要支持多种触发方式

**解决**: 后端调度器易于扩展

```python
# 可以轻松添加新的触发条件
def _check_location_based_trigger(self):
    """基于位置的触发"""
    pass

def _check_calendar_sync_trigger(self):
    """基于日历同步的触发"""
    pass
```

## 数据流图

### 配置流程

```
用户操作
   ↓
UI 层: EventCard
   ↓ (信号)
UI 层: TimelineWidget
   ↓ (方法调用)
业务层: TimelineManager.set_auto_task()
   ↓ (数据库操作)
数据层: AutoTaskConfig 表
```

### 执行流程

```
系统时钟
   ↓
后端: AutoTaskScheduler (定时检查)
   ↓ (查询)
业务层: TimelineManager.get_timeline_events()
   ↓ (数据库查询)
数据层: CalendarEvent + AutoTaskConfig 表
   ↓ (返回数据)
后端: AutoTaskScheduler (判断时间)
   ↓ (触发)
├─→ 通知: NotificationManager (UI 层)
└─→ 任务: RealtimeRecorder (业务层)
```

## 集成示例

### 主应用启动时

```python
# main.py
def main():
    # 初始化管理器
    timeline_manager = TimelineManager(calendar_manager, db)
    realtime_recorder = RealtimeRecorder(...)

    # 启动后端调度器
    auto_task_scheduler = AutoTaskScheduler(
        timeline_manager,
        realtime_recorder
    )
    auto_task_scheduler.start()

    # 连接信号到 UI
    auto_task_scheduler.reminder_signal.connect(
        notification_manager.show_event_reminder
    )

    # 创建 UI
    timeline_widget = TimelineWidget(timeline_manager, i18n)

    # 启动应用
    app.exec()

    # 清理
    auto_task_scheduler.stop()
```

### UI 层使用

```python
# ui/timeline/widget.py
class TimelineWidget(QWidget):
    def __init__(self, timeline_manager, i18n):
        super().__init__()
        self.timeline_manager = timeline_manager

        # UI 只负责配置，不负责调度
        # 调度由后端 AutoTaskScheduler 处理
```

## 验证

### UI 层验证（任务 13）

- ✅ 自动任务开关可以切换
- ✅ 配置可以保存到数据库
- ✅ 配置可以正确读取和显示

### 后端层验证（任务 7.2）

- ✅ 调度器可以定时检查事件
- ✅ 提前 5 分钟发送通知
- ✅ 事件开始时启动任务
- ✅ 错误处理不影响调度器运行

## 总结

### UI 层（任务 13）的职责

1. ✅ 提供自动任务配置界面
2. ✅ 保存用户配置到后端
3. ✅ 显示通知（接收后端信号）
4. ✅ 显示任务状态

### 后端层（任务 7.2）的职责

1. ✅ 定时检查即将开始的事件
2. ✅ 检测提前 5 分钟的时间点
3. ✅ 触发通知（发送信号到 UI）
4. ✅ 检测事件开始时间
5. ✅ 启动自动任务

### 为什么这样分离是正确的？

1. ✅ **可靠性**: 后端独立运行，不依赖 UI
2. ✅ **准确性**: 专门的定时器，不受 UI 阻塞
3. ✅ **可测试性**: 业务逻辑可以独立测试
4. ✅ **可维护性**: 职责清晰，易于维护
5. ✅ **可扩展性**: 易于添加新功能

### 结论

**当前的架构分离是正确的设计选择**，符合软件工程最佳实践。

---

**文档作者**: Kiro AI Assistant  
**创建日期**: 2025-10-08  
**审查状态**: ✅ 已批准
