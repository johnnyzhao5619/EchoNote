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
from typing import Any, Callable, Dict, Optional

from ui.common.theme import ThemeManager
from ui.common.style_utils import set_widget_state
from ui.constants import (
    APP_SEARCH_MAX_WIDTH,
    APP_SEARCH_MIN_WIDTH,
    APP_SHELL_CONTENT_MARGINS,
    APP_STATUS_BAR_HEIGHT,
    APP_STATUS_BAR_MARGINS,
    APP_SHELL_RESOURCE_BAR_HEIGHT,
    APP_SHELL_RESOURCE_BAR_WIDTH,
    APP_STATUS_BAR_SPACING,
    APP_TOP_BAR_CONTROL_HEIGHT,
    APP_TOP_BAR_HEIGHT,
    APP_TOP_BAR_HINT_WIDTH,
    APP_TOP_BAR_MARGINS,
    APP_TOP_BAR_SPACING,
    ROLE_SHELL_RESOURCE_BAR,
    SHELL_STATUS_REFRESH_INTERVAL_MS,
    ZERO_MARGINS,
    ZERO_SPACING,
)
from ui.navigation import NAV_ITEMS, NAV_PAGE_ORDER
from core.qt_imports import (
    QApplication,
    QCloseEvent,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPoint,
    QProgressBar,
    QSettings,
    QShortcut,
    QSize,
    QStackedWidget,
    Qt,
    QTimer,
    QVBoxLayout,
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
        self.theme_manager = ThemeManager()

        # Settings for window state persistence
        self.settings = QSettings("EchoNote", "EchoNote")

        # Page widgets dictionary (will be populated by subclasses/modules)
        self.pages: Dict[str, QWidget] = {}

        # Current page name
        self.current_page: Optional[str] = None
        self._shortcuts = []

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

        # Set application icon
        import os

        icon_path = os.path.join("resources", "icons", "echonote.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Create central widget
        central_widget = QWidget()
        central_widget.setObjectName("app_shell")
        self.setCentralWidget(central_widget)

        # Create shell layout (top bar + body + status bar)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(*ZERO_MARGINS)
        main_layout.setSpacing(ZERO_SPACING)

        self.top_bar = self._create_top_bar()
        main_layout.addWidget(self.top_bar)

        content_shell = QWidget()
        content_shell.setObjectName("content_shell")
        content_layout = QHBoxLayout(content_shell)
        content_layout.setContentsMargins(*APP_SHELL_CONTENT_MARGINS)
        content_layout.setSpacing(ZERO_SPACING)

        # Create sidebar and main stack
        self.sidebar = self.create_sidebar()
        content_layout.addWidget(self.sidebar)

        self.content_area = self.create_content_area()
        self.content_area.setObjectName("content_stack")
        content_layout.addWidget(self.content_area, stretch=1)
        main_layout.addWidget(content_shell, stretch=1)

        self.shell_status_bar = self._create_shell_status_bar()
        main_layout.addWidget(self.shell_status_bar)

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

        # Switch to first available page and start shell status updates.
        self._switch_to_first_available_page()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_shell_status)
        self._status_timer.start(SHELL_STATUS_REFRESH_INTERVAL_MS)
        self._update_shell_status()

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

        self._create_pages(content_area)

        return content_area

    def _create_top_bar(self) -> QWidget:
        """Create global application top bar."""
        top_bar = QWidget()
        top_bar.setObjectName("top_bar")
        top_bar.setFixedHeight(APP_TOP_BAR_HEIGHT)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(*APP_TOP_BAR_MARGINS)
        layout.setSpacing(APP_TOP_BAR_SPACING)

        self.brand_label = QLabel(self.i18n.t("app.name"))
        self.brand_label.setObjectName("top_bar_brand")
        layout.addWidget(self.brand_label)

        layout.addStretch()

        self.global_search_input = QLineEdit()
        self.global_search_input.setObjectName("top_bar_search")
        self.global_search_input.setMinimumWidth(APP_SEARCH_MIN_WIDTH)
        self.global_search_input.setMaximumWidth(APP_SEARCH_MAX_WIDTH)
        self.global_search_input.setFixedHeight(APP_TOP_BAR_CONTROL_HEIGHT)
        self.global_search_input.returnPressed.connect(self._on_global_search_submitted)
        layout.addWidget(self.global_search_input)

        self.search_hint_label = QLabel(self.i18n.t("app_shell.search_hint"))
        self.search_hint_label.setObjectName("top_bar_hint")
        self.search_hint_label.setFixedHeight(APP_TOP_BAR_CONTROL_HEIGHT)
        self.search_hint_label.setFixedWidth(APP_TOP_BAR_HINT_WIDTH)
        self.search_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.search_hint_label)

        self._refresh_shell_text()
        return top_bar

    def _create_shell_status_bar(self) -> QWidget:
        """Create footer status bar used by the shell."""
        bar = QWidget()
        bar.setObjectName("shell_status_bar")
        bar.setFixedHeight(APP_STATUS_BAR_HEIGHT)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(*APP_STATUS_BAR_MARGINS)
        layout.setSpacing(APP_STATUS_BAR_SPACING)

        self.task_status_label = QLabel()
        self.task_status_label.setObjectName("shell_status_item")
        layout.addWidget(self.task_status_label)

        self.record_status_label = QLabel()
        self.record_status_label.setObjectName("shell_status_item")
        layout.addWidget(self.record_status_label)

        layout.addStretch()

        self.shell_message_label = QLabel()
        self.shell_message_label.setObjectName("shell_status_message")
        layout.addWidget(self.shell_message_label)

        self._resource_warning_threshold_percent = self._resolve_resource_warning_threshold()
        self.cpu_resource_label = QLabel(self.i18n.t("app_shell.resource_cpu_label"))
        self.cpu_resource_label.setObjectName("shell_status_item")
        layout.addWidget(self.cpu_resource_label)

        self.cpu_resource_bar = self._create_resource_bar()
        layout.addWidget(self.cpu_resource_bar)

        self.gpu_resource_label = QLabel(self.i18n.t("app_shell.resource_gpu_label"))
        self.gpu_resource_label.setObjectName("shell_status_item")
        layout.addWidget(self.gpu_resource_label)

        self.gpu_resource_bar = self._create_resource_bar()
        layout.addWidget(self.gpu_resource_bar)

        return bar

    def _create_resource_bar(self) -> QProgressBar:
        """Create a compact progress bar for shell resource telemetry."""
        bar = QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(0)
        bar.setTextVisible(True)
        bar.setFormat("0%")
        bar.setFixedWidth(APP_SHELL_RESOURCE_BAR_WIDTH)
        bar.setFixedHeight(APP_SHELL_RESOURCE_BAR_HEIGHT)
        bar.setProperty("role", ROLE_SHELL_RESOURCE_BAR)
        self._set_resource_bar_state(bar, state="normal")
        return bar

    def _resolve_resource_warning_threshold(self) -> float:
        """Resolve CPU/GPU warning threshold from resource monitor settings."""
        resource_monitor = self.managers.get("resource_monitor")
        threshold = getattr(resource_monitor, "high_cpu_threshold_percent", 90.0)
        try:
            return max(1.0, min(float(threshold), 100.0))
        except (TypeError, ValueError):
            return 90.0

    @staticmethod
    def _set_resource_bar_state(bar: QProgressBar, *, state: str) -> None:
        """Set semantic state and refresh style from theme QSS."""
        set_widget_state(bar, state)

    def _switch_to_first_available_page(self):
        """Switch to the first registered page using shared nav order."""
        for page_name in NAV_PAGE_ORDER:
            if page_name in self.pages:
                self.switch_page(page_name)
                return
        if self.pages:
            self.switch_page(next(iter(self.pages)))

    def _register_page_widget(
        self,
        content_area: QStackedWidget,
        page_name: str,
        factory: Callable[[], QWidget],
        missing_message: Optional[str] = None,
    ):
        """Create/register a page widget or attach a placeholder on failure."""
        if missing_message:
            self._add_error_placeholder(content_area, page_name, missing_message)
            return

        try:
            page_widget = factory()
            content_area.addWidget(page_widget)
            self.pages[page_name] = page_widget
        except Exception as e:
            logger.error("Failed to create %s widget: %s", page_name, e)
            self._add_error_placeholder(content_area, page_name, str(e))

    def _get_calendar_missing_reason(self) -> Optional[str]:
        """Get missing dependency reason for calendar page."""
        if self.managers.get("calendar_manager") is None:
            return "Calendar manager not available"
        if self.managers.get("oauth_manager") is None:
            return "OAuth manager not available"
        return None

    def _create_pages(self, content_area: QStackedWidget):
        """
        Create and register all main feature pages.

        Args:
            content_area: Stacked widget to add pages to
        """
        # Import actual widget classes
        from ui.batch_transcribe.widget import BatchTranscribeWidget
        from ui.calendar_hub.widget import CalendarHubWidget
        from ui.realtime_record.widget import RealtimeRecordWidget
        from ui.settings.widget import SettingsWidget
        from ui.timeline.widget import TimelineWidget

        # Add main window to managers for theme application in settings page.
        managers_with_window = self.managers.copy()
        managers_with_window["main_window"] = self

        self._register_page_widget(
            content_area,
            "batch_transcribe",
            lambda: BatchTranscribeWidget(
                self.managers["transcription_manager"],
                self.i18n,
                self.managers.get("model_manager"),
            ),
            missing_message=(
                None
                if self.managers.get("transcription_manager") is not None
                else "Transcription manager not available"
            ),
        )

        self._register_page_widget(
            content_area,
            "realtime_record",
            lambda: RealtimeRecordWidget(
                self.managers["realtime_recorder"],
                self.managers["audio_capture"],
                self.i18n,
                settings_manager=self.managers.get("settings_manager"),
                model_manager=self.managers.get("model_manager"),
                transcription_manager=self.managers.get("transcription_manager"),
            ),
            missing_message=(
                None
                if self.managers.get("realtime_recorder") is not None
                else "Realtime recorder not available"
            ),
        )

        self._register_page_widget(
            content_area,
            "calendar_hub",
            lambda: CalendarHubWidget(
                self.managers["calendar_manager"],
                self.managers["oauth_manager"],
                self.i18n,
                transcription_manager=self.managers["transcription_manager"],
            ),
            missing_message=self._get_calendar_missing_reason(),
        )

        self._register_page_widget(
            content_area,
            "timeline",
            lambda: TimelineWidget(
                self.managers["timeline_manager"],
                self.managers["transcription_manager"],
                self.i18n,
                settings_manager=self.managers.get("settings_manager"),
            ),
            missing_message=(
                None
                if self.managers.get("timeline_manager") is not None
                else "Timeline manager not available"
            ),
        )

        self._register_page_widget(
            content_area,
            "settings",
            lambda: SettingsWidget(
                self.managers["settings_manager"],
                self.i18n,
                managers_with_window,
            ),
            missing_message=(
                None
                if self.managers.get("settings_manager") is not None
                else "Settings manager not available"
            ),
        )

        logger.debug(f"Created {len(self.pages)} page widgets")

    def _add_error_placeholder(self, content_area: QStackedWidget, page_name: str, error_msg: str):
        """
        Add an error placeholder page.

        Args:
            content_area: Stacked widget to add page to
            page_name: Name of the page
            error_msg: Error message to display
        """
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
        if hasattr(self, "sidebar"):
            self.sidebar.set_active_page(page_name)

        if page_name == "timeline" and hasattr(page_widget, "load_timeline_events"):
            try:
                page_widget.load_timeline_events(reset=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to refresh timeline on page switch: %s", exc)
        elif page_name == "calendar_hub" and hasattr(page_widget, "_refresh_current_view"):
            try:
                page_widget._refresh_current_view()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to refresh calendar on page switch: %s", exc)

        self._update_shell_status()
        logger.debug(f"Switched to page: {page_name}")

    def _get_page_title(self, page_name: str) -> str:
        """Get translated page title by page name."""
        for item in NAV_ITEMS:
            if item.page_name == page_name:
                return self.i18n.t(item.text_key)
        return page_name

    def _refresh_shell_text(self):
        """Refresh shell labels that depend on i18n text."""
        if hasattr(self, "global_search_input"):
            self.global_search_input.setPlaceholderText(self.i18n.t("app_shell.search_placeholder"))
        if hasattr(self, "search_hint_label"):
            self.search_hint_label.setText(self.i18n.t("app_shell.search_hint"))
        if hasattr(self, "cpu_resource_label"):
            self.cpu_resource_label.setText(self.i18n.t("app_shell.resource_cpu_label"))
        if hasattr(self, "gpu_resource_label"):
            self.gpu_resource_label.setText(self.i18n.t("app_shell.resource_gpu_label"))
        self._update_shell_status()

    def _resolve_search_target(self, raw_query: str) -> Optional[str]:
        """Resolve top-bar query to a navigation page name."""
        query = raw_query.strip().lower()
        if not query:
            return None

        if self._resolve_settings_category(query) is not None:
            return "settings"

        best_contains_match: Optional[str] = None
        for item in NAV_ITEMS:
            translated = self.i18n.t(item.text_key).lower()
            candidates = [translated, item.page_name.replace("_", " "), *item.aliases]
            if any(query == candidate.lower() for candidate in candidates):
                return item.page_name
            if best_contains_match is None and any(
                query in candidate.lower() for candidate in candidates
            ):
                best_contains_match = item.page_name

        return best_contains_match

    def _resolve_settings_category(self, query: str) -> Optional[str]:
        """Resolve query to settings category id if matched."""
        settings_widget = self.pages.get("settings")
        category_list = getattr(settings_widget, "category_list", None)
        if category_list is None:
            return None

        query_normalized = query.strip().lower()
        if not query_normalized:
            return None

        contains_match = None
        for row in range(category_list.count()):
            item = category_list.item(row)
            category_id = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(category_id, str):
                continue

            label_text = item.text().strip().lower()
            candidates = [
                category_id.lower(),
                category_id.replace("_", " ").lower(),
                label_text,
            ]
            if any(query_normalized == candidate for candidate in candidates):
                return category_id
            if contains_match is None and any(
                query_normalized in candidate for candidate in candidates
            ):
                contains_match = category_id

        return contains_match

    def _on_global_search_submitted(self):
        """Handle top-bar global search submit."""
        if not hasattr(self, "global_search_input"):
            return

        raw_query = self.global_search_input.text().strip()
        if not raw_query:
            self._set_shell_message("")
            return
        target_page = self._resolve_search_target(raw_query)
        if target_page is None:
            self._set_shell_message(self.i18n.t("app_shell.search_no_match", query=raw_query))
            return

        self.switch_page(target_page)
        display_name = self._get_page_title(target_page)
        if target_page == "settings":
            settings_category = self._resolve_settings_category(raw_query)
            settings_widget = self.pages.get("settings")
            if (
                isinstance(settings_category, str)
                and settings_widget is not None
                and hasattr(settings_widget, "show_page")
            ):
                try:
                    if settings_widget.show_page(settings_category):
                        display_name = (
                            f"{display_name} / "
                            f"{self.i18n.t(f'settings.category.{settings_category}')}"
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to navigate settings sub-page from search: %s", exc)
        self._set_shell_message(self.i18n.t("app_shell.search_result", page=display_name))

    def _focus_global_search(self):
        """Focus top-bar global search input."""
        if not hasattr(self, "global_search_input"):
            return
        self.global_search_input.setFocus()
        self.global_search_input.selectAll()

    def _set_shell_message(self, message: str):
        """Update shell footer message."""
        if hasattr(self, "shell_message_label"):
            self.shell_message_label.setText(message)

    def _update_shell_status(self):
        """Refresh footer status from real runtime state."""
        if not hasattr(self, "task_status_label"):
            return

        running_tasks = self._get_running_task_count()
        self.task_status_label.setText(
            self.i18n.t("app_shell.tasks_running", count=max(int(running_tasks), 0))
        )

        realtime_recorder = self.managers.get("realtime_recorder")
        is_recording = bool(getattr(realtime_recorder, "is_recording", False))
        recording_key = "app_shell.recording_on" if is_recording else "app_shell.recording_off"
        self.record_status_label.setText(self.i18n.t(recording_key))
        self._update_resource_usage_status()

    def _update_resource_usage_status(self) -> None:
        """Refresh CPU/GPU usage bars from current resource monitor statistics."""
        if not hasattr(self, "cpu_resource_bar") or not hasattr(self, "gpu_resource_bar"):
            return

        resource_monitor = self.managers.get("resource_monitor")
        if resource_monitor is None or not hasattr(resource_monitor, "get_current_stats"):
            self._set_resource_bar_unavailable(self.cpu_resource_bar)
            self._set_resource_bar_unavailable(self.gpu_resource_bar)
            return

        try:
            stats = resource_monitor.get_current_stats() or {}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to read resource monitor stats: %s", exc)
            self._set_resource_bar_unavailable(self.cpu_resource_bar)
            self._set_resource_bar_unavailable(self.gpu_resource_bar)
            return

        cpu_percent = self._normalize_percent(stats.get("cpu_percent"))
        if cpu_percent is not None:
            self._set_resource_bar_percent(self.cpu_resource_bar, cpu_percent)
        else:
            self._set_resource_bar_unavailable(self.cpu_resource_bar)

        gpu_percent = self._normalize_percent(stats.get("gpu_percent"))
        gpu_available = bool(stats.get("gpu_available", gpu_percent is not None))
        if gpu_available and gpu_percent is not None:
            self._set_resource_bar_percent(self.gpu_resource_bar, gpu_percent)
        else:
            self._set_resource_bar_unavailable(self.gpu_resource_bar)

    @staticmethod
    def _normalize_percent(value: Any) -> Optional[float]:
        """Normalize telemetry percentage into [0, 100]."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric < 0:
            return 0.0
        if numeric > 100:
            return 100.0
        return numeric

    def _set_resource_bar_percent(self, bar: QProgressBar, percent: float) -> None:
        """Render resource bar as a valid percentage with warning state."""
        value = int(round(percent))
        bar.setEnabled(True)
        bar.setValue(value)
        bar.setFormat(f"{value}%")
        self._set_resource_bar_state(
            bar,
            state="warning" if percent >= self._resource_warning_threshold_percent else "normal",
        )

    def _set_resource_bar_unavailable(self, bar: QProgressBar) -> None:
        """Render resource bar as unavailable."""
        bar.setEnabled(False)
        bar.setValue(0)
        bar.setFormat(self.i18n.t("app_shell.resource_unavailable"))
        self._set_resource_bar_state(bar, state="unavailable")

    def apply_theme(self, theme: str):
        """
        Apply a theme to the application.

        Args:
            theme: Theme name ('light', 'dark', or 'system')
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

                # Update ThemeManager state
                self.theme_manager.set_theme(theme)

                # Notify all pages to update their theme-dependent elements
                for page_name, page_widget in self.pages.items():
                    if hasattr(page_widget, "update_theme"):
                        try:
                            page_widget.update_theme()
                        except Exception as e:
                            logger.error(f"Error updating theme for page {page_name}: {e}")

                self._update_shell_status()
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
            has_transcription_tasks = self._has_active_transcription_tasks()
            is_recording = self._is_realtime_recording_active()
            return has_transcription_tasks or is_recording

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
            count = self._get_active_transcription_task_count()
            if self._is_realtime_recording_active():
                count += 1
            return count

        except Exception as e:
            logger.error(f"Error getting running task count: {e}")
            return 0

    def _has_active_transcription_tasks(self) -> bool:
        """Return whether transcription manager currently has active tasks."""
        transcription_manager = self.managers.get("transcription_manager")
        if transcription_manager is None:
            return False

        if hasattr(transcription_manager, "get_active_task_count"):
            has_running = bool(max(int(transcription_manager.get_active_task_count()), 0) > 0)
        elif hasattr(transcription_manager, "has_running_tasks"):
            has_running = bool(transcription_manager.has_running_tasks())
        else:
            has_running = False

        if has_running:
            logger.debug("Found running transcription tasks")
        return has_running

    def _get_active_transcription_task_count(self) -> int:
        """Return exact active transcription task count when possible."""
        transcription_manager = self.managers.get("transcription_manager")
        if transcription_manager is None:
            return 0

        if hasattr(transcription_manager, "get_active_task_count"):
            try:
                return max(int(transcription_manager.get_active_task_count()), 0)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to get active count from manager runtime: %s", exc)

        if hasattr(transcription_manager, "has_running_tasks"):
            try:
                return 1 if transcription_manager.has_running_tasks() else 0
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to get active task state from manager: %s", exc)

        return 0

    def _is_realtime_recording_active(self) -> bool:
        """Return whether realtime recorder is currently recording."""
        realtime_recorder = self.managers.get("realtime_recorder")
        if realtime_recorder is None or not hasattr(realtime_recorder, "is_recording"):
            return False
        is_recording = bool(realtime_recorder.is_recording)  # 这是属性，不是方法
        if is_recording:
            logger.debug("Found active recording session")
        return is_recording

    def _cleanup(self):
        """Perform cleanup before closing."""
        import time

        try:
            logger.info(self.i18n.t("logging.main_window.cleanup_starting"))
            cleanup_start = time.time()

            if hasattr(self, "_status_timer") and self._status_timer.isActive():
                self._status_timer.stop()

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
                    realtime_widget = self.pages.get("realtime_record")
                    cleaned_by_widget = False
                    if realtime_widget and hasattr(realtime_widget, "_cleanup_resources"):
                        logger.info(self.i18n.t("logging.main_window.stopping_realtime_recorder"))
                        realtime_widget._cleanup_resources()
                        cleaned_by_widget = True

                    # Fallback for exceptional cases where the page is unavailable.
                    if not cleaned_by_widget and hasattr(realtime_recorder, "audio_capture"):
                        try:
                            realtime_recorder.audio_capture.stop_capture()
                        except Exception:
                            pass
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
                    config_manager = getattr(settings_manager, "config_manager", None)
                    save_config = getattr(config_manager, "save", None)
                    if callable(save_config):
                        logger.info(self.i18n.t("logging.main_window.saving_settings"))
                        save_config()
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
        self._refresh_shell_text()

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
        for item in NAV_ITEMS:
            self._bind_shortcut(
                f"Ctrl+{item.shortcut_index}",
                lambda p=item.page_name: self.switch_page(p),
            )
            logger.debug(
                "Added keyboard shortcut Ctrl+%s for %s", item.shortcut_index, item.page_name
            )

        # Settings shortcut (Ctrl+,)
        self._bind_shortcut("Ctrl+,", lambda: self.switch_page("settings"))

        # Global search focus shortcut (Ctrl+K)
        self._bind_shortcut("Ctrl+K", self._focus_global_search)

        # Quit shortcut (Ctrl+Q)
        self._bind_shortcut("Ctrl+Q", self.close)

        logger.info(self.i18n.t("logging.main_window.keyboard_shortcuts_configured"))

    def _bind_shortcut(self, sequence: str, callback):
        """Create and retain a QShortcut binding."""
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(callback)
        if hasattr(self, "_shortcuts"):
            self._shortcuts.append(shortcut)
        return shortcut

    def _on_api_keys_updated(self):
        """
        Handle API keys updated event.

        This method is called when API keys are saved in settings.
        It notifies realtime components to refresh cloud-engine availability.
        """
        logger.info(self.i18n.t("logging.main_window.api_keys_updated"))

        # Notify realtime recorder to reload engines if needed
        realtime_recorder = self.managers.get("realtime_recorder")
        if realtime_recorder and hasattr(realtime_recorder, "reload_engine"):
            try:
                realtime_recorder.reload_engine()
                logger.info(self.i18n.t("logging.main_window.realtime_recorder_engine_reloaded"))
            except Exception as e:
                logger.error(f"Error reloading realtime recorder engine: {e}")

        # Refresh realtime record UI availability state (e.g. translation controls)
        realtime_widget = self.pages.get("realtime_record") if hasattr(self, "pages") else None
        if realtime_widget and hasattr(realtime_widget, "refresh_engine_availability"):
            try:
                realtime_widget.refresh_engine_availability()
            except Exception as e:
                logger.error(f"Error refreshing realtime record engine availability: {e}")

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
