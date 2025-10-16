# 转录结果查看器技术设计文档

## 概述

转录结果查看器是一个独立的对话框窗口，用于显示、编辑和导出批量转录任务的结果。设计遵循 EchoNote 的整体架构原则，完全集成国际化和主题系统。

### 设计原则

1. **模块化**：查看器作为独立组件，可被批量转录和时间线模块复用
2. **响应式**：支持窗口大小调整，自适应布局
3. **性能优先**：使用虚拟滚动处理长文本
4. **用户体验**：流畅的编辑体验，即时的视觉反馈
5. **一致性**：完全遵循应用的主题和语言设置

### 技术栈

- **UI 框架**：PyQt6
- **文本编辑**：QTextEdit（支持富文本和纯文本模式）
- **搜索高亮**：QTextDocument + QTextCursor
- **格式转换**：复用 core/transcription/format_converter.py
- **国际化**：集成 utils/i18n.py
- **主题**：使用应用全局 QSS 样式表

## 架构设计

### 组件结构

```
ui/batch_transcribe/
├── transcript_viewer.py      # 主查看器窗口
└── search_widget.py          # 搜索工具栏组件
```

### 类图

```
┌─────────────────────────────────────────┐
│      TranscriptViewerDialog             │
│  (QDialog)                              │
├─────────────────────────────────────────┤
│  - task_id: str                         │
│  - task_data: dict                      │
│  - transcript_content: str              │
│  - is_modified: bool                    │
│  - is_edit_mode: bool                   │
│  - text_edit: QTextEdit                 │
│  - search_widget: SearchWidget          │
├─────────────────────────────────────────┤
│  + __init__(task_id, parent)            │
│  + load_transcript()                    │
│  + toggle_edit_mode()                   │
│  + save_changes()                       │
│  + export_as(format)                    │
│  + copy_all()                           │
│  + apply_theme()                        │
│  + update_language()                    │
└─────────────────────────────────────────┘
           │
           │ contains
           ▼
┌─────────────────────────────────────────┐
│         SearchWidget                    │
│  (QWidget)                              │
├─────────────────────────────────────────┤
│  - search_input: QLineEdit              │
│  - match_count: int                     │
│  - current_match: int                   │
│  - case_sensitive: bool                 │
├─────────────────────────────────────────┤
│  + search(query)                        │
│  + find_next()                          │
│  + find_previous()                      │
│  + highlight_matches()                  │
│  + clear_highlights()                   │
└─────────────────────────────────────────┘
```

## 核心组件设计

### 1. TranscriptViewerDialog

**职责**：

- 显示转录结果和元数据
- 管理编辑模式切换
- 处理保存和导出操作
- 响应主题和语言变更

**关键方法**：

