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
User Feedback Mechanism

Provides operation success confirmation, status updates, and operation logging functionality.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config.app_config import get_app_dir
from ui.common.notification import get_notification_manager

logger = logging.getLogger(__name__)

# Constants
SECONDS_PER_MINUTE = 60


class OperationLogger:
    """
    Operation Logger

    Records user operation history to log files.
    """

    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize operation logger

        Args:
            log_file: Log file path, defaults to ~/.echonote/operation.log
        """
        if log_file is None:
            log_dir = get_app_dir()
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "operation.log"

        self.log_file = log_file
        logger.info(f"Operation logger initialized: {self.log_file}")

    def log_operation(self, operation: str, status: str, details: Optional[Dict[str, Any]] = None):
        """
        Log operation

        Args:
            operation: 操作名称
            status: 操作状态（success/error/warning）
            details: 操作详细信息（可选）
        """
        timestamp = datetime.now().isoformat()

        log_entry = {
            "timestamp": timestamp,
            "operation": operation,
            "status": status,
            "details": details or {},
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            logger.debug(f"Operation logged: {operation} - {status}")

        except Exception as e:
            logger.error(f"Failed to log operation: {e}")

    def get_recent_operations(self, count: int = None) -> list:
        """
        获取最近的操作记录

        Args:
            count: 返回的记录数量

        Returns:
            操作记录列表
        """
        from config.constants import DEFAULT_RECENT_OPERATIONS_COUNT

        if count is None:
            count = DEFAULT_RECENT_OPERATIONS_COUNT

        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 获取最后 count 行
            recent_lines = lines[-count:] if len(lines) > count else lines

            # 解析 JSON
            operations = []
            for line in recent_lines:
                try:
                    operations.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

            return operations

        except Exception as e:
            logger.error(f"Failed to read operation log: {e}")
            return []


# 全局操作日志记录器实例
_operation_logger: Optional[OperationLogger] = None


def get_operation_logger() -> OperationLogger:
    """
    获取全局操作日志记录器实例

    Returns:
        OperationLogger 实例
    """
    global _operation_logger

    if _operation_logger is None:
        _operation_logger = OperationLogger()

    return _operation_logger


class UserFeedback:
    """
    用户反馈工具类

    提供统一的用户反馈接口，包括通知、状态更新和操作日志。
    """

    @staticmethod
    def file_import_success(file_path: str, file_count: int = 1):
        """
        文件导入成功反馈

        Args:
            file_path: 文件路径
            file_count: 导入的文件数量
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        if file_count == 1:
            message = f"文件导入成功: {Path(file_path).name}"
        else:
            message = f"成功导入 {file_count} 个文件"

        notification_mgr.send_success("导入成功", message)
        operation_logger.log_operation(
            operation="file_import",
            status="success",
            details={"file_path": file_path, "file_count": file_count},
        )

        logger.info(f"File import success feedback sent: {file_path}")

    @staticmethod
    def transcription_complete(file_name: str, duration: float, output_path: str):
        """
        转录完成反馈

        Args:
            file_name: 文件名
            duration: 转录耗时（秒）
            output_path: 输出文件路径
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        from config.constants import SECONDS_PER_MINUTE

        minutes = int(duration / SECONDS_PER_MINUTE)
        seconds = int(duration % SECONDS_PER_MINUTE)
        time_str = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"

        message = f"{file_name} 转录完成（耗时 {time_str}）"

        notification_mgr.send_success("转录完成", message)
        operation_logger.log_operation(
            operation="transcription",
            status="success",
            details={
                "file_name": file_name,
                "duration": duration,
                "output_path": output_path,
            },
        )

        logger.info(f"Transcription complete feedback sent: {file_name}")

    @staticmethod
    def recording_complete(file_path: str, duration: float):
        """
        录制完成反馈

        Args:
            file_path: 录制文件路径
            duration: 录制时长（秒）
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        minutes = int(duration / SECONDS_PER_MINUTE)
        seconds = int(duration % SECONDS_PER_MINUTE)
        time_str = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"

        message = f"录制完成（时长 {time_str}）"

        notification_mgr.send_success("录制完成", message)
        operation_logger.log_operation(
            operation="recording",
            status="success",
            details={"file_path": file_path, "duration": duration},
        )

        logger.info(f"Recording complete feedback sent: {file_path}")

    @staticmethod
    def event_created(event_title: str, event_time: str):
        """
        事件创建成功反馈

        Args:
            event_title: 事件标题
            event_time: 事件时间
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        message = f"事件已创建: {event_title}"

        notification_mgr.send_success("事件创建成功", message)
        operation_logger.log_operation(
            operation="event_create",
            status="success",
            details={"event_title": event_title, "event_time": event_time},
        )

        logger.info(f"Event created feedback sent: {event_title}")

    @staticmethod
    def event_updated(event_title: str):
        """
        事件更新成功反馈

        Args:
            event_title: 事件标题
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        message = f"事件已更新: {event_title}"

        notification_mgr.send_success("事件更新成功", message)
        operation_logger.log_operation(
            operation="event_update",
            status="success",
            details={"event_title": event_title},
        )

        logger.info(f"Event updated feedback sent: {event_title}")

    @staticmethod
    def event_deleted(event_title: str):
        """
        事件删除成功反馈

        Args:
            event_title: 事件标题
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        message = f"事件已删除: {event_title}"

        notification_mgr.send_success("事件删除成功", message)
        operation_logger.log_operation(
            operation="event_delete",
            status="success",
            details={"event_title": event_title},
        )

        logger.info(f"Event deleted feedback sent: {event_title}")

    @staticmethod
    def settings_saved():
        """设置保存成功反馈"""
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        notification_mgr.send_success("设置已保存", "您的设置已成功保存")
        operation_logger.log_operation(operation="settings_save", status="success", details={})

        logger.info("Settings saved feedback sent")

    @staticmethod
    def calendar_sync_complete(event_count: int, service: str):
        """
        日历同步完成反馈

        Args:
            event_count: 同步的事件数量
            service: 服务名称（Google/Outlook）
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        message = f"已同步 {event_count} 个事件"

        notification_mgr.send_success(f"{service} 同步完成", message)
        operation_logger.log_operation(
            operation="calendar_sync",
            status="success",
            details={"event_count": event_count, "service": service},
        )

        logger.info(f"Calendar sync complete feedback sent: {service}")

    @staticmethod
    def operation_error(operation: str, error_message: str):
        """
        操作错误反馈

        Args:
            operation: 操作名称
            error_message: 错误消息
        """
        notification_mgr = get_notification_manager()
        operation_logger = get_operation_logger()

        notification_mgr.send_error("操作失败", error_message)
        operation_logger.log_operation(
            operation=operation,
            status="error",
            details={"error_message": error_message},
        )

        logger.error(f"Operation error feedback sent: {operation}")


class StatusUpdater:
    """
    状态更新器

    用于更新 UI 中的状态标签。
    """

    def __init__(self, status_label=None):
        """
        初始化状态更新器

        Args:
            status_label: PySide6 QLabel 对象（可选）
        """
        self.status_label = status_label

    def set_status_label(self, status_label):
        """
        设置状态标签

        Args:
            status_label: PySide6 QLabel 对象
        """
        self.status_label = status_label

    def update_status(self, message: str, status_type: str = "info"):
        """
        更新状态

        Args:
            message: 状态消息
            status_type: 状态类型（info/success/warning/error）
        """
        if self.status_label is None:
            logger.warning("Status label not set, cannot update status")
            return

        # 更新状态文本
        self.status_label.setText(message)

        # 根据状态类型设置语义属性
        self.status_label.setProperty("role", "user-feedback")
        self.status_label.setProperty("state", status_type)

        # 强制样式更新
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        logger.debug(f"Status updated: {message} ({status_type})")

    def clear_status(self):
        """清除状态"""
        if self.status_label is not None:
            self.status_label.setText("")
            self.status_label.setProperty("role", None)
            self.status_label.setProperty("state", None)

            # 强制样式更新
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
