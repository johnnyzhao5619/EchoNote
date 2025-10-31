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
Signal/slot helper functions for common UI patterns.

This module provides reusable functions for common signal/slot connection patterns
to reduce code duplication and ensure consistent behavior across the UI layer.
"""

import logging
from typing import Any, Callable, Optional

from ui.qt_imports import QPushButton, QTimer

logger = logging.getLogger(__name__)


def connect_button_with_emit(button: QPushButton, signal: Any, value: Any) -> None:
    """
    Connect a button's clicked signal to emit a signal with a specific value.

    This is a common pattern where buttons emit signals with task IDs or other values.

    Args:
        button: The button to connect
        signal: The signal to emit when button is clicked
        value: The value to emit with the signal
    """
    button.clicked.connect(lambda: signal.emit(value))


def connect_button_with_callback(button: QPushButton, callback: Callable[[], None]) -> None:
    """
    Connect a button's clicked signal to a callback function.

    Args:
        button: The button to connect
        callback: The callback function to call when button is clicked
    """
    button.clicked.connect(callback)


def connect_dialog_buttons(
    ok_button: QPushButton,
    cancel_button: Optional[QPushButton] = None,
    ok_callback: Optional[Callable[[], None]] = None,
    cancel_callback: Optional[Callable[[], None]] = None,
) -> None:
    """
    Connect standard dialog buttons (OK/Cancel) to their callbacks.

    Args:
        ok_button: The OK/Save button
        cancel_button: The Cancel button (optional)
        ok_callback: Callback for OK button (defaults to accept)
        cancel_callback: Callback for Cancel button (defaults to reject)
    """
    if ok_callback:
        ok_button.clicked.connect(ok_callback)
    else:
        # Assume this is a dialog and call accept()
        ok_button.clicked.connect(lambda: getattr(ok_button.parent(), "accept", lambda: None)())

    if cancel_button:
        if cancel_callback:
            cancel_button.clicked.connect(cancel_callback)
        else:
            # Assume this is a dialog and call reject()
            cancel_button.clicked.connect(
                lambda: getattr(cancel_button.parent(), "reject", lambda: None)()
            )


def connect_navigation_buttons(
    prev_button: QPushButton,
    next_button: QPushButton,
    today_button: Optional[QPushButton] = None,
    prev_callback: Optional[Callable[[], None]] = None,
    next_callback: Optional[Callable[[], None]] = None,
    today_callback: Optional[Callable[[], None]] = None,
) -> None:
    """
    Connect navigation buttons (prev/next/today) commonly used in calendar views.

    Args:
        prev_button: Previous navigation button
        next_button: Next navigation button
        today_button: Today/current button (optional)
        prev_callback: Callback for previous button
        next_callback: Callback for next button
        today_callback: Callback for today button
    """
    if prev_callback:
        prev_button.clicked.connect(prev_callback)
    if next_callback:
        next_button.clicked.connect(next_callback)
    if today_button and today_callback:
        today_button.clicked.connect(today_callback)


def connect_search_buttons(
    search_button: QPushButton,
    prev_button: Optional[QPushButton] = None,
    next_button: Optional[QPushButton] = None,
    clear_button: Optional[QPushButton] = None,
    search_callback: Optional[Callable[[], None]] = None,
    prev_callback: Optional[Callable[[], None]] = None,
    next_callback: Optional[Callable[[], None]] = None,
    clear_callback: Optional[Callable[[], None]] = None,
) -> None:
    """
    Connect search-related buttons commonly used in search widgets.

    Args:
        search_button: Main search button
        prev_button: Previous match button (optional)
        next_button: Next match button (optional)
        clear_button: Clear search button (optional)
        search_callback: Callback for search button
        prev_callback: Callback for previous button
        next_callback: Callback for next button
        clear_callback: Callback for clear button
    """
    if search_callback:
        search_button.clicked.connect(search_callback)
    if prev_button and prev_callback:
        prev_button.clicked.connect(prev_callback)
    if next_button and next_callback:
        next_button.clicked.connect(next_callback)
    if clear_button and clear_callback:
        clear_button.clicked.connect(clear_callback)


def connect_with_delay(signal: Any, callback: Callable[[], None], delay_ms: int = None) -> None:
    """
    Connect a signal to a callback with a delay using QTimer.singleShot.

    This is commonly used for temporary UI feedback (e.g., "Copied!" message).

    Args:
        signal: The signal to connect
        callback: The callback to execute after delay
        delay_ms: Delay in milliseconds (default: 2000ms)
    """
    from ui.constants import NOTIFICATION_RESET_DELAY_MS

    if delay_ms is None:
        delay_ms = NOTIFICATION_RESET_DELAY_MS

    def delayed_callback():
        QTimer.singleShot(delay_ms, callback)

    signal.connect(delayed_callback)


def connect_view_buttons(
    month_button: QPushButton,
    week_button: QPushButton,
    day_button: QPushButton,
    view_changed_callback: Callable[[str], None],
) -> None:
    """
    Connect calendar view buttons to a view changed callback.

    Args:
        month_button: Month view button
        week_button: Week view button
        day_button: Day view button
        view_changed_callback: Callback that receives view name ("month", "week", "day")
    """
    month_button.clicked.connect(lambda: view_changed_callback("month"))
    week_button.clicked.connect(lambda: view_changed_callback("week"))
    day_button.clicked.connect(lambda: view_changed_callback("day"))


def connect_task_action_buttons(
    start_button: QPushButton,
    pause_button: QPushButton,
    cancel_button: QPushButton,
    delete_button: QPushButton,
    view_button: QPushButton,
    export_button: QPushButton,
    retry_button: QPushButton,
    task_id: str,
    start_signal: Any,
    pause_signal: Any,
    cancel_signal: Any,
    delete_signal: Any,
    view_signal: Any,
    export_signal: Any,
    retry_signal: Any,
) -> None:
    """
    Connect task action buttons to their respective signals with task ID.

    This is commonly used in task item widgets for batch transcription.

    Args:
        start_button: Start task button
        pause_button: Pause task button
        cancel_button: Cancel task button
        delete_button: Delete task button
        view_button: View results button
        export_button: Export results button
        retry_button: Retry task button
        task_id: The task ID to emit with signals
        start_signal: Signal to emit when start is clicked
        pause_signal: Signal to emit when pause is clicked
        cancel_signal: Signal to emit when cancel is clicked
        delete_signal: Signal to emit when delete is clicked
        view_signal: Signal to emit when view is clicked
        export_signal: Signal to emit when export is clicked
        retry_signal: Signal to emit when retry is clicked
    """
    connect_button_with_emit(start_button, start_signal, task_id)
    connect_button_with_emit(pause_button, pause_signal, task_id)
    connect_button_with_emit(cancel_button, cancel_signal, task_id)
    connect_button_with_emit(delete_button, delete_signal, task_id)
    connect_button_with_emit(view_button, view_signal, task_id)
    connect_button_with_emit(export_button, export_signal, task_id)
    connect_button_with_emit(retry_button, retry_signal, task_id)


# Enhanced signal connection helpers


def connect_text_changed(widget, handler: Callable[[str], None]) -> None:
    """
    Connect a text widget's textChanged signal to a handler.

    Args:
        widget: Widget with textChanged signal
        handler: Handler function that accepts text string
    """
    if hasattr(widget, "textChanged"):
        widget.textChanged.connect(handler)


def connect_value_changed(widget, handler: Callable[[Any], None]) -> None:
    """
    Connect a widget's valueChanged signal to a handler.

    Args:
        widget: Widget with valueChanged signal
        handler: Handler function that accepts the new value
    """
    if hasattr(widget, "valueChanged"):
        widget.valueChanged.connect(handler)


def connect_selection_changed(widget, handler: Callable[[], None]) -> None:
    """
    Connect a widget's selection changed signal to a handler.

    Args:
        widget: Widget with selection changed signal
        handler: Handler function to call
    """
    # Try different selection change signal names
    for signal_name in ["selectionChanged", "currentChanged", "itemSelectionChanged"]:
        if hasattr(widget, signal_name):
            signal = getattr(widget, signal_name)
            signal.connect(handler)
            break


def connect_with_error_handling(
    signal, handler: Callable, error_handler: Optional[Callable[[Exception], None]] = None
) -> None:
    """
    Connect a signal to a handler with error handling.

    Args:
        signal: Signal to connect
        handler: Handler function
        error_handler: Optional error handler function
    """

    def wrapped_handler(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in signal handler: {e}")
            if error_handler:
                error_handler(e)
            else:
                # Re-raise if no error handler provided
                raise

    signal.connect(wrapped_handler)


def safe_disconnect(signal, handler: Optional[Callable] = None) -> bool:
    """
    Safely disconnect a signal from a handler.

    Args:
        signal: Signal to disconnect
        handler: Specific handler to disconnect, or None to disconnect all

    Returns:
        True if disconnection was successful, False otherwise
    """
    try:
        if handler:
            signal.disconnect(handler)
        else:
            signal.disconnect()
        return True
    except (TypeError, RuntimeError) as e:
        logger.debug(f"Signal disconnection failed: {e}")
        return False


def setup_form_validation(form_widgets: list, validation_handler: Callable[[], None]) -> None:
    """
    Setup validation for form widgets.

    Args:
        form_widgets: List of form widgets to monitor
        validation_handler: Handler to call when any widget changes
    """
    for widget in form_widgets:
        # Connect appropriate change signals based on widget type
        widget_type = type(widget).__name__

        if "LineEdit" in widget_type or "TextEdit" in widget_type:
            connect_text_changed(widget, lambda _: validation_handler())
        elif "ComboBox" in widget_type:
            connect_selection_changed(widget, validation_handler)
        elif "CheckBox" in widget_type or "RadioButton" in widget_type:
            if hasattr(widget, "toggled"):
                widget.toggled.connect(validation_handler)
        elif "SpinBox" in widget_type or "Slider" in widget_type:
            connect_value_changed(widget, lambda _: validation_handler())


def setup_auto_save(widgets: list, save_handler: Callable[[], None]) -> None:
    """
    Setup automatic saving when widgets change.

    Args:
        widgets: List of widgets to monitor
        save_handler: Handler to call when any widget changes
    """
    setup_form_validation(widgets, save_handler)
