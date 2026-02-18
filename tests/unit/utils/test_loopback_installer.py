# SPDX-License-Identifier: Apache-2.0
"""Unit tests for loopback one-click installer."""

from pathlib import Path
from unittest.mock import Mock, patch

from utils.loopback_installer import LoopbackInstallResult, LoopbackInstaller


def test_supports_one_click_install_on_macos_with_required_tools():
    installer = LoopbackInstaller()
    with (
        patch("platform.system", return_value="Darwin"),
        patch("shutil.which", return_value="/usr/bin/fake"),
    ):
        assert installer.supports_one_click_install() is True


def test_supports_one_click_install_on_windows_with_powershell():
    installer = LoopbackInstaller()

    def _which(cmd):
        if cmd == "powershell":
            return "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        return None

    with (
        patch("platform.system", return_value="Windows"),
        patch("shutil.which", side_effect=_which),
    ):
        assert installer.supports_one_click_install() is True


def test_supports_one_click_install_on_linux_with_pactl():
    installer = LoopbackInstaller()

    def _which(cmd):
        if cmd == "pactl":
            return "/usr/bin/pactl"
        return None

    with (
        patch("platform.system", return_value="Linux"),
        patch("shutil.which", side_effect=_which),
    ):
        assert installer.supports_one_click_install() is True


def test_install_loopback_input_rejects_unsupported_platform():
    installer = LoopbackInstaller()
    with patch("platform.system", return_value="FreeBSD"):
        result = installer.install_loopback_input()

    assert result.success is False
    assert "macOS" in result.message and "Windows" in result.message


def test_install_loopback_input_requires_homebrew():
    installer = LoopbackInstaller()

    def _which(cmd):
        if cmd == "brew":
            return None
        return "/usr/bin/fake"

    with (
        patch("platform.system", return_value="Darwin"),
        patch("shutil.which", side_effect=_which),
    ):
        result = installer.install_loopback_input()

    assert result.success is False
    assert "Homebrew" in result.message


def test_install_loopback_input_requires_powershell_on_windows():
    installer = LoopbackInstaller()

    def _which(_cmd):
        return None

    with (
        patch("platform.system", return_value="Windows"),
        patch("shutil.which", side_effect=_which),
    ):
        result = installer.install_loopback_input()

    assert result.success is False
    assert "PowerShell" in result.message


def test_install_loopback_input_success_sets_reboot_flag(tmp_path):
    installer = LoopbackInstaller()
    cached_pkg = tmp_path / "BlackHole2ch.pkg"
    cached_pkg.write_text("pkg")

    with (
        patch("platform.system", return_value="Darwin"),
        patch("shutil.which", return_value="/usr/bin/fake"),
        patch.object(installer, "_resolve_cached_pkg_path", return_value=(cached_pkg, "")),
        patch.object(
            installer,
            "_run_macos_pkg_installer",
            return_value=LoopbackInstallResult(success=True, message=""),
        ),
    ):
        result = installer.install_loopback_input()

    assert result.success is True
    assert result.requires_reboot is True


def test_install_loopback_input_windows_success_sets_reboot_flag(tmp_path):
    installer = LoopbackInstaller()
    setup_exe = tmp_path / "VBCABLE_Setup_x64.exe"
    setup_exe.write_text("exe")

    with (
        patch("platform.system", return_value="Windows"),
        patch.object(installer, "_powershell_executable", return_value="powershell"),
        patch.object(installer, "_resolve_windows_vbcable_url", return_value="https://example.com/a.zip"),
        patch("urllib.request.urlretrieve", return_value=(str(tmp_path / "a.zip"), None)),
        patch("zipfile.ZipFile") as zip_cls,
        patch.object(installer, "_find_windows_setup_executable", return_value=setup_exe),
        patch.object(
            installer,
            "_run_windows_elevated_setup",
            return_value=LoopbackInstallResult(success=True, message=""),
        ),
    ):
        zip_cls.return_value.__enter__.return_value.extractall.return_value = None
        result = installer.install_loopback_input()

    assert result.success is True
    assert result.requires_reboot is True


def test_install_loopback_input_propagates_cancelled_result(tmp_path):
    installer = LoopbackInstaller()
    cached_pkg = tmp_path / "BlackHole2ch.pkg"
    cached_pkg.write_text("pkg")
    cancelled = LoopbackInstallResult(success=False, cancelled=True, message="cancelled")

    with (
        patch("platform.system", return_value="Darwin"),
        patch("shutil.which", return_value="/usr/bin/fake"),
        patch.object(installer, "_resolve_cached_pkg_path", return_value=(cached_pkg, "")),
        patch.object(installer, "_run_macos_pkg_installer", return_value=cancelled),
    ):
        result = installer.install_loopback_input()

    assert result.success is False
    assert result.cancelled is True


def test_install_loopback_input_linux_configures_virtual_sink():
    installer = LoopbackInstaller()
    with (
        patch("platform.system", return_value="Linux"),
        patch.object(installer, "_ensure_linux_pactl_available", return_value=LoopbackInstallResult(success=True, message="")),
        patch.object(installer, "_linux_sink_exists", return_value=False),
        patch("subprocess.run", return_value=Mock(returncode=0, stdout="52\n", stderr="")),
    ):
        result = installer.install_loopback_input()

    assert result.success is True
    assert "configured" in result.message.lower()


def test_install_loopback_input_linux_skips_when_already_configured():
    installer = LoopbackInstaller()
    with (
        patch("platform.system", return_value="Linux"),
        patch.object(installer, "_ensure_linux_pactl_available", return_value=LoopbackInstallResult(success=True, message="")),
        patch.object(installer, "_linux_sink_exists", return_value=True),
    ):
        result = installer.install_loopback_input()

    assert result.success is True
    assert "already" in result.message.lower()


def test_resolve_cached_pkg_path_runs_fetch_when_cache_missing():
    installer = LoopbackInstaller()
    final_pkg = Path("/tmp/final.pkg")

    with (
        patch.object(installer, "_brew_cache_path", side_effect=[None, final_pkg]),
        patch.object(Path, "exists", return_value=True),
        patch("subprocess.run", return_value=Mock(returncode=0, stderr="", stdout="ok")),
    ):
        path, error = installer._resolve_cached_pkg_path()

    assert path == final_pkg
    assert error == ""


def test_install_confirm_message_includes_component_name():
    installer = LoopbackInstaller()
    with patch("platform.system", return_value="Windows"):
        text = installer.get_install_confirm_message()
    assert "VB-CABLE" in text