```python
class TranscriptViewerDialog(QDialog):
    def __init__(self, task_id: str, parent=None):
        """
        初始化查看器

        Args:
            task_id: 转录任务 ID
            parent: 父窗口
        """
```

        super().__init__(parent)
        self.task_id = task_id
        self.is_modified = False
        self.is_edit_mode = False

        # 加载任务数据
        self.task_data = self._load_task_data()
        self.transcript_content = self._load_transcript_file()

        # 初始化 UI
        self._init_ui()
        self._connect_signals()

        # 应用主题和语言
        self.apply_theme()
        self.update_language()

    def _load_task_data(self) -> dict:
        """从数据库加载任务元数据"""
        db = DatabaseConnection.get_instance()
        task = TranscriptionTask.get_by_id(db, self.task_id)
        if not task:
            raise ValueError(f"Task {self.task_id} not found")
        return task.to_dict()

    def _load_transcript_file(self) -> str:
        """加载转录文件内容"""
        output_path = self.task_data.get('output_path')
        if not output_path or not os.path.exists(output_path):
            raise FileNotFoundError("Transcript file not found")

        with open(output_path, 'r', encoding='utf-8') as f:
            return f.read()

    def toggle_edit_mode(self):
        """切换编辑模式"""
        self.is_edit_mode = not self.is_edit_mode
        self.text_edit.setReadOnly(not self.is_edit_mode)
        self.edit_button.setText(
            self.i18n.t('viewer.save') if self.is_edit_mode
            else self.i18n.t('viewer.edit')
        )

    def save_changes(self):
        """保存编辑后的内容"""
        if not self.is_modified:
            return

        try:
            output_path = self.task_data['output_path']
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(self.text_edit.toPlainText())

            self.is_modified = False
            self._show_notification(self.i18n.t('viewer.save_success'))
        except Exception as e:
            self._show_error(self.i18n.t('viewer.save_error'), str(e))

    def export_as(self, format: str):
        """导出为指定格式"""
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

        # 设置文件过滤器
        filters = {
            'txt': 'Text Files (*.txt)',
            'srt': 'Subtitle Files (*.srt)',
            'md': 'Markdown Files (*.md)'
        }
        file_dialog.setNameFilter(filters.get(format, ''))

        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            save_path = file_dialog.selectedFiles()[0]
            self._export_to_file(save_path, format)

    def _export_to_file(self, path: str, format: str):
        """执行导出操作"""
        try:
            converter = FormatConverter()
            content = self.text_edit.toPlainText()

            # 转换格式
            if format == 'txt':
                output = content
            elif format == 'srt':
                output = converter.to_srt(self._parse_content(content))
            elif format == 'md':
                output = converter.to_markdown(self._parse_content(content))

            with open(path, 'w', encoding='utf-8') as f:
                f.write(output)

            self._show_notification(
                self.i18n.t('viewer.export_success', format=format.upper())
            )
        except Exception as e:
            self._show_error(self.i18n.t('viewer.export_error'), str(e))

    def copy_all(self):
        """复制全部内容到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        self._show_notification(self.i18n.t('viewer.copied'))

    def apply_theme(self):
        """应用当前主题"""
        # 主题由全局 QSS 自动应用
        # 这里可以添加特定的主题调整
        pass

    def update_language(self):
        """更新界面语言"""
        self.setWindowTitle(
            self.i18n.t('viewer.title',
                       filename=self.task_data['file_name'])
        )
        # 更新所有按钮和标签文本
        self._update_ui_texts()

    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                self.i18n.t('viewer.unsaved_title'),
                self.i18n.t('viewer.unsaved_message'),
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                self.save_changes()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

````

### 2. SearchWidget

**职责**：
- 提供搜索输入界面
- 高亮显示匹配项
- 导航到上一个/下一个匹配

**关键方法**：

```python
class SearchWidget(QWidget):
    def __init__(self, text_edit: QTextEdit, parent=None):
        super().__init__(parent)
        self.text_edit = text_edit
        self.current_match = 0
        self.match_count = 0
        self.matches = []
        self._init_ui()

    def search(self, query: str):
        """执行搜索"""
        self.clear_highlights()

        if not query:
            return

        # 查找所有匹配项
        document = self.text_edit.document()
        cursor = QTextCursor(document)

        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive_checkbox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        self.matches = []
        while True:
            cursor = document.find(query, cursor, flags)
            if cursor.isNull():
                break
            self.matches.append(cursor)

        self.match_count = len(self.matches)
        self.current_match = 0 if self.matches else -1

        # 高亮所有匹配项
        self.highlight_matches()

        # 跳转到第一个匹配
        if self.matches:
            self.find_next()

    def highlight_matches(self):
        """高亮显示所有匹配项"""
        extra_selections = []

        for cursor in self.matches:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor

            # 使用主题相关的高亮颜色
            selection.format.setBackground(
                QColor('#FFEB3B' if self._is_light_theme() else '#FF9800')
            )
            extra_selections.append(selection)

        self.text_edit.setExtraSelections(extra_selections)

    def find_next(self):
        """跳转到下一个匹配"""
        if not self.matches:
            return

        self.current_match = (self.current_match + 1) % self.match_count
        self._jump_to_current_match()

    def find_previous(self):
        """跳转到上一个匹配"""
        if not self.matches:
            return

        self.current_match = (self.current_match - 1) % self.match_count
        self._jump_to_current_match()

    def _jump_to_current_match(self):
        """跳转到当前匹配项"""
        if 0 <= self.current_match < len(self.matches):
            cursor = self.matches[self.current_match]
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

            # 更新匹配计数显示
            self.match_label.setText(
                f"{self.current_match + 1}/{self.match_count}"
            )
````

## UI 设计

### 窗口布局

```
┌────────────────────────────────────────────────────────────┐
│  转录结果查看器 - interview_01.mp3                    [- □ ×]│
├────────────────────────────────────────────────────────────┤
│  元数据栏                                                   │
│  文件: interview_01.mp3 | 时长: 15:30 | 语言: 中文          │
│  引擎: faster-whisper (base) | 完成时间: 2025-10-07 10:30  │
├────────────────────────────────────────────────────────────┤
│  工具栏                                                     │
│  [编辑] [保存] [导出▼] [复制全部] [搜索 🔍]                │
├────────────────────────────────────────────────────────────┤
│  搜索栏 (可折叠)                                            │
│  [搜索框____________] [☐大小写] [↑] [↓] [×]  第 1/5 个匹配 │
├────────────────────────────────────────────────────────────┤
│  文本区域                                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ [00:00:15] 大家好，欢迎来到今天的会议。              │ │
│  │ [00:00:20] 我们今天主要讨论项目的进展情况。          │ │
│  │ [00:00:25] 首先，让我们回顾一下上周的工作...         │ │
│  │                                                       │ │
│  │                                                       │ │
│  │                                                       │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### 主题样式

**浅色主题**：

- 背景：#FFFFFF
- 文本：#212121
- 元数据栏背景：#F5F5F5
- 工具栏背景：#FAFAFA
- 搜索高亮：#FFEB3B
- 按钮：#2196F3

**深色主题**：

- 背景：#1E1E1E
- 文本：#E0E0E0
- 元数据栏背景：#2D2D2D
- 工具栏背景：#252525
- 搜索高亮：#FF9800
- 按钮：#42A5F5

## 数据流

### 打开查看器流程

```
用户点击"查看"按钮
    ↓
BatchTranscribeWidget.on_view_clicked(task_id)
    ↓
创建 TranscriptViewerDialog(task_id)
    ↓
加载任务数据（从数据库）
    ↓
加载转录文件（从文件系统）
    ↓
显示窗口
```

### 保存编辑流程

```
用户编辑文本
    ↓
text_edit.textChanged 信号
    ↓
设置 is_modified = True
    ↓
用户点击"保存"
    ↓
写入文件
    ↓
显示成功通知
    ↓
设置 is_modified = False
```

### 导出流程

```
用户点击"导出" → 选择格式
    ↓
打开文件保存对话框
    ↓
用户选择保存位置
    ↓
FormatConverter.convert(content, format)
    ↓
写入文件
    ↓
显示成功通知
```

## 国际化集成

### 翻译键定义

```json
{
  "viewer": {
    "title": "转录结果查看器 - {filename}",
    "edit": "编辑",
    "save": "保存",
    "export": "导出",
    "export_txt": "导出为 TXT",
    "export_srt": "导出为 SRT",
    "export_md": "导出为 Markdown",
    "copy_all": "复制全部",
    "search": "搜索",
    "search_placeholder": "输入搜索关键词...",
    "case_sensitive": "区分大小写",
    "match_count": "第 {current}/{total} 个匹配",
    "no_matches": "未找到匹配项",
    "copied": "已复制到剪贴板",
    "save_success": "转录结果已保存",
    "save_error": "保存失败",
    "export_success": "已导出为 {format}",
    "export_error": "导出失败",
    "unsaved_title": "未保存的修改",
    "unsaved_message": "您有未保存的修改，是否保存？",
    "file_not_found": "转录文件未找到，可能已被删除或移动",
    "file_read_error": "无法读取转录文件，请检查文件权限",
    "file_format_error": "转录文件格式错误，无法解析",
    "metadata": {
      "file": "文件",
      "duration": "时长",
      "language": "语言",
      "engine": "引擎",
      "completed": "完成时间"
    }
  }
}
```

### 语言切换处理

```python
# 在 MainWindow 中监听语言变更
self.i18n.language_changed.connect(self._on_language_changed)

def _on_language_changed(self):
    # 通知所有打开的查看器窗口
    for viewer in self.open_viewers:
        viewer.update_language()
```

## 性能优化

### 虚拟滚动（针对长文本）

```python
class VirtualTextEdit(QTextEdit):
    """支持虚拟滚动的文本编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.full_content = ""
        self.visible_range = (0, 1000)  # 初始显示前 1000 行
        self.line_height = 20

    def set_content(self, content: str):
        """设置完整内容"""
        self.full_content = content
        self.lines = content.split('\n')
        self._update_visible_content()

    def _update_visible_content(self):
        """更新可见内容"""
        start, end = self.visible_range
        visible_lines = self.lines[start:end]
        self.setPlainText('\n'.join(visible_lines))

    def wheelEvent(self, event):
        """滚动事件"""
        # 检测是否需要加载更多内容
        scrollbar = self.verticalScrollBar()
        if scrollbar.value() > scrollbar.maximum() * 0.8:
            self._load_more_content()
        super().wheelEvent(event)
