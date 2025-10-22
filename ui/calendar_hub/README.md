# Calendar Hub UI Implementation

## 概述 / Overview

本目录包含 EchoNote 日历中心功能的完整 UI 实现。日历中心提供了统一的界面来管理本地和外部日历事件，支持 Google Calendar 和 Outlook Calendar 同步。

This directory contains the complete UI implementation for the EchoNote Calendar Hub feature. The calendar hub provides a unified interface for managing local and external calendar events with support for Google Calendar and Outlook Calendar synchronization.

## 实现状态 / Implementation Status

✅ **已完成 / Completed** - 所有子任务已实现并通过验证

- 所有文件已创建并格式化
- 无语法错误
- 已集成业务逻辑
- 支持国际化

## Components

### 1. CalendarHubWidget (`widget.py`)

The main calendar hub widget that serves as the container for all calendar functionality.

**Features:**

- View switching (Month/Week/Day)
- Date navigation (Previous/Today/Next)
- Connected accounts display
- Event creation button
- Add account button

**Key Methods:**

- `_on_view_changed(view)`: Handle view switching
- `_on_date_changed(date)`: Handle date changes from calendar views
- `_on_event_clicked(event_id)`: Handle event clicks
- `_show_event_dialog(event)`: Show event creation/editing dialog
- `_create_event(event_data)`: Create new event
- `_update_event(event_data)`: Update existing event
- `show_add_account_dialog()`: Show account connection dialog
- `add_connected_account(provider, email)`: Add account badge
- `remove_connected_account(provider)`: Remove account badge

### 2. Calendar Views (`calendar_view.py`)

Three calendar view implementations for different time perspectives.

#### MonthView

- Displays a full month calendar grid
- Shows event indicators (colored dots) for each day
- Supports navigation between months
- Groups events by day

#### WeekView

- Displays a week with 7 day columns
- Shows event cards with time and title
- Supports navigation between weeks
- Sorts events by start time

#### DayView

- Displays all events for a single day
- Shows detailed event cards
- Supports navigation between days
- Displays "No events" message when empty

**Common Features:**

- Color-coded events by source (local/Google/Outlook)
- Event click handling
- Date navigation
- Automatic refresh

### 3. EventDialog (`event_dialog.py`)

Dialog for creating and editing calendar events.

**Form Fields:**

- Title (required)
- Event Type (Event/Task/Appointment)
- Start Time (required)
- End Time (required)
- Location (optional)
- Attendees (optional, comma-separated emails)
- Description (optional)
- Reminder (optional, multiple options)

**Features:**

- Form validation
- Email format validation
- Time range validation
- Sync to external calendars (checkboxes for connected accounts)
- Edit mode support

### 4. OAuth Authorization (`oauth_dialog.py`)

Dialogs for handling OAuth authorization flow with external calendar services.

#### OAuthDialog

- Guides user through OAuth authorization
- Opens browser for authorization
- Runs local HTTP server to receive callback
- Handles authorization code exchange
- Shows progress and status updates

#### OAuthResultDialog

- Displays authorization result (success/failure)
- Shows appropriate icon and message

**Features:**

- Browser integration
- Local callback server (configurable callback port, default 8080)
- Thread-safe callback handling
- Error handling and user feedback

## Integration

### With CalendarManager

The calendar hub integrates with the `CalendarManager` business logic:

```python
# Create event
event_id = calendar_manager.create_event(event_data, sync_to=['google'])

# Update event
calendar_manager.update_event(event_id, event_data)

# Get events
events = calendar_manager.get_events(start_date, end_date)

# Sync external calendar
calendar_manager.sync_external_calendar('google')
```

### With OAuth Adapters

OAuth flow integration with calendar sync adapters:

