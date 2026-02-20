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
"""One-click loopback installer using system-native authorization prompts."""

from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("echonote.utils.loopback_installer")


@dataclass
class LoopbackInstallResult:
    """Loopback installation execution result."""

    success: bool
    message: str
    cancelled: bool = False
    requires_reboot: bool = False


class LoopbackInstaller:
    """Install loopback input route with native privilege escalation prompts."""

    CASK_NAME = "blackhole-2ch"
    WINDOWS_VBCABLE_PAGE_URL = "https://vb-audio.com/Cable/"
    WINDOWS_VBCABLE_FALLBACK_URL = (
        "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"
    )
    WINDOWS_VBCABLE_URL_PATTERN = re.compile(
        r"https?://download\.vb-audio\.com/[^\"'\s>]*VBCABLE_Driver_Pack\d+\.zip",
        re.IGNORECASE,
    )
    LINUX_LOOPBACK_SINK_NAME = "echonote_loopback"

    def __init__(self, i18n=None):
        self.i18n = i18n

    def _t(self, key: str, default: str, **kwargs) -> str:
        if self.i18n is not None:
            try:
                translated = self.i18n.t(key, **kwargs)
                if translated and translated != key:
                    return translated
            except Exception:  # pragma: no cover
                pass
        try:
            return default.format(**kwargs)
        except Exception:
            return default

    def get_component_name(self) -> str:
        """Return platform-specific loopback component label."""
        system = platform.system()
        if system == "Darwin":
            return "BlackHole"
        if system == "Windows":
            return "VB-CABLE"
        if system == "Linux":
            return "PipeWire/PulseAudio virtual sink"
        return "loopback component"

    def get_install_confirm_message(self) -> str:
        """Return platform-aware confirmation message for one-click installation."""
        return self._t(
            "loopback.install_confirm_message",
            "This action will install or configure {component} for system audio "
            "and online meeting capture. Continue?",
            component=self.get_component_name(),
        )

    def get_authorization_note(self) -> str:
        """Return authorization note shown in installer dialog."""
        system = platform.system()
        if system in {"Darwin", "Windows"}:
            return self._t(
                "loopback.install_requires_admin",
                "One-click install uses the system authorization dialog. EchoNote "
                "does not collect or store your administrator password.",
            )
        if system == "Linux":
            return self._t(
                "loopback.install_linux_note",
                "Linux one-click setup creates a virtual sink with pactl. If required "
                "tools are missing, system authorization may be requested to install "
                "dependencies.",
            )
        return self._t(
            "loopback.install_requires_admin",
            "One-click install uses the system authorization dialog. EchoNote "
            "does not collect or store your administrator password.",
        )

    def supports_one_click_install(self) -> bool:
        """Return whether current platform supports in-app one-click install."""
        system = platform.system()
        if system == "Darwin":
            return shutil.which("brew") is not None and shutil.which("osascript") is not None
        if system == "Windows":
            return self._powershell_executable() is not None
        if system == "Linux":
            return shutil.which("pactl") is not None or (
                shutil.which("pkexec") is not None
                and self._detect_linux_package_manager() is not None
            )
        return False

    def install_loopback_input(self) -> LoopbackInstallResult:
        """Install loopback input route."""
        system = platform.system()
        if system == "Darwin":
            return self._install_macos_loopback_input()
        if system == "Windows":
            return self._install_windows_loopback_input()
        if system == "Linux":
            return self._install_linux_loopback_input()

        return LoopbackInstallResult(
            success=False,
            message=self._t(
                "loopback.install_unsupported_platform",
                "One-click loopback installation is available on macOS, Windows, and Linux.",
            ),
        )

    def _install_macos_loopback_input(self) -> LoopbackInstallResult:
        """Install loopback input on macOS with native admin authorization prompt."""
        if shutil.which("brew") is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_missing_brew",
                    "Homebrew is required for one-click installation. Install Homebrew first, then retry.",
                ),
            )

        if shutil.which("osascript") is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_missing_osascript",
                    "System authorization service (osascript) is unavailable on this system.",
                ),
            )

        package_path, error_message = self._resolve_cached_pkg_path()
        if package_path is None:
            return LoopbackInstallResult(success=False, message=error_message)

        install_result = self._run_macos_pkg_installer(package_path)
        if install_result.success:
            install_result.requires_reboot = True
            install_result.message = self._t(
                "loopback.install_success",
                "Loopback component installed successfully. Please reboot macOS "
                "before recording system audio.",
            )
        return install_result

    def _install_windows_loopback_input(self) -> LoopbackInstallResult:
        """Install VB-CABLE on Windows via UAC-authorized setup process."""
        powershell = self._powershell_executable()
        if powershell is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_missing_powershell",
                    "PowerShell is required for Windows one-click installation.",
                ),
            )

        download_url = self._resolve_windows_vbcable_url()
        if not download_url:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_windows_url_failed",
                    "Failed to resolve VB-CABLE download URL from official website.",
                ),
            )

        with tempfile.TemporaryDirectory(prefix="echonote-loopback-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            archive_path = tmp_path / "vbcable.zip"
            try:
                urllib.request.urlretrieve(download_url, str(archive_path))
            except Exception as exc:  # noqa: BLE001
                return LoopbackInstallResult(
                    success=False,
                    message=self._t(
                        "loopback.install_download_failed",
                        "Failed to download loopback package: {error}",
                        error=str(exc),
                    ),
                )

            extract_dir = tmp_path / "vbcable"
            extract_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    archive.extractall(extract_dir)
            except Exception as exc:  # noqa: BLE001
                return LoopbackInstallResult(
                    success=False,
                    message=self._t(
                        "loopback.install_extract_failed",
                        "Failed to extract loopback package: {error}",
                        error=str(exc),
                    ),
                )

            setup_executable = self._find_windows_setup_executable(extract_dir)
            if setup_executable is None:
                return LoopbackInstallResult(
                    success=False,
                    message=self._t(
                        "loopback.install_setup_not_found",
                        "Loopback setup executable was not found in downloaded package.",
                    ),
                )

            result = self._run_windows_elevated_setup(setup_executable, powershell)
            if result.success:
                result.requires_reboot = True
                result.message = self._t(
                    "loopback.install_windows_success",
                    "Loopback component installed successfully. Please reboot Windows "
                    "before recording system audio.",
                )
            return result

    def _install_linux_loopback_input(self) -> LoopbackInstallResult:
        """Configure Linux loopback route using PipeWire/PulseAudio virtual sink."""
        pactl_ready = self._ensure_linux_pactl_available()
        if not pactl_ready.success:
            return pactl_ready

        if self._linux_sink_exists():
            return LoopbackInstallResult(
                success=True,
                message=self._t(
                    "loopback.install_linux_already_configured",
                    "Linux loopback virtual sink is already configured.",
                ),
            )

        load_result = subprocess.run(
            [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={self.LINUX_LOOPBACK_SINK_NAME}",
                "sink_properties=device.description=EchoNote-Loopback",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if load_result.returncode != 0:
            error = (load_result.stderr or load_result.stdout or "").strip()
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_linux_setup_failed",
                    "Failed to configure Linux loopback sink: {error}",
                    error=error or "unknown error",
                ),
            )

        return LoopbackInstallResult(
            success=True,
            message=self._t(
                "loopback.install_linux_success",
                "Linux loopback virtual sink was configured. Select 'Monitor of "
                "EchoNote-Loopback' as EchoNote input and route app output to this sink.",
            ),
        )

    def _resolve_cached_pkg_path(self) -> tuple[Optional[Path], str]:
        """Resolve cask package path via Homebrew cache."""
        cache_path = self._brew_cache_path()
        if cache_path and cache_path.exists():
            return cache_path, ""

        logger.info("BlackHole cask not found in cache; running brew fetch...")
        fetch = subprocess.run(
            ["brew", "fetch", "--cask", self.CASK_NAME],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if fetch.returncode != 0:
            error = (fetch.stderr or fetch.stdout or "").strip()
            return None, self._t(
                "loopback.install_fetch_failed",
                "Failed to download loopback package: {error}",
                error=error or "unknown error",
            )

        cache_path = self._brew_cache_path()
        if cache_path and cache_path.exists():
            return cache_path, ""

        return None, self._t(
            "loopback.install_cache_not_found",
            "Loopback package cache was not found after download.",
        )

    def _brew_cache_path(self) -> Optional[Path]:
        """Return cached cask path from Homebrew."""
        result = subprocess.run(
            ["brew", "--cache", "--cask", self.CASK_NAME],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("Failed to query brew cache path: %s", result.stderr)
            return None

        path_text = (result.stdout or "").strip().splitlines()
        if not path_text:
            return None
        return Path(path_text[-1].strip()).expanduser()

    def _powershell_executable(self) -> Optional[str]:
        """Return available PowerShell executable path/name."""
        for command in ("powershell", "pwsh"):
            if shutil.which(command):
                return command
        return None

    def _resolve_windows_vbcable_url(self) -> str:
        """Resolve latest VB-CABLE package URL from official website."""
        try:
            with urllib.request.urlopen(self.WINDOWS_VBCABLE_PAGE_URL, timeout=30) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to query VB-CABLE page: %s", exc)
            return self.WINDOWS_VBCABLE_FALLBACK_URL

        matches = self.WINDOWS_VBCABLE_URL_PATTERN.findall(html)
        if not matches:
            return self.WINDOWS_VBCABLE_FALLBACK_URL

        # Use the highest pack number when multiple links are present.
        def _pack_version(url: str) -> int:
            found = re.search(r"Pack(\d+)\.zip", url, flags=re.IGNORECASE)
            return int(found.group(1)) if found else 0

        return sorted(matches, key=_pack_version, reverse=True)[0]

    def _find_windows_setup_executable(self, extract_dir: Path) -> Optional[Path]:
        """Find preferred VB-CABLE setup executable from extracted archive."""
        executables = []
        for path in extract_dir.rglob("*.exe"):
            name = path.name.lower()
            if "uninstall" in name:
                continue
            if "setup" not in name:
                continue
            if "vbcable" not in name and "vb-cable" not in name:
                continue
            executables.append(path)

        if not executables:
            return None

        machine = platform.machine().lower()
        prefer_x64 = any(token in machine for token in ("amd64", "x86_64", "arm64", "aarch64"))

        def _priority(path: Path) -> tuple[int, str]:
            name = path.name.lower()
            is_x64 = "x64" in name or "64" in name
            score = 0
            if prefer_x64 and is_x64:
                score = -2
            elif not prefer_x64 and not is_x64:
                score = -1
            return score, name

        return sorted(executables, key=_priority)[0]

    def _run_windows_elevated_setup(
        self, setup_executable: Path, powershell_executable: str
    ) -> LoopbackInstallResult:
        """Execute setup executable via UAC elevation prompt."""
        escaped_path = str(setup_executable).replace("'", "''")
        command = (
            f"$proc = Start-Process -FilePath '{escaped_path}' -Verb RunAs -Wait -PassThru; "
            "if ($null -eq $proc) { exit 1 }; "
            "exit $proc.ExitCode"
        )
        run = subprocess.run(
            [
                powershell_executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=3600,
        )

        if run.returncode == 0:
            return LoopbackInstallResult(success=True, message="")

        output = (run.stderr or run.stdout or "").strip()
        cancelled = run.returncode in {1223, 1602} or "cancel" in output.lower()
        if cancelled:
            return LoopbackInstallResult(
                success=False,
                cancelled=True,
                message=self._t(
                    "loopback.install_cancelled",
                    "Installation was cancelled in the system authorization dialog.",
                ),
            )

        return LoopbackInstallResult(
            success=False,
            message=self._t(
                "loopback.install_failed",
                "Loopback installation failed: {error}",
                error=output or f"exit code {run.returncode}",
            ),
        )

    def _detect_linux_package_manager(self) -> Optional[str]:
        """Detect supported Linux package manager."""
        for manager in ("apt-get", "dnf", "pacman", "zypper"):
            if shutil.which(manager):
                return manager
        return None

    def _ensure_linux_pactl_available(self) -> LoopbackInstallResult:
        """Ensure pactl exists, optionally installing dependencies with pkexec."""
        if shutil.which("pactl") is not None:
            return LoopbackInstallResult(success=True, message="")

        manager = self._detect_linux_package_manager()
        if manager is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_linux_pkg_manager_not_found",
                    "No supported Linux package manager was found to install loopback "
                    "dependencies.",
                ),
            )

        if shutil.which("pkexec") is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_missing_pkexec",
                    "pkexec is required for dependency installation on Linux.",
                ),
            )

        package_commands = {
            "apt-get": ["apt-get", "install", "-y", "pulseaudio-utils"],
            "dnf": ["dnf", "install", "-y", "pulseaudio-utils"],
            "pacman": ["pacman", "-S", "--noconfirm", "libpulse"],
            "zypper": ["zypper", "--non-interactive", "install", "pulseaudio-utils"],
        }
        command = package_commands.get(manager)
        if command is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_linux_pkg_manager_not_found",
                    "No supported Linux package manager was found to install loopback "
                    "dependencies.",
                ),
            )

        run = subprocess.run(
            ["pkexec", *command],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if run.returncode != 0:
            output = (run.stderr or run.stdout or "").strip()
            cancelled = run.returncode in {126, 127} or "cancel" in output.lower()
            if cancelled:
                return LoopbackInstallResult(
                    success=False,
                    cancelled=True,
                    message=self._t(
                        "loopback.install_cancelled",
                        "Installation was cancelled in the system authorization dialog.",
                    ),
                )
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_linux_package_failed",
                    "Failed to install Linux audio dependencies: {error}",
                    error=output or f"exit code {run.returncode}",
                ),
            )

        if shutil.which("pactl") is None:
            return LoopbackInstallResult(
                success=False,
                message=self._t(
                    "loopback.install_missing_pactl",
                    "pactl is still unavailable after dependency installation.",
                ),
            )

        return LoopbackInstallResult(success=True, message="")

    def _linux_sink_exists(self) -> bool:
        """Return whether EchoNote loopback sink already exists."""
        run = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if run.returncode != 0:
            return False
        return self.LINUX_LOOPBACK_SINK_NAME in (run.stdout or "")

    def _run_macos_pkg_installer(self, package_path: Path) -> LoopbackInstallResult:
        """Run macOS installer with native administrator authorization prompt."""
        package_path_str = str(package_path).replace('"', '\\"')
        applescript = (
            'do shell script "/usr/sbin/installer -pkg " & '
            f'quoted form of POSIX path of "{package_path_str}" & '
            '" -target /" with administrator privileges'
        )

        result = subprocess.run(
            ["/usr/bin/osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if result.returncode == 0:
            return LoopbackInstallResult(success=True, message="")

        error_output = (result.stderr or result.stdout or "").strip()
        cancelled = "User canceled" in error_output or "-128" in error_output
        if cancelled:
            return LoopbackInstallResult(
                success=False,
                cancelled=True,
                message=self._t(
                    "loopback.install_cancelled",
                    "Installation was cancelled in the system authorization dialog.",
                ),
            )

        return LoopbackInstallResult(
            success=False,
            message=self._t(
                "loopback.install_failed",
                "Loopback installation failed: {error}",
                error=error_output or "unknown error",
            ),
        )
