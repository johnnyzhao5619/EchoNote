# Timeline UI Implementation

## Overview

The Timeline UI provides a comprehensive view of past and future calendar events with integrated recording and transcription artifacts.

## Components

### 1. TimelineWidget (`widget.py`)

Main timeline interface with the following features:

- **Vertical scrolling timeline** with current time indicator
- **Search functionality** to find events by keyword
  - 点击搜索按钮或在搜索框中按下回车都会刷新时间线，即使关键字未变化，可作为手动刷新手段
- **Filter controls** for event type and source
- **Lazy loading** with pagination（默认每页 50 条，可在设置页调整）
- **Configurable time window**（默认展示当前时间前后各 30 天，可在设置页调整）
- **Virtual scrolling** for smooth performance with large datasets
- **加载期间的操作自动排队**，如果用户在刷新中发起新的搜索或过滤操作，会在当前加载完成后自动兑现，无需重复点击

**Key Methods:**

- `load_timeline_events()` - Load events from TimelineManager
- `_on_search()` - Handle search queries
- `_on_filter_changed()` - Apply filters
- `_on_scroll()` - Trigger pagination on scroll

### 2. EventCard (`event_card.py`)

Event card component with different layouts for past and future events:

**Future Events:**

- Event information (title, time, location, attendees)
- Auto-task toggles (enable transcription, enable recording, enable translation with target language selection)
- Saves configuration to TimelineManager

**Past Events:**

- Event information
- Artifact buttons (play recording, view transcript)
- Lazy loading of artifacts

**CurrentTimeIndicator:**

- Visual separator showing current time in timeline

### 3. AudioPlayer (`audio_player.py`)

Built-in audio player for recordings:

- **Playback controls** (play/pause)
- **Progress slider** with seek functionality
- **Volume control**
- **Time display** (current/total)
- **Error handling** for missing or unsupported files
- **Automatic reset on errors** so progress indicators clear and playback controls return to the initial state when decoding fails
- **Immediate feedback** when recordings are missing so users understand the failure reason
- **Instant translation refresh** when the application language changes


Uses PyQt6's QMediaPlayer and QAudioOutput.

> ℹ️ If QtMultimedia components are unavailable (e.g., package not installed),
> the timeline continues to load events, but playback controls are disabled and
> the user sees a localized warning explaining the limitation.

> ⚠️ When the audio player dialog fails to initialize (e.g., corrupted media or
> missing dependencies), the widget now surfaces a localized critical dialog
> summarizing the exception and suggests checking the recording file and
> application logs。发生错误时不会缓存对话框实例，避免残留的失效引用。

### 4. TranscriptViewer (`transcript_viewer.py`)

Transcript text viewer with:

- **Read-only text display**
- **Search functionality** with highlighting
- **Copy to clipboard**
- **Export to file** (txt, md)
- **Error handling** for missing files
- **Non-modal dialog reuse** so opening the same artifact reactivates the existing window and releases resources when closed

## Integration

### Signals

**TimelineWidget:**

- `event_selected(str)` - Event ID selected
- `auto_task_changed(str, dict)` - Auto-task config changed

**EventCard:**

- `auto_task_changed(str, dict)` - Auto-task config changed
- `view_recording(str)` - Recording file path
- `view_transcript(str)` - Transcript file path

**AudioPlayer:**

- `playback_error(str)` - Playback error message

**TranscriptViewer:**

- `export_requested(str)` - Export file path

### Business Logic Integration

The timeline UI integrates with:

1. **TimelineManager** - Event data, search, auto-task configuration
2. **CalendarManager** - Event CRUD operations (via TimelineManager)
3. **I18nQtManager** - Multi-language support

### Data Contract

- 搜索模式下，UI 通过调用 `TimelineManager.search_events(..., include_future_auto_tasks=True)`
  获取结果。返回列表中的未来事件条目将额外携带 `auto_tasks` 字段，其结构与
  `get_timeline_events()` 中未来事件一致。
- 未来事件在时间线上会按照开始时间从最近到最远的顺序排列，搜索模式与常规模式
  保持一致，最靠近当前时间指示器的卡片对应即将开始的事件。
- `auto_tasks` 始终提供完整的自动任务配置（已保存的配置或 `_default_auto_task_config`
  缺省值），UI 不再直接访问 `_get_auto_task_map()`。
- 历史事件的返回结构保持不变，不包含 `auto_tasks` 字段。

## Configuration

- `timeline.past_days`：控制向前加载多少天的事件，默认 30。
- `timeline.future_days`：控制向后加载多少天的事件，默认 30。
- `timeline.page_size`：分页加载的事件数量，默认 50。

时间线顶部的日期范围选择器会在构建时根据上述 past/future 配置自动计算默认范围，
并且在需要重置控件时同样会重新同步，确保界面与设置保持一致。