```python
# Get authorization request payload
auth_request = adapter.get_authorization_url()

# Launch dialog with state & PKCE verifier
dialog = OAuthDialog(
    provider='google',
    authorization_url=auth_request['authorization_url'],
    i18n=i18n_manager,
    state=auth_request['state'],
    code_verifier=auth_request['code_verifier'],
)

# Exchange code for token
token_data = adapter.exchange_code_for_token(
    code,
    code_verifier=auth_request['code_verifier'],
)
```

## Color Scheme

Events are color-coded by source:

- **Local events**: Blue (#2196F3)
- **Google Calendar**: Red (#EA4335)
- **Outlook Calendar**: Orange (#FF6F00)

## Internationalization

All UI text supports internationalization through the `I18nQtManager`:

```python
self.i18n.t('calendar_hub.create_event')
self.i18n.t('calendar_hub.view_week')
```

Translation keys are defined in `resources/translations/*.json`.

## Usage Example

```python
from ui.calendar_hub import CalendarHubWidget
from core.calendar.manager import CalendarManager
from utils.i18n import I18nQtManager

# Initialize managers
calendar_manager = CalendarManager(db_connection, sync_adapters)
i18n = I18nQtManager()

# Create calendar hub widget
calendar_hub = CalendarHubWidget(calendar_manager, i18n)

# Add to main window
main_window.add_page('calendar_hub', calendar_hub)
```

## Requirements Satisfied

This implementation satisfies the following requirements from the design document:

- **需求 3.1**: Local calendar event storage
- **需求 3.2**: Event creation with required fields
- **需求 3.3**: Event creation with optional fields
- **需求 3.4-3.7**: OAuth authorization flow
- **需求 3.10-3.11**: Event synchronization to external calendars
- **需求 3.13**: Month/Week/Day view switching
- **需求 3.15**: Unified event display with color coding
- **需求 3.18-3.19**: External calendar synchronization

## 代码质量 / Code Quality

### 验证结果 / Validation Results

- ✅ 所有文件通过语法检查 / All files pass syntax check
- ✅ 无错误 / No errors
- ⚠️ 仅有空白行格式警告（不影响功能）/ Only whitespace warnings (non-functional)
- ✅ 符合 PEP 8 代码规范 / Follows PEP 8 style guide
- ✅ 完整的类型注解 / Complete type annotations
- ✅ 详细的文档字符串 / Comprehensive docstrings

### 测试覆盖 / Test Coverage

实现包含以下验证点：

- UI 组件正常显示
- 视图切换功能
- 日期导航功能
- 事件 CRUD 操作
- OAuth 授权流程
- 外部日历同步

## 未来增强 / Future Enhancements

后续迭代的潜在改进：

1. 拖放事件重新安排 / Drag-and-drop event rescheduling
2. 事件重复编辑 / Event recurrence editing
3. 日历导出（iCal 格式）/ Calendar export (iCal format)
4. 事件搜索和过滤 / Event search and filtering
5. 多日历支持 / Multiple calendar support
6. 事件提醒/通知 / Event reminders/notifications
7. 冲突检测 / Conflict detection
8. 时区支持 / Time zone support

## 维护说明 / Maintenance Notes

### 依赖关系 / Dependencies

- **PyQt6**: UI 框架 / UI framework
- **CalendarManager**: 业务逻辑管理器 / Business logic manager
- **I18nQtManager**: 国际化管理器 / Internationalization manager
- **OAuth Adapters**: 外部日历同步适配器 / External calendar sync adapters

### 关键接口 / Key Interfaces

所有 UI 组件都遵循以下设计原则：

- 信号/槽机制用于组件通信 / Signal/slot mechanism for component communication
- 业务逻辑与 UI 分离 / Business logic separated from UI
- 支持国际化 / Internationalization support
- 错误处理和用户反馈 / Error handling and user feedback

### 更新日志 / Changelog

**2025-10-08**

- ✅ 初始实现完成 / Initial implementation completed
- ✅ 所有子任务完成 / All sub-tasks completed
- ✅ 代码格式化和验证 / Code formatted and validated
- ✅ 文档更新 / Documentation updated
