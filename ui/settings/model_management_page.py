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
from typing import Dict, Union

from core.qt_imports import (
    QDialog,
    QFont,
    QFrame,
    QLabel,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    Slot,
)

from core.models.registry import ModelInfo
from core.models.translation_registry import TranslationModelInfo
from ui.base_widgets import (
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_vbox,
)
from ui.common.error_dialog import show_error_dialog
from ui.constants import (
    MODEL_DETAILS_DIALOG_MIN_HEIGHT,
    MODEL_DETAILS_DIALOG_MIN_WIDTH,
    MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_MEDIUM,
    MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_SMALL,
    MODEL_MANAGEMENT_LIST_SPACING,
    MODEL_MANAGEMENT_MODEL_NAME_FONT_SIZE,
    MODEL_MANAGEMENT_RECOMMENDED_BUTTON_MAX_WIDTH,
    MODEL_MANAGEMENT_SECTION_TITLE_FONT_SIZE,
    ROLE_AUDIO_FILE,
    ROLE_MODEL_REASON,
    ROLE_SETTINGS_INLINE_ACTION,
    ROLE_TIME_DISPLAY,
    ZERO_MARGINS,
)
from ui.settings.base_page import BaseSettingsPage
from ui.settings.components.model_card import ModelCardWidget
from utils.i18n import I18nQtManager
from utils.model_download import run_model_download
from utils.time_utils import format_localized_datetime

logger = logging.getLogger("echonote.ui.settings.model_management")


