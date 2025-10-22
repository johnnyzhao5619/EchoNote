# 日历中心快速参考 / Calendar Hub Quick Reference

## 快速开始 / Quick Start

### 基本使用 / Basic Usage

```python
from ui.calendar_hub import CalendarHubWidget
from core.calendar.manager import CalendarManager
from utils.i18n import I18nQtManager

# 初始化管理器 / Initialize managers
calendar_manager = CalendarManager(db_connection, sync_adapters)
i18n = I18nQtManager()

# 创建日历中心组件 / Create calendar hub widget
calendar_hub = CalendarHubWidget(calendar_manager, i18n)

# 添加到主窗口 / Add to main window
main_window.add_page('calendar_hub', calendar_hub)
```

---

## 核心组件 / Core Components

### 1. CalendarHubWidget

主日历界面组件 / Main calendar interface component

```python
# 创建实例 / Create instance
widget = CalendarHubWidget(calendar_manager, i18n, parent)

# 添加已连接账户 / Add connected account
widget.add_connected_account('google', 'user@gmail.com')

# 移除已连接账户 / Remove connected account
widget.remove_connected_account('google')

# 刷新视图 / Refresh view
widget._refresh_current_view()
```

**信号 / Signals**:

- `view_changed(str)`: 视图切换时触发 / Emitted on view change
- `date_changed(datetime)`: 日期改变时触发 / Emitted on date change
- `create_event_requested()`: 请求创建事件时触发 / Emitted on create event request
- `add_account_requested()`: 请求添加账户时触发 / Emitted on add account request

---

### 2. MonthView / WeekView / DayView

日历视图组件 / Calendar view components

```python
# 创建月视图 / Create month view
month_view = MonthView(calendar_manager, i18n)

# 设置日期 / Set date
month_view.set_date(datetime.now())

# 导航 / Navigation
month_view.next_month()
month_view.prev_month()
month_view.today()

# 刷新视图 / Refresh view
month_view.refresh_view()
```

**信号 / Signals**:

- `date_changed(datetime)`: 日期改变时触发 / Emitted on date change
- `event_clicked(str)`: 事件被点击时触发 / Emitted on event click

---

### 3. EventDialog

事件创建/编辑对话框 / Event creation/editing dialog

```python
# 创建新事件 / Create new event
dialog = EventDialog(i18n, connected_accounts, None, parent)

# 编辑现有事件 / Edit existing event
event_data = {
    'id': 'event_123',
    'title': 'Meeting',
    'event_type': 'Event',
    'start_time': datetime.now(),
    'end_time': datetime.now() + timedelta(hours=1),
    # ... 其他字段 / other fields
}
dialog = EventDialog(i18n, connected_accounts, event_data, parent)

# 显示对话框并获取结果 / Show dialog and get result
if dialog.exec() == QDialog.DialogCode.Accepted:
    result = dialog.get_event_data()
    # 处理结果 / Process result
```

**返回数据结构 / Return Data Structure**:

```python
{
    'title': str,              # 必填 / Required
    'event_type': str,         # Event/Task/Appointment
    'start_time': datetime,    # 必填 / Required
    'end_time': datetime,      # 必填 / Required
    'location': str | None,    # 可选 / Optional
    'attendees': list | None,  # 可选 / Optional
    'description': str | None, # 可选 / Optional
    'reminder_minutes': int | None,  # 可选 / Optional
    'sync_to': list | None     # ['google', 'outlook']
}
```

---

### 4. OAuthDialog

OAuth 授权对话框 / OAuth authorization dialog

```python
# 创建 OAuth 对话框 / Create OAuth dialog
dialog = OAuthDialog(
    provider='google',
    authorization_url='https://...',
    i18n=i18n,
    parent=parent
)

# 连接信号 / Connect signals
dialog.authorization_complete.connect(on_auth_complete)
dialog.authorization_failed.connect(on_auth_failed)

# 显示对话框 / Show dialog
dialog.exec()
```

**信号 / Signals**:

- `authorization_complete(str)`: 授权成功，返回授权码 / Auth success, returns code
- `authorization_failed(str)`: 授权失败，返回错误信息 / Auth failed, returns error

---

## 事件颜色方案 / Event Color Scheme

```python
source_colors = {
    'local': '#2196F3',    # 蓝色 / Blue
    'google': '#EA4335',   # 红色 / Red
    'outlook': '#FF6F00'   # 橙色 / Orange
}
```

