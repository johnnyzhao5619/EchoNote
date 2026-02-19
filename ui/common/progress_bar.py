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
Progress bar widget for EchoNote application.

Provides a customizable progress bar with percentage display.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from ui.base_widgets import BaseWidget, create_hbox
from ui.constants import ZERO_MARGINS

logger = logging.getLogger("echonote.ui.progress_bar")


class ProgressBar(BaseWidget):
    """
    Custom progress bar widget with label and percentage display.

    Emits progress_changed signal when progress is updated.
    """

    # Signal emitted when progress changes
    progress_changed = Signal(float)

    def __init__(
        self,
        label_text: str = "",
        show_percentage: bool = True,
        show_estimated_time: bool = False,
        parent: Optional[QWidget] = None,
        i18n=None,
    ):
        """
        Initialize progress bar.

        Args:
            label_text: Text to display above progress bar
            show_percentage: Whether to show percentage text
            show_estimated_time: Whether to show estimated time remaining
            parent: Parent widget
            i18n: Internationalization manager for text translation
        """
        super().__init__(i18n, parent)

        self.show_percentage = show_percentage
        self.show_estimated_time = show_estimated_time
        self.i18n = i18n

        # Time tracking for estimation
        self.start_time = None
        self.last_progress = 0.0

        # Setup UI
        self.setup_ui(label_text)

    def setup_ui(self, label_text: str):
        """
        Set up the progress bar UI.

        Args:
            label_text: Text to display above progress bar
        """
        # Create layout
        layout = QVBoxLayout(self)

        # Create top row with label and percentage
        top_layout = create_hbox(margins=ZERO_MARGINS)

        # Create label
        self.label = QLabel(label_text)
        top_layout.addWidget(self.label)

        # Add stretch
        top_layout.addStretch()

        # Create percentage label
        if self.show_percentage:
            self.percentage_label = QLabel("0%")
            self.percentage_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            top_layout.addWidget(self.percentage_label)

        layout.addLayout(top_layout)

        # Create progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)  # We show percentage separately
        layout.addWidget(self.progress_bar)

        # Create estimated time label
        if self.show_estimated_time:
            self.time_label = QLabel("")
            self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(self.time_label)

    def set_progress(self, value: float):
        """
        Set progress value.

        Args:
            value: Progress value (0-100)
        """
        import time

        # Clamp value to 0-100
        value = max(0.0, min(100.0, value))

        # Initialize start time on first progress update
        if self.start_time is None and value > 0:
            self.start_time = time.time()

        # Update progress bar
        self.progress_bar.setValue(int(value))

        # Update percentage label
        if self.show_percentage:
            self.percentage_label.setText(f"{int(value)}%")

        # Update estimated time
        if self.show_estimated_time and self.start_time is not None:
            self._update_estimated_time(value)

        self.last_progress = value

        # Emit signal
        self.progress_changed.emit(value)

    def _update_estimated_time(self, current_progress: float):
        """
        Update estimated time remaining.

        Args:
            current_progress: Current progress (0-100)
        """
        import time

        if current_progress <= 0 or current_progress >= 100:
            if hasattr(self, "time_label"):
                self.time_label.setText("")
            return

        # Calculate elapsed time
        elapsed = time.time() - self.start_time

        # Calculate estimated total time
        estimated_total = elapsed / (current_progress / 100.0)

        # Calculate remaining time
        remaining = estimated_total - elapsed

        # Format time string
        time_str = self._format_time(remaining)

        if hasattr(self, "time_label"):
            if self.i18n:
                self.time_label.setText(
                    self.i18n.t("common.progress.remaining_time", time=time_str)
                )
            else:
                self.time_label.setText(f"Remaining time: {time_str}")

    def _format_time(self, seconds: float) -> str:
        """
        Format time in seconds to human-readable string.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        if seconds < 0:
            if self.i18n:
                return self.i18n.t("common.progress.calculating")
            else:
                return "Calculating..."

        if seconds < 60:
            if self.i18n:
                return self.i18n.t("common.progress.seconds", count=int(seconds))
            else:
                return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            if self.i18n:
                return self.i18n.t("common.progress.minutes_seconds", minutes=minutes, seconds=secs)
            else:
                return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            if self.i18n:
                return self.i18n.t("common.progress.hours_minutes", hours=hours, minutes=minutes)
            else:
                return f"{hours}h {minutes}m"

    def get_progress(self) -> float:
        """
        Get current progress value.

        Returns:
            Current progress (0-100)
        """
        return float(self.progress_bar.value())

    def set_label_text(self, text: str):
        """
        Set label text.

        Args:
            text: New label text
        """
        self.label.setText(text)

    def get_label_text(self) -> str:
        """
        Get label text.

        Returns:
            Current label text
        """
        return self.label.text()

    def reset(self):
        """Reset progress to 0."""
        self.start_time = None
        self.last_progress = 0.0
        self.set_progress(0.0)
        if self.show_estimated_time and hasattr(self, "time_label"):
            self.time_label.setText("")

    def set_indeterminate(self, indeterminate: bool):
        """
        Set progress bar to indeterminate mode.

        Args:
            indeterminate: True for indeterminate mode, False for normal
        """
        if indeterminate:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)
            if self.show_percentage:
                self.percentage_label.setText("")
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            if self.show_percentage:
                self.percentage_label.setText(
                    self.i18n.t("ui_strings.common.progress_bar.zero_percent")
                )
