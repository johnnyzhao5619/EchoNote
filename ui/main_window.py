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
Main window for EchoNote application.

Provides the primary application window with sidebar navigation and
content area for different features.
"""

import logging
from typing import Any, Dict, Optional

from ui.qt_imports import (
    QApplication,
    QCloseEvent,
    QHBoxLayout,
    QKeySequence,
    QMainWindow,
    QPoint,
    QSettings,
    QShortcut,
    QSize,
    QStackedWidget,
    Qt,
    QWidget,
)

from utils.i18n import I18nQtManager

logger = logging.getLogger("echonote.ui.main_window")


class MainWindow(QMainWindow):
    """
    Main application window with sidebar navigation and content area.

    Manages page switching, theme application, window state persistence,
    and language switching.
    """

    def __init__(self, managers: Dict[str, Any], i18n: I18nQtManager):
        """
        Initialize main window.

        Args:
            managers: Dictionary of business logic managers:
                - transcription_manager: TranscriptionManager instance
                - calendar_manager: CalendarManager instance
                - timeline_manager: TimelineManager instance
                - settings_manager: SettingsManager instance
                - realtime_recorder: RealtimeRecorder instance
            i18n: Internationalization manager with Qt signal support
        """
        super().__init__()

        self.managers = managers
        self.i18n = i18n

        # Settings for window state persistence
        self.settings = QSettings("EchoNote", "EchoNote")

        # Page widgets dictionary (will be populated by subclasses/modules)
        self.pages: Dict[str, QWidget] = {}

        # Current page name
        self.current_page: Optional[str] = None

        # Setup UI
        self.setup_ui()

        # Connect language change signal
        self.i18n.language_changed.connect(self._on_language_changed)

        # Connect API keys updated signal
        settings_manager = self.managers.get("settings_manager")
        if settings_manager:
            settings_manager.api_keys_updated.connect(self._on_api_keys_updated)

        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Restore window state
        self.restore_window_state()

        logger.info(self.i18n.t("logging.main_window.initialized"))

    def setup_ui(self):
        """Set up the main window UI layout."""
        # Set window properties
        self.setWindowTitle(self.i18n.t("app.title"))
        self.setMinimumSize(1024, 768)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout (horizontal: sidebar + content)
        main_layout = QHBoxLayout(central_widget)
        # # main_layout.setSpacing(0)

        # Create sidebar
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)

        # Create content area
        self.content_area = self.create_content_area()
        main_layout.addWidget(self.content_area, stretch=1)

        # Apply default theme
        theme = self.managers.get("settings_manager")
        if theme:
            try:
                current_theme = theme.get_setting("ui.theme")
                self.apply_theme(current_theme or "light")
            except Exception as e:
                logger.warning(f"Could not load theme setting: {e}")
                self.apply_theme("light")
        else:
            self.apply_theme("light")

        logger.debug("Main window UI setup complete")

    def create_sidebar(self) -> QWidget:
        """
        Create sidebar navigation widget.

        Returns:
            Sidebar widget
        """
        # Import here to avoid circular imports
        from ui.sidebar import Sidebar

        sidebar = Sidebar(self.i18n, self)

        # Connect page change signal
        sidebar.page_changed.connect(self.switch_page)

        return sidebar

    def create_content_area(self) -> QStackedWidget:
        """
        Create main content area with stacked widget for page switching.

        Returns:
            Stacked widget for content pages
        """
        content_area = QStackedWidget()

        # Create placeholder pages
        # These will be replaced with actual implementations in subsequent tasks
        self._create_placeholder_pages(content_area)

        return content_area

    def _create_placeholder_pages(self, content_area: QStackedWidget):
        """
        Create actual page widgets.

        Args:
            content_area: Stacked widget to add pages to
        """
        # Import actual widget classes
        from ui.batch_transcribe.widget import BatchTranscribeWidget
        from ui.calendar_hub.widget import CalendarHubWidget
        from ui.realtime_record.widget import RealtimeRecordWidget
        from ui.settings.widget import SettingsWidget
        from ui.timeline.widget import TimelineWidget

        # Create batch transcribe widget
        if self.managers.get("transcription_manager") is not None:
            try:
                batch_widget = BatchTranscribeWidget(
                    self.managers["transcription_manager"],
                    self.i18n,
                    self.managers.get("model_manager"),
                )
                content_area.addWidget(batch_widget)
                self.pages["batch_transcribe"] = batch_widget
            except Exception as e:
                logger.error(f"Failed to create batch transcribe widget: {e}")
                self._add_error_placeholder(content_area, "batch_transcribe", str(e))
        else:
            self._add_error_placeholder(
                content_area, "batch_transcribe", "Transcription manager not available"
            )

        # Create realtime record widget
        if self.managers.get("realtime_recorder") is not None:
            try:
                realtime_widget = RealtimeRecordWidget(
                    self.managers["realtime_recorder"],
                    self.managers["audio_capture"],
                    self.i18n,
                    settings_manager=self.managers.get("settings_manager"),
                    model_manager=self.managers.get("model_manager"),
                )
                content_area.addWidget(realtime_widget)
                self.pages["realtime_record"] = realtime_widget
            except Exception as e:
                logger.error(f"Failed to create realtime record widget: {e}")
                self._add_error_placeholder(content_area, "realtime_record", str(e))
        else:
            self._add_error_placeholder(
                content_area, "realtime_record", "Realtime recorder not available"
            )

        # Create calendar hub widget
        if (
            self.managers.get("calendar_manager") is not None
            and self.managers.get("oauth_manager") is not None
        ):
            try:
                calendar_widget = CalendarHubWidget(
                    self.managers["calendar_manager"], self.managers["oauth_manager"], self.i18n
                )
                content_area.addWidget(calendar_widget)
                self.pages["calendar_hub"] = calendar_widget
            except Exception as e:
                logger.error(f"Failed to create calendar hub widget: {e}")
                self._add_error_placeholder(content_area, "calendar_hub", str(e))
        else:
            error_msg = "Calendar manager not available"
            if self.managers.get("oauth_manager") is None:
                error_msg = "OAuth manager not available"
            self._add_error_placeholder(content_area, "calendar_hub", error_msg)

        # Create timeline widget
        if self.managers.get("timeline_manager") is not None:
            try:
                timeline_widget = TimelineWidget(
                    self.managers["timeline_manager"],
                    self.i18n,
                    settings_manager=self.managers.get("settings_manager"),
                )
                content_area.addWidget(timeline_widget)
                self.pages["timeline"] = timeline_widget
            except Exception as e:
                logger.error(f"Failed to create timeline widget: {e}")
                self._add_error_placeholder(content_area, "timeline", str(e))
        else:
            self._add_error_placeholder(content_area, "timeline", "Timeline manager not available")

        # Create settings widget
        if self.managers.get("settings_manager") is not None:
            try:
                # Add main window to managers for theme application
                managers_with_window = self.managers.copy()
                managers_with_window["main_window"] = self

                settings_widget = SettingsWidget(
                    self.managers["settings_manager"], self.i18n, managers_with_window
                )
                content_area.addWidget(settings_widget)
                self.pages["settings"] = settings_widget
            except Exception as e:
                logger.error(f"Failed to create settings widget: {e}")
                self._add_error_placeholder(content_area, "settings", str(e))
        else:
            self._add_error_placeholder(content_area, "settings", "Settings manager not available")

        logger.debug(f"Created {len(self.pages)} page widgets")

    def _add_error_placeholder(self, content_area: QStackedWidget, page_name: str, error_msg: str):
        """
        Add an error placeholder page.

        Args:
            content_area: Stacked widget to add page to
            page_name: Name of the page
            error_msg: Error message to display
        """
        from PySide6.QtWidgets import QLabel, QVBoxLayout

        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)

        label = QLabel(f"Error loading {page_name}\n\n{error_msg}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)

        content_area.addWidget(placeholder)
        self.pages[page_name] = placeholder

    def switch_page(self, page_name: str):
        """
        Switch to a different page.

        Args:
            page_name: Name of the page to switch to
        """
        if page_name not in self.pages:
            logger.warning(f"Page '{page_name}' not found")
            return

        # Get the widget for this page
        page_widget = self.pages[page_name]

        # Switch to the page
        self.content_area.setCurrentWidget(page_widget)
        self.current_page = page_name

        logger.debug(f"Switched to page: {page_name}")

    def apply_theme(self, theme: str):
        """
        Apply a theme to the application.

        Args:
            theme: Theme name ('light', 'dark', 'high_contrast', or 'system')
        """
        try:
            # Handle system theme
            if theme == "system":
                # Detect system theme
                theme = self._detect_system_theme()

            # Load theme stylesheet
            theme_path = self._get_theme_path(theme)

            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    stylesheet = f.read()

                # Apply stylesheet to application
                QApplication.instance().setStyleSheet(stylesheet)

                logger.info(f"Applied theme: {theme}")

            except FileNotFoundError:
                logger.warning(f"Theme file not found: {theme_path}, using default")
                # Clear stylesheet to use default
                QApplication.instance().setStyleSheet("")

        except Exception as e:
            logger.error(f"Error applying theme: {e}")

    def _detect_system_theme(self) -> str:
        """
        Detect system theme preference.

        Returns:
            'light' or 'dark'
        """
        # Try to detect system theme
        try:
            import platform

            system = platform.system()

            if system == "Darwin":  # macOS
                # Check macOS dark mode
                import subprocess

                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and "Dark" in result.stdout:
                    return "dark"
                return "light"

            elif system == "Windows":
                # Check Windows dark mode
                try:
                    import winreg

                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    )
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    winreg.CloseKey(key)
                    return "light" if value == 1 else "dark"
                except Exception:
                    pass

            # Default to light theme
            return "light"

        except Exception as e:
            logger.warning(f"Could not detect system theme: {e}")
            return "light"

    def _get_theme_path(self, theme: str) -> str:
        """
        Get path to theme stylesheet file.

        Args:
            theme: Theme name ('light' or 'dark')

        Returns:
            Path to theme file
        """
        from pathlib import Path

        # Get resources directory
        resources_dir = Path(__file__).parent.parent / "resources" / "themes"

        # Get theme file path
        theme_file = resources_dir / f"{theme}.qss"

        return str(theme_file)

    def save_window_state(self):
        """Save window state (position, size, maximized) to settings."""
        try:
            # Save window geometry
            self.settings.setValue("window/geometry", self.saveGeometry())

            # Save window state (maximized, etc.)
            self.settings.setValue("window/state", self.saveState())

            # Save position and size explicitly as backup
            self.settings.setValue("window/position", self.pos())
            self.settings.setValue("window/size", self.size())
            self.settings.setValue("window/maximized", self.isMaximized())

            logger.debug("Window state saved")

        except Exception as e:
            logger.error(f"Error saving window state: {e}")

    def restore_window_state(self):
        """Restore window state from settings."""
        try:
            # Try to restore geometry and state
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)

            state = self.settings.value("window/state")
            if state:
                self.restoreState(state)

            # Fallback to explicit position and size
            if not geometry:
                position = self.settings.value("window/position")
                size = self.settings.value("window/size")
                maximized = self.settings.value("window/maximized", False, type=bool)

                if position and isinstance(position, QPoint):
                    self.move(position)

                if size and isinstance(size, QSize):
                    self.resize(size)

                if maximized:
                    self.showMaximized()

            logger.debug("Window state restored")

        except Exception as e:
            logger.error(f"Error restoring window state: {e}")
            # Use default size if restoration fails
            self.resize(1024, 768)

    def closeEvent(self, event: QCloseEvent):
        """
        Handle window close event.

        Args:
            event: Close event
        """
        try:
            # Check for running tasks
            if self._has_running_tasks():
                # Get task count for better user message
                task_count = self._get_running_task_count()

                # Show confirmation dialog
                from PySide6.QtWidgets import QMessageBox

                # Build message with task count
                if task_count > 0:
                    message = self.i18n.t(
                        "app.exit_confirmation_message_with_count", count=task_count
                    )
                else:
                    message = self.i18n.t("app.exit_confirmation_message")

                reply = QMessageBox.question(
                    self,
                    self.i18n.t("app.exit_confirmation_title"),
                    message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply != QMessageBox.StandardButton.Yes:
                    # User chose not to exit
                    event.ignore()
                    logger.info(self.i18n.t("logging.main_window.exit_cancelled"))
                    return

                # If Yes, continue with exit (force stop tasks)
                logger.info(f"User confirmed exit with {task_count} running task(s)")

            # Save window state
            self.save_window_state()

            # Perform cleanup
            self._cleanup()

            # Accept the close event
            event.accept()

            logger.info(self.i18n.t("logging.main_window.closed"))

        except Exception as e:
            logger.error(f"Error during window close: {e}")
            event.accept()

    def _has_running_tasks(self) -> bool:
        """
        Check if there are any running tasks.

        Returns:
            True if there are running tasks
        """
        try:
            task_count = 0

            # Check transcription tasks
            if "transcription_manager" in self.managers:
                transcription_manager = self.managers["transcription_manager"]
                if hasattr(transcription_manager, "has_running_tasks"):
                    if transcription_manager.has_running_tasks():
                        logger.debug("Found running transcription tasks")
                        task_count += 1

            # Check realtime recording
            if "realtime_recorder" in self.managers:
                realtime_recorder = self.managers["realtime_recorder"]
                if hasattr(realtime_recorder, "is_recording"):
                    if realtime_recorder.is_recording:  # 这是属性，不是方法
                        logger.debug("Found active recording session")
                        task_count += 1

            return task_count > 0

        except Exception as e:
            logger.error(f"Error checking running tasks: {e}")
            return False

    def _get_running_task_count(self) -> int:
        """
        Get the count of running tasks.

        Returns:
            Number of running tasks
        """
        try:
            count = 0

            # Count transcription tasks
            if "transcription_manager" in self.managers:
                transcription_manager = self.managers["transcription_manager"]
                if hasattr(transcription_manager, "has_running_tasks"):
                    if transcription_manager.has_running_tasks():
                        # Get actual count from database
                        try:
                            result = self.managers["db_connection"].execute(
                                "SELECT COUNT(*) as count FROM transcription_tasks "
                                "WHERE status = 'processing'"
                            )
                            if result and len(result) > 0:
                                count += result[0]["count"]
                        except Exception:
                            count += 1  # Fallback to 1 if query fails

            # Count realtime recording
            if "realtime_recorder" in self.managers:
                realtime_recorder = self.managers["realtime_recorder"]
                if hasattr(realtime_recorder, "is_recording"):
                    if realtime_recorder.is_recording:
                        count += 1

            return count

        except Exception as e:
            logger.error(f"Error getting running task count: {e}")
            return 0

    def _cleanup(self):
        """Perform cleanup before closing."""
        import time

        try:
            logger.info(self.i18n.t("logging.main_window.cleanup_starting"))
            cleanup_start = time.time()

            # Close all open transcript viewer windows
            try:
                batch_widget = self.pages.get("batch_transcribe")
                if batch_widget and hasattr(batch_widget, "close_all_viewers"):
                    logger.info(self.i18n.t("logging.main_window.closing_transcript_viewers"))
                    batch_widget.close_all_viewers()
            except Exception as e:
                logger.error(f"Error closing transcript viewers: {e}")

            # Stop transcription manager
            if "transcription_manager" in self.managers:
                try:
                    transcription_manager = self.managers["transcription_manager"]
                    if hasattr(transcription_manager, "stop_all_tasks"):
                        logger.info(self.i18n.t("logging.main_window.stopping_transcription_tasks"))
                        transcription_manager.stop_all_tasks()

                        # Wait for tasks to stop (with timeout)
                        wait_start = time.time()
                        while transcription_manager._running and time.time() - wait_start < 3.0:
                            time.sleep(0.1)

                        if transcription_manager._running:
                            logger.warning(
                                self.i18n.t("logging.main_window.transcription_manager_timeout")
                            )
                except Exception as e:
                    logger.error(f"Error stopping transcription manager: {e}")

            # Stop realtime recorder
            if "realtime_recorder" in self.managers:
                try:
                    realtime_recorder = self.managers["realtime_recorder"]
                    if (
                        hasattr(realtime_recorder, "is_recording")
                        and realtime_recorder.is_recording
                    ):
                        logger.info(self.i18n.t("logging.main_window.stopping_realtime_recorder"))
                        # Set flag to stop recording
                        realtime_recorder.is_recording = False

                        # Stop audio capture
                        if hasattr(realtime_recorder, "audio_capture"):
                            try:
                                realtime_recorder.audio_capture.stop_capture()
                            except Exception:
                                pass

                        # Wait briefly for recording to stop
                        time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error stopping realtime recorder: {e}")

            # Stop resource monitor
            if "resource_monitor" in self.managers:
                try:
                    resource_monitor = self.managers["resource_monitor"]
                    if hasattr(resource_monitor, "stop"):
                        logger.info(self.i18n.t("logging.main_window.stopping_resource_monitor"))
                        resource_monitor.stop()
                except Exception as e:
                    logger.error(f"Error stopping resource monitor: {e}")

            # Stop schedulers
            if "auto_task_scheduler" in self.managers:
                try:
                    auto_task_scheduler = self.managers["auto_task_scheduler"]
                    if hasattr(auto_task_scheduler, "stop"):
                        logger.info(self.i18n.t("logging.main_window.stopping_auto_task_scheduler"))
                        auto_task_scheduler.stop()
                except Exception as e:
                    logger.error(f"Error stopping auto task scheduler: {e}")

            if "sync_scheduler" in self.managers:
                try:
                    sync_scheduler = self.managers["sync_scheduler"]
                    if hasattr(sync_scheduler, "stop"):
                        logger.info(self.i18n.t("logging.main_window.stopping_sync_scheduler"))
                        sync_scheduler.stop()
                except Exception as e:
                    logger.error(f"Error stopping sync scheduler: {e}")

            # Save settings
            if "settings_manager" in self.managers:
                try:
                    settings_manager = self.managers["settings_manager"]
                    if hasattr(settings_manager, "save_settings"):
                        logger.info(self.i18n.t("logging.main_window.saving_settings"))
                        settings_manager.save_settings()
                except Exception as e:
                    logger.error(f"Error saving settings: {e}")

            # Close database connection
            if "db_connection" in self.managers:
                try:
                    db_connection = self.managers["db_connection"]
                    if hasattr(db_connection, "close_all"):
                        logger.info(self.i18n.t("logging.main_window.closing_database_connection"))
                        db_connection.close_all()
                except Exception as e:
                    logger.error(f"Error closing database: {e}")

            # Clean up temporary files (only files older than today)
            if "file_manager" in self.managers:
                try:
                    file_manager = self.managers["file_manager"]
                    if hasattr(file_manager, "cleanup_temp_files"):
                        logger.info(self.i18n.t("logging.main_window.cleaning_temp_files"))
                        # Clean files older than 1 day (not current session files)
                        file_manager.cleanup_temp_files(older_than_days=1)
                except Exception as e:
                    logger.error(f"Error cleaning up temp files: {e}")

            # Disconnect signals
            try:
                self.i18n.language_changed.disconnect(self._on_language_changed)
            except Exception:
                pass

            try:
                settings_manager = self.managers.get("settings_manager")
                if settings_manager:
                    settings_manager.api_keys_updated.disconnect(self._on_api_keys_updated)
            except Exception:
                pass

            cleanup_duration = time.time() - cleanup_start
            logger.info(f"Cleanup complete (took {cleanup_duration:.2f}s)")

            # Warn if cleanup took too long
            if cleanup_duration > 10.0:
                logger.warning(f"Cleanup took longer than expected: {cleanup_duration:.2f}s")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _on_language_changed(self, language: str):
        """
        Handle language change event.

        Args:
            language: New language code
        """
        logger.info(f"Language changed to: {language}")

        # Update window title
        self.setWindowTitle(self.i18n.t("app.title"))

        # Notify all pages to update their text
        # This will be implemented when actual page widgets are created
        for page_name, page_widget in self.pages.items():
            if hasattr(page_widget, "update_translations"):
                try:
                    page_widget.update_translations()
                except Exception as e:
                    logger.error(f"Error updating translations for page {page_name}: {e}")

    def _setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts for accessibility."""
        # Navigation shortcuts (Ctrl+1-5)
        pages = ["batch_transcribe", "realtime_record", "calendar_hub", "timeline", "settings"]
        for i, page in enumerate(pages, 1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(lambda p=page: self.switch_page(p))
            logger.debug(f"Added keyboard shortcut Ctrl+{i} for {page}")

        # Settings shortcut (Ctrl+,)
        settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        settings_shortcut.activated.connect(lambda: self.switch_page("settings"))

        # Quit shortcut (Ctrl+Q)
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)

        logger.info(self.i18n.t("logging.main_window.keyboard_shortcuts_configured"))

    def _on_api_keys_updated(self):
        """
        Handle API keys updated event.

        This method is called when API keys are saved in settings.
        It notifies relevant components to reload their engines with new keys.
        """
        logger.info(self.i18n.t("logging.main_window.api_keys_updated"))

        # Notify transcription manager to reload engines if needed
        transcription_manager = self.managers.get("transcription_manager")
        if transcription_manager and hasattr(transcription_manager, "reload_engine"):
            try:
                transcription_manager.reload_engine()
                logger.info(self.i18n.t("logging.main_window.transcription_engine_reloaded"))
            except Exception as e:
                logger.error(f"Error reloading transcription engine: {e}")

        # Notify realtime recorder to reload engines if needed
        realtime_recorder = self.managers.get("realtime_recorder")
        if realtime_recorder and hasattr(realtime_recorder, "reload_engine"):
            try:
                realtime_recorder.reload_engine()
                logger.info(self.i18n.t("logging.main_window.realtime_recorder_engine_reloaded"))
            except Exception as e:
                logger.error(f"Error reloading realtime recorder engine: {e}")

        logger.info(self.i18n.t("logging.main_window.cloud_engines_reload_completed"))

    def add_page(self, page_name: str, page_widget: QWidget):
        """
        Add a page to the main window.

        This method allows dynamically adding pages after initialization.

        Args:
            page_name: Unique name for the page
            page_widget: Widget to display for this page
        """
        if page_name in self.pages:
            # Remove old page
            old_widget = self.pages[page_name]
            self.content_area.removeWidget(old_widget)
            old_widget.deleteLater()

        # Add new page
        self.content_area.addWidget(page_widget)
        self.pages[page_name] = page_widget

        logger.debug(f"Added page: {page_name}")

    def remove_page(self, page_name: str):
        """
        Remove a page from the main window.

        Args:
            page_name: Name of the page to remove
        """
        if page_name not in self.pages:
            logger.warning(f"Cannot remove page '{page_name}': not found")
            return

        # Get widget
        widget = self.pages[page_name]

        # Remove from content area
        self.content_area.removeWidget(widget)

        # Remove from pages dict
        del self.pages[page_name]

        # Delete widget
        widget.deleteLater()

        logger.debug(f"Removed page: {page_name}")
