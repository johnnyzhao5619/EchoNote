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
Settings widget for EchoNote application.

Provides a comprehensive settings interface with categorized pages
for configuring all application features.
"""

import logging
from typing import Any, Dict

from core.qt_imports import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from ui.base_widgets import BaseWidget, create_hbox, create_primary_button, create_secondary_button
from ui.constants import (
    PAGE_COMPACT_SPACING,
    PAGE_LAYOUT_SPACING,
    ROLE_SETTINGS_CANCEL_ACTION,
    ROLE_SETTINGS_NAV,
    ROLE_SETTINGS_RESET_ACTION,
    ROLE_SETTINGS_SAVE_ACTION,
    SETTINGS_NAV_WIDTH,
)
from ui.settings.base_page import PostSaveMessage
from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.settings")


class SettingsWidget(BaseWidget):
    """
    Main settings widget with categorized navigation and pages.

    Provides a two-panel layout with category list on the left
    and settings pages on the right.
    """

    # Signal emitted when settings are saved
    settings_saved = Signal()

    def __init__(
        self, settings_manager, i18n: I18nQtManager, managers: Dict[str, Any], parent=None
    ):
        """
        Initialize settings widget.

        Args:
            settings_manager: SettingsManager instance
            i18n: Internationalization manager
            managers: Dictionary of other managers (for API key testing, etc.)
            parent: Parent widget
        """
        super().__init__(i18n, parent)

        self.settings_manager = settings_manager
        self.managers = managers

        # Track unsaved changes
        self.has_unsaved_changes = False

        # Store original settings for change detection
        self.original_settings: Dict[str, Any] = {}

        # Settings pages dictionary
        self.settings_pages: Dict[str, QWidget] = {}

        # Setup UI
        self.setup_ui()

        # Load current settings
        self.load_settings()

        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)

        logger.info(self.i18n.t("logging.settings.widget_initialized"))

    def setup_ui(self):
        """Set up the settings UI layout."""
        # Main layout
        main_layout = self.create_page_layout()

        # Title
        self.title_label = self.create_page_title("settings.title", main_layout)

        # Content layout (category list + pages)
        content_layout = create_hbox(spacing=PAGE_LAYOUT_SPACING)

        # Category list
        self.category_list = self._create_category_list()
        content_layout.addWidget(self.category_list)

        # Settings pages container
        self.pages_container = QStackedWidget()
        self._create_settings_pages()
        content_layout.addWidget(self.pages_container, stretch=1)

        main_layout.addLayout(content_layout, stretch=1)

        # Now that pages_container is created, select first category
        # This will trigger _on_category_changed which needs pages_container
        self.category_list.setCurrentRow(0)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Button layout
        button_layout = create_hbox(spacing=PAGE_COMPACT_SPACING)
        button_layout.addStretch()

        # Reset button
        self.reset_button = create_secondary_button(self.i18n.t("settings.reset"))
        self.reset_button.setProperty("role", ROLE_SETTINGS_RESET_ACTION)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        button_layout.addWidget(self.reset_button)

        # Cancel button
        self.cancel_button = create_secondary_button(self.i18n.t("settings.cancel"))
        self.cancel_button.setProperty("role", ROLE_SETTINGS_CANCEL_ACTION)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        # Save button
        self.save_button = create_primary_button(self.i18n.t("settings.save"))
        self.save_button.setProperty("role", ROLE_SETTINGS_SAVE_ACTION)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

        logger.debug("Settings UI setup complete")

    def _create_category_list(self) -> QListWidget:
        """
        Create category navigation list.

        Returns:
            Category list widget
        """
        category_list = QListWidget()
        category_list.setFixedWidth(SETTINGS_NAV_WIDTH)
        category_list.setProperty("role", ROLE_SETTINGS_NAV)

        # Define categories based on available pages/managers
        categories = [
            (category_id, f"settings.category.{category_id}")
            for category_id in self._get_available_category_ids()
        ]

        # Add category items
        for category_id, text_key in categories:
            item = QListWidgetItem(self.i18n.t(text_key))
            item.setData(Qt.ItemDataRole.UserRole, category_id)
            category_list.addItem(item)

        # Connect selection change
        category_list.currentRowChanged.connect(self._on_category_changed)

        # Don't select first category here - will be done after pages are created
        # to avoid triggering signal before pages_container exists

        return category_list

    def _create_settings_pages(self):
        """Create all settings pages and add to container."""
        # Import page classes
        from ui.settings.appearance_page import AppearanceSettingsPage
        from ui.settings.calendar_page import CalendarSettingsPage
        from ui.settings.language_page import LanguageSettingsPage
        from ui.settings.model_management_page import ModelManagementPage
        from ui.settings.realtime_page import RealtimeSettingsPage
        from ui.settings.timeline_page import TimelineSettingsPage
        from ui.settings.transcription_page import TranscriptionSettingsPage

        # Page definitions: (id, class, args)
        page_defs = [
            (
                "transcription",
                TranscriptionSettingsPage,
                (self.settings_manager, self.i18n, self.managers),
            ),
            (
                "realtime",
                RealtimeSettingsPage,
                (self.settings_manager, self.i18n, self.managers),
            ),
            (
                "model_management",
                ModelManagementPage,
                (self.settings_manager, self.i18n, self.managers.get("model_manager")),
            ),
            (
                "calendar",
                CalendarSettingsPage,
                (self.settings_manager, self.i18n, self.managers),
            ),
            ("timeline", TimelineSettingsPage, (self.settings_manager, self.i18n)),
            (
                "appearance",
                AppearanceSettingsPage,
                (self.settings_manager, self.i18n, self.managers),
            ),
            ("language", LanguageSettingsPage, (self.settings_manager, self.i18n)),
        ]

        for page_id, page_class, args in page_defs:
            # Skip model management if manager not available
            if page_id == "model_management" and "model_manager" not in self.managers:
                continue

            try:
                page_widget = page_class(*args)
                self.pages_container.addWidget(page_widget)
                self.settings_pages[page_id] = page_widget

                # Connect change signal
                if hasattr(page_widget, "settings_changed"):
                    page_widget.settings_changed.connect(self._on_settings_changed)

            except Exception as e:
                logger.error(f"Error creating settings page '{page_id}': {e}", exc_info=True)
                # Create placeholder for failed page
                placeholder = QWidget()
                layout = QVBoxLayout(placeholder)
                error_label = QLabel(
                    self.i18n.t("settings.error.page_load_failed", category=page_id)
                    + f"\n({str(e)})"
                )
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(error_label)
                self.pages_container.addWidget(placeholder)
                self.settings_pages[page_id] = placeholder

        logger.debug(f"Created settings pages: {list(self.settings_pages.keys())}")

    def _get_available_category_ids(self) -> list[str]:
        """Return category IDs that should be visible for this session."""
        categories = [
            "transcription",
            "realtime",
            "calendar",
            "timeline",
            "appearance",
            "language",
        ]
        if "model_manager" in self.managers:
            categories.insert(2, "model_management")
        return categories

    def _on_category_changed(self, index: int):
        """
        Handle category selection change.

        Args:
            index: Selected category index
        """
        # Switch to corresponding page if index is valid
        if 0 <= index < self.pages_container.count():
            self.pages_container.setCurrentIndex(index)
            logger.debug(f"Switched to settings category: {index}")
        else:
            logger.warning("Invalid settings category index: %s", index)

    def show_page(self, page_id: str) -> bool:
        """Navigate to a settings category by page identifier."""
        if page_id not in self.settings_pages:
            logger.warning("Settings page '%s' not found", page_id)
            return False

        for row in range(self.category_list.count()):
            item = self.category_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == page_id:
                self.category_list.setCurrentRow(row)
                return True

        logger.warning("Settings category for page '%s' not found in navigation list", page_id)
        return False

    def _get_config_manager(self):
        """Return ConfigManager attached to settings manager."""
        config_manager = getattr(self.settings_manager, "config_manager", None)
        if config_manager is None:
            raise RuntimeError("SettingsManager.config_manager is unavailable")
        return config_manager

    def _get_settings_snapshot(self) -> Dict[str, Any]:
        """Capture current settings snapshot from config manager."""
        config_manager = self._get_config_manager()
        get_all = getattr(config_manager, "get_all", None)
        if not callable(get_all):
            raise RuntimeError("ConfigManager.get_all is unavailable")

        snapshot = get_all()
        if not isinstance(snapshot, dict):
            raise TypeError("ConfigManager.get_all must return a dictionary snapshot")
        return snapshot

    def _persist_settings(self) -> None:
        """Persist current in-memory settings to disk."""
        config_manager = self._get_config_manager()
        save = getattr(config_manager, "save", None)
        if not callable(save):
            raise RuntimeError("ConfigManager.save is unavailable")
        save()

    def _restore_settings_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """Restore full settings snapshot in memory."""
        if not isinstance(snapshot, dict):
            return False

        try:
            config_manager = self._get_config_manager()
            replace_all = getattr(config_manager, "replace_all", None)
            if not callable(replace_all):
                return False

            replace_all(snapshot)

            setting_changed = getattr(self.settings_manager, "setting_changed", None)
            emit = getattr(setting_changed, "emit", None)
            if callable(emit):
                emit("*", None)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Error restoring settings snapshot: %s", exc, exc_info=True)
            return False

    def load_settings(self):
        """Load current settings into all pages."""
        try:
            # Store original settings for change detection
            self.original_settings = self._get_settings_snapshot()

            # Load settings into each page
            for page_widget in self.settings_pages.values():
                if hasattr(page_widget, "load_settings"):
                    page_widget.load_settings()

            # Reset change flag
            self.has_unsaved_changes = False
            self._update_button_states()

            logger.debug("Settings loaded")

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.show_error(
                self.i18n.t("settings.error.title"),
                self.i18n.t("settings.error.load_failed", error=str(e)),
            )

    def save_settings(self) -> bool:
        """
        Save settings from all pages.

        Returns:
            True if settings were saved successfully
        """
        settings_snapshot: Dict[str, Any] = self._get_settings_snapshot()
        try:
            # Validate settings in all pages
            for _page_id, page_widget in self.settings_pages.items():
                if hasattr(page_widget, "validate_settings"):
                    is_valid, error_msg = page_widget.validate_settings()
                    if not is_valid:
                        self.show_warning(self.i18n.t("settings.validation.title"), error_msg)
                        # Switch to the page with error
                        page_index = self.pages_container.indexOf(page_widget)
                        if page_index >= 0:
                            self.category_list.setCurrentRow(page_index)
                        return False

            # Save settings from each page
            for page_widget in self.settings_pages.values():
                if hasattr(page_widget, "save_settings"):
                    page_widget.save_settings()

            # Persist to disk
            self._persist_settings()

            # Run page-level post-save side effects only after disk save succeeds.
            has_post_save_warnings = self._run_page_post_save_hooks()

            # Apply runtime-only settings after global save succeeds.
            self._apply_post_save_runtime_state()

            # Update original settings
            self.original_settings = self._get_settings_snapshot()

            # Reset change flag
            self.has_unsaved_changes = False
            self._update_button_states()

            # Emit signal
            self.settings_saved.emit()

            # Show success message only when no post-save warnings were reported.
            if not has_post_save_warnings:
                self.show_info(
                    self.i18n.t("settings.success.title"), self.i18n.t("settings.success.saved")
                )

            logger.info(self.i18n.t("logging.settings.saved_successfully"))
            return True

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            rollback_succeeded = self._rollback_settings(settings_snapshot)
            error_message = self.i18n.t("settings.error.save_failed", error=str(e))
            if not rollback_succeeded:
                error_message = f"{error_message}\n{self.i18n.t('settings.error.rollback_failed')}"
            self.show_error(
                self.i18n.t("settings.error.title"),
                error_message,
            )
            return False

    def _rollback_settings(self, snapshot: Dict[str, Any]) -> bool:
        """Rollback in-memory settings and runtime side effects after save failure."""
        if not isinstance(snapshot, dict):
            return False

        restored = self._restore_settings_snapshot(snapshot)
        if not restored:
            return False

        self._restore_runtime_state(snapshot)
        return True

    def _apply_post_save_runtime_state(self) -> None:
        """Apply runtime-only settings that should follow successful global save."""
        try:
            theme = self.settings_manager.get_setting("ui.theme")
            main_window = self.managers.get("main_window")
            if (
                isinstance(theme, str)
                and main_window is not None
                and hasattr(main_window, "apply_theme")
            ):
                main_window.apply_theme(theme)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to apply theme after saving settings: %s", exc, exc_info=True)

        try:
            language = self.settings_manager.get_setting("ui.language")
            if isinstance(language, str) and hasattr(self.i18n, "change_language"):
                self.i18n.change_language(language)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to apply language after saving settings: %s", exc, exc_info=True)

    def _run_page_post_save_hooks(self) -> bool:
        """Run optional page post-save hooks and return whether warnings were shown."""
        warnings: list[PostSaveMessage] = []

        for page_id, page_widget in self.settings_pages.items():
            post_save = getattr(page_widget, "apply_post_save", None)
            if not callable(post_save):
                continue

            try:
                result = post_save()
                warnings.extend(self._normalize_post_save_messages(page_id, result))
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Post-save hook failed for settings page '%s': %s",
                    page_id,
                    exc,
                    exc_info=True,
                )
                warnings.append(
                    {
                        "level": "warning",
                        "source": page_id,
                        "message": str(exc),
                    }
                )

        if warnings:
            details = "; ".join(
                f"[{item.get('source', 'settings')}/{item.get('level', 'warning')}] "
                f"{item.get('message', '')}"
                for item in warnings
            )
            self.show_warning(
                self.i18n.t("common.warning"),
                self.i18n.t("settings.warning.post_save_actions_partial", details=details),
            )
            return True

        return False

    def _normalize_post_save_messages(self, page_id: str, result: Any) -> list[PostSaveMessage]:
        """Normalize post-save hook return values to structured message objects."""
        normalized: list[PostSaveMessage] = []
        items: list[Any]

        if isinstance(result, str):
            items = [result]
        elif isinstance(result, (list, tuple, set)):
            items = list(result)
        elif isinstance(result, dict):
            items = [result]
        else:
            return normalized

        for item in items:
            if isinstance(item, str):
                message = item.strip()
                if message:
                    normalized.append({"level": "warning", "source": page_id, "message": message})
                continue

            if isinstance(item, dict):
                message = str(item.get("message", "")).strip()
                if not message:
                    continue
                level = str(item.get("level", "warning")).strip() or "warning"
                source = str(item.get("source", page_id)).strip() or page_id
                normalized.append({"level": level, "source": source, "message": message})

        return normalized

    def _restore_runtime_state(self, snapshot: Dict[str, Any]) -> None:
        """Restore runtime-only side effects (theme/language) from snapshot."""
        ui_settings = snapshot.get("ui")
        if not isinstance(ui_settings, dict):
            return

        theme = ui_settings.get("theme")
        main_window = self.managers.get("main_window")
        if (
            isinstance(theme, str)
            and main_window is not None
            and hasattr(main_window, "apply_theme")
        ):
            main_window.apply_theme(theme)

        language = ui_settings.get("language")
        if isinstance(language, str) and hasattr(self.i18n, "change_language"):
            self.i18n.change_language(language)

    def _on_settings_changed(self):
        """Handle settings change in any page."""
        self.has_unsaved_changes = True
        self._update_button_states()

    def _update_button_states(self):
        """Update button enabled states based on changes."""
        self.save_button.setEnabled(self.has_unsaved_changes)
        self.cancel_button.setEnabled(self.has_unsaved_changes)

    def _on_save_clicked(self):
        """Handle save button click."""
        self.save_settings()

    def _confirm_discard_changes(self) -> bool:
        """Ask user to confirm discarding unsaved settings."""
        reply = QMessageBox.question(
            self,
            self.i18n.t("settings.confirm.title"),
            self.i18n.t("settings.confirm.discard_changes"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        if self.has_unsaved_changes and self._confirm_discard_changes():
            # Reload original settings
            self.load_settings()

    def _on_reset_clicked(self):
        """Handle reset button click."""
        # Confirm reset
        reply = QMessageBox.question(
            self,
            self.i18n.t("settings.confirm.title"),
            self.i18n.t("settings.confirm.reset_defaults"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Reset all settings to defaults
                self.settings_manager.reset_to_default()

                # Reload settings
                self.load_settings()

                self.show_info(
                    self.i18n.t("settings.success.title"),
                    self.i18n.t("settings.success.reset"),
                )

                logger.info(self.i18n.t("logging.settings.reset_to_defaults"))

            except Exception as e:
                logger.error(f"Error resetting settings: {e}")
                self.show_error(
                    self.i18n.t("settings.error.title"),
                    self.i18n.t("settings.error.reset_failed", error=str(e)),
                )

    def _on_language_changed(self, language: str):
        """
        Handle language change event.

        Args:
            language: New language code
        """
        logger.debug(f"Updating settings text for language: {language}")

        # Update title
        self.title_label.setText(self.i18n.t("settings.title"))

        # Update UI text
        # Note: This is a simplified implementation
        # In a real app, you'd update all text elements
        self.save_button.setText(self.i18n.t("settings.save"))
        self.cancel_button.setText(self.i18n.t("settings.cancel"))
        self.reset_button.setText(self.i18n.t("settings.reset"))

        # Update category list
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            category_id = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self.i18n.t(f"settings.category.{category_id}"))

        # Update pages
        for page_widget in self.settings_pages.values():
            if hasattr(page_widget, "update_translations"):
                page_widget.update_translations()

    def check_unsaved_changes(self) -> bool:
        """
        Check if there are unsaved changes and prompt user.

        Returns:
            True if it's safe to proceed (no changes or user confirmed discard)
        """
        if not self.has_unsaved_changes:
            return True

        return self._confirm_discard_changes()
