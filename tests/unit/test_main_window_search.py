# SPDX-License-Identifier: Apache-2.0
"""Tests for main window shell search behavior."""

from unittest.mock import Mock

from ui.main_window import MainWindow


class _CategoryItem:
    def __init__(self, category_id: str, label: str):
        self._category_id = category_id
        self._label = label

    def data(self, _role):
        return self._category_id

    def text(self):
        return self._label


class _CategoryList:
    def __init__(self, items):
        self._items = items

    def count(self):
        return len(self._items)

    def item(self, index: int):
        return self._items[index]


def _build_i18n():
    i18n = Mock()

    def _t(key: str, **kwargs):
        mapping = {
            "sidebar.batch_transcribe": "Batch Transcribe",
            "sidebar.realtime_record": "Real-time Record",
            "sidebar.calendar_hub": "Calendar Hub",
            "sidebar.timeline": "Timeline",
            "sidebar.settings": "Settings",
            "settings.category.appearance": "Appearance",
            "app_shell.search_result": "Opened {page}",
            "app_shell.search_no_match": "No page matched \"{query}\"",
        }
        template = mapping.get(key, key)
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    i18n.t = Mock(side_effect=_t)
    return i18n


def _bind_search_methods(fake_window):
    fake_window._resolve_settings_category = (
        lambda query: MainWindow._resolve_settings_category(fake_window, query)
    )
    fake_window._resolve_search_target = (
        lambda query: MainWindow._resolve_search_target(fake_window, query)
    )
    fake_window._get_page_title = lambda page: MainWindow._get_page_title(fake_window, page)


def test_resolve_settings_category_by_id():
    settings_widget = Mock()
    settings_widget.category_list = _CategoryList([_CategoryItem("appearance", "Appearance")])

    fake_window = Mock()
    fake_window.pages = {"settings": settings_widget}

    assert MainWindow._resolve_settings_category(fake_window, "appearance") == "appearance"


def test_resolve_settings_category_by_label_contains():
    settings_widget = Mock()
    settings_widget.category_list = _CategoryList(
        [
            _CategoryItem("realtime", "Real-time Recording"),
            _CategoryItem("appearance", "Appearance"),
        ]
    )

    fake_window = Mock()
    fake_window.pages = {"settings": settings_widget}

    assert MainWindow._resolve_settings_category(fake_window, "record") == "realtime"


def test_global_search_routes_to_settings_subpage():
    settings_widget = Mock()
    settings_widget.category_list = _CategoryList([_CategoryItem("appearance", "Appearance")])
    settings_widget.show_page = Mock(return_value=True)

    fake_window = Mock()
    fake_window.i18n = _build_i18n()
    fake_window.pages = {"settings": settings_widget}
    fake_window.global_search_input = Mock()
    fake_window.global_search_input.text.return_value = "appearance"
    fake_window.switch_page = Mock()
    fake_window._set_shell_message = Mock()
    _bind_search_methods(fake_window)

    MainWindow._on_global_search_submitted(fake_window)

    fake_window.switch_page.assert_called_once_with("settings")
    settings_widget.show_page.assert_called_once_with("appearance")
    fake_window._set_shell_message.assert_called_once_with("Opened Settings / Appearance")
