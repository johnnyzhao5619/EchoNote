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
统一错误处理器

提供统一的错误处理机制，将各种异常转换为用户友好的错误消息和建议。
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

from engines.speech.base import AUDIO_VIDEO_FORMATS

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误类别"""

    FILE_FORMAT = "file_format"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    API_LIMIT = "api_limit"
    PERMISSION = "permission"
    RESOURCE = "resource"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


# 自定义异常类
class EchoNoteError(Exception):
    """EchoNote 基础异常类"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN):
        super().__init__(message)
        self.category = category


class UnsupportedFormatError(EchoNoteError):
    """不支持的文件格式错误"""

    def __init__(self, file_format: str):
        self.format = file_format
        msg = f"不支持的文件格式: {file_format}"
        super().__init__(msg, ErrorCategory.FILE_FORMAT)


class NetworkError(EchoNoteError):
    """网络连接错误"""

    def __init__(self, message: str = "网络连接失败"):
        super().__init__(message, ErrorCategory.NETWORK)


class AuthenticationError(EchoNoteError):
    """认证错误"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(message, ErrorCategory.AUTHENTICATION)


class APILimitError(EchoNoteError):
    """API 速率限制错误"""

    def __init__(self, message: str = "API 速率限制", retry_after: Optional[int] = None):
        super().__init__(message, ErrorCategory.API_LIMIT)
        self.retry_after = retry_after


class PermissionError(EchoNoteError):
    """权限错误"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(message, ErrorCategory.PERMISSION)


class ResourceError(EchoNoteError):
    """资源错误（磁盘空间、内存等）"""

    def __init__(self, message: str = "系统资源不足"):
        super().__init__(message, ErrorCategory.RESOURCE)


class ValidationError(EchoNoteError):
    """输入验证错误"""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, ErrorCategory.VALIDATION)
        self.field = field


class ErrorHandler:
    """统一错误处理器"""

    # 支持的音频/视频格式
    SUPPORTED_FORMATS = list(AUDIO_VIDEO_FORMATS)

    @staticmethod
    def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        统一错误处理

        Args:
            error: 异常对象
            context: 错误上下文信息（可选）

        Returns:
            包含错误信息的字典:
            {
                "user_message": "用户友好的错误消息",
                "technical_details": "技术细节（用于日志）",
                "suggested_action": "建议的解决方案",
                "retry_possible": True/False,
                "category": "错误类别"
            }
        """
        context = context or {}

        # 记录错误到日志
        logger.error(
            f"Error occurred: {type(error).__name__}: {str(error)}",
            exc_info=True,
            extra={"context": context},
        )

        # 处理自定义异常
        if isinstance(error, UnsupportedFormatError):
            formats = ", ".join(ErrorHandler.SUPPORTED_FORMATS).upper()
            return {
                "user_message": f"不支持的文件格式: {error.format}",
                "technical_details": str(error),
                "suggested_action": (
                    f"支持的格式: {formats}\n" f"建议使用 FFmpeg 转换为支持的格式"
                ),
                "retry_possible": False,
                "category": error.category.value,
            }

        elif isinstance(error, NetworkError):
            action = "请检查网络连接后重试，或使用本地引擎（faster-whisper）"
            return {
                "user_message": "网络连接失败",
                "technical_details": str(error),
                "suggested_action": action,
                "retry_possible": True,
                "category": error.category.value,
            }

        elif isinstance(error, AuthenticationError):
            action = "请检查 API Key 是否正确，或重新连接外部服务"
            return {
                "user_message": "认证失败",
                "technical_details": str(error),
                "suggested_action": action,
                "retry_possible": False,
                "category": error.category.value,
            }

        elif isinstance(error, APILimitError):
            retry_msg = ""
            if error.retry_after:
                retry_msg = f"，请在 {error.retry_after} 秒后重试"
            return {
                "user_message": f"API 速率限制已达到{retry_msg}",
                "technical_details": str(error),
                "suggested_action": "请稍后重试，或考虑升级 API 套餐",
                "retry_possible": True,
                "category": error.category.value,
                "retry_after": error.retry_after,
            }

        elif isinstance(error, PermissionError):
            return {
                "user_message": "权限不足",
                "technical_details": str(error),
                "suggested_action": "请检查文件/目录权限，或以管理员身份运行",
                "retry_possible": False,
                "category": error.category.value,
            }

        elif isinstance(error, ResourceError):
            return {
                "user_message": "系统资源不足",
                "technical_details": str(error),
                "suggested_action": "请释放磁盘空间或内存后重试",
                "retry_possible": True,
                "category": error.category.value,
            }

        elif isinstance(error, ValidationError):
            field_msg = f" ({error.field})" if error.field else ""
            return {
                "user_message": f"输入验证失败{field_msg}",
                "technical_details": str(error),
                "suggested_action": "请检查输入内容是否符合要求",
                "retry_possible": False,
                "category": error.category.value,
            }

        # 处理标准 Python 异常
        elif isinstance(error, FileNotFoundError):
            return {
                "user_message": "文件未找到",
                "technical_details": str(error),
                "suggested_action": "请检查文件路径是否正确",
                "retry_possible": False,
                "category": ErrorCategory.FILE_FORMAT.value,
            }

        elif isinstance(error, OSError) and "disk" in str(error).lower():
            return {
                "user_message": "磁盘空间不足",
                "technical_details": str(error),
                "suggested_action": "请释放磁盘空间后重试",
                "retry_possible": True,
                "category": ErrorCategory.RESOURCE.value,
            }

        elif isinstance(error, MemoryError):
            return {
                "user_message": "内存不足",
                "technical_details": str(error),
                "suggested_action": "请关闭其他应用程序或处理较小的文件",
                "retry_possible": True,
                "category": ErrorCategory.RESOURCE.value,
            }

        elif isinstance(error, ValueError):
            return {
                "user_message": "输入值无效",
                "technical_details": str(error),
                "suggested_action": "请检查输入内容是否符合要求",
                "retry_possible": False,
                "category": ErrorCategory.VALIDATION.value,
            }

        elif isinstance(error, TimeoutError):
            return {
                "user_message": "操作超时",
                "technical_details": str(error),
                "suggested_action": "请检查网络连接或稍后重试",
                "retry_possible": True,
                "category": ErrorCategory.NETWORK.value,
            }

        # 未知错误
        else:
            return {
                "user_message": "发生未知错误",
                "technical_details": f"{type(error).__name__}: {str(error)}",
                "suggested_action": "请查看日志文件获取详细信息，或联系技术支持",
                "retry_possible": False,
                "category": ErrorCategory.UNKNOWN.value,
            }

    @staticmethod
    def format_user_message(error_info: Dict[str, Any], include_action: bool = True) -> str:
        """
        格式化用户错误消息

        Args:
            error_info: handle_error 返回的错误信息字典
            include_action: 是否包含建议操作

        Returns:
            格式化的错误消息字符串
        """
        message = error_info["user_message"]

        if include_action and error_info.get("suggested_action"):
            message += f"\n\n{error_info['suggested_action']}"

        return message

    @staticmethod
    def is_retryable(error_info: Dict[str, Any]) -> bool:
        """
        判断错误是否可重试

        Args:
            error_info: handle_error 返回的错误信息字典

        Returns:
            是否可重试
        """
        return error_info.get("retry_possible", False)
