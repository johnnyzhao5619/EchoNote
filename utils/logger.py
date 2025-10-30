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
日志系统配置

提供集中式日志设置，支持文件轮转和控制台输出。
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.app_config import get_app_dir

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

class SensitiveDataFilter(logging.Filter):
    """
    过滤敏感数据的日志过滤器

    防止 API Key、Token 等敏感信息被记录到日志中。
    """

    # 敏感关键词列表
    SENSITIVE_KEYWORDS = [
        "api_key",
        "api-key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "credential",
        "authorization",
        "bearer",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录

        Args:
            record: 日志记录对象

        Returns:
            是否允许记录该日志
        """
        # 检查消息中是否包含敏感关键词
        message = record.getMessage().lower()

        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in message:
                # 替换敏感信息为 ***
                record.msg = self._mask_sensitive_data(record.msg)
                break

        return True

    def _mask_sensitive_data(self, message: str) -> str:
        """
        遮蔽敏感数据

        Args:
            message: 原始消息

        Returns:
            遮蔽后的消息
        """
        import re

        # 遮蔽类似 "api_key=xxx" 的模式
        patterns = [
            (r"(api[_-]?key\s*[=:]\s*)[^\s,\)]+", r"\1***"),
            (r"(token\s*[=:]\s*)[^\s,\)]+", r"\1***"),
            (r"(password\s*[=:]\s*)[^\s,\)]+", r"\1***"),
            (r"(secret\s*[=:]\s*)[^\s,\)]+", r"\1***"),
            (r"(bearer\s+)[^\s,\)]+", r"\1***"),
        ]

        masked = message
        for pattern, replacement in patterns:
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)

        return masked

def setup_logging(
    log_dir: str = None, level: str = None, console_output: bool = True
) -> logging.Logger:
    """
    设置应用日志系统

    配置文件轮转处理器和控制台处理器。

    Args:
        log_dir: 日志文件目录，默认为 ~/.echonote/logs
        level: 日志级别，默认根据环境变量 ECHONOTE_ENV 决定
               (development: DEBUG, production: INFO)
        console_output: 是否输出到控制台，默认 True

    Returns:
        配置好的应用根日志器
    """
    # 确定日志目录
    if log_dir is None:
        log_dir = get_app_dir() / "logs"
    else:
        log_dir = Path(log_dir)

    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)

    # 确定日志级别
    if level is None:
        # 根据环境变量决定日志级别
        env = os.environ.get("ECHONOTE_ENV", "production").lower()
        level = "DEBUG" if env == "development" else "INFO"

    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    # 获取应用根日志器
    logger = logging.getLogger("echonote")
    logger.setLevel(logging.DEBUG)  # 设置为最低级别，由处理器控制

    # 清除现有处理器，避免重复
    logger.handlers.clear()

    # 添加敏感数据过滤器
    sensitive_filter = SensitiveDataFilter()

    # 文件处理器 - 详细日志，带轮转
    from config.constants import LOG_FILE_BACKUP_COUNT, LOG_FILE_MAX_BYTES

    log_file = log_dir / "echonote.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_FILE_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(sensitive_filter)
    logger.addHandler(file_handler)

    # 控制台处理器 - 简化日志
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(sensitive_filter)
        logger.addHandler(console_handler)

    # 记录初始化消息
    logger.info("日志系统已初始化")
    logger.debug(f"日志文件位置: {log_file}")
    logger.debug(f"日志级别: {level}")

    return logger

def get_logger(name: str) -> logging.Logger:
    """
    获取特定模块的日志器实例

    Args:
        name: 模块名称（通常使用 __name__）

    Returns:
        日志器实例

    Example:
        logger = get_logger(__name__)
        logger.info("This is an info message")
    """
    # 如果名称已经包含 'echonote' 前缀，直接使用
    if name.startswith("echonote."):
        return logging.getLogger(name)

    # 否则添加前缀
    return logging.getLogger(f"echonote.{name}")

def set_log_level(level: str):
    """
    动态设置日志级别

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)

    Example:
        set_log_level('DEBUG')
    """
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logger = logging.getLogger("echonote")

    # 更新所有处理器的级别
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.setLevel(log_level)

    logger.info(f"日志级别已更改为: {level}")

def get_log_file_path() -> Path:
    """
    获取当前日志文件路径

    Returns:
        日志文件路径
    """
    logger = logging.getLogger("echonote")

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            return Path(handler.baseFilename)

    # 如果没有找到文件处理器，返回默认路径
    return get_app_dir() / "logs" / "echonote.log"

def get_recent_logs(lines: int = None) -> list:
    """
    获取最近的日志行

    Args:
        lines: 要读取的行数，默认使用 DEFAULT_LOG_LINES_TO_READ

    Returns:
        日志行列表
    """
    if lines is None:
        from config.constants import DEFAULT_LOG_LINES_TO_READ

        lines = DEFAULT_LOG_LINES_TO_READ
    log_file = get_log_file_path()

    if not log_file.exists():
        return []

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # 读取最后 N 行
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        return [f"Error reading log file: {e}"]