```

### 搜索优化

```python
# 使用正则表达式加速搜索
import re

def fast_search(self, query: str, content: str) -> list:
    """快速搜索所有匹配位置"""
    pattern = re.escape(query)
    if not self.case_sensitive:
        pattern = f"(?i){pattern}"

    matches = []
    for match in re.finditer(pattern, content):
        matches.append((match.start(), match.end()))

    return matches
```

## 错误处理

### 异常处理策略

```python
class TranscriptViewerDialog(QDialog):
    def __init__(self, task_id: str, parent=None):
        try:
            super().__init__(parent)
            self.task_data = self._load_task_data()
            self.transcript_content = self._load_transcript_file()
            self._init_ui()
        except FileNotFoundError:
            self._show_error_and_close(
                self.i18n.t('viewer.file_not_found')
            )
        except PermissionError:
            self._show_error_and_close(
                self.i18n.t('viewer.file_read_error')
            )
        except Exception as e:
            logger.error(f"Failed to open viewer: {e}")
            self._show_error_and_close(
                self.i18n.t('viewer.file_format_error')
            )

    def _show_error_and_close(self, message: str):
        """显示错误并关闭窗口"""
        QMessageBox.critical(self.parent(), "错误", message)
        self.close()
```

## 测试策略

### 单元测试

```python
# tests/unit/test_transcript_viewer.py

