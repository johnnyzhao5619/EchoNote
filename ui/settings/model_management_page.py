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
模型管理设置页面

提供 Whisper 模型的下载、删除和管理功能
"""

import logging
from datetime import datetime
from typing import Dict

from PySide6.QtCore import Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.models.registry import ModelInfo
from ui.common.error_dialog import show_error_dialog
from ui.settings.base_page import BaseSettingsPage
from utils.i18n import I18nQtManager
from utils.model_download import run_model_download

logger = logging.getLogger("echonote.ui.settings.model_management")


class ModelManagementPage(BaseSettingsPage):
    """模型管理页面"""

    def __init__(self, settings_manager, i18n: I18nQtManager, model_manager):
        """
        初始化模型管理页面

        Args:
            settings_manager: 设置管理器实例
            i18n: 国际化管理器
            model_manager: 模型管理器实例
        """
        super().__init__(settings_manager, i18n)

        self.model_manager = model_manager

        # 存储模型卡片的引用，用于更新进度
        self.model_cards: Dict[str, QWidget] = {}

        # 连接模型管理器的信号
        self.model_manager.models_updated.connect(self._refresh_model_list)
        self.model_manager.downloader.download_progress.connect(self._update_download_progress)
        self.model_manager.downloader.download_completed.connect(self._on_download_completed)
        self.model_manager.downloader.download_failed.connect(self._on_download_failed)
        self.model_manager.model_validation_failed.connect(self._on_validation_failed)

        # 连接语言切换信号
        self.i18n.language_changed.connect(self.update_translations)

        # 设置 UI
        self.setup_ui()

        logger.info("Model management page initialized")

    def setup_ui(self):
        """设置 UI 布局"""
        # 页面标题
        self.title_label = QLabel(self.i18n.t("settings.model_management.title"))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.content_layout.addWidget(self.title_label)

        # 页面描述
        self.desc_label = QLabel(self.i18n.t("settings.model_management.description"))
        self.desc_label.setWordWrap(True)
        self.desc_label.setObjectName("description_label")
        self.content_layout.addWidget(self.desc_label)

        self.add_spacing(10)

        # 推荐模型卡片区域（条件显示）
        self.recommendation_container = QWidget()
        self.recommendation_layout = QVBoxLayout(self.recommendation_container)
        self.recommendation_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addWidget(self.recommendation_container)

        # 已下载模型区域
        section_font = QFont()
        section_font.setPointSize(12)
        section_font.setBold(True)

        self.downloaded_title = QLabel(self.i18n.t("settings.model_management.downloaded_models"))
        self.downloaded_title.setFont(section_font)
        self.content_layout.addWidget(self.downloaded_title)

        self.downloaded_models_container = QWidget()
        self.downloaded_models_layout = QVBoxLayout(self.downloaded_models_container)
        self.downloaded_models_layout.setContentsMargins(0, 0, 0, 0)
        self.downloaded_models_layout.setSpacing(10)
        self.content_layout.addWidget(self.downloaded_models_container)

        self.add_spacing(20)

        # 可下载模型区域
        self.available_title = QLabel(self.i18n.t("settings.model_management.available_models"))
        self.available_title.setFont(section_font)
        self.content_layout.addWidget(self.available_title)

        self.available_models_container = QWidget()
        self.available_models_layout = QVBoxLayout(self.available_models_container)
        self.available_models_layout.setContentsMargins(0, 0, 0, 0)
        self.available_models_layout.setSpacing(10)
        self.content_layout.addWidget(self.available_models_container)

        # 添加弹性空间
        self.content_layout.addStretch()

        # 刷新模型列表
        self._refresh_model_list()

        logger.debug("Model management UI setup complete")

    def update_translations(self):
        """更新所有 UI 文本以响应语言切换"""
        logger.debug("Updating translations for model management page")

        # 更新页面标题和描述
        if hasattr(self, "title_label"):
            self.title_label.setText(self.i18n.t("settings.model_management.title"))
        if hasattr(self, "desc_label"):
            self.desc_label.setText(self.i18n.t("settings.model_management.description"))

        # 更新区域标题
        if hasattr(self, "downloaded_title"):
            self.downloaded_title.setText(
                self.i18n.t("settings.model_management.downloaded_models")
            )
        if hasattr(self, "available_title"):
            self.available_title.setText(self.i18n.t("settings.model_management.available_models"))

        # 刷新整个模型列表，这会重新创建所有卡片并使用新的翻译
        self._refresh_model_list()

        logger.debug("Translations updated for model management page")

    @Slot()
    def _refresh_model_list(self):
        """刷新模型列表"""
        logger.debug("Refreshing model list")

        # 清空现有列表
        self._clear_layout(self.recommendation_layout)
        self._clear_layout(self.downloaded_models_layout)
        self._clear_layout(self.available_models_layout)
        self.model_cards.clear()

        # 获取所有模型
        all_models = self.model_manager.get_all_models()

        # 检查是否有已下载的模型
        downloaded_models = [m for m in all_models if m.is_downloaded]

        # 如果没有已下载的模型，显示推荐卡片
        if not downloaded_models:
            self._create_recommendation_card()
        else:
            # 隐藏推荐卡片
            self.recommendation_container.setVisible(False)

        # 分类显示模型
        for model in all_models:
            if model.is_downloaded:
                card = self._create_downloaded_model_card(model)
                self.downloaded_models_layout.addWidget(card)
                self.model_cards[model.name] = card
            else:
                card = self._create_available_model_card(model)
                self.available_models_layout.addWidget(card)
                self.model_cards[model.name] = card

        logger.debug(
            f"Model list refreshed: {len(downloaded_models)} downloaded, "
            f"{len(all_models) - len(downloaded_models)} available"
        )

    def _create_downloaded_model_card(self, model: ModelInfo) -> QWidget:
        """
        创建已下载模型卡片

        Args:
            model: 模型信息

        Returns:
            模型卡片控件
        """
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setObjectName("model-card-downloaded")

        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # 第一行：模型名称和按钮
        header_layout = QHBoxLayout()

        # 模型名称
        name_label = QLabel(f"✓ {model.full_name}")
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #2e7d32;")
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        # 配置按钮
        config_btn = QPushButton(self.i18n.t("settings.model_management.configure"))
        config_btn.setMaximumWidth(80)
        config_btn.clicked.connect(lambda: self._on_config_clicked(model.name))
        header_layout.addWidget(config_btn)

        # 删除按钮
        delete_btn = QPushButton(self.i18n.t("settings.model_management.delete"))
        delete_btn.setMaximumWidth(80)
        delete_btn.setStyleSheet("QPushButton { color: #d32f2f; }")
        delete_btn.clicked.connect(lambda: self._on_delete_clicked(model.name))

        # 检查模型是否正在使用（如果 ModelManager 支持此功能）
        if hasattr(self.model_manager, "is_model_in_use"):
            if self.model_manager.is_model_in_use(model.name):
                delete_btn.setEnabled(False)
                delete_btn.setToolTip(self.i18n.t("settings.model_management.model_in_use"))

        header_layout.addWidget(delete_btn)

        # 查看详情按钮
        details_btn = QPushButton(self.i18n.t("settings.model_management.view_details"))
        details_btn.setMaximumWidth(80)
        details_btn.clicked.connect(lambda: self._on_view_details_clicked(model.name))
        header_layout.addWidget(details_btn)

        layout.addLayout(header_layout)

        # 第二行：模型特征
        features_layout = QHBoxLayout()

        # 大小
        size_text = f"{self.i18n.t('settings.model_management.size')}: " f"{model.size_mb} MB"
        size_label = QLabel(size_text)
        features_layout.addWidget(size_label)

        # 速度
        speed_text = (
            f"{self.i18n.t('settings.model_management.speed')}: "
            f"{self._translate_speed(model.speed)}"
        )
        speed_label = QLabel(speed_text)
        features_layout.addWidget(speed_label)

        # 准确度
        accuracy_text = (
            f"{self.i18n.t('settings.model_management.accuracy')}: "
            f"{self._translate_accuracy(model.accuracy)}"
        )
        accuracy_label = QLabel(accuracy_text)
        features_layout.addWidget(accuracy_label)

        features_layout.addStretch()

        layout.addLayout(features_layout)

        # 第三行：使用统计
        stats_layout = QHBoxLayout()

        # 使用次数
        usage_text = self.i18n.t("settings.model_management.usage_count", count=model.usage_count)
        usage_label = QLabel(usage_text)
        usage_label.setStyleSheet("color: #666;")
        stats_layout.addWidget(usage_label)

        # 最后使用时间
        if model.last_used:
            last_used_text = self._format_relative_time(model.last_used)
            last_used_label = QLabel(
                f"{self.i18n.t('settings.model_management.last_used')}: " f"{last_used_text}"
            )
            last_used_label.setStyleSheet("color: #666;")
            stats_layout.addWidget(last_used_label)
        else:
            never_used_label = QLabel(self.i18n.t("settings.model_management.never_used"))
            never_used_label.setStyleSheet("color: #666;")
            stats_layout.addWidget(never_used_label)

        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        return card

    def _create_available_model_card(self, model: ModelInfo) -> QWidget:
        """
        创建可下载模型卡片

        Args:
            model: 模型信息

        Returns:
            模型卡片控件
        """
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setObjectName("model-card-available")

        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # 第一行：模型名称和下载按钮
        header_layout = QHBoxLayout()

        # 模型名称
        name_label = QLabel(model.full_name)
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        name_label.setFont(name_font)
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        # 下载按钮
        download_btn = QPushButton(self.i18n.t("settings.model_management.download"))
        download_btn.setObjectName(f"download_btn_{model.name}")
        download_btn.setMaximumWidth(100)
        download_btn.clicked.connect(lambda: self._on_download_clicked(model.name))
        header_layout.addWidget(download_btn)

        layout.addLayout(header_layout)

        # 第二行：模型特征
        features_layout = QHBoxLayout()

        # 大小
        size_text = f"{self.i18n.t('settings.model_management.size')}: " f"{model.size_mb} MB"
        size_label = QLabel(size_text)
        features_layout.addWidget(size_label)

        # 速度
        speed_text = (
            f"{self.i18n.t('settings.model_management.speed')}: "
            f"{self._translate_speed(model.speed)}"
        )
        speed_label = QLabel(speed_text)
        features_layout.addWidget(speed_label)

        # 准确度
        accuracy_text = (
            f"{self.i18n.t('settings.model_management.accuracy')}: "
            f"{self._translate_accuracy(model.accuracy)}"
        )
        accuracy_label = QLabel(accuracy_text)
        features_layout.addWidget(accuracy_label)

        features_layout.addStretch()

        layout.addLayout(features_layout)

        # 第三行：支持的语言
        lang_layout = QHBoxLayout()

        if "multi" in model.languages:
            lang_text = self.i18n.t("settings.model_management.multilingual")
        else:
            lang_text = self.i18n.t("settings.model_management.english_only")

        lang_label = QLabel(lang_text)
        lang_label.setStyleSheet("color: #666;")
        lang_layout.addWidget(lang_label)

        lang_layout.addStretch()

        layout.addLayout(lang_layout)

        # 进度条（初始隐藏）
        progress_bar = QProgressBar()
        progress_bar.setObjectName(f"progress_bar_{model.name}")
        progress_bar.setVisible(False)
        progress_bar.setMaximum(100)
        layout.addWidget(progress_bar)

        # 取消下载按钮（初始隐藏）
        cancel_btn = QPushButton(self.i18n.t("settings.model_management.cancel_download"))
        cancel_btn.setObjectName(f"cancel_btn_{model.name}")
        cancel_btn.setVisible(False)
        cancel_btn.setMaximumWidth(100)
        cancel_btn.clicked.connect(lambda: self._on_cancel_download_clicked(model.name))
        layout.addWidget(cancel_btn)

        return card

    def _translate_speed(self, speed: str) -> str:
        """
        翻译速度描述

        Args:
            speed: 速度描述（英文）

        Returns:
            翻译后的速度描述
        """
        speed_map = {
            "fastest": self.i18n.t("settings.model_management.speed_fastest"),
            "fast": self.i18n.t("settings.model_management.speed_fast"),
            "medium": self.i18n.t("settings.model_management.speed_medium"),
            "slow": self.i18n.t("settings.model_management.speed_slow"),
        }
        return speed_map.get(speed, speed)

    def _translate_accuracy(self, accuracy: str) -> str:
        """
        翻译准确度描述

        Args:
            accuracy: 准确度描述（英文）

        Returns:
            翻译后的准确度描述
        """
        accuracy_map = {
            "low": self.i18n.t("settings.model_management.accuracy_low"),
            "medium": self.i18n.t("settings.model_management.accuracy_medium"),
            "high": self.i18n.t("settings.model_management.accuracy_high"),
        }
        return accuracy_map.get(accuracy, accuracy)

    def _format_relative_time(self, dt: datetime) -> str:
        """
        格式化相对时间

        Args:
            dt: 日期时间

        Returns:
            相对时间描述
        """
        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return self.i18n.t("settings.model_management.days_ago", days=diff.days)
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return self.i18n.t("settings.model_management.hours_ago", hours=hours)
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return self.i18n.t("settings.model_management.minutes_ago", minutes=minutes)
        else:
            return self.i18n.t("settings.model_management.just_now")

    def _on_config_clicked(self, model_name: str):
        """
        处理配置按钮点击

        Args:
            model_name: 模型名称
        """
        logger.info(f"Config clicked for model: {model_name}")

        # 获取模型信息
        model = self.model_manager.get_model(model_name)
        if not model:
            logger.error(f"Model not found: {model_name}")
            return

        # 创建并显示配置对话框
        dialog = ModelConfigDialog(model, self.settings_manager, self.i18n, self)
        if dialog.exec():
            # 配置已保存
            logger.info(f"Configuration saved for model: {model_name}")

    def _on_delete_clicked(self, model_name: str):
        """
        处理删除按钮点击

        Args:
            model_name: 模型名称
        """
        logger.info(f"Delete clicked for model: {model_name}")

        # 获取模型信息
        model = self.model_manager.get_model(model_name)
        if not model:
            logger.error(f"Model not found: {model_name}")
            return

        # 显示确认对话框
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(self.i18n.t("settings.model_management.delete_confirm_title"))

        # 构建确认消息
        confirm_text = self.i18n.t(
            "settings.model_management.delete_confirm_message",
            model=model.full_name,
            size=model.size_mb,
        )
        warning_text = self.i18n.t("settings.model_management.delete_warning")

        msg_box.setText(confirm_text)
        msg_box.setInformativeText(warning_text)

        # 添加按钮
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        # 显示对话框
        reply = msg_box.exec()

        # 如果用户确认删除
        if reply == QMessageBox.StandardButton.Yes:
            self._on_delete_confirmed(model_name)

    def _on_delete_confirmed(self, model_name: str):
        """
        执行模型删除

        Args:
            model_name: 模型名称
        """
        logger.info(f"Deleting model: {model_name}")

        try:
            # 执行删除
            success = self.model_manager.delete_model(model_name)

            if success:
                # 显示成功通知
                QMessageBox.information(
                    self,
                    self.i18n.t("settings.model_management.delete_success_title"),
                    self.i18n.t(
                        "settings.model_management.delete_success_message", model=model_name
                    ),
                )

                # 刷新模型列表
                self._refresh_model_list()

                logger.info(f"Model deleted successfully: {model_name}")
            else:
                # 删除失败 - 使用错误对话框
                error_title = self.i18n.t("settings.model_management.delete_error_title")
                error_message = self.i18n.t(
                    "settings.model_management.delete_error_message", model=model_name
                )

                # 提供解决建议
                suggestions = self.i18n.t("settings.model_management.delete_suggestion")
                error_message += f"\n\n{suggestions}"

                show_error_dialog(
                    title=error_title,
                    message=error_message,
                    details=None,
                    i18n=self.i18n,
                    parent=self,
                )

        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}", exc_info=True)

            # 使用错误对话框显示详细错误
            error_title = self.i18n.t("settings.model_management.delete_error_title")
            error_message = self.i18n.t(
                "settings.model_management.delete_error_message", model=model_name
            )

            # 根据错误类型提供建议
            suggestions = self._get_delete_error_suggestions(str(e))
            if suggestions:
                error_message += (
                    f"\n\n{self.i18n.t('settings.model_management.suggestions')}:\n{suggestions}"
                )

            show_error_dialog(
                title=error_title,
                message=error_message,
                details=str(e),
                i18n=self.i18n,
                parent=self,
            )

    def _get_delete_error_suggestions(self, error: str) -> str:
        """
        根据删除错误消息提供解决建议

        Args:
            error: 错误消息

        Returns:
            解决建议文本
        """
        error_lower = error.lower()

        # 文件被占用
        if any(keyword in error_lower for keyword in ["in use", "being used", "locked"]):
            return self.i18n.t("settings.model_management.delete_suggestion_in_use")

        # 权限错误
        if any(keyword in error_lower for keyword in ["permission", "access", "denied"]):
            return self.i18n.t("settings.model_management.delete_suggestion_permission")

        # 通用建议
        return self.i18n.t("settings.model_management.delete_suggestion_general")

    @Slot(str, str)
    def _on_validation_failed(self, model_name: str, error_message: str):
        """
        处理模型验证失败事件

        Args:
            model_name: 模型名称
            error_message: 错误消息
        """
        logger.warning(f"Model validation failed for {model_name}: {error_message}")

        # 显示错误对话框
        error_title = self.i18n.t("settings.model_management.validation_error_title")
        error_msg = self.i18n.t(
            "settings.model_management.validation_error_message", model=model_name
        )

        # 提供解决建议
        suggestions = self.i18n.t("settings.model_management.validation_suggestion")
        error_msg += f"\n\n{suggestions}"

        show_error_dialog(
            title=error_title, message=error_msg, details=error_message, i18n=self.i18n, parent=self
        )

    def _on_view_details_clicked(self, model_name: str):
        """
        处理查看详情按钮点击

        Args:
            model_name: 模型名称
        """
        logger.info(f"View details clicked for model: {model_name}")

        # 获取模型信息
        model = self.model_manager.get_model(model_name)
        if not model:
            logger.error(f"Model not found: {model_name}")
            return

        # 创建并显示详情对话框
        dialog = ModelDetailsDialog(model, self.i18n, self)
        dialog.exec()

    def _on_download_clicked(self, model_name: str):
        """
        处理下载按钮点击

        Args:
            model_name: 模型名称
        """
        logger.info(f"Starting download for model: {model_name}")

        # 获取模型卡片
        if model_name not in self.model_cards:
            logger.error(f"Model card not found for: {model_name}")
            return

        card = self.model_cards[model_name]

        # 查找并禁用下载按钮
        download_btn = card.findChild(QPushButton, f"download_btn_{model_name}")
        if download_btn:
            download_btn.setEnabled(False)
            download_btn.setText(self.i18n.t("settings.model_management.downloading"))

        # 显示进度条
        progress_bar = card.findChild(QProgressBar, f"progress_bar_{model_name}")
        if progress_bar:
            progress_bar.setVisible(True)
            progress_bar.setValue(0)

        # 显示取消按钮
        cancel_btn = card.findChild(QPushButton, f"cancel_btn_{model_name}")
        if cancel_btn:
            cancel_btn.setVisible(True)

        # 启动异步下载（使用 QThreadPool）

        def run_download():
            """在新线程中运行下载"""

            def _log_success():
                logger.info("Model %s download completed via settings page", model_name)

            run_model_download(
                self.model_manager,
                model_name,
                logger=logger,
                on_success=_log_success,
                error_message=("Download failed in thread for model " f"{model_name}"),
            )

        # 在线程池中执行下载
        from PySide6.QtCore import QRunnable, QThreadPool

        class DownloadRunnable(QRunnable):
            def run(self):
                run_download()

        QThreadPool.globalInstance().start(DownloadRunnable())

    def _on_cancel_download_clicked(self, model_name: str):
        """
        处理取消下载按钮点击

        Args:
            model_name: 模型名称
        """
        logger.info(f"Cancelling download for model: {model_name}")

        # 确认取消
        reply = QMessageBox.question(
            self,
            self.i18n.t("settings.model_management.cancel_download_title"),
            self.i18n.t("settings.model_management.cancel_download_confirm", model=model_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 取消下载
            self.model_manager.cancel_download(model_name)

            # 重置 UI
            if model_name in self.model_cards:
                card = self.model_cards[model_name]

                # 重新启用下载按钮
                download_btn = card.findChild(QPushButton, f"download_btn_{model_name}")
                if download_btn:
                    download_btn.setEnabled(True)
                    download_btn.setText(self.i18n.t("settings.model_management.download"))

                # 隐藏进度条
                progress_bar = card.findChild(QProgressBar, f"progress_bar_{model_name}")
                if progress_bar:
                    progress_bar.setVisible(False)
                    progress_bar.setValue(0)

                # 隐藏取消按钮
                cancel_btn = card.findChild(QPushButton, f"cancel_btn_{model_name}")
                if cancel_btn:
                    cancel_btn.setVisible(False)

            logger.info(f"Download cancelled for model: {model_name}")

    def _clear_layout(self, layout: QVBoxLayout):
        """
        清空布局中的所有控件

        Args:
            layout: 要清空的布局
        """
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _create_recommendation_card(self):
        """创建推荐模型卡片"""
        logger.debug("Creating recommendation card")

        # 获取推荐的模型
        recommended_model_name = self.model_manager.recommend_model()
        recommended_model = self.model_manager.get_model(recommended_model_name)

        if not recommended_model:
            logger.warning(f"Recommended model {recommended_model_name} not found")
            return

        # 创建推荐卡片
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setObjectName("recommendation-card")

        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        # 推荐标题
        title_label = QLabel(
            self.i18n.t(
                "settings.model_management.recommendation_title", model=recommended_model.full_name
            )
        )
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1976d2;")
        layout.addWidget(title_label)

        # 推荐理由
        reason_text = self._get_recommendation_reason(recommended_model_name)
        reason_label = QLabel(reason_text)
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet("color: #424242; margin-bottom: 8px;")
        layout.addWidget(reason_label)

        # 模型特征
        features_layout = QHBoxLayout()

        # 大小
        size_text = (
            f"{self.i18n.t('settings.model_management.size')}: " f"{recommended_model.size_mb} MB"
        )
        size_label = QLabel(size_text)
        size_label.setStyleSheet("font-weight: bold;")
        features_layout.addWidget(size_label)

        # 速度
        speed_text = (
            f"{self.i18n.t('settings.model_management.speed')}: "
            f"{self._translate_speed(recommended_model.speed)}"
        )
        speed_label = QLabel(speed_text)
        speed_label.setStyleSheet("font-weight: bold;")
        features_layout.addWidget(speed_label)

        # 准确度
        accuracy_text = (
            f"{self.i18n.t('settings.model_management.accuracy')}: "
            f"{self._translate_accuracy(recommended_model.accuracy)}"
        )
        accuracy_label = QLabel(accuracy_text)
        accuracy_label.setStyleSheet("font-weight: bold;")
        features_layout.addWidget(accuracy_label)

        features_layout.addStretch()

        layout.addLayout(features_layout)

        # 一键下载按钮
        download_btn = QPushButton(self.i18n.t("settings.model_management.download_recommended"))
        download_btn.setMaximumWidth(200)
        download_btn.clicked.connect(lambda: self._on_download_recommended(recommended_model_name))
        layout.addWidget(download_btn)

        # 添加到推荐容器
        self.recommendation_layout.addWidget(card)
        self.recommendation_container.setVisible(True)

        logger.info(f"Recommendation card created for model: {recommended_model_name}")

    def _get_recommendation_reason(self, model_name: str) -> str:
        """
        获取推荐理由

        Args:
            model_name: 模型名称

        Returns:
            推荐理由文本
        """
        # 从 ModelManager 获取系统信息
        system_info = self.model_manager.get_recommendation_context()
        memory_gb = system_info["memory_gb"]
        has_gpu = system_info["has_gpu"]

        # 根据推荐的模型生成理由
        if model_name in ["tiny", "tiny.en"]:
            if memory_gb < 8:
                return self.i18n.t("settings.model_management.recommendation_reason_low_memory")
            else:
                return self.i18n.t("settings.model_management.recommendation_reason_fast")
        elif model_name in ["base", "base.en"]:
            return self.i18n.t("settings.model_management.recommendation_reason_balanced")
        elif model_name in ["small", "small.en"]:
            if has_gpu:
                return self.i18n.t("settings.model_management.recommendation_reason_gpu_small")
            else:
                return self.i18n.t("settings.model_management.recommendation_reason_medium_memory")
        elif model_name in ["medium", "medium.en"]:
            if has_gpu:
                return self.i18n.t("settings.model_management.recommendation_reason_gpu_medium")
            else:
                return self.i18n.t("settings.model_management.recommendation_reason_high_memory")
        else:  # large models
            return self.i18n.t("settings.model_management.recommendation_reason_best_quality")

    def _on_download_recommended(self, model_name: str):
        """
        处理推荐模型下载

        Args:
            model_name: 模型名称
        """
        logger.info(f"Downloading recommended model: {model_name}")
        self._on_download_clicked(model_name)

    @Slot(str, int, float)
    def _update_download_progress(self, model_name: str, progress: int, speed: float):
        """
        更新下载进度

        Args:
            model_name: 模型名称
            progress: 进度百分比 (0-100)
            speed: 下载速度 (MB/s)
        """
        logger.debug(f"Download progress for {model_name}: " f"{progress}% at {speed:.2f} MB/s")

        # 获取模型卡片
        if model_name not in self.model_cards:
            return

        card = self.model_cards[model_name]

        # 更新进度条
        progress_bar = card.findChild(QProgressBar, f"progress_bar_{model_name}")
        if progress_bar:
            progress_bar.setValue(progress)

            # 设置进度条文本（显示速度和百分比）
            if speed > 0:
                progress_bar.setFormat(f"{progress}% ({speed:.1f} MB/s)")
            else:
                progress_bar.setFormat(f"{progress}%")

    @Slot(str)
    def _on_download_completed(self, model_name: str):
        """
        处理下载完成事件

        Args:
            model_name: 模型名称
        """
        logger.info(f"Download completed for model: {model_name}")

        # 显示成功通知
        QMessageBox.information(
            self,
            self.i18n.t("settings.model_management.download_success_title"),
            self.i18n.t("settings.model_management.download_success_message", model=model_name),
        )

        # 刷新模型列表（会自动将模型移到已下载区域）
        self._refresh_model_list()

    @Slot(str, str)
    def _on_download_failed(self, model_name: str, error: str):
        """
        处理下载失败事件

        Args:
            model_name: 模型名称
            error: 错误消息
        """
        logger.error(f"Download failed for {model_name}: {error}")

        # 重置 UI
        if model_name in self.model_cards:
            card = self.model_cards[model_name]

            # 重新启用下载按钮
            download_btn = card.findChild(QPushButton, f"download_btn_{model_name}")
            if download_btn:
                download_btn.setEnabled(True)
                download_btn.setText(self.i18n.t("settings.model_management.download"))

            # 隐藏进度条
            progress_bar = card.findChild(QProgressBar, f"progress_bar_{model_name}")
            if progress_bar:
                progress_bar.setVisible(False)
                progress_bar.setValue(0)

            # 隐藏取消按钮
            cancel_btn = card.findChild(QPushButton, f"cancel_btn_{model_name}")
            if cancel_btn:
                cancel_btn.setVisible(False)

        # 显示错误对话框
        error_title = self.i18n.t("settings.model_management.download_error_title")
        error_message = self.i18n.t(
            "settings.model_management.download_error_message", model=model_name
        )

        # 提供解决建议
        suggestions = self._get_error_suggestions(error)
        if suggestions:
            error_message += (
                f"\n\n{self.i18n.t('settings.model_management.suggestions')}:\n{suggestions}"
            )

        # 显示错误对话框，包含详细错误信息
        show_error_dialog(
            title=error_title, message=error_message, details=error, i18n=self.i18n, parent=self
        )

        # 询问是否重试
        retry_reply = QMessageBox.question(
            self,
            self.i18n.t("settings.model_management.retry_title"),
            self.i18n.t("settings.model_management.retry_message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if retry_reply == QMessageBox.StandardButton.Yes:
            logger.info(f"Retrying download for model: {model_name}")
            self._on_download_clicked(model_name)

    def _get_error_suggestions(self, error: str) -> str:
        """
        根据错误消息提供解决建议

        Args:
            error: 错误消息

        Returns:
            解决建议文本
        """
        error_lower = error.lower()

        # 网络错误
        if any(
            keyword in error_lower
            for keyword in ["network", "connection", "timeout", "unreachable"]
        ):
            return self.i18n.t("settings.model_management.suggestion_network")

        # 磁盘空间不足
        if any(keyword in error_lower for keyword in ["disk", "space", "storage", "insufficient"]):
            return self.i18n.t("settings.model_management.suggestion_disk_space")

        # 权限错误
        if any(keyword in error_lower for keyword in ["permission", "access", "denied"]):
            return self.i18n.t("settings.model_management.suggestion_permission")

        # 通用建议
        return self.i18n.t("settings.model_management.suggestion_general")

    def load_settings(self):
        """加载设置（模型管理页面不需要加载设置）"""
        pass

    def save_settings(self):
        """保存设置（模型管理页面不需要保存设置）"""
        pass


class ModelDetailsDialog(QDialog):
    """模型详情对话框"""

    def __init__(self, model: ModelInfo, i18n: I18nQtManager, parent=None):
        """
        初始化模型详情对话框

        Args:
            model: 模型信息
            i18n: 国际化管理器
            parent: 父控件
        """
        super().__init__(parent)

        import platform
        import subprocess
        from pathlib import Path

        from PySide6.QtWidgets import QGridLayout

        self.model = model
        self.i18n = i18n

        self.setWindowTitle(i18n.t("settings.model_management.details_title"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel(model.full_name)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # 详细信息网格
        info_layout = QGridLayout()
        info_layout.setSpacing(10)
        info_layout.setColumnStretch(1, 1)

        row = 0

        # 模型名称
        info_layout.addWidget(QLabel(i18n.t("settings.model_management.model_name") + ":"), row, 0)
        info_layout.addWidget(QLabel(model.name), row, 1)
        row += 1

        # 模型版本（从 huggingface_id 提取）
        version = "v3"  # 默认版本
        if "large-v1" in model.name:
            version = "v1"
        elif "large-v2" in model.name:
            version = "v2"
        elif "large-v3" in model.name:
            version = "v3"

        info_layout.addWidget(
            QLabel(i18n.t("settings.model_management.model_version") + ":"), row, 0
        )
        info_layout.addWidget(QLabel(version), row, 1)
        row += 1

        # 支持的语言
        info_layout.addWidget(
            QLabel(i18n.t("settings.model_management.supported_languages") + ":"), row, 0
        )
        if "multi" in model.languages:
            lang_text = i18n.t("settings.model_management.multilingual")
        else:
            lang_text = i18n.t("settings.model_management.english_only")
        info_layout.addWidget(QLabel(lang_text), row, 1)
        row += 1

        # 模型大小
        info_layout.addWidget(QLabel(i18n.t("settings.model_management.model_size") + ":"), row, 0)
        info_layout.addWidget(QLabel(f"{model.size_mb} MB"), row, 1)
        row += 1

        # 模型文件路径
        if model.local_path:
            info_layout.addWidget(
                QLabel(i18n.t("settings.model_management.model_path") + ":"), row, 0
            )
            path_label = QLabel(model.local_path)
            path_label.setWordWrap(True)
            path_label.setStyleSheet("color: #666;")
            info_layout.addWidget(path_label, row, 1)
            row += 1

            # 实际占用磁盘空间
            try:
                model_path = Path(model.local_path)
                if model_path.exists():
                    actual_size_mb = sum(
                        f.stat().st_size for f in model_path.rglob("*") if f.is_file()
                    ) / (1024 * 1024)

                    info_layout.addWidget(
                        QLabel(i18n.t("settings.model_management.disk_usage") + ":"), row, 0
                    )
                    info_layout.addWidget(QLabel(f"{actual_size_mb:.1f} MB"), row, 1)
                    row += 1
            except Exception as e:
                logger.error(f"Error calculating disk usage: {e}")

        # 下载日期
        if model.download_date:
            info_layout.addWidget(
                QLabel(i18n.t("settings.model_management.download_date") + ":"), row, 0
            )
            date_str = model.download_date.strftime("%Y-%m-%d %H:%M:%S")
            info_layout.addWidget(QLabel(date_str), row, 1)
            row += 1

        # 最后使用日期
        info_layout.addWidget(QLabel(i18n.t("settings.model_management.last_used") + ":"), row, 0)
        if model.last_used:
            last_used_str = model.last_used.strftime("%Y-%m-%d %H:%M:%S")
            info_layout.addWidget(QLabel(last_used_str), row, 1)
        else:
            info_layout.addWidget(QLabel(i18n.t("settings.model_management.never_used")), row, 1)
        row += 1

        # 使用次数
        info_layout.addWidget(
            QLabel(i18n.t("settings.model_management.usage_count_label") + ":"), row, 0
        )
        info_layout.addWidget(QLabel(str(model.usage_count)), row, 1)
        row += 1

        layout.addLayout(info_layout)

        # 添加弹性空间
        layout.addStretch()

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 在文件管理器中显示按钮
        if model.local_path:
            show_in_explorer_btn = QPushButton(i18n.t("settings.model_management.show_in_explorer"))
            show_in_explorer_btn.clicked.connect(
                lambda: self._on_show_in_explorer(model.local_path)
            )
            button_layout.addWidget(show_in_explorer_btn)

        # 关闭按钮
        close_btn = QPushButton(i18n.t("settings.model_management.close"))
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_show_in_explorer(self, path: str):
        """
        在文件管理器中显示模型文件

        Args:
            path: 模型文件路径
        """
        import platform
        import subprocess
        from pathlib import Path

        try:
            model_path = Path(path)

            if not model_path.exists():
                logger.error(f"Model path does not exist: {path}")
                return

            system = platform.system()

            if system == "Darwin":  # macOS
                subprocess.run(["open", "-R", str(model_path)])
            elif system == "Windows":
                subprocess.run(["explorer", "/select,", str(model_path)])
            else:  # Linux
                # Try to open the parent directory
                subprocess.run(["xdg-open", str(model_path.parent)])

            logger.info(f"Opened model path in file explorer: {path}")

        except Exception as e:
            logger.error(f"Error opening file explorer: {e}")


class ModelConfigDialog(QDialog):
    """模型配置对话框"""

    def __init__(self, model: ModelInfo, settings_manager, i18n: I18nQtManager, parent=None):
        """
        初始化模型配置对话框

        Args:
            model: 模型信息
            settings_manager: 设置管理器
            i18n: 国际化管理器
            parent: 父控件
        """
        super().__init__(parent)

        self.model = model
        self.settings_manager = settings_manager
        self.i18n = i18n

        self.setWindowTitle(i18n.t("settings.model_management.config_title", model=model.full_name))
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel(i18n.t("settings.model_management.config_description"))
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # 配置表单
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # 计算设备选择
        device_label = QLabel(i18n.t("settings.model_management.compute_device") + ":")
        device_combo = QComboBox()
        device_combo.addItems(["cpu", "cuda", "auto"])

        # 检查 CUDA 是否可用
        cuda_available = False
        try:
            import torch

            cuda_available = torch.cuda.is_available()
        except:
            pass

        if not cuda_available:
            # 禁用 CUDA 选项
            cuda_index = device_combo.findText("cuda")
            if cuda_index >= 0:
                device_combo.model().item(cuda_index).setEnabled(False)

        form_layout.addRow(device_label, device_combo)

        # 计算精度选择
        compute_type_label = QLabel(i18n.t("settings.model_management.compute_precision") + ":")
        compute_type_combo = QComboBox()
        compute_type_combo.addItems(["int8", "float16", "float32"])
        form_layout.addRow(compute_type_label, compute_type_combo)

        # VAD 过滤（批量转录）
        vad_label = QLabel(i18n.t("settings.model_management.enable_vad") + ":")
        vad_checkbox = QCheckBox(i18n.t("settings.model_management.vad_description"))
        form_layout.addRow(vad_label, vad_checkbox)

        # VAD 静音阈值
        vad_threshold_label = QLabel(i18n.t("settings.model_management.vad_threshold") + ":")
        vad_threshold_spin = QSpinBox()
        vad_threshold_spin.setMinimum(100)
        vad_threshold_spin.setMaximum(5000)
        vad_threshold_spin.setSingleStep(100)
        vad_threshold_spin.setValue(500)
        vad_threshold_spin.setSuffix(" ms")
        vad_threshold_spin.setEnabled(False)  # 初始禁用

        # VAD 复选框状态改变时启用/禁用阈值设置
        vad_checkbox.stateChanged.connect(
            lambda state: vad_threshold_spin.setEnabled(
                state == vad_checkbox.checkState().Checked.value
            )
        )

        form_layout.addRow(vad_threshold_label, vad_threshold_spin)

        layout.addLayout(form_layout)

        # 加载当前配置
        config_key = f"transcription.model_configs.{model.name}"

        # 设备
        current_device = settings_manager.get_setting(f"{config_key}.device") or "cpu"
        device_index = device_combo.findText(current_device)
        if device_index >= 0:
            device_combo.setCurrentIndex(device_index)

        # 计算精度
        current_compute_type = settings_manager.get_setting(f"{config_key}.compute_type") or "int8"
        compute_type_index = compute_type_combo.findText(current_compute_type)
        if compute_type_index >= 0:
            compute_type_combo.setCurrentIndex(compute_type_index)

        # VAD 设置
        current_vad_enabled = settings_manager.get_setting(f"{config_key}.vad_filter")
        if current_vad_enabled is None:
            current_vad_enabled = False
        vad_checkbox.setChecked(current_vad_enabled)

        current_vad_threshold = (
            settings_manager.get_setting(f"{config_key}.vad_threshold_ms") or 500
        )
        vad_threshold_spin.setValue(current_vad_threshold)

        # 提示信息
        if not cuda_available:
            cuda_note = QLabel(i18n.t("settings.model_management.cuda_not_available"))
            cuda_note.setWordWrap(True)
            cuda_note.setStyleSheet("color: #ff9800; font-style: italic;")
            layout.addWidget(cuda_note)

        # 添加弹性空间
        layout.addStretch()

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 取消按钮
        cancel_btn = QPushButton(i18n.t("settings.model_management.cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # 保存按钮
        save_btn = QPushButton(i18n.t("settings.model_management.save"))
        save_btn.setDefault(True)

        def save_config():
            # 验证配置
            selected_device = device_combo.currentText()

            if selected_device == "cuda" and not cuda_available:
                QMessageBox.warning(
                    self,
                    i18n.t("settings.model_management.validation_error"),
                    i18n.t("settings.model_management.cuda_not_available"),
                )
                return

            # 保存配置
            settings_manager.set_setting(f"{config_key}.device", selected_device)
            settings_manager.set_setting(
                f"{config_key}.compute_type", compute_type_combo.currentText()
            )
            settings_manager.set_setting(f"{config_key}.vad_filter", vad_checkbox.isChecked())
            settings_manager.set_setting(
                f"{config_key}.vad_threshold_ms", vad_threshold_spin.value()
            )

            # 保存到磁盘
            settings_manager.save_settings()

            logger.info(f"Configuration saved for model: {model.name}")
            self.accept()

        save_btn.clicked.connect(save_config)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)
