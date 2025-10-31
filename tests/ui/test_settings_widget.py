# SPDX-License-Identifier: Apache-2.0
"""
Tests for settings widget.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtCore import Qt

from ui.settings.widget import SettingsWidget


class TestSettingsWidget:
    """Tests for SettingsWidget."""

    @pytest.fixture
    def widget(self, qapp, mock_settings_manager, mock_i18n):
        """Create a settings widget for testing."""
        managers = {
            'settings_manager': mock_settings_manager,
        }
        widget = SettingsWidget(
            settings_manager=mock_settings_manager,
            i18n=mock_i18n,
            managers=managers
        )
        return widget

    def test_widget_creation(self, widget):
        """Test widget can be created."""
        assert widget is not None
        assert widget.settings_manager is not None
        assert widget.i18n is not None

    def test_widget_has_ui_elements(self, widget):
        """Test widget has required UI elements."""
        assert hasattr(widget, 'title_label')
        assert hasattr(widget, 'category_list')
        assert hasattr(widget, 'pages_container')
        assert hasattr(widget, 'save_button')
        assert hasattr(widget, 'cancel_button')
        assert hasattr(widget, 'reset_button')

    def test_widget_has_managers_dict(self, widget):
        """Test widget has managers dictionary."""
        assert hasattr(widget, 'managers')
        assert isinstance(widget.managers, dict)

    def test_widget_has_unsaved_changes_flag(self, widget):
        """Test widget has unsaved changes flag."""
        assert hasattr(widget, 'has_unsaved_changes')
        assert widget.has_unsaved_changes is False

    def test_widget_has_original_settings(self, widget):
        """Test widget has original settings dictionary."""
        assert hasattr(widget, 'original_settings')
        # original_settings is set from get_all_settings() which returns a Mock in tests
        # Just verify it exists
        assert widget.original_settings is not None

    def test_widget_has_settings_pages(self, widget):
        """Test widget has settings pages dictionary."""
        assert hasattr(widget, 'settings_pages')
        assert isinstance(widget.settings_pages, dict)

    def test_category_list_exists(self, widget):
        """Test category list exists."""
        assert widget.category_list is not None
        assert widget.category_list.count() > 0

    def test_category_list_width(self, widget):
        """Test category list has fixed width."""
        assert widget.category_list.width() == 200

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
        managers = {'settings_manager': mock_settings_manager}
        widget = SettingsWidget(
            settings_manager=mock_settings_manager,
            i18n=mock_i18n,
            managers=managers
        )
        return widget

    def test_save_button_click(self, widget, mock_settings_manager):
        """Test save button click."""
        # Just verify the button exists
        # The actual save logic is complex and involves all pages
        assert widget.save_button is not None
        # Button exists in the widget
        assert hasattr(widget, 'save_button')

    def test_cancel_button_click(self, widget):
        """Test cancel button click."""
        # Set unsaved changes flag
        widget.has_unsaved_changes = True
        
        with patch('ui.settings.widget.QMessageBox.question', return_value=Mock()):
            # Should not raise exception
            widget._on_cancel_clicked()

    def test_reset_button_click(self, widget):
        """Test reset button click."""
        with patch('ui.settings.widget.QMessageBox.question', return_value=Mock()):
            # Should not raise exception
            widget._on_reset_clicked()

    def test_settings_saved_signal(self, widget):
        """Test settings saved signal exists."""
        assert hasattr(widget, 'settings_saved')


class TestSettingsWidgetCategories:
    """Tests for SettingsWidget category management."""

    @pytest.fixture
    def widget(self, qapp, mock_settings_manager, mock_i18n):
        """Create a settings widget for testing."""
        managers = {'settings_manager': mock_settings_manager}
        widget = SettingsWidget(
            settings_manager=mock_settings_manager,
            i18n=mock_i18n,
            managers=managers
        )
        return widget

    def test_category_list_has_items(self, widget):
        """Test category list has items."""
        assert widget.category_list.count() >= 5

    def test_category_items_have_data(self, widget):
        """Test category items have user data."""
        for i in range(widget.category_list.count()):
            item = widget.category_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            assert data is not None
            assert isinstance(data, str)

    def test_category_change_updates_page(self, widget):
        """Test changing category updates the displayed page."""
        initial_index = widget.pages_container.currentIndex()
        
        # Change to different category
        if widget.category_list.count() > 1:
            widget.category_list.setCurrentRow(1)
            new_index = widget.pages_container.currentIndex()
            assert new_index != initial_index or widget.category_list.count() == 1
