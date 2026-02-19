# SPDX-License-Identifier: Apache-2.0
"""Tests for transcription settings page side-effect behavior."""

from unittest.mock import Mock

from ui.settings.transcription_page import TranscriptionSettingsPage


class _FakeSettingsManager:
    def __init__(self):
        self.api_keys_updated = Mock()
        self.api_keys_updated.emit = Mock()

    def get_setting(self, _key):
        return None

    def set_setting(self, _key, _value):
        return True


class _FakeSecretsManager:
    def __init__(self):
        self._api_keys = {
            "openai": "openai-old",
            "google": "google-old",
            "azure": "azure-old",
        }
        self._secrets = {"azure_region": "eastus"}

        self.set_api_key = Mock(side_effect=self._set_api_key)
        self.delete_api_key = Mock(side_effect=self._delete_api_key)
        self.set_secret = Mock(side_effect=self._set_secret)
        self.delete_secret = Mock(side_effect=self._delete_secret)

    def get_api_key(self, provider):
        return self._api_keys.get(provider)

    def _set_api_key(self, provider, value):
        self._api_keys[provider] = value

    def _delete_api_key(self, provider):
        self._api_keys.pop(provider, None)

    def get_secret(self, key):
        return self._secrets.get(key)

    def _set_secret(self, key, value):
        self._secrets[key] = value

    def _delete_secret(self, key):
        self._secrets.pop(key, None)


def _create_page(mock_i18n, transcription_manager=None):
    settings_manager = _FakeSettingsManager()
    secrets_manager = _FakeSecretsManager()
    managers = {"secrets_manager": secrets_manager}
    if transcription_manager is not None:
        managers["transcription_manager"] = transcription_manager
    page = TranscriptionSettingsPage(
        settings_manager=settings_manager,
        i18n=mock_i18n,
        managers=managers,
    )
    return page, settings_manager, secrets_manager


def _set_all_key_fields_to_current_values(page):
    page.openai_key_edit.setText("openai-old")
    page.google_key_edit.setText("google-old")
    page.azure_key_edit.setText("azure-old")
    page.azure_region_edit.setText("eastus")


def test_save_api_keys_skips_signal_when_no_changes(qapp, mock_i18n):
    page, settings_manager, secrets_manager = _create_page(mock_i18n)
    _set_all_key_fields_to_current_values(page)

    changed = page._save_api_keys()

    assert changed is False
    settings_manager.api_keys_updated.emit.assert_not_called()
    secrets_manager.set_api_key.assert_not_called()
    secrets_manager.delete_api_key.assert_not_called()
    secrets_manager.set_secret.assert_not_called()
    secrets_manager.delete_secret.assert_not_called()


def test_save_api_keys_emits_signal_only_when_values_changed(qapp, mock_i18n):
    page, settings_manager, secrets_manager = _create_page(mock_i18n)
    _set_all_key_fields_to_current_values(page)

    page.google_key_edit.setText("google-new")
    page.azure_region_edit.setText("")

    changed = page._save_api_keys()

    assert changed is True
    settings_manager.api_keys_updated.emit.assert_called_once()
    secrets_manager.set_api_key.assert_called_once_with("google", "google-new")
    secrets_manager.delete_secret.assert_called_once_with("azure_region")
    secrets_manager.delete_api_key.assert_not_called()
    secrets_manager.set_secret.assert_not_called()


def test_apply_post_save_collects_reload_warning(qapp, mock_i18n):
    transcription_manager = Mock()
    transcription_manager.update_max_concurrent = Mock()
    transcription_manager.reload_engine = Mock(return_value=False)
    page, _, _ = _create_page(mock_i18n, transcription_manager=transcription_manager)
    _set_all_key_fields_to_current_values(page)

    warnings = page.apply_post_save()

    assert any(
        "settings.transcription.engine_reload_warning_message" in warning.get("message", "")
        for warning in warnings
    )


def test_apply_post_save_collects_api_key_save_error_warning(qapp, mock_i18n):
    page, _, secrets_manager = _create_page(mock_i18n)
    _set_all_key_fields_to_current_values(page)
    page.openai_key_edit.setText("openai-new")
    secrets_manager.set_api_key.side_effect = RuntimeError("boom")

    warnings = page.apply_post_save()

    assert any(
        "settings.transcription.api_keys_save_failed_message" in warning.get("message", "")
        for warning in warnings
    )


def test_transcription_settings_uses_semantic_roles_for_groups_and_inline_actions(qapp, mock_i18n):
    page, _, _ = _create_page(mock_i18n)

    assert page.whisper_group.property("role") == "settings-config-group"
    assert page.cloud_group.property("role") == "settings-config-group"
    assert page.openai_group.property("role") == "settings-config-group-nested"
    assert page.google_group.property("role") == "settings-config-group-nested"
    assert page.azure_group.property("role") == "settings-config-group-nested"

    assert page.ffmpeg_install_btn.property("role") == "settings-inline-action"
    assert page.browse_button.property("role") == "settings-inline-action"
    assert page.refresh_usage_button.property("role") == "settings-inline-action"
    assert page.openai_show_button.property("role") == "settings-inline-action"
    assert page.openai_test_button.property("role") == "settings-inline-action"
    assert page.google_show_button.property("role") == "settings-inline-action"
    assert page.google_test_button.property("role") == "settings-inline-action"
    assert page.azure_show_button.property("role") == "settings-inline-action"
    assert page.azure_test_button.property("role") == "settings-inline-action"


def test_update_translations_refreshes_device_info_label(qapp, mock_i18n, monkeypatch):
    language = {"code": "zh"}

    def _t(key, **kwargs):
        if key == "settings.transcription.will_automatically_use":
            template = (
                "将自动使用：{device_name}（{compute_type}）"
                if language["code"] == "zh"
                else "Will automatically use: {device_name} ({compute_type})"
            )
            return template.format(**kwargs)
        if key == "ui_strings.gpu_detector.device_names.cpu":
            return "CPU"
        if key == "ui_strings.gpu_detector.device_names.auto":
            return "Auto (Recommended)"
        if key == "ui_strings.gpu_detector.device_names.cuda":
            return "CUDA (NVIDIA GPU)"
        return key

    mock_i18n.t.side_effect = _t

    from utils.gpu_detector import GPUDetector

    monkeypatch.setattr(
        GPUDetector,
        "get_available_device_options",
        staticmethod(lambda _i18n=None: [("auto", "Auto (Recommended)"), ("cpu", "CPU")]),
    )
    monkeypatch.setattr(
        GPUDetector,
        "get_recommended_device",
        staticmethod(lambda: ("cpu", "int8")),
    )
    monkeypatch.setattr(
        GPUDetector,
        "get_device_display_name",
        staticmethod(lambda device, _i18n=None: "CPU" if device == "cpu" else device),
    )

    page, _, _ = _create_page(mock_i18n)
    page._update_device_info()
    assert page.device_info_label.text() == "将自动使用：CPU（int8）"

    language["code"] = "en"
    page.update_translations()
    assert page.device_info_label.text() == "Will automatically use: CPU (int8)"
