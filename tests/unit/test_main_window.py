# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for PySide6 migration verification.
"""


def test_pyside6_imports():
    """Test that UI modules use PySide6 imports correctly."""
    import ui.main_window
    import ui.sidebar
    import ui.common.error_dialog

    # Verify PySide6 imports are used
    modules_to_check = [ui.main_window, ui.sidebar, ui.common.error_dialog]

    for module in modules_to_check:
        module_dict = module.__dict__

        # Check that no PyQt6 references exist
        for key, value in module_dict.items():
            if hasattr(value, "__module__") and value.__module__:
                assert "PyQt6" not in str(
                    value.__module__
                ), f"Found PyQt6 reference in {module.__name__}.{key}"


def test_pyside6_signal_imports():
    """Test that Signal imports are from PySide6."""
    from PySide6.QtCore import Signal

    # Test that Signal class is available from PySide6
    assert Signal is not None

    # Test that we can create a Signal instance
    test_signal = Signal()
    assert test_signal is not None
