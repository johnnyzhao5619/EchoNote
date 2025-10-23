"""
网络错误处理器

提供统一的网络错误处理机制，包括重试装饰器和网络连接检测。
"""

import logging
import time
import socket
from contextlib import closing
from functools import wraps
from typing import Callable, Optional, Any
import httpx


logger = logging.getLogger(__name__)


def check_network_connectivity(
    host: str = "8.8.8.8",
    port: int = 53,
    timeout: float = 3.0
) -> bool:
    """
    检查网络连接是否可用
    
    Args:
        host: 测试主机（默认 Google DNS）
        port: 测试端口（默认 DNS 端口 53）
        timeout: 超时时间（秒）
    
    Returns:
        网络是否可用
    """
    sock: Optional[socket.socket] = None
    try:
        socket.setdefaulttimeout(timeout)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.connect((host, port))
            return True
    except (socket.error, socket.timeout):
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                logger.debug("Failed to close socket cleanly", exc_info=True)


def get_network_error_message(error: Exception) -> tuple[str, str]:
    """
    获取网络错误的用户友好消息和建议
    
    Args:
        error: 网络异常对象
    
    Returns:
        (错误消息, 建议操作) 元组
    """
    if isinstance(error, httpx.ConnectError):
        message = "网络连接失败，无法连接到服务器"
        suggestion = "请检查网络连接，或使用本地引擎（faster-whisper）"
    
    elif isinstance(error, httpx.TimeoutException):
        message = "网络请求超时"
        suggestion = "请检查网络速度，或稍后重试"
    
    elif isinstance(error, httpx.ConnectTimeout):
        message = "连接超时，无法建立连接"
        suggestion = "请检查网络连接，或使用本地引擎（faster-whisper）"
    
    elif isinstance(error, httpx.ReadTimeout):
        message = "读取超时，服务器响应过慢"
        suggestion = "请检查网络速度，或稍后重试"
    
    elif isinstance(error, httpx.WriteTimeout):
        message = "写入超时，上传数据失败"
        suggestion = "请检查网络速度，或稍后重试"
    
    elif isinstance(error, httpx.PoolTimeout):
        message = "连接池超时，服务器繁忙"
        suggestion = "请稍后重试"
    
    elif isinstance(error, httpx.NetworkError):
        message = "网络错误"
        suggestion = "请检查网络连接，或使用本地引擎（faster-whisper）"
    
    elif isinstance(error, httpx.ProxyError):
        message = "代理服务器错误"
        suggestion = "请检查代理设置"
    
    elif isinstance(error, httpx.UnsupportedProtocol):
        message = "不支持的协议"
        suggestion = "请联系技术支持"
    
    elif isinstance(error, httpx.RemoteProtocolError):
        message = "远程协议错误"
        suggestion = "服务器返回了无效的响应，请稍后重试"
    
    elif isinstance(error, httpx.LocalProtocolError):
        message = "本地协议错误"
        suggestion = "请求格式错误，请联系技术支持"
    
    elif isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        
        if status_code == 400:
            message = "请求参数错误"
            suggestion = "请检查输入内容"
        elif status_code == 401:
            message = "认证失败，API Key 无效"
            suggestion = (
                "请在设置中检查 API Key 是否正确"
            )
        elif status_code == 403:
            message = "访问被拒绝，权限不足"
            suggestion = "请检查 API Key 权限设置"
        elif status_code == 404:
            message = "请求的资源不存在"
            suggestion = "请联系技术支持"
        elif status_code == 429:
            message = "API 速率限制已达到"
            retry_after = error.response.headers.get('Retry-After')
            if retry_after:
                try:
                    seconds = int(retry_after)
                    suggestion = f"请在 {seconds} 秒后重试"
                except ValueError:
                    suggestion = "请稍后重试"
            else:
                suggestion = (
                    "请稍后重试，或考虑升级 API 套餐"
                )
        elif status_code >= 500:
            message = f"服务器错误 ({status_code})"
            suggestion = "服务器暂时不可用，请稍后重试"
        else:
            message = f"HTTP 错误 ({status_code})"
            suggestion = "请稍后重试"
    
    else:
        message = f"网络错误: {type(error).__name__}"
        suggestion = (
            "请检查网络连接，或使用本地引擎（faster-whisper）"
        )
    
    return message, suggestion