---

## 国际化键值 / Internationalization Keys

### 日历中心 / Calendar Hub

```python
'calendar_hub.title'              # 日历中心
'calendar_hub.view_month'         # 月
'calendar_hub.view_week'          # 周
'calendar_hub.view_day'           # 日
'calendar_hub.today'              # 今天
'calendar_hub.connected_accounts' # 已连接
'calendar_hub.add_account'        # 添加账户
'calendar_hub.create_event'       # 创建事件
```

### 事件类型 / Event Types

```python
'calendar_hub.event_types.event'       # 事件
'calendar_hub.event_types.task'        # 任务
'calendar_hub.event_types.appointment' # 约会
```

### 通用 / Common

```python
'common.ok'      # 确定
'common.cancel'  # 取消
'common.save'    # 保存
'common.delete'  # 删除
'common.edit'    # 编辑
```

---

## 常见任务 / Common Tasks

### 创建事件 / Create Event

```python
# 1. 准备事件数据 / Prepare event data
event_data = {
    'title': '团队会议',
    'event_type': 'Event',
    'start_time': datetime(2025, 10, 8, 14, 0),
    'end_time': datetime(2025, 10, 8, 15, 0),
    'location': '会议室 A',
    'attendees': ['user1@example.com', 'user2@example.com'],
    'description': '讨论项目进展',
    'reminder_minutes': 15,
    'sync_to': ['google']  # 同步到 Google Calendar
}

# 2. 调用 CalendarManager / Call CalendarManager
event_id = calendar_manager.create_event(
    event_data,
    sync_to=event_data.pop('sync_to', None)
)

# 3. 刷新视图 / Refresh view
calendar_hub._refresh_current_view()
```

---

### 更新事件 / Update Event

```python
# 1. 准备更新数据 / Prepare update data
event_id = 'event_123'
update_data = {
    'title': '更新后的标题',
    'start_time': datetime(2025, 10, 8, 15, 0),
    'end_time': datetime(2025, 10, 8, 16, 0)
}

# 2. 调用 CalendarManager / Call CalendarManager
calendar_manager.update_event(event_id, update_data)

# 3. 刷新视图 / Refresh view
calendar_hub._refresh_current_view()
```

---

### 连接外部日历 / Connect External Calendar

```python
# 1. 获取同步适配器 / Get sync adapter
adapter = calendar_manager.sync_adapters['google']

# 2. 获取授权请求 / Get authorization request
auth_request = adapter.get_authorization_url()

# 3. 显示 OAuth 对话框 / Show OAuth dialog
oauth_dialog = OAuthDialog(
    'google',
    auth_request['authorization_url'],
    i18n,
    parent,
    state=auth_request['state'],
    code_verifier=auth_request['code_verifier'],
)
oauth_dialog.authorization_complete.connect(
    lambda code, verifier: complete_oauth(code, verifier)
)
oauth_dialog.exec()

# 4. 完成授权 / Complete authorization
def complete_oauth(code, code_verifier):
    token_data = adapter.exchange_code_for_token(
        code,
        code_verifier=code_verifier,
    )
    email = token_data.get('email', 'user@example.com')
    calendar_hub.add_connected_account('google', email)
    calendar_manager.sync_external_calendar('google')
```

---

### 同步外部日历 / Sync External Calendar

```python
# 手动触发同步 / Manually trigger sync
calendar_manager.sync_external_calendar('google')

# 刷新视图以显示新事件 / Refresh view to show new events
calendar_hub._refresh_current_view()
```

---

## 错误处理 / Error Handling

### 事件创建失败 / Event Creation Failed

```python
try:
    event_id = calendar_manager.create_event(event_data)
except Exception as e:
    logger.error(f"Error creating event: {e}")
    QMessageBox.critical(
        parent,
        "Error",
        f"Failed to create event: {str(e)}"
    )
```

---

### OAuth 授权失败 / OAuth Authorization Failed

```python
def handle_oauth_error(provider, error):
    logger.error(f"OAuth error for {provider}: {error}")
    QMessageBox.critical(
        parent,
        "Authorization Failed",
        f"Failed to connect {provider} calendar:\n{error}"
    )
```

---

### 事件加载失败 / Event Loading Failed

