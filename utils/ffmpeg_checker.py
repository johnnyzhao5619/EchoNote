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
FFmpeg availability checker.

Checks if ffmpeg/ffprobe is installed and provides installation guidance.
"""

import logging
import platform
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger("echonote.utils.ffmpeg_checker")


class FFmpegChecker:
    """
    Utility class to check ffmpeg/ffprobe availability.

    Provides methods to check installation status and get installation
    instructions for different platforms.
    """

    def __init__(self):
        """Initialize FFmpeg checker."""
        self._ffmpeg_available = None
        self._ffprobe_available = None
        self._version = None

    def is_ffmpeg_available(self) -> bool:
        """
        Check if ffmpeg is available.

        Returns:
            True if ffmpeg is installed and accessible, False otherwise
        """
        if self._ffmpeg_available is None:
            self._ffmpeg_available = self._check_command("ffmpeg")
        return self._ffmpeg_available

    def is_ffprobe_available(self) -> bool:
        """
        Check if ffprobe is available.

        Returns:
            True if ffprobe is installed and accessible, False otherwise
        """
        if self._ffprobe_available is None:
            self._ffprobe_available = self._check_command("ffprobe")
        return self._ffprobe_available

    def get_version(self) -> Optional[str]:
        """
        Get ffmpeg version string.

        Returns:
            Version string if available, None otherwise
        """
        if self._version is None and self.is_ffmpeg_available():
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # Extract version from first line
                    first_line = result.stdout.split("\n")[0]
                    self._version = first_line
                    logger.debug(f"FFmpeg version: {self._version}")
            except Exception as e:
                logger.warning(f"Could not get ffmpeg version: {e}")

        return self._version

    def _check_command(self, command: str) -> bool:
        """
        Check if a command is available.

        Args:
            command: Command name to check

        Returns:
            True if command is available, False otherwise
        """
        try:
            result = subprocess.run(
                [command, "-version"], capture_output=True, text=True, timeout=5
            )
            available = result.returncode == 0
            logger.debug(f"{command} available: {available}")
            return available
        except FileNotFoundError:
            logger.debug(f"{command} not found")
            return False
        except Exception as e:
            logger.warning(f"Error checking {command}: {e}")
            return False

    def get_installation_instructions(self, i18n=None) -> Tuple[str, str]:
        """
        Get installation instructions for current platform.

        Args:
            i18n: Optional I18n manager for translations. If None, returns
                  Chinese instructions for backward compatibility.

        Returns:
            Tuple of (title, instructions) for the current platform
        """
        system = platform.system()

        if system == "Darwin":  # macOS
            if i18n:
                title = i18n.t("ffmpeg.dialog_title", platform="macOS")
                instructions = (
                    f"{i18n.t('ffmpeg.detected_system', system='macOS')}\n\n"
                    f"{i18n.t('ffmpeg.purpose')}\n\n"
                    f"{i18n.t('ffmpeg.recommended_install', method=i18n.t('ffmpeg.macos.method_homebrew'))}\n\n"
                    f"{i18n.t('ffmpeg.macos.step1')}\n"
                    f"{i18n.t('ffmpeg.macos.step1_url')}\n\n"
                    f"{i18n.t('ffmpeg.macos.step2')}\n"
                    f"{i18n.t('ffmpeg.macos.step2_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.after_install')}\n\n"
                    f"{i18n.t('ffmpeg.verify_install')}\n"
                    f"{i18n.t('ffmpeg.verify_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.skip_note')}"
                )
            else:
                title = "安装 FFmpeg (macOS)"
                instructions = (
                    "检测到您的系统：macOS\n\n"
                    "FFmpeg 用于处理视频格式（MP4、MKV 等）的音频信息。\n\n"
                    "推荐使用 Homebrew 安装：\n\n"
                    "1. 如果还没有安装 Homebrew，请访问：\n"
                    "   https://brew.sh\n\n"
                    "2. 在终端（Terminal）中运行：\n"
                    "   brew install ffmpeg\n\n"
                    "3. 安装完成后重启 EchoNote\n\n"
                    "验证安装：\n"
                    "   ffmpeg -version\n\n"
                    "注意：没有 FFmpeg，您仍然可以处理 WAV、MP3、FLAC 等纯音频格式。"
                )

        elif system == "Linux":
            # Try to detect Linux distribution
            distro_info = ""
            try:
                result = subprocess.run(
                    ["cat", "/etc/os-release"], capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if line.startswith("PRETTY_NAME="):
                            distro_info = line.split("=")[1].strip('"')
                            break
            except Exception:
                pass

            if i18n:
                title = i18n.t("ffmpeg.dialog_title", platform="Linux")
                system_info = i18n.t("ffmpeg.detected_system", system="Linux")
                if distro_info:
                    system_info += f" ({distro_info})"

                instructions = (
                    f"{system_info}\n\n"
                    f"{i18n.t('ffmpeg.purpose')}\n\n"
                    f"{i18n.t('ffmpeg.linux.choose_distro')}\n\n"
                    f"{i18n.t('ffmpeg.linux.ubuntu_debian')}\n"
                    f"{i18n.t('ffmpeg.linux.ubuntu_cmd1')}\n"
                    f"{i18n.t('ffmpeg.linux.ubuntu_cmd2')}\n\n"
                    f"{i18n.t('ffmpeg.linux.fedora')}\n"
                    f"{i18n.t('ffmpeg.linux.fedora_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.linux.arch')}\n"
                    f"{i18n.t('ffmpeg.linux.arch_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.linux.opensuse')}\n"
                    f"{i18n.t('ffmpeg.linux.opensuse_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.after_install')}\n\n"
                    f"{i18n.t('ffmpeg.verify_install')}\n"
                    f"{i18n.t('ffmpeg.verify_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.skip_note')}"
                )
            else:
                title = "安装 FFmpeg (Linux)"
                system_info = "检测到您的系统：Linux"
                if distro_info:
                    system_info += f" ({distro_info})"

                instructions = (
                    f"{system_info}\n\n"
                    "FFmpeg 用于处理视频格式（MP4、MKV 等）的音频信息。\n\n"
                    "根据您的发行版选择安装命令：\n\n"
                    "Ubuntu/Debian:\n"
                    "   sudo apt-get update\n"
                    "   sudo apt-get install ffmpeg\n\n"
                    "Fedora:\n"
                    "   sudo dnf install ffmpeg\n\n"
                    "Arch Linux:\n"
                    "   sudo pacman -S ffmpeg\n\n"
                    "openSUSE:\n"
                    "   sudo zypper install ffmpeg\n\n"
                    "安装完成后重启 EchoNote\n\n"
                    "验证安装：\n"
                    "   ffmpeg -version\n\n"
                    "注意：没有 FFmpeg，您仍然可以处理 WAV、MP3、FLAC 等纯音频格式。"
                )

        elif system == "Windows":
            # Try to detect Windows version
            windows_version = ""
            try:
                windows_version = platform.win32_ver()[0]
            except Exception:
                pass

            if i18n:
                title = i18n.t("ffmpeg.dialog_title", platform="Windows")
                system_info = i18n.t("ffmpeg.detected_system", system="Windows")
                if windows_version:
                    system_info += f" {windows_version}"

                instructions = (
                    f"{system_info}\n\n"
                    f"{i18n.t('ffmpeg.purpose')}\n\n"
                    f"{i18n.t('ffmpeg.windows.method1_chocolatey')}\n"
                    f"{i18n.t('ffmpeg.windows.choco_step1')}\n"
                    f"{i18n.t('ffmpeg.windows.choco_step2')}\n"
                    f"{i18n.t('ffmpeg.windows.choco_step2_url')}\n"
                    f"{i18n.t('ffmpeg.windows.choco_step3')}\n"
                    f"{i18n.t('ffmpeg.windows.choco_step3_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.windows.method2_scoop')}\n"
                    f"{i18n.t('ffmpeg.windows.scoop_step1')}\n"
                    f"{i18n.t('ffmpeg.windows.scoop_step2')}\n"
                    f"{i18n.t('ffmpeg.windows.scoop_step2_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.windows.method3_manual')}\n"
                    f"{i18n.t('ffmpeg.windows.manual_step1')}\n"
                    f"{i18n.t('ffmpeg.windows.manual_step2')}\n"
                    f"{i18n.t('ffmpeg.windows.manual_step3')}\n"
                    f"{i18n.t('ffmpeg.windows.manual_step4')}\n"
                    f"{i18n.t('ffmpeg.windows.manual_step5')}\n\n"
                    f"{i18n.t('ffmpeg.verify_install')}\n"
                    f"{i18n.t('ffmpeg.verify_cmd')}\n\n"
                    f"{i18n.t('ffmpeg.skip_note')}"
                )
            else:
                title = "安装 FFmpeg (Windows)"
                system_info = "检测到您的系统：Windows"
                if windows_version:
                    system_info += f" {windows_version}"

                instructions = (
                    f"{system_info}\n\n"
                    "FFmpeg 用于处理视频格式（MP4、MKV 等）的音频信息。\n\n"
                    "方法1 - 使用 Chocolatey（推荐，最简单）：\n"
                    "1. 以管理员身份打开 PowerShell\n"
                    "2. 安装 Chocolatey（如果还没有）：\n"
                    "   访问 https://chocolatey.org/install\n"
                    "3. 安装 FFmpeg：\n"
                    "   choco install ffmpeg\n\n"
                    "方法2 - 使用 Scoop（推荐）：\n"
                    "1. 安装 Scoop：https://scoop.sh\n"
                    "2. 在 PowerShell 中运行：\n"
                    "   scoop install ffmpeg\n\n"
                    "方法3 - 手动安装：\n"
                    "1. 访问：https://ffmpeg.org/download.html\n"
                    "2. 下载 Windows 版本（选择 gyan.dev 或 BtbN 构建）\n"
                    "3. 解压到目录（如 C:\\ffmpeg）\n"
                    "4. 将 bin 目录添加到系统 PATH 环境变量\n"
                    "5. 重启 EchoNote\n\n"
                    "验证安装：\n"
                    "   在命令提示符中运行：ffmpeg -version\n\n"
                    "注意：没有 FFmpeg，您仍然可以处理 WAV、MP3、FLAC 等纯音频格式。"
                )

        else:
            if i18n:
                title = i18n.t("ffmpeg.dialog_title", platform=system)
                instructions = (
                    f"{i18n.t('ffmpeg.detected_system', system=system)}\n\n"
                    f"{i18n.t('ffmpeg.purpose')}\n\n"
                    f"{i18n.t('ffmpeg.generic.visit_website')}\n\n"
                    f"{i18n.t('ffmpeg.generic.ensure_available')}\n\n"
                    f"{i18n.t('ffmpeg.verify_install')}\n"
                    f"{i18n.t('ffmpeg.verify_cmd')}\n"
                    f"{i18n.t('ffmpeg.verify_cmd_probe')}\n\n"
                    f"{i18n.t('ffmpeg.skip_note')}"
                )
            else:
                title = "安装 FFmpeg"
                instructions = (
                    f"检测到您的系统：{system}\n\n"
                    "FFmpeg 用于处理视频格式（MP4、MKV 等）的音频信息。\n\n"
                    "请访问 https://ffmpeg.org/download.html 下载适合您系统的版本。\n\n"
                    "安装后，请确保 ffmpeg 和 ffprobe 命令可以在终端中运行。\n\n"
                    "验证安装：\n"
                    "   ffmpeg -version\n"
                    "   ffprobe -version\n\n"
                    "注意：没有 FFmpeg，您仍然可以处理 WAV、MP3、FLAC 等纯音频格式。"
                )

        return title, instructions

    def get_status_message(self) -> str:
        """
        Get a status message about ffmpeg availability.

        Returns:
            Status message string
        """
        if self.is_ffmpeg_available() and self.is_ffprobe_available():
            version = self.get_version()
            if version:
                return f"FFmpeg 已安装：{version}"
            else:
                return "FFmpeg 已安装"
        elif self.is_ffmpeg_available():
            return "FFmpeg 已安装，但 ffprobe 不可用"
        elif self.is_ffprobe_available():
            return "ffprobe 已安装，但 FFmpeg 不可用"
        else:
            return "FFmpeg 未安装"

    def check_and_log(self) -> bool:
        """
        Check ffmpeg availability and log the result.

        Returns:
            True if both ffmpeg and ffprobe are available, False otherwise
        """
        # Log system information
        system = platform.system()
        logger.info(f"System platform: {system}")

        ffmpeg_ok = self.is_ffmpeg_available()
        ffprobe_ok = self.is_ffprobe_available()

        if ffmpeg_ok and ffprobe_ok:
            version = self.get_version()
            logger.info(f"✓ FFmpeg is available: {version}")
            logger.info("Full audio/video format support enabled")
            return True
        else:
            logger.warning(
                f"✗ FFmpeg availability check: ffmpeg={ffmpeg_ok}, " f"ffprobe={ffprobe_ok}"
            )
            logger.warning(
                "Video format support will be limited without FFmpeg. "
                "Only pure audio formats (WAV, MP3, FLAC) will be fully supported."
            )

            # Log installation hint
            title, _ = self.get_installation_instructions()
            logger.info(f"Installation guide: {title}")

            return False


# Global instance
_checker = None


def get_ffmpeg_checker() -> FFmpegChecker:
    """
    Get the global FFmpeg checker instance.

    Returns:
        FFmpegChecker instance
    """
    global _checker
    if _checker is None:
        _checker = FFmpegChecker()
    return _checker