def test_load_transcript():
    """测试加载转录文件"""
    viewer = TranscriptViewerDialog(task_id="test-123")
    assert viewer.transcript_content is not None
    assert len(viewer.transcript_content) > 0

def test_edit_mode_toggle():
    """测试编辑模式切换"""
    viewer = TranscriptViewerDialog(task_id="test-123")
    assert viewer.is_edit_mode == False
    viewer.toggle_edit_mode()
    assert viewer.is_edit_mode == True

def test_search_functionality():
    """测试搜索功能"""
    viewer = TranscriptViewerDialog(task_id="test-123")
    viewer.search_widget.search("测试")
    assert viewer.search_widget.match_count > 0
```

### 集成测试

```python
# tests/integration/test_viewer_integration.py

def test_save_and_reload():
    """测试保存后重新加载"""
    viewer = TranscriptViewerDialog(task_id="test-123")
    original_content = viewer.text_edit.toPlainText()

    # 编辑并保存
    viewer.toggle_edit_mode()
    viewer.text_edit.setPlainText(original_content + "\n新增内容")
    viewer.save_changes()

    # 重新打开
    viewer2 = TranscriptViewerDialog(task_id="test-123")
    assert "新增内容" in viewer2.text_edit.toPlainText()
```

## 实现注意事项

1. **窗口管理**：使用字典跟踪已打开的查看器，避免重复打开
2. **内存管理**：关闭窗口时正确释放资源
3. **信号连接**：确保主题和语言变更信号正确连接
4. **文件监控**：考虑监控文件变更，提示用户重新加载
5. **快捷键**：实现标准编辑快捷键（Ctrl+S 保存，Ctrl+F 搜索等）
6. **可访问性**：确保键盘导航和屏幕阅读器支持
