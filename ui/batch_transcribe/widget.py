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
Batch transcription widget.

Provides UI for importing audio files and managing transcription tasks.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from config.constants import (
    DEFAULT_TRANSLATION_TARGET_LANGUAGE,
    TRANSLATION_ENGINE_OPUS_MT,
    TRANSLATION_LANGUAGE_AUTO,
)
from core.settings.manager import resolve_translation_languages_from_settings
from core.transcription.manager import (
    TRANSCRIPTION_TASK_KIND,
    TEXT_TRANSLATION_SUFFIXES,
    TRANSLATION_TASK_KIND,
    TranscriptionManager,
)
from engines.speech.base import AUDIO_VIDEO_SUFFIXES
from ui.base_widgets import (
    BaseWidget,
    connect_button_with_callback,
    create_button,
    create_hbox,
    create_primary_button,
)
from ui.batch_transcribe.task_item import TaskItem
from ui.constants import (
    BATCH_SELECTOR_MIN_WIDTH,
    PAGE_COMPACT_SPACING,
    ROLE_TOOLBAR_SECONDARY_ACTION,
)
from core.qt_imports import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSize,
    QTabWidget,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from utils.i18n import I18nQtManager, LANGUAGE_OPTION_KEYS

if TYPE_CHECKING:
    from ui.batch_transcribe.transcript_viewer import TranscriptViewerDialog

logger = logging.getLogger("echonote.ui.batch_transcribe")


@dataclass
class _TaskTabContext:
    kind: str
    tab: QWidget
    queue_label: QLabel
    task_list: QListWidget
    import_file_btn: QPushButton
    import_folder_btn: QPushButton
    clear_queue_btn: QPushButton
    download_guide_frame: QFrame
    download_guide_message_label: QLabel
    download_guide_button: QPushButton
    paste_text_btn: Optional[QPushButton] = None


