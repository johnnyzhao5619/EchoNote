# SPDX-License-Identifier: Apache-2.0
"""
Tests for settings widget.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from PySide6.QtCore import Qt

from ui.constants import SETTINGS_NAV_WIDTH
from ui.settings.widget import SettingsWidget

pytestmark = pytest.mark.ui


class TestSettingsWidget:
    """Tests for SettingsWidget."""

    @pytest.fixture
    def widget(self, qapp, mock_settings_manager, mock_i18n):
        """Create a settings widget for testing."""
        managers = {
            "settings_manager": mock_settings_manager,
        }
        widget = SettingsWidget(
            settings_manager=mock_settings_manager, i18n=mock_i18n, managers=managers
        )
        return widget

    def test_widget_creation(self, widget):
        """Test widget can be created."""
        assert widget is not None
        assert widget.settings_manager is not None
        assert widget.i18n is not None

    def test_widget_has_ui_elements(self, widget):
        """Test widget has required UI elements."""
        assert hasattr(widget, "title_label")
        assert hasattr(widget, "category_list")
        assert hasattr(widget, "pages_container")
        assert hasattr(widget, "save_button")
        assert hasattr(widget, "cancel_button")
        assert hasattr(widget, "reset_button")

    def test_widget_has_managers_dict(self, widget):
        """Test widget has managers dictionary."""
        assert hasattr(widget, "managers")
        assert isinstance(widget.managers, dict)

    def test_widget_has_unsaved_changes_flag(self, widget):
        """Test widget has unsaved changes flag."""
        assert hasattr(widget, "has_unsaved_changes")
        assert widget.has_unsaved_changes is False

    def test_widget_has_original_settings(self, widget):
        """Test widget has original settings dictionary."""
        assert hasattr(widget, "original_settings")
        # original_settings is set from config_manager.get_all() in tests
        # Just verify it exists
        assert widget.original_settings is not None

    def test_widget_has_settings_pages(self, widget):
        """Test widget has settings pages dictionary."""
        assert hasattr(widget, "settings_pages")
        assert isinstance(widget.settings_pages, dict)

    def test_category_list_exists(self, widget):
        """Test category list exists."""
        assert widget.category_list is not None
        assert widget.category_list.count() > 0

    def test_category_list_width(self, widget):
        """Test category list has fixed width."""
        assert widget.category_list.width() == SETTINGS_NAV_WIDTH

    def test_pages_container_exists(self, widget):
        """Test pages container exists."""
        assert widget.pages_container is not None

    def test_save_button_exists(self, widget):
        """Test save button exists."""
        assert widget.save_button is not None
        assert widget.save_button.isDefault()

    def test_cancel_button_exists(self, widget):
        """Test cancel button exists."""
        assert widget.cancel_button is not None

    def test_reset_button_exists(self, widget):
        """Test reset button exists."""
        assert widget.reset_button is not None

    def test_footer_buttons_use_semantic_roles_and_variants(self, widget):
        """Settings footer buttons should expose stable semantic styling hooks."""
        assert widget.save_button.property("role") == "settings-save-action"
        assert widget.save_button.property("variant") == "primary"
        assert widget.cancel_button.property("role") == "settings-cancel-action"
        assert widget.cancel_button.property("variant") == "secondary"
        assert widget.reset_button.property("role") == "settings-reset-action"
        assert widget.reset_button.property("variant") == "secondary"

    def test_language_change_connected(self, widget, mock_i18n):
        """Test language change signal is connected."""
        mock_i18n.language_changed.connect.assert_called()

    def test_category_selection(self, widget):
        """Test category can be selected."""
        # Select first category
        widget.category_list.setCurrentRow(0)
        assert widget.category_list.currentRow() == 0

    def test_update_translations(self, widget):
        """Test update translations method."""
        # Should not raise exception
        widget._on_language_changed("en_US")


class TestSettingsWidgetButtons:
    """Tests for SettingsWidget button actions."""

    @pytest.fixture
    def widget(self, qapp, mock_settings_manager, mock_i18n):
        """Create a settings widget for testing."""
        managers = {"settings_manager": mock_settings_manager}
        widget = SettingsWidget(
            settings_manager=mock_settings_manager, i18n=mock_i18n, managers=managers
        )
        return widget

    def test_save_button_click(self, widget, mock_settings_manager):
        """Test save button click."""
        # Just verify the button exists
        # The actual save logic is complex and involves all pages
        assert widget.save_button is not None
        # Button exists in the widget
        assert hasattr(widget, "save_button")

    def test_cancel_button_click(self, widget):
        """Test cancel button click."""
        # Set unsaved changes flag
        widget.has_unsaved_changes = True

        with patch("ui.settings.widget.QMessageBox.question", return_value=Mock()):
            # Should not raise exception
            widget._on_cancel_clicked()

    def test_reset_button_click(self, widget):
        """Test reset button click."""
        with patch("ui.settings.widget.QMessageBox.question", return_value=Mock()):
            # Should not raise exception
            widget._on_reset_clicked()

    def test_settings_saved_signal(self, widget):
        """Test settings saved signal exists."""
        assert hasattr(widget, "settings_saved")


class TestSettingsWidgetCategories:
    """Tests for SettingsWidget category management."""

    @pytest.fixture
    def widget(self, qapp, mock_settings_manager, mock_i18n):
        """Create a settings widget for testing."""
        managers = {"settings_manager": mock_settings_manager}
        widget = SettingsWidget(
            settings_manager=mock_settings_manager, i18n=mock_i18n, managers=managers
        )
        return widget

    def test_category_list_has_items(self, widget):
        """Test category list has items."""
        assert widget.category_list.count() >= 5

    def test_category_count_matches_page_count(self, widget):
        """Category list and page stack should stay aligned."""
        assert widget.category_list.count() == len(widget.settings_pages)

    def test_category_items_have_data(self, widget):
        """Test category items have user data."""
        for i in range(widget.category_list.count()):
            item = widget.category_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            assert data is not None
            assert isinstance(data, str)

    def test_model_management_hidden_without_model_manager(self, widget):
        """Model management category should be hidden when manager is unavailable."""
        category_ids = [
            widget.category_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(widget.category_list.count())
        ]
        assert "model_management" not in category_ids

    def test_category_change_updates_page(self, widget):
        """Test changing category updates the displayed page."""
        initial_index = widget.pages_container.currentIndex()

        # Change to different category
        if widget.category_list.count() > 1:
            widget.category_list.setCurrentRow(1)
            new_index = widget.pages_container.currentIndex()
            assert new_index != initial_index or widget.category_list.count() == 1


def test_save_failure_rolls_back_settings_and_runtime_state(qapp, mock_i18n):
    settings_manager = MagicMock()
    settings_manager.config_manager = MagicMock()
    settings_snapshot = {
        "ui": {"theme": "light", "language": "en_US"},
        "timeline": {"past_days": 30},
    }
    settings_manager.config_manager.get_all.return_value = settings_snapshot
    settings_manager.config_manager.save.side_effect = OSError("disk full")

    main_window = Mock()
    mock_i18n.change_language = Mock()

    widget = SettingsWidget(
        settings_manager=settings_manager,
        i18n=mock_i18n,
        managers={"settings_manager": settings_manager, "main_window": main_window},
    )

    page = Mock()
    page.validate_settings.return_value = (True, "")
    widget.settings_pages = {"dummy": page}
    widget.show_error = Mock()

    assert widget.save_settings() is False

    settings_manager.config_manager.replace_all.assert_called_once_with(settings_snapshot)
    main_window.apply_theme.assert_called_once_with("light")
    mock_i18n.change_language.assert_called_once_with("en_US")


def test_save_success_applies_runtime_state_once(qapp, mock_i18n):
    settings_manager = MagicMock()
    settings_manager.config_manager = MagicMock()
    settings_manager.config_manager.save.return_value = None
    settings_manager.config_manager.get_all.return_value = {
        "ui": {"theme": "dark", "language": "zh_CN"}
    }

    def _get_setting(key):
        mapping = {
            "ui.theme": "dark",
            "ui.language": "zh_CN",
        }
        return mapping.get(key)

    settings_manager.get_setting.side_effect = _get_setting

    main_window = Mock()
    mock_i18n.change_language = Mock()

    widget = SettingsWidget(
        settings_manager=settings_manager,
        i18n=mock_i18n,
        managers={"settings_manager": settings_manager, "main_window": main_window},
    )

    page = Mock()
    page.validate_settings.return_value = (True, "")
    widget.settings_pages = {"dummy": page}
    widget.show_info = Mock()

    assert widget.save_settings() is True

    main_window.apply_theme.assert_called_once_with("dark")
    mock_i18n.change_language.assert_called_once_with("zh_CN")


def test_save_success_runs_page_post_save_hook(qapp, mock_i18n):
    settings_manager = MagicMock()
    settings_manager.config_manager = MagicMock()
    settings_manager.config_manager.save.return_value = None
    settings_manager.config_manager.get_all.return_value = {"ui": {}}
    settings_manager.get_setting.return_value = None

    widget = SettingsWidget(
        settings_manager=settings_manager,
        i18n=mock_i18n,
        managers={"settings_manager": settings_manager},
    )

    page = Mock()
    page.validate_settings.return_value = (True, "")
    page.apply_post_save = Mock()
    widget.settings_pages = {"dummy": page}
    widget.show_info = Mock()

    assert widget.save_settings() is True
    page.apply_post_save.assert_called_once()


def test_save_failure_skips_page_post_save_hook(qapp, mock_i18n):
    settings_manager = MagicMock()
    settings_manager.config_manager = MagicMock()
    settings_manager.config_manager.save.side_effect = RuntimeError("write failed")
    settings_manager.config_manager.get_all.return_value = {"ui": {}}

    widget = SettingsWidget(
        settings_manager=settings_manager,
        i18n=mock_i18n,
        managers={"settings_manager": settings_manager},
    )

    page = Mock()
    page.validate_settings.return_value = (True, "")
    page.apply_post_save = Mock()
    widget.settings_pages = {"dummy": page}
    widget.show_error = Mock()

    assert widget.save_settings() is False
    page.apply_post_save.assert_not_called()


def test_save_success_with_post_save_warning_shows_warning_only(qapp, mock_i18n):
    settings_manager = MagicMock()
    settings_manager.config_manager = MagicMock()
    settings_manager.config_manager.save.return_value = None
    settings_manager.config_manager.get_all.return_value = {"ui": {}}
    settings_manager.get_setting.return_value = None

    widget = SettingsWidget(
        settings_manager=settings_manager,
        i18n=mock_i18n,
        managers={"settings_manager": settings_manager},
    )

    page = Mock()
    page.validate_settings.return_value = (True, "")
    page.apply_post_save = Mock(
        return_value=[{"level": "warning", "source": "dummy", "message": "runtime update failed"}]
    )
    widget.settings_pages = {"dummy": page}
    widget.show_warning = Mock()
    widget.show_info = Mock()

    assert widget.save_settings() is True
    widget.show_warning.assert_called_once()
    widget.show_info.assert_not_called()