def retry_on_network_error(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_backoff: bool = True,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    网络错误重试装饰器
    
    自动重试网络请求，使用指数退避策略。
    
    Args:
        max_retries: 最大重试次数（默认 3）
        base_delay: 基础延迟时间（秒，默认 1）
        exponential_backoff: 是否使用指数退避（默认 True）
        on_retry: 重试时的回调函数，接收 (error, attempt) 参数
    
    Returns:
        装饰器函数
    
    Example:
        @retry_on_network_error(max_retries=3)
        def fetch_data():
            response = httpx.get("https://api.example.com/data")
            return response.json()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    # 执行函数
                    return func(*args, **kwargs)
                
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.HTTPStatusError
                ) as e:
                    last_error = e
                    
                    # 如果是最后一次尝试，抛出异常
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}"
                        )
                        raise
                    
                    # 对于某些 HTTP 状态码，不重试
                    if isinstance(e, httpx.HTTPStatusError):
                        status_code = e.response.status_code
                        # 4xx 错误（除了 429）通常不应该重试
                        if 400 <= status_code < 500 and status_code != 429:
                            logger.error(
                                f"Non-retryable HTTP error {status_code} in {func.__name__}"
                            )
                            raise
                    
                    # 计算延迟时间
                    if exponential_backoff:
                        delay = base_delay * (2 ** attempt)
                    else:
                        delay = base_delay
                    
                    # 对于 429 错误，尝试从响应头获取 Retry-After
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = float(retry_after)
                                # 限制最大等待时间为 60 秒
                                if delay > 60:
                                    logger.warning(
                                        f"Retry-After too long ({delay}s), not retrying"
                                    )
                                    raise
                            except ValueError:
                                pass
                    
                    # 记录重试信息
                    error_msg, _ = get_network_error_message(e)
                    logger.warning(
                        f"{error_msg} in {func.__name__}, "
                        f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                    )
                    
                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(
                                f"Error in retry callback: {callback_error}"
                            )
                    
                    # 等待后重试
                    time.sleep(delay)
            
            # 不应该到达这里
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Unexpected error in retry loop for {func.__name__}")
        
        return wrapper
    
    return decorator


def async_retry_on_network_error(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_backoff: bool = True,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    异步网络错误重试装饰器
    
    自动重试异步网络请求，使用指数退避策略。
    
    Args:
        max_retries: 最大重试次数（默认 3）
        base_delay: 基础延迟时间（秒，默认 1）
        exponential_backoff: 是否使用指数退避（默认 True）
        on_retry: 重试时的回调函数，接收 (error, attempt) 参数
    
    Returns:
        装饰器函数
    
    Example:
        @async_retry_on_network_error(max_retries=3)
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            import asyncio
            
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    # 执行异步函数
                    return await func(*args, **kwargs)
                
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.HTTPStatusError
                ) as e:
                    last_error = e
                    
                    # 如果是最后一次尝试，抛出异常
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}"
                        )
                        raise
                    
                    # 对于某些 HTTP 状态码，不重试
                    if isinstance(e, httpx.HTTPStatusError):
                        status_code = e.response.status_code
                        # 4xx 错误（除了 429）通常不应该重试
                        if 400 <= status_code < 500 and status_code != 429:
                            logger.error(
                                f"Non-retryable HTTP error {status_code} in {func.__name__}"
                            )
                            raise
                    
                    # 计算延迟时间
                    if exponential_backoff:
                        delay = base_delay * (2 ** attempt)
                    else:
                        delay = base_delay
                    
                    # 对于 429 错误，尝试从响应头获取 Retry-After
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = float(retry_after)
                                # 限制最大等待时间为 60 秒
                                if delay > 60:
                                    logger.warning(
                                        f"Retry-After too long ({delay}s), not retrying"
                                    )
                                    raise
                            except ValueError:
                                pass
                    
                    # 记录重试信息
                    error_msg, _ = get_network_error_message(e)
                    logger.warning(
                        f"{error_msg} in {func.__name__}, "
                        f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                    )
                    
                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(
                                f"Error in retry callback: {callback_error}"
                            )
                    
                    # 等待后重试
                    await asyncio.sleep(delay)
            
            # 不应该到达这里
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Unexpected error in retry loop for {func.__name__}")
        
        return wrapper
    
    return decorator