class BatchTranscribeWidget(BaseWidget):
    """
    Main widget for batch audio transcription.

    Provides file import, engine selection, and task queue management.
    """

    # Signal emitted when a task is added
    task_added = Signal(str)  # task_id
    # Internal signal for manager events (thread-safe bridge)
    manager_event = Signal(str, dict)

    _CLEAR_QUEUE_MAX_RETRIES = 10
    _CLEAR_QUEUE_RETRY_INTERVAL_MS = 300
    def __init__(
        self,
        transcription_manager: TranscriptionManager,
        i18n: I18nQtManager,
        model_manager=None,
        parent: Optional[QWidget] = None,
        allow_deferred_load: bool = True,
    ):
        """
        Initialize batch transcribe widget.

        Args:
            transcription_manager: Transcription manager instance
            i18n: Internationalization manager
            model_manager: Model manager instance (optional)
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.transcription_manager = transcription_manager
        self.model_manager = model_manager

        # Task item widgets dictionary (task_id -> TaskItem)
        self.task_items: Dict[str, TaskItem] = {}
        self.task_item_kinds: Dict[str, str] = {}
        self._tab_contexts: Dict[str, _TaskTabContext] = {}

        # Open transcript viewer windows dictionary (task_id -> TranscriptViewerDialog)
        self.open_viewers: Dict[str, "TranscriptViewerDialog"] = {}

        self._clear_queue_in_progress = False

        # Setup UI
        self.setup_ui()

        # Connect language change signal
        self.i18n.language_changed.connect(self.update_translations)

        # Connect model manager signals if available
        if self.model_manager:
            self.model_manager.models_updated.connect(self._update_model_list)
            if hasattr(self.model_manager, "translation_models_updated"):
                self.model_manager.translation_models_updated.connect(
                    self._on_translation_models_updated
                )

        # Connect manager event signal
        self.manager_event.connect(self._handle_manager_event)

        # Initial load of tasks and models (delayed to avoid startup crash on macOS)
        if allow_deferred_load:
            QTimer.singleShot(50, self._initial_load)
        else:
            self._initial_load()

        logger.info(self.i18n.t("logging.batch_transcribe.widget_initialized"))

    def setup_ui(self):
        """Set up the user interface."""
        layout = self.create_page_layout()
        self.title_label = self.create_page_title("batch_transcribe.title", layout)

        self.task_tabs = QTabWidget()
        self.task_tabs.setObjectName("main_tabs")
        self.task_tabs.currentChanged.connect(self._on_task_tab_changed)
        layout.addWidget(self.task_tabs)

        transcription_context = self._build_task_tab(TRANSCRIPTION_TASK_KIND)
        translation_context = self._build_task_tab(TRANSLATION_TASK_KIND)
        self._tab_contexts = {
            TRANSCRIPTION_TASK_KIND: transcription_context,
            TRANSLATION_TASK_KIND: translation_context,
        }
        self.task_tabs.addTab(transcription_context.tab, "")
        self.task_tabs.addTab(translation_context.tab, "")

        # Backward-compatible aliases used by tests and legacy call-sites.
        self.import_file_btn = transcription_context.import_file_btn
        self.import_folder_btn = transcription_context.import_folder_btn
        self.clear_queue_btn = transcription_context.clear_queue_btn
        self.paste_text_btn = translation_context.paste_text_btn
        self.transcription_import_file_btn = transcription_context.import_file_btn
        self.transcription_import_folder_btn = transcription_context.import_folder_btn
        self.transcription_clear_queue_btn = transcription_context.clear_queue_btn
        self.translation_import_file_btn = translation_context.import_file_btn
        self.translation_import_folder_btn = translation_context.import_folder_btn
        self.translation_clear_queue_btn = translation_context.clear_queue_btn
        self.translation_paste_text_btn = translation_context.paste_text_btn
        self.queue_label = transcription_context.queue_label
        self.task_list = transcription_context.task_list
        self.transcription_queue_label = transcription_context.queue_label
        self.translation_queue_label = translation_context.queue_label
        self.transcription_task_list = transcription_context.task_list
        self.translation_task_list = translation_context.task_list

        self.update_translations()
        self._populate_translation_target_languages()
        self._update_mode_controls()

        logger.debug("Batch transcribe UI setup complete")

    def _build_task_tab(self, task_kind: str) -> _TaskTabContext:
        tab = QWidget()
        tab.setObjectName("transcription_tab" if task_kind == TRANSCRIPTION_TASK_KIND else "translation_tab")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(PAGE_COMPACT_SPACING)

        config_layout = create_hbox(spacing=PAGE_COMPACT_SPACING)
        if task_kind == TRANSCRIPTION_TASK_KIND:
            if self.model_manager:
                self.model_label = QLabel()
                self.model_label.setObjectName("model_label")
                config_layout.addWidget(self.model_label)

                self.model_combo = QComboBox()
                self.model_combo.setObjectName("model_combo")
                self.model_combo.setMinimumWidth(BATCH_SELECTOR_MIN_WIDTH)
                config_layout.addWidget(self.model_combo)
            else:
                self.engine_label = QLabel()
                self.engine_label.setObjectName("engine_label")
                config_layout.addWidget(self.engine_label)

                self.engine_combo = QComboBox()
                self.engine_combo.setObjectName("engine_combo")
                self.engine_combo.setMinimumWidth(BATCH_SELECTOR_MIN_WIDTH)
                self._populate_engines(self.engine_combo)
                config_layout.addWidget(self.engine_combo)
        else:
            self.translation_target_label = QLabel()
            self.translation_target_label.setObjectName("translation_target_label")
            config_layout.addWidget(self.translation_target_label)

            self.translation_target_combo = QComboBox()
            self.translation_target_combo.setObjectName("translation_target_combo")
            self.translation_target_combo.setMinimumWidth(BATCH_SELECTOR_MIN_WIDTH)
            self.translation_target_combo.currentIndexChanged.connect(self._on_translation_target_changed)
            config_layout.addWidget(self.translation_target_combo)

        config_layout.addStretch()
        tab_layout.addLayout(config_layout)

        (
            download_guide_frame,
            download_guide_message_label,
            download_guide_button,
        ) = self._create_download_guide_widget(task_kind)
        tab_layout.addWidget(download_guide_frame)

        action_layout = create_hbox(spacing=PAGE_COMPACT_SPACING)
        import_file_btn = self._create_toolbar_button(
            action_layout,
            callback=self._on_import_file,
            callback_args=(task_kind,),
        )
        import_folder_btn = self._create_toolbar_button(
            action_layout,
            callback=self._on_import_folder,
            callback_args=(task_kind,),
        )
        paste_text_btn: Optional[QPushButton] = None
        if task_kind == TRANSLATION_TASK_KIND:
            paste_text_btn = self._create_toolbar_button(
                action_layout,
                callback=self._on_paste_text,
                callback_args=(task_kind,),
            )
        clear_queue_btn = self._create_toolbar_button(
            action_layout,
            callback=self._on_clear_queue,
            callback_args=(task_kind,),
        )
        action_layout.addStretch()
        tab_layout.addLayout(action_layout)

        queue_label = QLabel()
        queue_label.setObjectName("section_title")
        tab_layout.addWidget(queue_label)

        task_list = QListWidget()
        task_list.setObjectName("task_list")
        tab_layout.addWidget(task_list)

        return _TaskTabContext(
            kind=task_kind,
            tab=tab,
            queue_label=queue_label,
            task_list=task_list,
            import_file_btn=import_file_btn,
            import_folder_btn=import_folder_btn,
            clear_queue_btn=clear_queue_btn,
            download_guide_frame=download_guide_frame,
            download_guide_message_label=download_guide_message_label,
            download_guide_button=download_guide_button,
            paste_text_btn=paste_text_btn,
        )

    def _create_download_guide_widget(
        self, task_kind: str
    ) -> tuple[QFrame, QLabel, QPushButton]:
        guide_frame = QFrame()
        guide_frame.setObjectName("download_guide_frame")
        guide_frame.setFrameShape(QFrame.Shape.StyledPanel)
        guide_frame.setVisible(False)

        guide_layout = QVBoxLayout(guide_frame)
        message_label = QLabel()
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guide_layout.addWidget(message_label)

        download_btn = create_primary_button(self.i18n.t("batch_transcribe.go_to_download"))
        connect_button_with_callback(download_btn, self._on_go_to_download, task_kind)
        guide_layout.addWidget(download_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return guide_frame, message_label, download_btn

    def _create_toolbar_button(
        self,
        toolbar_layout: QHBoxLayout,
        *,
        callback,
        callback_args: tuple = (),
    ) -> QPushButton:
        """Create and append a standard toolbar action button."""
        button = QPushButton()
        button.setProperty("role", ROLE_TOOLBAR_SECONDARY_ACTION)
        connect_button_with_callback(button, callback, *callback_args)
        toolbar_layout.addWidget(button)
        return button

    def _current_task_kind(self) -> str:
        if hasattr(self, "task_tabs") and self.task_tabs.currentIndex() == 1:
            return TRANSLATION_TASK_KIND
        return TRANSCRIPTION_TASK_KIND

    def _is_translation_mode(self) -> bool:
        return self._current_task_kind() == TRANSLATION_TASK_KIND

    def _translation_engine_available(self) -> bool:
        return bool(getattr(self.transcription_manager, "translation_engine", None))

    def _on_task_tab_changed(self, _index: int) -> None:
        self._update_mode_controls()

    def _on_translation_target_changed(self, _index: int) -> None:
        if self._is_translation_mode():
            self._refresh_download_guide()

    def _on_translation_models_updated(self) -> None:
        self._refresh_download_guide()
        self._update_mode_controls()

    def _update_mode_controls(self) -> None:
        transcription_ready = self._transcription_mode_ready()
        translation_ready, _ = self._resolve_translation_readiness()

        transcription_context = self._tab_contexts.get(TRANSCRIPTION_TASK_KIND)
        if transcription_context:
            transcription_context.import_file_btn.setEnabled(transcription_ready)
            transcription_context.import_folder_btn.setEnabled(transcription_ready)

        translation_context = self._tab_contexts.get(TRANSLATION_TASK_KIND)
        if translation_context:
            translation_context.import_file_btn.setEnabled(translation_ready)
            translation_context.import_folder_btn.setEnabled(translation_ready)
            if translation_context.paste_text_btn is not None:
                translation_context.paste_text_btn.setEnabled(translation_ready)

        if hasattr(self, "translation_target_combo"):
            self.translation_target_combo.setEnabled(self._translation_engine_available())
        self._set_clear_buttons_enabled(not self._clear_queue_in_progress)
        self._refresh_download_guide()

    def _set_clear_buttons_enabled(self, enabled: bool) -> None:
        for context in self._tab_contexts.values():
            context.clear_queue_btn.setEnabled(enabled)

    def _transcription_mode_ready(self) -> bool:
        if not self.model_manager or not hasattr(self, "model_combo"):
            return True
        return self.model_combo.isEnabled() and self.model_combo.currentData() is not None

    def _get_settings_manager(self):
        main_window = self.window()
        managers = getattr(main_window, "managers", None)
        if isinstance(managers, dict):
            return managers.get("settings_manager")
        return None

    def _get_translation_preferences(self) -> Dict[str, str]:
        settings_manager = self._get_settings_manager()
        resolved_languages = resolve_translation_languages_from_settings(settings_manager)
        source_lang = resolved_languages.get("translation_source_lang", TRANSLATION_LANGUAGE_AUTO)
        target_lang = resolved_languages.get(
            "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
        )
        engine = ""

        if settings_manager and hasattr(settings_manager, "get_translation_preferences"):
            try:
                preferences = settings_manager.get_translation_preferences()
                if isinstance(preferences, dict):
                    engine = str(preferences.get("translation_engine") or "")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load translation preferences: %s", exc)

        return {
            "translation_source_lang": source_lang,
            "translation_target_lang": target_lang,
            "translation_engine": engine,
        }

    def _resolve_translation_languages(
        self,
        *,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> Dict[str, str]:
        """Resolve translation language pair with page override > settings > defaults."""
        return resolve_translation_languages_from_settings(
            self._get_settings_manager(),
            source_lang=source_lang,
            target_lang=target_lang,
        )

    def _populate_translation_target_languages(self) -> None:
        if not hasattr(self, "translation_target_combo"):
            return

        preferences = self._get_translation_preferences()
        preferred_target = (
            self.translation_target_combo.currentData()
            or preferences.get("translation_target_lang")
            or DEFAULT_TRANSLATION_TARGET_LANGUAGE
        )
        self.translation_target_combo.blockSignals(True)
        self.translation_target_combo.clear()
        for code, label_key in LANGUAGE_OPTION_KEYS:
            self.translation_target_combo.addItem(self.i18n.t(label_key), code)

        target_index = self.translation_target_combo.findData(preferred_target)
        if target_index < 0:
            target_index = self.translation_target_combo.findData(DEFAULT_TRANSLATION_TARGET_LANGUAGE)
        if target_index < 0 and self.translation_target_combo.count() > 0:
            target_index = 0
        if target_index >= 0:
            self.translation_target_combo.setCurrentIndex(target_index)
        self.translation_target_combo.blockSignals(False)

    def _selected_translation_source_lang(self) -> str:
        return self._resolve_translation_languages().get(
            "translation_source_lang", TRANSLATION_LANGUAGE_AUTO
        )

    def _selected_translation_target_lang(self) -> str:
        selected = self.translation_target_combo.currentData() if hasattr(
            self, "translation_target_combo"
        ) else None
        return self._resolve_translation_languages(target_lang=selected).get(
            "translation_target_lang", DEFAULT_TRANSLATION_TARGET_LANGUAGE
        )

    def _translation_engine_name(self) -> str:
        translation_engine = getattr(self.transcription_manager, "translation_engine", None)
        if translation_engine is None:
            return ""
        get_name = getattr(translation_engine, "get_name", None)
        if callable(get_name):
            try:
                return str(get_name()).strip().lower()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to get translation engine name: %s", exc)
        return translation_engine.__class__.__name__.strip().lower()

    def _translation_uses_local_models(self) -> bool:
        preference_engine = str(
            self._get_translation_preferences().get("translation_engine") or ""
        ).strip().lower()
        if preference_engine == TRANSLATION_ENGINE_OPUS_MT:
            return True

        engine_name = self._translation_engine_name()
        return "opus" in engine_name

    def _resolve_translation_readiness(self) -> tuple[bool, str]:
        if not self._translation_engine_available():
            return False, self.i18n.t("batch_transcribe.translation_not_available")

        if not self._translation_uses_local_models():
            return True, ""

        if not self.model_manager or not hasattr(self.model_manager, "get_best_translation_model"):
            return False, self.i18n.t("batch_transcribe.translation_not_available")

        source_lang = self._selected_translation_source_lang()
        target_lang = self._selected_translation_target_lang()
        auto_detect = source_lang == TRANSLATION_LANGUAGE_AUTO

        try:
            model_info = self.model_manager.get_best_translation_model(
                source_lang,
                target_lang,
                auto_detect=auto_detect,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to resolve translation model readiness: %s", exc)
            return False, self.i18n.t("batch_transcribe.translation_not_available")

        if model_info and getattr(model_info, "is_downloaded", False):
            return True, ""

        model_name = getattr(model_info, "model_id", f"opus-mt-{source_lang}-{target_lang}")
        return False, self.i18n.t("settings.translation.opus_mt_not_downloaded", model=model_name)

    def _ensure_translation_ready(self) -> bool:
        ready, message = self._resolve_translation_readiness()
        if ready:
            return True

        self.show_warning(
            self.i18n.t("common.warning"),
            message or self.i18n.t("batch_transcribe.translation_not_available"),
        )
        self._refresh_download_guide()
        return False

    def _preferred_transcription_model(self) -> str:
        settings_manager = self._get_settings_manager()
        if settings_manager and hasattr(settings_manager, "get_setting"):
            try:
                configured_model = settings_manager.get_setting("transcription.faster_whisper.model_size")
                if isinstance(configured_model, str) and configured_model.strip():
                    return configured_model.strip()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to read preferred transcription model: %s", exc)
        return ""

    def _build_import_file_filter(self, task_kind: Optional[str] = None) -> str:
        audio_patterns = " ".join(f"*{suffix}" for suffix in sorted(AUDIO_VIDEO_SUFFIXES))
        text_patterns = " ".join(f"*{suffix}" for suffix in sorted(TEXT_TRANSLATION_SUFFIXES))
        if (task_kind or self._current_task_kind()) == TRANSLATION_TASK_KIND:
            return (
                f"Translation Source Files ({audio_patterns} {text_patterns});;All Files (*)"
            )
        return f"Audio/Video Files ({audio_patterns});;All Files (*)"

    def _populate_engines(self, combo: QComboBox):
        """
        Populate engine combo box with available engines.

        Args:
            combo: Combo box to populate
        """
        try:
            # Get current engine name
            if (
                self.transcription_manager
                and hasattr(self.transcription_manager, "speech_engine")
                and self.transcription_manager.speech_engine
            ):
                current_engine = self.transcription_manager.speech_engine.get_name()
                # Add current engine
                combo.addItem(current_engine)
                logger.debug(f"Populated engines: {current_engine}")
            else:
                # No engine available
                combo.addItem(self.i18n.t("ui_strings.batch_transcribe.no_engine_configured"))
                combo.setEnabled(False)
                logger.warning(self.i18n.t("logging.batch_transcribe.no_speech_engine"))
        except Exception as e:
            logger.error(f"Error populating engines: {e}")
            combo.addItem(self.i18n.t("ui_strings.batch_transcribe.error_loading_engines"))
            combo.setEnabled(False)

    def _update_model_list(self):
        """Update model combo box with downloaded models."""
        if not self.model_manager or not hasattr(self, "model_combo"):
            return

        try:
            # Save current selection
            current_model = self.model_combo.currentData()

            # Clear combo box
            self.model_combo.clear()

            # Get downloaded models
            downloaded_models = list(self.model_manager.get_downloaded_models() or [])

            if not downloaded_models:
                # No models available
                self.model_combo.addItem(self.i18n.t("batch_transcribe.no_models_available"), None)
                self.model_combo.setEnabled(False)

                logger.warning(self.i18n.t("logging.batch_transcribe.no_models_downloaded"))
            else:
                # Enable combo box
                self.model_combo.setEnabled(True)

                # Add models to combo box
                for model in downloaded_models:
                    self.model_combo.addItem(model.name, model.name)

                # Restore previous selection if still available
                preferred_model = (
                    current_model
                    or self._preferred_transcription_model()
                    or self.model_manager.recommend_model()
                )
                index = self.model_combo.findData(preferred_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
                elif self.model_combo.count() > 0:
                    self.model_combo.setCurrentIndex(0)

                logger.info(f"Updated model list: {len(downloaded_models)} models")
            self._update_mode_controls()

        except Exception as e:
            logger.error(f"Error updating model list: {e}")
            self.model_combo.addItem(
                self.i18n.t("ui_strings.batch_transcribe.error_loading_models"),
                None,
            )
            self.model_combo.setEnabled(False)
            self._update_mode_controls()

    def _show_download_guide(self, task_kind: str, message: str):
        """Show contextual download guide inside the target tab."""
        context = self._tab_contexts.get(task_kind)
        if not context:
            return

        if not message:
            context.download_guide_frame.hide()
            return

        context.download_guide_message_label.setText(message)
        context.download_guide_frame.show()

    def _hide_download_guide(self, task_kind: Optional[str] = None):
        if task_kind:
            context = self._tab_contexts.get(task_kind)
            if context:
                context.download_guide_frame.hide()
            return
        for context in self._tab_contexts.values():
            context.download_guide_frame.hide()

    def _refresh_download_guide(self) -> None:
        if self.model_manager and hasattr(self, "model_combo") and not self._transcription_mode_ready():
            self._show_download_guide(
                TRANSCRIPTION_TASK_KIND,
                self.i18n.t("batch_transcribe.no_models_message"),
            )
        else:
            self._hide_download_guide(TRANSCRIPTION_TASK_KIND)

        translation_ready, message = self._resolve_translation_readiness()
        if translation_ready:
            self._hide_download_guide(TRANSLATION_TASK_KIND)
        else:
            self._show_download_guide(TRANSLATION_TASK_KIND, message)

    def _on_go_to_download(self, task_kind: Optional[str] = None):
        """Handle 'Go to Download' button click."""
        try:
            active_kind = task_kind or self._current_task_kind()
            main_window = self.window()
            if hasattr(main_window, "switch_page"):
                main_window.switch_page("settings")
                settings_widget = main_window.pages.get("settings")
                if settings_widget and hasattr(settings_widget, "show_page"):
                    def _show_model_management():
                        settings_widget.show_page("model_management")
                        if active_kind != TRANSLATION_TASK_KIND:
                            return
                        model_page = getattr(settings_widget, "settings_pages", {}).get(
                            "model_management"
                        )
                        if model_page and hasattr(model_page, "tabs"):
                            model_page.tabs.setCurrentIndex(1)

                    QTimer.singleShot(100, _show_model_management)

                logger.info(self.i18n.t("logging.batch_transcribe.navigating_to_model_management"))
            else:
                logger.warning(
                    self.i18n.t("logging.batch_transcribe.cannot_navigate_main_window_not_found")
                )

        except Exception as e:
            logger.error(f"Error navigating to download page: {e}")

    def update_translations(self):
        """Update all UI text with current language translations."""
        try:
            self.title_label.setText(self.i18n.t("batch_transcribe.title"))
            if hasattr(self, "task_tabs"):
                self.task_tabs.setTabText(0, self.i18n.t("batch_transcribe.mode_transcription"))
                self.task_tabs.setTabText(1, self.i18n.t("batch_transcribe.mode_translation"))

            transcription_context = self._tab_contexts.get(TRANSCRIPTION_TASK_KIND)
            if transcription_context:
                transcription_context.import_file_btn.setText(self.i18n.t("batch_transcribe.import_file"))
                transcription_context.import_folder_btn.setText(
                    self.i18n.t("batch_transcribe.import_folder")
                )
                transcription_context.clear_queue_btn.setText(self.i18n.t("batch_transcribe.clear_queue"))
                transcription_context.download_guide_button.setText(
                    self.i18n.t("batch_transcribe.go_to_download")
                )

            translation_context = self._tab_contexts.get(TRANSLATION_TASK_KIND)
            if translation_context:
                translation_context.import_file_btn.setText(self.i18n.t("batch_transcribe.import_file"))
                translation_context.import_folder_btn.setText(
                    self.i18n.t("batch_transcribe.import_folder")
                )
                if translation_context.paste_text_btn is not None:
                    translation_context.paste_text_btn.setText(self.i18n.t("batch_transcribe.paste_text"))
                translation_context.clear_queue_btn.setText(self.i18n.t("batch_transcribe.clear_queue"))
                translation_context.download_guide_button.setText(
                    self.i18n.t("batch_transcribe.go_to_download")
                )

            if hasattr(self, "model_label"):
                self.model_label.setText(self.i18n.t("batch_transcribe.model") + ":")
            elif hasattr(self, "engine_label"):
                self.engine_label.setText(self.i18n.t("batch_transcribe.engine") + ":")
            if hasattr(self, "translation_target_label"):
                self.translation_target_label.setText(
                    self.i18n.t("settings.translation.target_language")
                )

            self._populate_translation_target_languages()
            self._update_mode_controls()
            self._update_queue_label()
            self._refresh_download_guide()

            logger.debug("Translations updated")

        except Exception as e:
            logger.error(f"Error updating translations: {e}")

    def _update_queue_label(self):
        """Update both queue labels with current task counts."""
        for context in self._tab_contexts.values():
            task_count = context.task_list.count()
            context.queue_label.setText(
                self.i18n.t("batch_transcribe.task_queue")
                + " "
                + self.i18n.t("batch_transcribe.tasks_count", count=task_count)
            )

    def _on_import_file(self, task_kind: Optional[str] = None):
        """Handle import file button click."""
        try:
            active_kind = task_kind or self._current_task_kind()
            if active_kind == TRANSLATION_TASK_KIND and not self._ensure_translation_ready():
                return

            # Open file dialog
            file_filter = self._build_import_file_filter(active_kind)
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, self.i18n.t("batch_transcribe.import_file"), "", file_filter
            )

            if not file_paths:
                return

            # Add tasks for each file
            for file_path in file_paths:
                self._add_task(file_path, active_kind)

            logger.info(f"Imported {len(file_paths)} files")

        except Exception as e:
            logger.error(f"Error importing files: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_import_folder(self, task_kind: Optional[str] = None):
        """Handle import folder button click."""
        try:
            active_kind = task_kind or self._current_task_kind()
            if active_kind == TRANSLATION_TASK_KIND and not self._ensure_translation_ready():
                return

            # Open folder dialog
            folder_path = QFileDialog.getExistingDirectory(
                self, self.i18n.t("batch_transcribe.import_folder"), ""
            )

            if not folder_path:
                return

            # Add tasks from folder with the same options used by single-file import
            if active_kind == TRANSLATION_TASK_KIND:
                options = self._build_translation_task_options()
                task_ids = self.transcription_manager.add_translation_tasks_from_folder(
                    folder_path, options
                )
            else:
                options = self._build_task_options()
                task_ids = self.transcription_manager.add_tasks_from_folder(folder_path, options)
            logger.info(f"Added {len(task_ids)} tasks from folder")

            logger.info(f"Importing from folder: {folder_path}")

        except Exception as e:
            logger.error(f"Error importing folder: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_paste_text(self, task_kind: Optional[str] = None):
        """Handle creating translation task from pasted text."""
        active_kind = task_kind or self._current_task_kind()
        if active_kind != TRANSLATION_TASK_KIND:
            return

        if not self._ensure_translation_ready():
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.i18n.t("batch_transcribe.paste_dialog_title"))
        dialog.setMinimumSize(640, 420)

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        file_name_edit = QLineEdit("pasted_text.txt")
        form_layout.addRow(
            self.i18n.t("batch_transcribe.paste_filename_label"),
            file_name_edit,
        )

        output_format_combo = QComboBox()
        output_format_combo.addItem("TXT", "txt")
        output_format_combo.addItem("MD", "md")
        form_layout.addRow(
            self.i18n.t("batch_transcribe.paste_output_format_label"),
            output_format_combo,
        )
        layout.addLayout(form_layout)

        text_editor = QPlainTextEdit()
        text_editor.setPlaceholderText(self.i18n.t("batch_transcribe.paste_text_placeholder"))
        layout.addWidget(text_editor)

        action_layout = create_hbox()
        action_layout.addStretch()
        cancel_btn = create_button(self.i18n.t("common.cancel"))
        confirm_btn = create_primary_button(self.i18n.t("common.ok"))
        connect_button_with_callback(cancel_btn, dialog.reject)
        connect_button_with_callback(confirm_btn, dialog.accept)
        action_layout.addWidget(cancel_btn)
        action_layout.addWidget(confirm_btn)
        layout.addLayout(action_layout)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        text = text_editor.toPlainText()
        if not text.strip():
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("batch_transcribe.paste_text_empty"),
            )
            return

        options = self._build_translation_task_options()
        options["output_format"] = output_format_combo.currentData()
        self.transcription_manager.add_translation_text_task(
            text=text,
            file_name=file_name_edit.text().strip() or "pasted_text.txt",
            options=options,
        )
        self._notify_user(self.i18n.t("batch_transcribe.translation_queued"))

    def _on_clear_queue(self, task_kind: Optional[str] = None):
        """Handle clear queue button click."""
        try:
            if self._clear_queue_in_progress:
                logger.info("Clear queue already in progress, ignoring duplicate request")
                return

            active_kind = task_kind or self._current_task_kind()

            # Confirm with user
            reply = QMessageBox.question(
                self,
                self.i18n.t("batch_transcribe.clear_queue"),
                self.i18n.t("batch_transcribe.confirm_clear_queue"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._clear_queue_in_progress = True
                self._set_clear_buttons_enabled(False)

                # Stop all running/pending tasks first to avoid race conditions
                self.transcription_manager.stop_all_tasks()

                self._clear_queue_with_retry(active_kind, attempt=1)

        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            self._clear_queue_in_progress = False
            self._update_mode_controls()
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _clear_queue_with_retry(self, task_kind: str, attempt: int):
        """Delete queue tasks of a specific kind with short retries."""
        deleted_task_ids = set()
        remaining_processing_ids = []

        for task_data in self.transcription_manager.get_all_tasks():
            if self._resolve_task_kind_from_data(task_data) != task_kind:
                continue
            task_id = task_data["id"]
            if self.transcription_manager.delete_task(task_id):
                deleted_task_ids.add(task_id)
            elif task_data.get("status") == "processing":
                remaining_processing_ids.append(task_id)

        for task_id in list(deleted_task_ids):
            self._remove_task_item(task_id)

        if remaining_processing_ids and attempt < self._CLEAR_QUEUE_MAX_RETRIES:
            logger.info(
                "Clear queue retry %d/%d for %d processing task(s)",
                attempt,
                self._CLEAR_QUEUE_MAX_RETRIES,
                len(remaining_processing_ids),
            )
            QTimer.singleShot(
                self._CLEAR_QUEUE_RETRY_INTERVAL_MS,
                lambda: self._clear_queue_with_retry(task_kind, attempt + 1),
            )
            return

        if remaining_processing_ids:
            logger.warning(
                "Clear queue partial completion, %d task(s) still processing after retries: %s",
                len(remaining_processing_ids),
                ", ".join(remaining_processing_ids),
            )
            self._notify_user(
                self.i18n.t(
                    "batch_transcribe.feedback.clear_queue_partial",
                    count=len(remaining_processing_ids),
                )
            )

        self.transcription_manager.start_processing()
        self._clear_queue_in_progress = False
        self._update_mode_controls()
        self._update_queue_label()
        logger.info(self.i18n.t("logging.batch_transcribe.task_queue_cleared"))

    def _add_task(self, file_path: str, task_kind: Optional[str] = None):
        """
        Add a task according to current mode.

        Args:
            file_path: Source file path
        """
        try:
            source_path = Path(file_path)
            suffix = source_path.suffix.lower()
            active_kind = task_kind or self._current_task_kind()

            if active_kind == TRANSLATION_TASK_KIND:
                if not self._ensure_translation_ready():
                    return
                supported_suffixes = AUDIO_VIDEO_SUFFIXES | TEXT_TRANSLATION_SUFFIXES
                if suffix not in supported_suffixes:
                    raise ValueError(
                        self.i18n.t("batch_transcribe.unsupported_translation_file_type")
                    )
                options = self._build_translation_task_options()
                task_id = self.transcription_manager.add_translation_task(file_path, options)
            else:
                task_id = self.transcription_manager.add_task(file_path, self._build_task_options())

            logger.info("Task added: %s (%s)", task_id, active_kind)

        except Exception as e:
            logger.error(f"Error adding task: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _build_task_options(self) -> Dict[str, str]:
        """Build task options from current UI selection."""
        options: Dict[str, str] = {}

        if self.model_manager and hasattr(self, "model_combo"):
            selected_model = self.model_combo.currentData()
            if not selected_model:
                raise ValueError(self.i18n.t("batch_transcribe.no_models_available"))

            model_info = self.model_manager.get_model(str(selected_model))
            if not model_info or not model_info.is_downloaded:
                raise ValueError(
                    self.i18n.t("batch_transcribe.model_not_available", model=selected_model)
                )

            options["model_name"] = str(selected_model)
            options["model_path"] = model_info.local_path
            logger.debug(f"Using model {selected_model} at {model_info.local_path}")

        return options

    def _build_translation_task_options(self) -> Dict[str, str]:
        """Build translation task options with language preferences."""
        selected_target = self.translation_target_combo.currentData() if hasattr(
            self, "translation_target_combo"
        ) else None
        return self._resolve_translation_languages(target_lang=selected_target)

    def _refresh_tasks(self):
        """Refresh task list from transcription manager."""
        try:
            all_tasks = self.transcription_manager.get_all_tasks()
            current_task_ids = set(self.task_items.keys())
            new_task_ids = {task["id"] for task in all_tasks}

            for task_id in current_task_ids - new_task_ids:
                self._remove_task_item(task_id)

            for task_data in all_tasks:
                self._upsert_task_item(task_data)

            self._update_queue_label()
            self._set_tasks_pause_state(self.transcription_manager.is_paused())

        except Exception as e:
            logger.error(f"Error refreshing tasks: {e}")

    @staticmethod
    def _resolve_task_kind_from_data(task_data: Dict) -> str:
        task_kind = task_data.get("task_kind")
        if task_kind in {TRANSCRIPTION_TASK_KIND, TRANSLATION_TASK_KIND}:
            return str(task_kind)
        if task_data.get("engine") == "translation":
            return TRANSLATION_TASK_KIND
        return TRANSCRIPTION_TASK_KIND

    def _task_list_for_kind(self, task_kind: str) -> QListWidget:
        context = self._tab_contexts.get(task_kind) or self._tab_contexts.get(TRANSCRIPTION_TASK_KIND)
        if context is None:
            raise RuntimeError(f"Task list context missing for kind: {task_kind}")
        return context.task_list

    def _upsert_task_item(self, task_data: Dict) -> None:
        task_id = task_data["id"]
        desired_kind = self._resolve_task_kind_from_data(task_data)
        existing_item = self.task_items.get(task_id)
        if existing_item is None:
            self._add_task_item(task_data)
            return

        current_kind = self.task_item_kinds.get(task_id, desired_kind)
        if current_kind != desired_kind:
            merged_data = dict(existing_item.task_data)
            merged_data.update(task_data)
            self._remove_task_item(task_id)
            self._add_task_item(merged_data)
            return

        if task_data.get("status") == "processing":
            logger.debug(
                "Updating task %s: progress=%.1f%%",
                task_id,
                float(task_data.get("progress", 0)),
            )
        existing_item.update_task_data(task_data)

    def _add_task_item(self, task_data: Dict):
        """
        Add a task item widget to the list.

        Args:
            task_data: Task information dictionary
        """
        try:
            task_id = task_data["id"]
            task_kind = self._resolve_task_kind_from_data(task_data)
            target_list = self._task_list_for_kind(task_kind)

            task_item = TaskItem(task_data, self.i18n)
            task_item.start_clicked.connect(self._on_task_start)
            task_item.pause_clicked.connect(self._on_task_pause)
            task_item.cancel_clicked.connect(self._on_task_cancel)
            task_item.delete_clicked.connect(self._on_task_delete)
            task_item.view_clicked.connect(self._on_task_view)
            task_item.export_clicked.connect(self._on_task_export)
            task_item.retry_clicked.connect(self._on_task_retry)

            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(800, 160))
            target_list.addItem(list_item)
            target_list.setItemWidget(list_item, task_item)

            self.task_items[task_id] = task_item
            self.task_item_kinds[task_id] = task_kind

            task_item.set_processing_paused(self.transcription_manager.is_paused())

            logger.debug("Added task item for task %s (%s)", task_id, task_kind)

        except Exception as e:
            logger.error(f"Error adding task item: {e}")

    def _remove_task_item(self, task_id: str):
        """
        Remove a task item widget from the list.

        Args:
            task_id: Task identifier
        """
        try:
            if task_id not in self.task_items:
                return

            task_lists = []
            current_kind = self.task_item_kinds.get(task_id)
            if current_kind in self._tab_contexts:
                task_lists.append(self._tab_contexts[current_kind].task_list)
            for context in self._tab_contexts.values():
                if context.task_list not in task_lists:
                    task_lists.append(context.task_list)

            for task_list in task_lists:
                for i in range(task_list.count()):
                    item = task_list.item(i)
                    widget = task_list.itemWidget(item)
                    if isinstance(widget, TaskItem) and widget.task_id == task_id:
                        task_list.takeItem(i)
                        break

            del self.task_items[task_id]
            self.task_item_kinds.pop(task_id, None)

            logger.debug(f"Removed task item for task {task_id}")

        except Exception as e:
            logger.error(f"Error removing task item: {e}")

    def _on_task_start(self, task_id: str):
        """Handle task start button click."""
        try:
            # Task will start automatically when added to queue
            logger.info(f"Start requested for task {task_id}")
        except Exception as e:
            logger.error(f"Error starting task: {e}")

    def _on_task_pause(self, task_id: str):
        """Handle task pause button click."""
        try:
            logger.debug(f"Pause toggle requested by task {task_id}")

            if self.transcription_manager.is_paused():
                self.transcription_manager.resume_processing()
                self._set_tasks_pause_state(False)
                message = self.i18n.t("batch_transcribe.feedback.resumed")
            else:
                self.transcription_manager.pause_processing()
                self._set_tasks_pause_state(True)
                message = self.i18n.t("batch_transcribe.feedback.paused")

            self._notify_user(message)
        except Exception as e:
            logger.error(f"Error toggling pause state: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_task_cancel(self, task_id: str):
        """Handle task cancel button click."""
        try:
            cancelled = self.transcription_manager.cancel_task(task_id)
            if cancelled:
                logger.info(f"Cancelled task {task_id}")
            else:
                logger.warning(f"Failed to cancel task {task_id}")
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")

    def _on_task_delete(self, task_id: str):
        """Handle task delete button click."""
        try:
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                self.i18n.t("common.delete"),
                self.i18n.t("batch_transcribe.confirm_delete_task"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                deleted = self.transcription_manager.delete_task(task_id)
                if deleted:
                    self._remove_task_item(task_id)
                    logger.info(f"Deleted task {task_id}")
                else:
                    logger.warning(f"Failed to delete task {task_id}")
                    self._show_error(
                        self.i18n.t("common.warning"),
                        self.i18n.t("batch_transcribe.delete_processing_not_allowed"),
                    )

        except Exception as e:
            logger.error(f"Error deleting task: {e}")

    def _on_task_view(self, task_id: str):
        """Handle task view button click."""
        try:
            # Check if viewer for this task is already open
            if task_id in self.open_viewers:
                # Activate existing window
                existing_viewer = self.open_viewers[task_id]
                existing_viewer.raise_()
                existing_viewer.activateWindow()
                logger.info(f"Activated existing viewer for task {task_id}")
                return

            # Import here to avoid circular imports
            from ui.batch_transcribe.transcript_viewer import TranscriptViewerDialog

            # Get settings manager and db connection from managers
            settings_manager = None
            db_connection = None
            if hasattr(self, "parent") and self.parent():
                main_window = self.window()
                if hasattr(main_window, "managers"):
                    settings_manager = main_window.managers.get("settings_manager")

            # Get db connection from transcription manager
            db_connection = self.transcription_manager.db

            # Create and show transcript viewer dialog
            viewer = TranscriptViewerDialog(
                task_id,
                self.transcription_manager,
                db_connection,
                self.i18n,
                settings_manager=settings_manager,
                parent=self,
            )

            # Store reference to open viewer
            self.open_viewers[task_id] = viewer

            # Connect to viewer's finished signal to remove from dictionary
            viewer.finished.connect(lambda: self._on_viewer_closed(task_id))

            # Show viewer as non-modal window
            viewer.show()

            logger.info(f"Opened transcript viewer for task {task_id}")
        except Exception as e:
            logger.error(f"Error viewing task: {e}")
            self._show_error(self.i18n.t("common.error"), str(e))

    def _on_viewer_closed(self, task_id: str):
        """
        Handle viewer window closed event.

        Args:
            task_id: Task ID of the closed viewer
        """
        try:
            if task_id in self.open_viewers:
                del self.open_viewers[task_id]
                logger.info(f"Closed viewer for task {task_id}")
        except Exception as e:
            logger.error(f"Error removing viewer reference: {e}")

    def _initial_load(self):
        """Perform heavy initial loading tasks after UI is established."""
        try:
            logger.debug("Performing delayed initial load for batch transcribe...")

            # 1. Register listener (deferred to ensure main loop is ready)
            if self.transcription_manager:
                self.transcription_manager.add_listener(self._on_manager_event_threadsafe)

            # 2. Populate models
            if self.model_manager:
                self._update_model_list()
            self._populate_translation_target_languages()

            # 3. Refresh task list (queries database and creates sub-widgets)
            self._refresh_tasks()
            self._update_mode_controls()

            logger.debug("Initial load complete")
        except Exception as e:
            logger.error(f"Error during initial load: {e}")

    def _on_manager_event_threadsafe(self, event_type: str, data: Dict):
        """
        Handle events from transcription manager (thread-safe bridge).

        Emits signal to handle event on main UI thread.
        """
        try:
            self.manager_event.emit(event_type, data)
        except Exception as e:
            logger.error(f"Error emitting manager event: {e}")

    def _handle_manager_event(self, event_type: str, data: Dict):
        """
        Handle manager event on main thread.

        Args:
            event_type: Type of event
            data: Event data
        """
        try:
            if event_type == "task_added":
                self._upsert_task_item(data)
                self._update_queue_label()

            elif event_type == "task_updated":
                self._upsert_task_item(data)

            elif event_type == "task_deleted":
                task_id = data["id"]
                self._remove_task_item(task_id)
                self._update_queue_label()

            elif event_type == "processing_paused":
                self._set_tasks_pause_state(True)

            elif event_type == "processing_resumed":
                self._set_tasks_pause_state(False)

        except Exception as e:
            logger.error(f"Error handling manager event {event_type}: {e}")

    def _on_task_export(self, task_id: str):
        """Handle task export button click."""
        try:
            # Get task data
            task_data = self.transcription_manager.get_task_status(task_id)
            if not task_data:
                return

            # Open save dialog
            default_name = task_data["file_name"].rsplit(".", 1)[0]
            file_filter = self.i18n.t("batch_transcribe.export_file_filter")
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                self.i18n.t("batch_transcribe.actions.export"),
                default_name,
                file_filter,
            )

            if not file_path:
                return

            # Determine format from extension first, then selected filter pattern.
            file_extension = Path(file_path).suffix.lower()
            if file_extension in {".txt", ".srt", ".md"}:
                output_format = file_extension.lstrip(".")
            elif "*.srt" in selected_filter:
                output_format = "srt"
                file_path = f"{file_path}.srt"
            elif "*.md" in selected_filter:
                output_format = "md"
                file_path = f"{file_path}.md"
            else:
                output_format = "txt"
                file_path = f"{file_path}.txt"

            # Export
            self.transcription_manager.export_result(task_id, output_format, file_path)

            self.show_info(
                self.i18n.t("common.success"),
                self.i18n.t("batch_transcribe.export_success", path=file_path),
            )

            logger.info(f"Exported task {task_id} to {file_path}")

        except Exception as e:
            logger.error(f"Error exporting task: {e}")
            self._show_error(self.i18n.t("errors.unknown_error"), str(e))

    def _on_task_retry(self, task_id: str):
        """Handle task retry button click."""
        try:
            retried = self.transcription_manager.retry_task(task_id)
            if retried:
                logger.info(f"Retrying task {task_id}")
            else:
                logger.warning(f"Failed to retry task {task_id}")
        except Exception as e:
            logger.error(f"Error retrying task: {e}")

    def _show_error(self, title: str, message: str):
        """
        Show error message dialog.

        Args:
            title: Error title
            message: Error message
        """
        self.show_error(title, message)

    def _set_tasks_pause_state(self, paused: bool):
        """Update pause button state for all task items."""
        for task_item in self.task_items.values():
            task_item.set_processing_paused(paused)

    def _notify_user(self, message: str):
        """Display feedback to the user and log it."""
        status_bar = None
        main_window = self.window()

        if hasattr(main_window, "statusBar"):
            try:
                status_bar = main_window.statusBar()
            except Exception:
                status_bar = None

        if status_bar:
            status_bar.showMessage(message, 5000)

        logger.info(message)

    def close_all_viewers(self):
        """Close all open transcript viewer windows."""
        try:
            # Close all open viewers
            for task_id, viewer in list(self.open_viewers.items()):
                try:
                    viewer.close()
                except Exception as e:
                    logger.error(f"Error closing viewer for task {task_id}: {e}")

            # Clear the dictionary
            self.open_viewers.clear()

            logger.info(self.i18n.t("logging.batch_transcribe.closed_all_transcript_viewers"))
        except Exception as e:
            logger.error(f"Error closing all viewers: {e}")