class ModelManagementPage(BaseSettingsPage):
    """模型管理页面"""

    PAGE_TITLE_OBJECT_NAME = "page_title"
    MODEL_LIST_SPACING = MODEL_MANAGEMENT_LIST_SPACING
    SECTION_TITLE_FONT_SIZE = MODEL_MANAGEMENT_SECTION_TITLE_FONT_SIZE
    MODEL_NAME_FONT_SIZE = MODEL_MANAGEMENT_MODEL_NAME_FONT_SIZE
    ACTION_BUTTON_MAX_WIDTH_SMALL = MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_SMALL
    ACTION_BUTTON_MAX_WIDTH_MEDIUM = MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_MEDIUM
    RECOMMENDED_BUTTON_MAX_WIDTH = MODEL_MANAGEMENT_RECOMMENDED_BUTTON_MAX_WIDTH

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
        self.model_manager.downloader.download_cancelled.connect(self._on_download_cancelled)
        self.model_manager.downloader.download_failed.connect(self._on_download_failed)
        self.model_manager.model_validation_failed.connect(self._on_validation_failed)

        # 连接翻译模型下载器信号
        self.model_manager.translation_models_updated.connect(self._refresh_translation_model_list)
        self.model_manager.translation_downloader.download_progress.connect(
            self._update_download_progress
        )
        self.model_manager.translation_downloader.download_completed.connect(
            self._refresh_translation_model_list
        )
        self.model_manager.translation_downloader.download_failed.connect(
            self._refresh_translation_model_list
        )
        # 翻译模型卡片引用
        self.translation_model_cards: Dict[str, QWidget] = {}

        # 连接语言切换信号
        self.i18n.language_changed.connect(self.update_translations)

        # 设置 UI
        self.setup_ui()

        logger.info(self.i18n.t("logging.settings.model_management_page.initialized"))

    def setup_ui(self):
        """设置 UI 布局"""
        # 页面标题
        self.title_label = QLabel(self.i18n.t("settings.model_management.title"))
        self.title_label.setObjectName(self.PAGE_TITLE_OBJECT_NAME)
        self.content_layout.addWidget(self.title_label)

        # 页面描述
        self.desc_label = QLabel(self.i18n.t("settings.model_management.description"))
        self.desc_label.setWordWrap(True)
        self.desc_label.setObjectName("description_label")
        self.content_layout.addWidget(self.desc_label)

        self.related_settings_layout = create_hbox()
        self.related_settings_label = QLabel(
            self.i18n.t("settings.model_management.related_settings")
        )
        self.go_to_transcription_button = create_button(
            self.i18n.t("settings.model_management.go_to_transcription_settings")
        )
        self.go_to_transcription_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.go_to_transcription_button.clicked.connect(self._on_go_to_transcription_settings)
        self.go_to_translation_button = create_button(
            self.i18n.t("settings.model_management.go_to_translation_settings")
        )
        self.go_to_translation_button.setProperty("role", ROLE_SETTINGS_INLINE_ACTION)
        self.go_to_translation_button.clicked.connect(self._on_go_to_translation_settings)
        self.related_settings_layout.addWidget(self.related_settings_label)
        self.related_settings_layout.addWidget(self.go_to_transcription_button)
        self.related_settings_layout.addWidget(self.go_to_translation_button)
        self.related_settings_layout.addStretch()
        self.content_layout.addLayout(self.related_settings_layout)

        self.add_spacing()

        # 引入标签页
        self.tabs = QTabWidget()
        self.tabs.setObjectName("model_management_tabs")
        self.content_layout.addWidget(self.tabs)

        # ---- 语音模型标签页 ----
        self.speech_tab = QWidget()
        self.speech_layout = create_vbox(margins=(10, 10, 10, 10), spacing=20)
        self.speech_tab.setLayout(self.speech_layout)

        # 推荐模型卡片区域（条件显示）
        self.recommendation_container = QWidget()
        self.recommendation_layout = create_vbox(
            spacing=self.MODEL_LIST_SPACING,
            margins=ZERO_MARGINS,
        )
        self.recommendation_container.setLayout(self.recommendation_layout)
        self.speech_layout.addWidget(self.recommendation_container)

        # 已下载语音模型区域
        self.downloaded_title = self.add_section_title(
            self.i18n.t("settings.model_management.downloaded_models"), layout=self.speech_layout
        )

        self.downloaded_models_container = QWidget()
        self.downloaded_models_layout = create_vbox(
            spacing=self.MODEL_LIST_SPACING,
            margins=ZERO_MARGINS,
        )
        self.downloaded_models_container.setLayout(self.downloaded_models_layout)
        self.speech_layout.addWidget(self.downloaded_models_container)

        self.add_section_spacing(layout=self.speech_layout)

        # 可下载语音模型区域
        self.available_title = self.add_section_title(
            self.i18n.t("settings.model_management.available_models"), layout=self.speech_layout
        )

        self.available_models_container = QWidget()
        self.available_models_layout = create_vbox(
            spacing=self.MODEL_LIST_SPACING,
            margins=ZERO_MARGINS,
        )
        self.available_models_container.setLayout(self.available_models_layout)
        self.speech_layout.addWidget(self.available_models_container)

        self.speech_layout.addStretch()
        self.tabs.addTab(self.speech_tab, self.i18n.t("settings.model_management.speech_tab"))

        # ---- 翻译模型标签页 ----
        self.translation_tab = QWidget()
        self.translation_layout = create_vbox(margins=(10, 10, 10, 10), spacing=20)
        self.translation_tab.setLayout(self.translation_layout)

        self.translation_models_title = self.add_section_title(
            self.i18n.t("settings.model_management.translation_models"),
            layout=self.translation_layout,
        )

        self.translation_models_desc = QLabel(
            self.i18n.t("settings.model_management.translation_models_desc")
        )
        self.translation_models_desc.setWordWrap(True)
        self.translation_models_desc.setObjectName("description_label")
        self.translation_layout.addWidget(self.translation_models_desc)

        self.translation_models_container = QWidget()
        self.translation_models_layout = create_vbox(
            spacing=self.MODEL_LIST_SPACING,
            margins=ZERO_MARGINS,
        )
        self.translation_models_container.setLayout(self.translation_models_layout)
        self.translation_layout.addWidget(self.translation_models_container)

        self.translation_layout.addStretch()
        self.tabs.addTab(
            self.translation_tab, self.i18n.t("settings.model_management.translation_tab")
        )

        # 刷新模型列表
        self._refresh_model_list()
        self._refresh_translation_model_list()

        logger.debug("Model management UI setup complete")

    def update_translations(self):
        """更新所有 UI 文本以响应语言切换"""
        logger.debug("Updating translations for model management page")

        # 更新页面标题和描述
        if hasattr(self, "title_label"):
            self.title_label.setText(self.i18n.t("settings.model_management.title"))
        if hasattr(self, "desc_label"):
            self.desc_label.setText(self.i18n.t("settings.model_management.description"))
        if hasattr(self, "related_settings_label"):
            self.related_settings_label.setText(
                self.i18n.t("settings.model_management.related_settings")
            )
        if hasattr(self, "go_to_transcription_button"):
            self.go_to_transcription_button.setText(
                self.i18n.t("settings.model_management.go_to_transcription_settings")
            )
        if hasattr(self, "go_to_translation_button"):
            self.go_to_translation_button.setText(
                self.i18n.t("settings.model_management.go_to_translation_settings")
            )

        # 更新区域标题
        if hasattr(self, "downloaded_title"):
            self.downloaded_title.setText(
                self.i18n.t("settings.model_management.downloaded_models")
            )
        if hasattr(self, "available_title"):
            self.available_title.setText(self.i18n.t("settings.model_management.available_models"))
        if hasattr(self, "translation_models_title"):
            self.translation_models_title.setText(
                self.i18n.t("settings.model_management.translation_models")
            )
        if hasattr(self, "translation_models_desc"):
            self.translation_models_desc.setText(
                self.i18n.t("settings.model_management.translation_models_desc")
            )

        # 更新标签页标题
        if hasattr(self, "tabs"):
            self.tabs.setTabText(0, self.i18n.t("settings.model_management.speech_tab"))
            self.tabs.setTabText(1, self.i18n.t("settings.model_management.translation_tab"))

        # 刷新整个模型列表，这会重新创建所有卡片并使用新的翻译
        self._refresh_model_list()
        self._refresh_translation_model_list()

        logger.debug("Translations updated for model management page")

    @Slot()
    def _refresh_model_list(self):
        """刷新语音模型列表"""
        logger.debug("Refreshing speech model list")

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
            self.recommendation_container.setVisible(True)
        else:
            # 隐藏推荐卡片
            self.recommendation_container.setVisible(False)

        # 分类显示模型
        for model in all_models:
            card = self._create_unified_card(model)
            if model.is_downloaded:
                self.downloaded_models_layout.addWidget(card)
            else:
                self.available_models_layout.addWidget(card)
            self.model_cards[model.name] = card

        logger.debug(f"Speech model list refreshed: {len(downloaded_models)} downloaded")

    def _create_unified_card(
        self, model: Union[ModelInfo, TranslationModelInfo]
    ) -> ModelCardWidget:
        """创建并配置统一的模型卡片组件。"""
        card = ModelCardWidget(model, self.i18n, self.model_manager)

        # 连接信号
        if isinstance(model, TranslationModelInfo):
            card.download_clicked.connect(self._download_translation_model)
            card.delete_clicked.connect(self._delete_translation_model)
            card.details_clicked.connect(self._on_view_translation_details_clicked)
        else:
            card.download_clicked.connect(self._on_download_clicked)
            card.delete_clicked.connect(self._on_delete_clicked)
            card.details_clicked.connect(self._on_view_details_clicked)

        card.cancel_download_clicked.connect(self._on_cancel_download_clicked)

        return card

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

        confirm_text = self.i18n.t(
            "settings.model_management.delete_confirm_message",
            model=model.full_name,
            size=model.size_mb,
        )
        warning_text = self.i18n.t("settings.model_management.delete_warning")

        if self.show_question(
            self.i18n.t("settings.model_management.delete_confirm_title"),
            f"{confirm_text}\n\n{warning_text}",
        ):
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
                self.show_info(
                    self.i18n.t("settings.model_management.delete_success_title"),
                    self.i18n.t(
                        "settings.model_management.delete_success_message", model=model_name
                    ),
                )

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
        from core.qt_imports import QRunnable, QThreadPool

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
        if self.show_question(
            self.i18n.t("settings.model_management.cancel_download_title"),
            self.i18n.t("settings.model_management.cancel_download_confirm", model=model_name),
        ):
            # 取消下载
            self.model_manager.cancel_download(model_name)
            logger.info(f"Cancel requested for model download: {model_name}")

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

        # 推荐标题
        title_label = self._create_model_name_label(
            self.i18n.t(
                "settings.model_management.recommendation_title", model=recommended_model.full_name
            ),
            point_size=self.SECTION_TITLE_FONT_SIZE,
            role="model-title-recommendation",
        )
        layout.addWidget(title_label)

        # 推荐理由
        reason_text = self._get_recommendation_reason(recommended_model_name)
        reason_label = QLabel(reason_text)
        reason_label.setWordWrap(True)
        reason_label.setProperty("role", ROLE_MODEL_REASON)
        layout.addWidget(reason_label)

        # 模型特征
        features_layout = create_hbox()

        # 大小
        size_text = (
            f"{self.i18n.t('settings.model_management.size')}: " f"{recommended_model.size_mb} MB"
        )
        size_label = QLabel(size_text)
        size_label.setProperty("role", ROLE_AUDIO_FILE)
        features_layout.addWidget(size_label)

        # 速度
        speed_text = (
            f"{self.i18n.t('settings.model_management.speed')}: "
            f"{self._translate_speed(recommended_model.speed)}"
        )
        speed_label = QLabel(speed_text)
        speed_label.setProperty("role", ROLE_AUDIO_FILE)
        features_layout.addWidget(speed_label)

        # 准确度
        accuracy_text = (
            f"{self.i18n.t('settings.model_management.accuracy')}: "
            f"{self._translate_accuracy(recommended_model.accuracy)}"
        )
        accuracy_label = QLabel(accuracy_text)
        accuracy_label.setProperty("role", ROLE_AUDIO_FILE)
        features_layout.addWidget(accuracy_label)

        features_layout.addStretch()

        layout.addLayout(features_layout)

        # 一键下载按钮
        download_btn = create_button(self.i18n.t("settings.model_management.download_recommended"))
        download_btn.setMaximumWidth(self.RECOMMENDED_BUTTON_MAX_WIDTH)
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

    def _create_model_name_label(
        self, text: str, point_size: int = 12, role: str = "model-title"
    ) -> QLabel:
        """创建统一样式的模型名称标签"""
        label = QLabel(text)
        font = QFont()
        font.setPointSize(point_size)
        font.setBold(True)
        label.setFont(font)
        label.setProperty("role", role)
        return label

    def _translate_speed(self, speed: str) -> str:
        """翻译速度描述"""
        speed_map = {
            "fastest": self.i18n.t("settings.model_management.speed_fastest"),
            "fast": self.i18n.t("settings.model_management.speed_fast"),
            "medium": self.i18n.t("settings.model_management.speed_medium"),
            "slow": self.i18n.t("settings.model_management.speed_slow"),
        }
        return speed_map.get(speed, speed)

    def _translate_accuracy(self, accuracy: str) -> str:
        """翻译准确度描述"""
        accuracy_map = {
            "low": self.i18n.t("settings.model_management.accuracy_low"),
            "medium": self.i18n.t("settings.model_management.accuracy_medium"),
            "high": self.i18n.t("settings.model_management.accuracy_high"),
        }
        return accuracy_map.get(accuracy, accuracy)

    @Slot(str, int, float)
    def _update_download_progress(self, model_id: str, progress: int, speed: float):
        """更新下载进度。支持语音和翻译模型。"""
        # 在语音模型卡片或翻译模型卡片中查找
        card = self.model_cards.get(model_id) or self.translation_model_cards.get(model_id)
        if card and isinstance(card, ModelCardWidget):
            card.update_progress(progress)

    @Slot(str)
    def _on_download_completed(self, model_name: str):
        """处理下载完成事件"""
        logger.info(f"Download completed for model: {model_name}")
        # 注意：刷新逻辑由 ModelManager.models_updated 信号触发

        # 显示成功通知
        self.show_info(
            self.i18n.t("settings.model_management.download_success_title"),
            self.i18n.t("settings.model_management.download_success_message", model=model_name),
        )

    @Slot(str)
    def _on_download_cancelled(self, model_name: str):
        """处理下载取消事件。"""
        logger.info(f"Download cancelled for model: {model_name}")

    @Slot(str, str)
    def _on_download_failed(self, model_name: str, error: str):
        """处理下载失败事件"""
        logger.error(f"Download failed for {model_name}: {error}")

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
        if self.show_question(
            self.i18n.t("settings.model_management.retry_title"),
            self.i18n.t("settings.model_management.retry_message"),
            default_yes=True,
        ):
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

    def save_settings(self):
        """保存设置（模型管理页面不需要保存设置）"""

    def _on_go_to_transcription_settings(self) -> None:
        """Navigate to transcription settings page."""
        self._open_settings_page("transcription")

    def _on_go_to_translation_settings(self) -> None:
        """Navigate to translation settings page."""
        self._open_settings_page("translation")

    # ------------------------------------------------------------------
    # 翻译模型（Opus-MT）管理方法
    # ------------------------------------------------------------------

    @Slot()
    def _refresh_translation_model_list(self):
        """刷新翻译模型列表"""
        if not hasattr(self, "translation_models_layout"):
            return

        logger.debug("Refreshing translation model list")
        self._clear_layout(self.translation_models_layout)
        self.translation_model_cards.clear()

        all_models = self.model_manager.get_all_translation_models()
        for model in all_models:
            card = self._create_unified_card(model)
            self.translation_models_layout.addWidget(card)
            self.translation_model_cards[model.model_id] = card

    def _on_view_translation_details_clicked(self, model_id: str):
        """处理翻译模型查看详情点击"""
        model = self.model_manager.get_translation_model(model_id)
        if model:
            dialog = ModelDetailsDialog(model, self.i18n, self)
            dialog.exec()

    def _download_translation_model(self, model_id: str) -> None:
        """触发翻译模型下载（在 QThreadPool 线程中异步运行）。"""
        from core.qt_imports import QRunnable, QThreadPool

        model_info = self.model_manager.get_translation_model(model_id)
        if not model_info:
            return

        model_manager = self.model_manager

        def run_download() -> None:
            import asyncio as _asyncio

            loop = _asyncio.new_event_loop()
            try:
                _asyncio.set_event_loop(loop)
                loop.run_until_complete(model_manager.download_translation_model(model_id))
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Translation model download failed in thread for %s: %s",
                    model_id,
                    exc,
                    exc_info=True,
                )
            finally:
                loop.close()

        class _DownloadRunnable(QRunnable):
            def run(self) -> None:
                run_download()

        QThreadPool.globalInstance().start(_DownloadRunnable())

    def _delete_translation_model(self, model_id: str) -> None:
        """确认后删除翻译模型。"""
        model_info = self.model_manager.get_translation_model(model_id)
        if not model_info:
            return

        if self.show_question(
            self.i18n.t("settings.model_management.confirm_delete_title"),
            self.i18n.t(
                "settings.model_management.confirm_delete_message",
                model=model_info.display_name,
            ),
        ):
            success = self.model_manager.delete_translation_model(model_id)
            if not success:
                show_error_dialog(
                    parent=self,
                    title=self.i18n.t("settings.model_management.validation_error"),
                    message=self.i18n.t("settings.model_management.delete_failed"),
                )