```python
try:
    events = calendar_manager.get_events(start_date, end_date)
except Exception as e:
    logger.error(f"Error loading events: {e}")
    events = []  # 使用空列表作为后备 / Use empty list as fallback
```

---

## 调试技巧 / Debugging Tips

### 启用详细日志 / Enable Verbose Logging

```python
import logging

# 设置日志级别 / Set log level
logging.getLogger('echonote.ui.calendar_hub').setLevel(logging.DEBUG)
logging.getLogger('echonote.calendar.manager').setLevel(logging.DEBUG)
```

---

### 检查事件数据 / Inspect Event Data

```python
# 打印事件详情 / Print event details
event = calendar_manager.get_event(event_id)
print(f"Event: {event.title}")
print(f"Start: {event.start_time}")
print(f"End: {event.end_time}")
print(f"Source: {event.source}")
```

---

### 验证 OAuth 配置 / Verify OAuth Configuration

```python
# 检查同步适配器 / Check sync adapters
print(f"Available adapters: {calendar_manager.sync_adapters.keys()}")

# 检查授权请求 / Check authorization request
adapter = calendar_manager.sync_adapters['google']
auth_request = adapter.get_authorization_url()
print(f"Auth URL: {auth_request['authorization_url']}")
print(f"State: {auth_request['state']}")
```

---

## 性能优化建议 / Performance Optimization Tips

### 1. 事件加载优化 / Event Loading Optimization

```python
# 只加载可见范围的事件 / Load only visible events
start_date = current_date - timedelta(days=7)
end_date = current_date + timedelta(days=7)
events = calendar_manager.get_events(start_date, end_date)
```

---

### 2. 视图刷新优化 / View Refresh Optimization

```python
# 避免频繁刷新 / Avoid frequent refreshes
# 使用防抖机制 / Use debouncing
from PyQt6.QtCore import QTimer

self.refresh_timer = QTimer()
self.refresh_timer.setSingleShot(True)
self.refresh_timer.timeout.connect(self._do_refresh)

def request_refresh(self):
    self.refresh_timer.start(300)  # 300ms 延迟 / 300ms delay
```

---

### 3. 缓存事件数据 / Cache Event Data

```python
# 缓存最近加载的事件 / Cache recently loaded events
self.event_cache = {}

def get_events_cached(self, start_date, end_date):
    cache_key = f"{start_date}_{end_date}"
    if cache_key not in self.event_cache:
        self.event_cache[cache_key] = (
            calendar_manager.get_events(start_date, end_date)
        )
    return self.event_cache[cache_key]
```

---

## 常见问题 / FAQ

### Q: 如何添加新的日历服务？ / How to add a new calendar service?

A: 实现一个新的同步适配器并注册到 CalendarManager：

```python
class NewCalendarAdapter:
    def get_authorization_url(self):
        # 实现 / Implementation
        pass

    def exchange_code_for_token(self, code):
        # 实现 / Implementation
        pass

# 注册适配器 / Register adapter
calendar_manager.sync_adapters['new_service'] = NewCalendarAdapter()
```

---

### Q: 如何自定义事件颜色？ / How to customize event colors?

A: 修改 `calendar_view.py` 中的 `source_colors` 字典：

```python
self.source_colors = {
    'local': '#YOUR_COLOR',
    'google': '#YOUR_COLOR',
    'outlook': '#YOUR_COLOR',
    'new_service': '#YOUR_COLOR'
}
```

---

### Q: 如何处理时区？ / How to handle time zones?

A: 当前实现使用本地时区。要支持多时区：

```python
from datetime import timezone
import pytz

# 转换到特定时区 / Convert to specific timezone
tz = pytz.timezone('Asia/Shanghai')
local_time = event.start_time.astimezone(tz)
```

---

## 相关资源 / Related Resources

- **设计文档 / Design Document**: `.kiro/specs/echonote-core/design.md`
- **需求文档 / Requirements Document**: `.kiro/specs/echonote-core/requirements.md`
- **任务列表 / Task List**: `.kiro/specs/echonote-core/tasks.md`
- **实现总结 / Implementation Summary**: `ui/calendar_hub/IMPLEMENTATION_SUMMARY.md`
- **完整文档 / Full Documentation**: `ui/calendar_hub/README.md`

---

**版本 / Version**: 1.0  
**最后更新 / Last Updated**: 2025-10-08
