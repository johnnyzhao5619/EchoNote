# Timeline UI - 技术文档

## 架构设计

### 组件层次结构

```
TimelineWidget (主容器)
├── Header (搜索和过滤)
│   ├── QLineEdit (搜索框)
│   ├── QPushButton (搜索按钮)
│   ├── QComboBox (事件类型过滤)
│   └── QComboBox (来源过滤)
├── QScrollArea (滚动区域)
│   └── Timeline Container
│       ├── EventCard (未来事件) × N
│       ├── CurrentTimeIndicator (当前时间线)
│       └── EventCard (过去事件) × N
└── Dialogs
    ├── AudioPlayerDialog
    └── TranscriptViewerDialog
```

### 数据流

```
TimelineManager (业务逻辑)
    ↓
TimelineWidget (UI 控制器)
    ↓
EventCard (事件卡片)
    ↓
User Actions (用户操作)
    ↓
Signals (Qt 信号)
    ↓
TimelineManager (更新数据)
```

## 性能优化

### 1. 虚拟滚动

虽然使用了 QScrollArea，但实现了以下优化：

- **分页加载**：每次只加载 50 个事件
- **延迟加载**：滚动到 80% 时才加载下一页
- **懒加载附件**：过去事件的附件信息仅在卡片显示时加载

### 2. 内存管理

```python
# 动态创建和销毁卡片
def clear_timeline(self):
    for card in self.event_cards:
        self.timeline_layout.removeWidget(card)
        card.deleteLater()  # Qt 的内存管理
    self.event_cards.clear()
```

### 3. 信号优化

使用 Qt 的信号/槽机制避免轮询：

```python
# 自动更新 UI，无需手动刷新
self.player.positionChanged.connect(self._on_position_changed)
self.i18n.language_changed.connect(self.update_translations)
```

## 国际化实现

### 翻译键命名规范

```
{模块}.{功能}_{类型}

示例：
- timeline.search_placeholder
- transcript.viewer_title
- common.error
```

### 动态语言切换

```python
def update_translations(self):
    """当语言改变时更新所有 UI 文本"""
    self.search_input.setPlaceholderText(
        self.i18n.t('timeline.search_placeholder')
    )
    # 递归更新所有子组件
    for card in self.event_cards:
        if hasattr(card, 'update_translations'):
            card.update_translations()
```

## 样式设计

### CSS-like 样式

使用 Qt 样式表实现现代化 UI：

```python
self.setStyleSheet("""
    EventCard {
        background-color: white;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 15px;
    }
    EventCard:hover {
        border-color: #2196F3;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
""")
```

### 颜色方案

- **主色调**：#2196F3 (蓝色)
- **成功色**：#4CAF50 (绿色)
- **警告色**：#FF9800 (橙色)
- **错误色**：#F44336 (红色)
- **中性色**：#666, #888, #E0E0E0

## 错误处理

### 分层错误处理

1. **UI 层**：显示用户友好的错误消息
2. **业务逻辑层**：记录详细错误日志
3. **数据层**：抛出具体异常

```python
try:
    self.timeline_manager.set_auto_task(event_id, config)
    logger.info(f"Auto-task config updated for event: {event_id}")
except Exception as e:
    logger.error(f"Failed to update auto-task config: {e}")
    QMessageBox.critical(self, "错误", str(e))
```

## 测试建议

### 单元测试

```python
# 测试事件卡片创建
def test_event_card_creation():
    event_data = {
        'event': mock_event,
        'auto_tasks': {}
    }
    card = EventCard(event_data, is_future=True, i18n=mock_i18n)
    assert card.is_future == True
    assert card.event == mock_event
```

### 集成测试

```python
# 测试时间线加载
def test_timeline_load():
    widget = TimelineWidget(timeline_manager, i18n)
    widget.load_timeline_events()
    assert len(widget.event_cards) > 0
```

### UI 测试

- 手动测试搜索功能
- 验证过滤器工作正常
- 测试音频播放器
- 测试转录查看器
- 验证多语言切换

## 依赖关系

### 核心依赖

```python
# PyQt6 组件
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLineEdit,
    QComboBox, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# 业务逻辑
from core.timeline.manager import TimelineManager
from utils.i18n import I18nQtManager
```

### 可选依赖

- **音频编解码器**：系统音频库（macOS/Windows 自带）
- **字体**：系统默认字体

## 部署注意事项

### macOS

```bash
# 确保包含 Qt 多媒体插件
pyinstaller --add-binary '/path/to/Qt/plugins/multimedia:multimedia' main.py
```

### Windows

```bash
# 包含必要的 DLL
pyinstaller --add-binary 'C:\Qt\plugins\multimedia;multimedia' main.py
```

## 性能指标

### 目标性能

- **初始加载**：< 500ms (50 个事件)
- **滚动流畅度**：60 FPS
- **搜索响应**：< 200ms
- **内存占用**：< 100MB (1000 个事件)

### 实际测试

需要在实际环境中测试：

```python
import time

start = time.time()
widget.load_timeline_events()
end = time.time()
print(f"加载时间: {(end - start) * 1000:.2f}ms")
```

## 维护指南

### 添加新功能

1. 在 `TimelineWidget` 中添加 UI 元素
2. 在 `TimelineManager` 中添加业务逻辑
3. 连接信号和槽
4. 添加翻译键到所有语言文件
5. 更新文档

### 修复 Bug

1. 在日志中查找错误信息
2. 添加单元测试重现问题
3. 修复代码
4. 验证测试通过
5. 更新 CHANGELOG

### 代码审查清单

- [ ] 代码符合 PEP 8 规范
- [ ] 所有函数都有文档字符串
- [ ] 添加了适当的日志记录
- [ ] 错误处理完善
- [ ] 翻译键已添加到所有语言
- [ ] 没有硬编码的字符串
- [ ] 信号/槽连接正确
- [ ] 内存泄漏检查通过

## 常见问题

### Q: 为什么使用 QScrollArea 而不是 QListView？

A: QScrollArea 提供更灵活的布局控制，可以轻松实现自定义卡片样式和当前时间指示器。

### Q: 如何优化大量事件的性能？

A: 使用分页加载和虚拟滚动。考虑实现真正的虚拟列表（只渲染可见项）。

### Q: 音频播放器支持哪些格式？

A: 取决于系统的音频编解码器。通常支持 MP3, WAV, M4A, OGG。

### Q: 如何添加新的过滤器？

A: 在 `create_header()` 中添加新的 QComboBox，并在 `_on_filter_changed()` 中处理。

## 参考资料

- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html)
- [Material Design Guidelines](https://material.io/design)
- [EchoNote Design Document](../../.kiro/specs/echonote-core/design.md)
