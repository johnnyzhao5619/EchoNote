# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
基础UI组件

提供可重用的基础组件和工具函数，减少重复代码并统一UI行为。
"""

import logging
from typing import Any, Callable, Optional

from core.qt_imports import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Signal,
)
from ui.constants import (
    DEFAULT_LAYOUT_SPACING,
    PAGE_CONTENT_MARGINS,
    PAGE_LAYOUT_SPACING,
    ROLE_DANGER,
    ROLE_EVENT_CARD,
    ROLE_EVENT_INDICATOR,
    ROLE_EVENT_META,
    ROLE_EVENT_TIME,
    ROLE_EVENT_TITLE,
    ROLE_EVENT_TYPE_BADGE,
    ZERO_MARGINS,
)
from ui.common.style_utils import set_widget_dynamic_property
from ui.signal_helpers import connect_button_with_callback as connect_button_signal
from ui.signal_helpers import safe_disconnect as safe_disconnect_signal
from utils.i18n import I18nQtManager
from utils.time_utils import format_localized_datetime, to_local_datetime

logger = logging.getLogger(__name__)


class BaseWidget(QWidget):
    """基础UI组件

    集成了国际化、主题和错误处理功能的基础组件。
    所有UI组件都应该继承此类以获得统一的行为。
    """

    def __init__(self, i18n: I18nQtManager, parent: Optional[QWidget] = None):
        """初始化基础组件

        Args:
            i18n: 国际化管理器
            parent: 父组件
        """
        # 初始化QWidget
        super().__init__(parent)

        # 手动添加混入功能
        self.i18n = i18n
        if hasattr(self.i18n, "language_changed"):
            self.i18n.language_changed.connect(self.update_translations)

        # 初始化主题属性
        self._theme_properties = {}

        # 初始化错误处理
        self._i18n = i18n

        # 注意：不在这里调用 setup_ui()，让子类在自己的 __init__ 中调用
        # 这样可以确保子类的属性已经被正确设置

    def setup_ui(self):
        """设置UI布局

        子类应该重写此方法来创建UI元素。
        """
        pass

    def update_translations(self):
        """更新翻译

        子类应该重写此方法来更新所有UI文本。
        """
        pass

    def tr(self, key: str, **kwargs) -> str:
        """翻译快捷方法

        Args:
            key: 翻译键
            **kwargs: 翻译参数

        Returns:
            翻译后的文本
        """
        return self.i18n.t(key, **kwargs)

    def set_theme_property(self, property_name: str, value: Any):
        """设置主题属性

        Args:
            property_name: 属性名
            value: 属性值
        """
        self._theme_properties[property_name] = value
        if hasattr(self, "setProperty"):
            set_widget_dynamic_property(self, property_name, value)

    def get_theme_property(self, property_name: str, default: Any = None) -> Any:
        """获取主题属性

        Args:
            property_name: 属性名
            default: 默认值

        Returns:
            属性值
        """
        return self._theme_properties.get(property_name, default)

    def show_error(self, title: str, message: str, details: str = None):
        """显示错误对话框

        Args:
            title: 错误标题
            message: 错误消息
            details: 详细信息（可选）
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        ok_button = msg_box.addButton(self.i18n.t("common.ok"), QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(ok_button)

        if details:
            msg_box.setDetailedText(details)

        msg_box.exec()

    def show_warning(self, title: str, message: str) -> bool:
        """显示警告对话框

        Args:
            title: 警告标题
            message: 警告消息

        Returns:
            用户是否点击了确定
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        ok_button = msg_box.addButton(self.i18n.t("common.ok"), QMessageBox.ButtonRole.AcceptRole)
        cancel_button = msg_box.addButton(self.i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(ok_button)
        
        msg_box.exec()
        return msg_box.clickedButton() == ok_button

    def show_info(self, title: str, message: str):
        """显示信息对话框

        Args:
            title: 信息标题
            message: 信息消息
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        ok_button = msg_box.addButton(self.i18n.t("common.ok"), QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(ok_button)
        
        msg_box.exec()

    def create_page_title(self, text_key: str, layout=None) -> QLabel:
        """
        Create a standardized page title label.

        Args:
            text_key: i18n key for the title text
            layout: Optional layout to immediately add the label to

        Returns:
            Configured title label
        """
        label = QLabel(self.i18n.t(text_key))
        label.setObjectName("page_title")
        if layout is not None:
            layout.addWidget(label)
        return label

    def create_page_layout(
        self,
        margins: tuple = PAGE_CONTENT_MARGINS,
        spacing: int = PAGE_LAYOUT_SPACING,
    ) -> QVBoxLayout:
        """
        Create a standard root page layout bound to this widget.

        Args:
            margins: Content margins for the page
            spacing: Vertical spacing between page sections

        Returns:
            Configured QVBoxLayout attached to this widget
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        return layout

    def create_row_container(
        self,
        *,
        object_name: Optional[str] = None,
        margins: tuple = ZERO_MARGINS,
        spacing: int = DEFAULT_LAYOUT_SPACING,
    ) -> tuple[QWidget, QHBoxLayout]:
        """
        Create a QWidget with a configured horizontal layout.

        Args:
            object_name: Optional object name for styling
            margins: Layout margins (left, top, right, bottom)
            spacing: Layout spacing

        Returns:
            Tuple of (container widget, horizontal layout)
        """
        container = QWidget()
        if object_name:
            container.setObjectName(object_name)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        return container, layout


class ButtonHelper:
    """按钮辅助工具类

    提供创建和配置按钮的便捷方法。
    """

    @staticmethod
    def create_button(
        text: str,
        callback: Callable = None,
        object_name: str = None,
        tooltip: str = None,
        enabled: bool = True,
    ) -> QPushButton:
        """创建按钮

        Args:
            text: 按钮文本
            callback: 点击回调函数
            object_name: 对象名称
            tooltip: 工具提示
            enabled: 是否启用

        Returns:
            配置好的按钮
        """
        button = QPushButton(text)
        button.setProperty("variant", "default")

        if callback:
            button.clicked.connect(callback)

        if object_name:
            button.setObjectName(object_name)

        if tooltip:
            button.setToolTip(tooltip)

        button.setEnabled(enabled)

        return button

    @staticmethod
    def create_primary_button(text: str, callback: Callable = None) -> QPushButton:
        """创建主要按钮

        Args:
            text: 按钮文本
            callback: 点击回调函数

        Returns:
            主要样式的按钮
        """
        button = ButtonHelper.create_button(text, callback)
        button.setObjectName("primary_button")
        button.setProperty("variant", "primary")
        return button

    @staticmethod
    def create_secondary_button(text: str, callback: Callable = None) -> QPushButton:
        """创建次要按钮

        Args:
            text: 按钮文本
            callback: 点击回调函数

        Returns:
            次要样式的按钮
        """
        button = ButtonHelper.create_button(text, callback)
        button.setObjectName("secondary_button")
        button.setProperty("variant", "secondary")
        return button


class LayoutHelper:
    """布局辅助工具类

    提供创建和配置布局的便捷方法。
    """

    @staticmethod
    def create_vbox(
        spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = ZERO_MARGINS
    ) -> QVBoxLayout:
        """创建垂直布局

        Args:
            spacing: 间距
            margins: 边距 (left, top, right, bottom)

        Returns:
            配置好的垂直布局
        """
        layout = QVBoxLayout()
        layout.setSpacing(spacing)
        layout.setContentsMargins(*margins)
        return layout

    @staticmethod
    def create_hbox(
        spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = ZERO_MARGINS
    ) -> QHBoxLayout:
        """创建水平布局

        Args:
            spacing: 间距
            margins: 边距 (left, top, right, bottom)

        Returns:
            配置好的水平布局
        """
        layout = QHBoxLayout()
        layout.setSpacing(spacing)
        layout.setContentsMargins(*margins)
        return layout


class SignalHelper:
    """信号辅助工具类

    提供信号连接的便捷方法。
    """

    @staticmethod
    def connect_button_with_callback(button: QPushButton, callback: Callable, *args, **kwargs):
        """连接按钮点击信号到回调函数

        Args:
            button: 按钮对象
            callback: 回调函数
            *args: 传递给回调函数的位置参数
            **kwargs: 传递给回调函数的关键字参数
        """
        if args or kwargs:
            button.clicked.connect(lambda: callback(*args, **kwargs))
            return
        connect_button_signal(button, callback)

    @staticmethod
    def safe_connect(signal, slot, connection_type=None):
        """安全连接信号到槽

        Args:
            signal: 信号对象
            slot: 槽函数
            connection_type: 连接类型（可选）
        """
        try:
            if connection_type:
                signal.connect(slot, connection_type)
            else:
                signal.connect(slot)
        except Exception as e:
            logger.warning(f"Failed to connect signal: {e}")

    @staticmethod
    def safe_disconnect(signal, slot=None):
        """安全断开信号连接

        Args:
            signal: 信号对象
            slot: 槽函数（可选，如果不提供则断开所有连接）
        """
        if safe_disconnect_signal(signal, slot):
            return
        logger.warning("Failed to disconnect signal")


# 导出常用的辅助函数，方便其他模块使用
def create_button(text: str, callback: Callable = None, **kwargs) -> QPushButton:
    """创建按钮的便捷函数"""
    return ButtonHelper.create_button(text, callback, **kwargs)


def create_primary_button(text: str, callback: Callable = None) -> QPushButton:
    """创建主要按钮的便捷函数"""
    return ButtonHelper.create_primary_button(text, callback)


def create_secondary_button(text: str, callback: Callable = None) -> QPushButton:
    """创建次要按钮的便捷函数"""
    return ButtonHelper.create_secondary_button(text, callback)


def create_vbox(
    spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = ZERO_MARGINS
) -> QVBoxLayout:
    """创建垂直布局的便捷函数"""
    return LayoutHelper.create_vbox(spacing, margins)


def create_hbox(
    spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = ZERO_MARGINS
) -> QHBoxLayout:
    """创建水平布局的便捷函数"""
    return LayoutHelper.create_hbox(spacing, margins)


def create_danger_button(text: str, callback: Callable = None) -> QPushButton:
    """创建危险操作按钮的便捷函数"""
    button = create_button(text, callback)
    button.setProperty("role", ROLE_DANGER)
    button.setProperty("variant", "danger")
    return button


def connect_button_with_callback(button: QPushButton, callback: Callable, *args, **kwargs):
    """连接按钮回调的便捷函数"""
    SignalHelper.connect_button_with_callback(button, callback, *args, **kwargs)


class BaseEventCard(QFrame):
    """
    Base class for event card widgets.

    Provides common functionality for displaying calendar events:
    - Standardized title and time display
    - Localized date/time formatting
    - Event type and source badges
    - Consistency across different views (Timeline, Calendar Hub)
    """

    EVENT_TYPE_TRANSLATION_MAP = {
        "event": "timeline.filter_event",
        "task": "timeline.filter_task",
        "appointment": "timeline.filter_appointment",
    }

    SOURCE_TRANSLATION_MAP = {
        "local": "timeline.source_local",
        "google": "timeline.source_google",
        "outlook": "timeline.source_outlook",
    }

    def __init__(
        self,
        calendar_event: Any,
        i18n: I18nQtManager,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize base event card.

        Args:
            calendar_event: CalendarEvent instance
            i18n: Internationalization manager
            parent: Parent widget
        """
        super().__init__(parent)
        self.calendar_event = calendar_event
        self.i18n = i18n

        # Label references for updates
        self.title_label = None
        self.time_label = None
        self.type_badge_label = None
        self.source_badge_label = None

        if hasattr(self.i18n, "language_changed"):
            self.i18n.language_changed.connect(self.update_translations)

    def setup_base_ui(self):
        """Set up standard card styling."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setObjectName("event_card")
        self.setProperty("role", ROLE_EVENT_CARD)
        self.setProperty("source", self.calendar_event.source)

    def create_common_header(self, layout: QVBoxLayout):
        """
        Create standard header elements (title, time, badges).

        Args:
            layout: Layout to add header elements to
        """
        # Title
        self.title_label = QLabel(self.calendar_event.title)
        self.title_label.setProperty("role", ROLE_EVENT_TITLE)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Meta row (Time, Type, Source)
        meta_layout = create_hbox()

        # Localized time
        self.time_label = QLabel(self._get_formatted_time())
        self.time_label.setProperty("role", ROLE_EVENT_TIME)
        meta_layout.addWidget(self.time_label)

        # Type badge
        self.type_badge_label = QLabel(self._get_event_type_text())
        self.type_badge_label.setProperty("role", ROLE_EVENT_TYPE_BADGE)
        meta_layout.addWidget(self.type_badge_label)

        # Source badge
        self.source_badge_label = QLabel(self._get_source_text())
        self.source_badge_label.setProperty("role", ROLE_EVENT_INDICATOR)
        self.source_badge_label.setProperty("source", self.calendar_event.source)
        meta_layout.addWidget(self.source_badge_label)

        meta_layout.addStretch()
        layout.addLayout(meta_layout)

    def _get_formatted_time(self) -> str:
        """Get localized time string for the event."""
        try:
            start_time = to_local_datetime(self.calendar_event.start_time)
            end_time = to_local_datetime(self.calendar_event.end_time)
            return f"{format_localized_datetime(start_time)} - {format_localized_datetime(end_time, include_date=False)}"
        except Exception as exc:
            logger.warning("Failed to localize event time: %s", exc)
            return f"{self.calendar_event.start_time} - {self.calendar_event.end_time}"

    def _get_event_type_text(self) -> str:
        """Get translated event type text."""
        event_type = getattr(self.calendar_event, "event_type", "") or ""
        key = self.EVENT_TYPE_TRANSLATION_MAP.get(event_type.lower())
        return self.i18n.t(key) if key else event_type

    def _get_source_text(self) -> str:
        """Get translated source text."""
        source = getattr(self.calendar_event, "source", "") or ""
        key = self.SOURCE_TRANSLATION_MAP.get(source.lower())
        return self.i18n.t(key) if key else source.capitalize()

    def update_translations(self):
        """Update all standard labels on language change."""
        if self.title_label:
            self.title_label.setText(self.calendar_event.title)
        if self.time_label:
            self.time_label.setText(self._get_formatted_time())
        if self.type_badge_label:
            self.type_badge_label.setText(self._get_event_type_text())
        if self.source_badge_label:
            self.source_badge_label.setText(self._get_source_text())
