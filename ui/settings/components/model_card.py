# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2025 EchoNote Contributors

import logging
from datetime import datetime
from typing import Dict, Optional, Union

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models.registry import ModelInfo
from core.models.translation_registry import TranslationModelInfo
from ui.base_widgets import (
    create_button,
    create_hbox,
    create_primary_button,
)
from ui.constants import (
    MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_MEDIUM,
    MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_SMALL,
    MODEL_MANAGEMENT_MODEL_NAME_FONT_SIZE,
)
from utils.i18n import I18nQtManager
from utils.time_utils import now_utc

logger = logging.getLogger("echonote.ui.settings.components.model_card")

class ModelCardWidget(QFrame):
    """
    统一风格的模型卡片。支持语音模型 (ModelInfo) 和翻译模型 (TranslationModelInfo)。
    """
    
    # 信号定义
    download_clicked = Signal(str)      # model_id
    delete_clicked = Signal(str)        # model_id
    config_clicked = Signal(str)        # model_id
    details_clicked = Signal(str)       # model_id
    cancel_download_clicked = Signal(str) # model_id

    def __init__(
        self, 
        model: Union[ModelInfo, TranslationModelInfo], 
        i18n: I18nQtManager,
        model_manager,
        parent=None
    ):
        super().__init__(parent)
        self.model = model
        self.i18n = i18n
        self.model_manager = model_manager
        
        self.is_translation = isinstance(model, TranslationModelInfo)
        self.model_id = model.model_id if self.is_translation else model.name
        
        self._setup_ui()
        self._update_state()

    def _setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName(f"model-card-{'translation' if self.is_translation else 'speech'}")
        
        self.main_layout = QVBoxLayout(self)
        
        # 第一行：标题和主要操作按钮
        header_layout = create_hbox()
        title = self.model.display_name if self.is_translation else self.model.full_name
        self.name_label = QLabel(title)
        font = QFont()
        font.setPointSize(MODEL_MANAGEMENT_MODEL_NAME_FONT_SIZE)
        font.setBold(True)
        self.name_label.setFont(font)
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        
        # 操作按钮容器
        self.actions_layout = create_hbox(spacing=10)
        header_layout.addLayout(self.actions_layout)
        self.main_layout.addLayout(header_layout)
        
        # 第二行：特征信息（大小、速度等）
        self.features_layout = create_hbox()
        self.main_layout.addLayout(self.features_layout)
        
        # 第三行：状态/统计信息
        self.stats_layout = create_hbox()
        self.main_layout.addLayout(self.stats_layout)
        
        # 进度条和取消按钮
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName(f"progress_bar_{self.model_id}")
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(100)
        self.main_layout.addWidget(self.progress_bar)
        
        self.cancel_btn = create_button(self.i18n.t("settings.model_management.cancel_download"))
        self.cancel_btn.setObjectName(f"cancel_btn_{self.model_id}")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setMaximumWidth(MODEL_MANAGEMENT_ACTION_BUTTON_MAX_WIDTH_MEDIUM)
        self.cancel_btn.clicked.connect(lambda: self.cancel_download_clicked.emit(self.model_id))
        self.main_layout.addWidget(self.cancel_btn)

    def _update_state(self):
        # 清除旧按钮
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        while self.features_layout.count():
            item = self.features_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. 按钮构建
        if self.model.is_downloaded:
            if not self.is_translation:
                config_btn = create_button(self.i18n.t("settings.model_management.configure"))
                config_btn.clicked.connect(lambda: self.config_clicked.emit(self.model_id))
                self.actions_layout.addWidget(config_btn)
            
            delete_btn = create_button(self.i18n.t("settings.model_management.delete"))
            delete_btn.setProperty("role", "model-delete")
            delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.model_id))
            
            # 语音模型忙碌检查
            if not self.is_translation and self.model_manager.is_model_in_use(self.model_id):
                delete_btn.setEnabled(False)
                delete_btn.setToolTip(self.i18n.t("settings.model_management.model_in_use"))
            
            self.actions_layout.addWidget(delete_btn)
            
            details_btn = create_button(self.i18n.t("settings.model_management.view_details"))
            details_btn.clicked.connect(lambda: self.details_clicked.emit(self.model_id))
            self.actions_layout.addWidget(details_btn)
        else:
            download_btn = create_primary_button(self.i18n.t("settings.model_management.download"))
            download_btn.clicked.connect(lambda: self.download_clicked.emit(self.model_id))
            
            # 检查是否正在下载
            is_downloading = False
            if self.is_translation:
                is_downloading = self.model_manager.translation_downloader.is_downloading(self.model_id)
            else:
                is_downloading = self.model_manager.downloader.is_downloading(self.model_id)
            
            if is_downloading:
                download_btn.setEnabled(False)
                download_btn.setText(self.i18n.t("settings.model_management.downloading"))
                self.progress_bar.setVisible(True)
                self.cancel_btn.setVisible(True)
            
            self.actions_layout.addWidget(download_btn)

        # 2. 特征显示
        size_text = f"{self.i18n.t('settings.model_management.size')}: {self.model.size_mb} MB"
        self.features_layout.addWidget(QLabel(size_text))
        
        if self.is_translation:
            lang_text = f"{self.model.source_lang} -> {self.model.target_lang}"
            self.features_layout.addWidget(QLabel(lang_text))
        else:
            speed_text = f"{self.i18n.t('settings.model_management.speed')}: {self._translate_speed(self.model.speed)}"
            self.features_layout.addWidget(QLabel(speed_text))
            accuracy_text = f"{self.i18n.t('settings.model_management.accuracy')}: {self._translate_accuracy(self.model.accuracy)}"
            self.features_layout.addWidget(QLabel(accuracy_text))
        
        self.features_layout.addStretch()

        # 3. 统计显示
        if self.model.is_downloaded:
            usage_count = getattr(self.model, "usage_count", 0) if not self.is_translation else getattr(self.model, "use_count", 0)
            usage_text = self.i18n.t("settings.model_management.usage_count", count=usage_count)
            stats_label = QLabel(usage_text)
            stats_label.setProperty("role", "time-display")
            self.stats_layout.addWidget(stats_label)
            
            last_used = self.model.last_used
            if last_used:
                last_used_text = self._format_relative_time(last_used)
                time_label = QLabel(f"{self.i18n.t('settings.model_management.last_used')}: {last_used_text}")
            else:
                time_label = QLabel(self.i18n.t("settings.model_management.never_used"))
            
            time_label.setProperty("role", "time-display")
            self.stats_layout.addWidget(time_label)
            self.stats_layout.addStretch()

    def _translate_speed(self, speed: str) -> str:
        speed_map = {
            "fastest": self.i18n.t("settings.model_management.speed_fastest"),
            "fast": self.i18n.t("settings.model_management.speed_fast"),
            "medium": self.i18n.t("settings.model_management.speed_medium"),
            "slow": self.i18n.t("settings.model_management.speed_slow"),
        }
        return speed_map.get(speed, speed)

    def _translate_accuracy(self, accuracy: str) -> str:
        accuracy_map = {
            "low": self.i18n.t("settings.model_management.accuracy_low"),
            "medium": self.i18n.t("settings.model_management.accuracy_medium"),
            "high": self.i18n.t("settings.model_management.accuracy_high"),
        }
        return accuracy_map.get(accuracy, accuracy)

    def _format_relative_time(self, dt: datetime) -> str:
        now = now_utc()
        # Ensure dt is also aware for subtraction
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=now.tzinfo)
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

    def update_progress(self, progress: float):
        """更新下载进度并确保 UI 处于下载状态。"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(int(progress))
        self.cancel_btn.setVisible(True)
        
        # 查找并更新可能存在的下载按钮状态（双重保险）
        for i in range(self.actions_layout.count()):
            widget = self.actions_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton) and widget.text() == self.i18n.t("settings.model_management.download"):
                widget.setEnabled(False)
                widget.setText(self.i18n.t("settings.model_management.downloading"))

    def refresh(self, model: Union[ModelInfo, TranslationModelInfo]):
        """外部调用以重新同步数据并刷新 UI。"""
        self.model = model
        self._update_state()