class ModelDetailsDialog(QDialog):
    """模型详情对话框"""

    MIN_WIDTH = MODEL_DETAILS_DIALOG_MIN_WIDTH
    MIN_HEIGHT = MODEL_DETAILS_DIALOG_MIN_HEIGHT

    def __init__(
        self, model: Union[ModelInfo, TranslationModelInfo], i18n: I18nQtManager, parent=None
    ):
        """
        初始化模型详情对话框

        Args:
            model: 模型信息 (语音或翻译)
            i18n: 国际化管理器
            parent: 父控件
        """
        super().__init__(parent)
        from pathlib import Path

        from core.qt_imports import QGridLayout

        self.model = model
        self.i18n = i18n

        is_translation = isinstance(model, TranslationModelInfo)
        title = model.display_name if is_translation else model.full_name
        name_id = model.model_id if is_translation else model.name

        self.setWindowTitle(i18n.t("settings.model_management.details_title"))
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMinimumHeight(self.MIN_HEIGHT)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel(title)
        title_label.setObjectName("section_title")
        layout.addWidget(title_label)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # 详细信息网格
        info_layout = QGridLayout()
        info_layout.setColumnStretch(1, 1)

        row = 0

        # 模型标识符
        info_layout.addWidget(QLabel(i18n.t("settings.model_management.model_name") + ":"), row, 0)
        info_layout.addWidget(QLabel(name_id), row, 1)
        row += 1

        if not is_translation:
            # 模型版本（仅语音模型显示，尝试从名称提取）
            version = "v3"
            if "large-v1" in name_id:
                version = "v1"
            elif "large-v2" in name_id:
                version = "v2"
            elif "large-v3" in name_id:
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
            is_multilingual = "multi" in model.languages
            lang_text = (
                i18n.t("settings.model_management.multilingual")
                if is_multilingual
                else i18n.t("settings.model_management.english_only")
            )

            info_layout.addWidget(QLabel(lang_text), row, 1)
            row += 1
        else:
            # 翻译模型特有信息：语言对
            info_layout.addWidget(
                QLabel(i18n.t("settings.model_management.language_pair") + ":"), row, 0
            )
            info_layout.addWidget(QLabel(f"{model.source_lang} -> {model.target_lang}"), row, 1)
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
            path_label.setProperty("role", ROLE_TIME_DISPLAY)
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
            date_str = format_localized_datetime(model.download_date)
            info_layout.addWidget(QLabel(date_str), row, 1)
            row += 1

        # 最后使用日期
        info_layout.addWidget(QLabel(i18n.t("settings.model_management.last_used") + ":"), row, 0)
        if model.last_used:
            last_used_str = format_localized_datetime(model.last_used)
            info_layout.addWidget(QLabel(last_used_str), row, 1)
        else:
            info_layout.addWidget(QLabel(i18n.t("settings.model_management.never_used")), row, 1)
        row += 1

        # 使用次数
        info_layout.addWidget(
            QLabel(i18n.t("settings.model_management.usage_count_label") + ":"), row, 0
        )
        is_translation = isinstance(model, TranslationModelInfo)
        usage_count = (
            getattr(model, "usage_count", 0)
            if not is_translation
            else getattr(model, "use_count", 0)
        )
        info_layout.addWidget(QLabel(str(usage_count)), row, 1)
        row += 1

        layout.addLayout(info_layout)

        # 添加弹性空间
        layout.addStretch()

        # 按钮布局
        button_layout = create_hbox()
        button_layout.addStretch()

        # 在文件管理器中显示按钮
        if model.local_path:
            show_in_explorer_btn = create_button(
                i18n.t("settings.model_management.show_in_explorer")
            )
            show_in_explorer_btn.clicked.connect(
                lambda: self._on_show_in_explorer(model.local_path)
            )
            button_layout.addWidget(show_in_explorer_btn)

        # 关闭按钮
        close_btn = create_button(i18n.t("settings.model_management.close"))
        close_btn.setDefault(True)
        connect_button_with_callback(close_btn, self.accept)
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