当 `TimelineWidget` 接收到 `SettingsManager` 或底层 `ConfigManager` 时，会在初始化期间读取这些设置，并在调用 `load_timeline_events()` 时应用。若设置不存在或值非法，将回退到默认配置，确保时间线功能稳定。

加载流程在最新版本中进一步增强：当 `TimelineWidget` 正在等待时间线数据返回时，用户触发的刷新请求会记录下来。当前加载完成后，这些请求会立即通过 `QTimer.singleShot(0, ...)` 重新调度，从新的调用栈发起最新一次刷新，避免重复工作和潜在的递归调用；若期间既有分页加载又有需要重置的刷新请求，系统会优先保留重置指令，确保最新的过滤条件和设置立即生效。

## Translation Keys

All UI text is internationalized using the following keys:

### Timeline

- `timeline.search_placeholder`
- `timeline.search`
- `timeline.filter_all`, `filter_event`, `filter_task`, `filter_appointment`
- `timeline.source_all`, `source_local`, `source_google`, `source_outlook`
- `timeline.current_time`
- `timeline.enable_transcription`, `enable_recording`, `enable_translation`
- `timeline.translation_target_label`
- `timeline.play_recording`, `view_transcript`
- `timeline.no_artifacts`
- `timeline.audio_player_title`
- `timeline.audio_player.*` for button labels, tooltips, and volume indicator

### Transcript

- `transcript.viewer_title`
- `transcript.search_placeholder`, `search`, `clear_search`
- `transcript.copy_all`, `copied`, `export`
- `transcript.export_dialog_title`, `export_success`
- `transcript.load_error`

## Usage Example

```python
from ui.timeline import TimelineWidget
from core.timeline.manager import TimelineManager
from utils.i18n import I18nQtManager
from core.settings.manager import SettingsManager
from config.app_config import ConfigManager

# Initialize managers
timeline_manager = TimelineManager(calendar_manager, db_connection)
i18n = I18nQtManager()
config_manager = ConfigManager()
settings_manager = SettingsManager(config_manager)

# Create timeline widget（可选传入 settings_manager 或 ConfigManager）
timeline_widget = TimelineWidget(
    timeline_manager,
    i18n,
    settings_manager=settings_manager,
)

# Connect signals
timeline_widget.auto_task_changed.connect(on_auto_task_changed)

# Add to main window
main_window.add_page('timeline', timeline_widget)
```

## Requirements Satisfied

This implementation satisfies the following requirements from the spec:

- **需求 4.1** - Timeline view with current time indicator
- **需求 4.2** - Display future events
- **需求 4.3** - Display past events
- **需求 4.4** - Future event cards with auto-task toggles
- **需求 4.5** - Auto-task configuration
- **需求 4.8** - Past event cards
- **需求 4.9** - Recording playback button
- **需求 4.10** - Transcript view button
- **需求 4.11** - Built-in audio player
- **需求 4.12** - Transcript viewer with copy/export
- **需求 4.13** - Search functionality
- **需求 4.14** - Search result highlighting
- **需求 4.15** - Virtual scrolling
- **需求 4.16** - Pagination

## Code Quality

### Standards Compliance

All code follows Python best practices:

- **PEP 8** - Code style guidelines (line length ≤ 79 characters)
- **Type Hints** - Full type annotations for better IDE support
- **Docstrings** - Comprehensive documentation for all classes and methods
- **Logging** - Structured logging for debugging and monitoring
- **Error Handling** - Graceful error handling with user feedback

### Testing

The implementation has been verified for:

- ✅ No syntax errors
- ✅ No import errors
- ✅ Proper signal/slot connections
- ✅ Translation key coverage
- ✅ Code formatting compliance

### Known Issues

None. All diagnostics have been resolved.

## Technical Documentation

For detailed technical information, please refer to:

- **TECHNICAL.md** - Architecture, performance optimization, and best practices
- **VIRTUAL_SCROLLING_DECISION.md** - Why we chose pagination over QAbstractItemModel
- **ARCHITECTURE_SEPARATION.md** - UI/Backend responsibility separation
- **CHANGELOG.md** - Version history and changes
- **REVIEW_REPORT.md** - Implementation review and verification
- **IMPLEMENTATION_SUMMARY.md** - Complete implementation summary

## Future Enhancements

Potential improvements:

1. **Caching** - Cache loaded events to reduce database queries
2. **Animations** - Smooth transitions when adding/removing cards
3. **Drag & Drop** - Reorder events or drag to calendar
4. **Keyboard Shortcuts** - Navigate timeline with keyboard
5. **Export Timeline** - Export entire timeline to PDF/HTML
6. **Event Details Dialog** - Full event details in modal dialog
7. **Performance Optimization** - Further optimize virtual scrolling for 1000+ events
