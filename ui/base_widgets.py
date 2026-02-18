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

from ui.qt_imports import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.constants import DEFAULT_LAYOUT_SPACING
from utils.i18n import I18nQtManager

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
            self.setProperty(property_name, value)

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
        reply = QMessageBox.warning(
            self, title, message, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        return reply == QMessageBox.StandardButton.Ok

    def show_info(self, title: str, message: str):
        """显示信息对话框

        Args:
            title: 信息标题
            message: 信息消息
        """
        QMessageBox.information(self, title, message)


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
        return button


class LayoutHelper:
    """布局辅助工具类

    提供创建和配置布局的便捷方法。
    """

    @staticmethod
    def create_vbox(
        spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = (0, 0, 0, 0)
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
        spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = (0, 0, 0, 0)
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

    @staticmethod
    def add_stretch_and_widgets(
        layout, widgets: list, stretch_before: bool = False, stretch_after: bool = True
    ):
        """向布局添加组件和弹性空间

        Args:
            layout: 目标布局
            widgets: 要添加的组件列表
            stretch_before: 是否在组件前添加弹性空间
            stretch_after: 是否在组件后添加弹性空间
        """
        if stretch_before:
            layout.addStretch()

        for widget in widgets:
            layout.addWidget(widget)

        if stretch_after:
            layout.addStretch()


class LabelHelper:
    """标签辅助工具类

    提供创建和配置标签的便捷方法。
    """

    @staticmethod
    def create_title_label(text: str) -> QLabel:
        """创建标题标签

        Args:
            text: 标签文本

        Returns:
            标题样式的标签
        """
        label = QLabel(text)
        label.setObjectName("title_label")
        return label

    @staticmethod
    def create_subtitle_label(text: str) -> QLabel:
        """创建副标题标签

        Args:
            text: 标签文本

        Returns:
            副标题样式的标签
        """
        label = QLabel(text)
        label.setObjectName("subtitle_label")
        return label

    @staticmethod
    def create_info_label(text: str) -> QLabel:
        """创建信息标签

        Args:
            text: 标签文本

        Returns:
            信息样式的标签
        """
        label = QLabel(text)
        label.setObjectName("info_label")
        label.setWordWrap(True)
        return label


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
        else:
            button.clicked.connect(callback)

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
        try:
            if slot:
                signal.disconnect(slot)
            else:
                signal.disconnect()
        except Exception as e:
            logger.warning(f"Failed to disconnect signal: {e}")


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
    spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = (0, 0, 0, 0)
) -> QVBoxLayout:
    """创建垂直布局的便捷函数"""
    return LayoutHelper.create_vbox(spacing, margins)


def create_hbox(
    spacing: int = DEFAULT_LAYOUT_SPACING, margins: tuple = (0, 0, 0, 0)
) -> QHBoxLayout:
    """创建水平布局的便捷函数"""
    return LayoutHelper.create_hbox(spacing, margins)


def connect_button_with_callback(button: QPushButton, callback: Callable, *args, **kwargs):
    """连接按钮回调的便捷函数"""
    SignalHelper.connect_button_with_callback(button, callback, *args, **kwargs)
