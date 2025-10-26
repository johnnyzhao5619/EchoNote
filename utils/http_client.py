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
可重试的 HTTP 客户端

提供带有自动重试机制的 HTTP 客户端，支持指数退避和速率限制处理。
"""

import logging
import time
from typing import Iterable, Optional, Set
import httpx


logger = logging.getLogger(__name__)


class RetryableHttpClient:
    """
    可重试的 HTTP 客户端
    
    包装 httpx.Client，提供自动重试机制：
    - 指数退避重试策略
    - 速率限制处理（429 错误）
    - 超时处理
    - 可重试错误类型判断
    """
    
    # 可重试的 HTTP 状态码
    RETRYABLE_STATUS_CODES = {
        408,  # Request Timeout
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }

    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
        base_delay: float = 1.0,
        max_retry_after: Optional[float] = 60.0,
        retryable_status_codes: Optional[Iterable[int]] = None,
        **client_kwargs
    ):
        """
        初始化可重试的 HTTP 客户端
        
        Args:
            max_retries: 最大重试次数（默认 3）
            timeout: 请求超时时间（秒，默认 30）
            base_delay: 基础延迟时间（秒，默认 1）
            max_retry_after: 429 响应允许的最大 Retry-After 秒数，None 表示不限制
            retryable_status_codes: 自定义可重试的 HTTP 状态码集合，默认为类属性
            **client_kwargs: 传递给 httpx.Client 的其他参数
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_delay = base_delay
        self.max_retry_after = max_retry_after
        self.retryable_status_codes: Set[int] = (
            set(retryable_status_codes)
            if retryable_status_codes is not None
            else set(self.RETRYABLE_STATUS_CODES)
        )
        
        # 设置默认超时
        if 'timeout' not in client_kwargs:
            client_kwargs['timeout'] = timeout
        
        self.client = httpx.Client(**client_kwargs)
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    def close(self):
        """关闭客户端"""
        self.client.close()
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        计算指数退避延迟时间
        
        Args:
            attempt: 当前重试次数（从 0 开始）
        
        Returns:
            延迟时间（秒）
        """
        # 指数退避：1s, 2s, 4s, 8s, ...
        return self.base_delay * (2 ** attempt)
    
    def _is_retryable_error(
        self,
        error: Exception,
        response: Optional[httpx.Response] = None
    ) -> bool:
        """
        判断错误是否可重试
        
        Args:
            error: 异常对象
            response: HTTP 响应对象（如果有）
        
        Returns:
            是否可重试
        """
        # 网络错误可重试
        if isinstance(error, (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.NetworkError
        )):
            return True
        
        # HTTP 状态错误
        if isinstance(error, httpx.HTTPStatusError):
            if response and response.status_code in self.retryable_status_codes:
                return True
        
        return False
    
    def _get_retry_after(self, response: httpx.Response) -> Optional[float]:
        """
        从响应头获取 Retry-After 时间
        
        Args:
            response: HTTP 响应对象
        
        Returns:
            重试等待时间（秒），如果没有则返回 None
        """
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        
        retry_after = response.headers.get('Retry-After')
        
        if retry_after:
            try:
                # Retry-After 可能是秒数
                return float(retry_after)
            except ValueError:
                # 或者是 HTTP 日期格式
                try:
                    retry_date = parsedate_to_datetime(retry_after)
                    now = datetime.now(timezone.utc)
                    delta = (retry_date - now).total_seconds()
                    return max(0, delta)  # 确保不返回负数
                except Exception as e:
                    logger.warning(
                        f"Failed to parse Retry-After header: "
                        f"{retry_after}, error: {e}"
                    )
        
        return None
    
    def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        发送 HTTP 请求，带自动重试
        
        Args:
            method: HTTP 方法（GET, POST, etc.）
            url: 请求 URL
            **kwargs: 传递给 httpx.request 的其他参数
        
        Returns:
            HTTP 响应对象
        
        Raises:
            httpx.HTTPError: 请求失败且重试次数用尽
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 发送请求
                response = self.client.request(method, url, **kwargs)
                
                # 检查 HTTP 状态
                response.raise_for_status()
                
                # 成功，返回响应
                if attempt > 0:
                    logger.info(
                        f"Request succeeded after {attempt} retries: "
                        f"{method} {url}"
                    )
                
                return response
            
            except httpx.HTTPStatusError as e:
                last_error = e
                response = e.response
                
                # 检查是否可重试
                if not self._is_retryable_error(e, response):
                    logger.error(
                        f"Non-retryable HTTP error: "
                        f"{response.status_code} {method} {url}"
                    )
                    raise
                
                # 如果是最后一次尝试，抛出异常
                if attempt >= self.max_retries:
                    logger.error(
                        f"Max retries exceeded: {method} {url}"
                    )
                    raise
                
                # 处理速率限制（429）
                if response.status_code == 429:
                    retry_after = self._get_retry_after(response)
                    if retry_after:
                        if (
                            self.max_retry_after is not None
                            and retry_after > self.max_retry_after
                        ):
                            logger.error(
                                "Rate limit retry time too long (%ss > %ss), not retrying",
                                retry_after,
                                self.max_retry_after,
                            )
                            raise
                        delay = retry_after
                        logger.warning(
                            f"Rate limited (429), waiting {delay}s "
                            f"before retry {attempt + 1}/{self.max_retries}"
                        )
                    else:
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            f"Rate limited (429), using exponential backoff "
                            f"{delay}s before retry {attempt + 1}/{self.max_retries}"
                        )
                else:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"HTTP error {response.status_code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                
                time.sleep(delay)
            
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.NetworkError
            ) as e:
                last_error = e
                
                # 如果是最后一次尝试，抛出异常
                if attempt >= self.max_retries:
                    logger.error(
                        f"Max retries exceeded for network error: {method} {url}"
                    )
                    raise
                
                # 计算延迟并重试
                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Network error: {type(e).__name__}, retrying in {delay}s "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                
                time.sleep(delay)
        
        # 不应该到达这里，但为了安全起见
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Unexpected error in retry loop")
    
    def get(self, url: str, **kwargs) -> httpx.Response:
        """发送 GET 请求"""
        return self.request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> httpx.Response:
        """发送 POST 请求"""
        return self.request('POST', url, **kwargs)
    
    def put(self, url: str, **kwargs) -> httpx.Response:
        """发送 PUT 请求"""
        return self.request('PUT', url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> httpx.Response:
        """发送 DELETE 请求"""
        return self.request('DELETE', url, **kwargs)
    
    def patch(self, url: str, **kwargs) -> httpx.Response:
        """发送 PATCH 请求"""
        return self.request('PATCH', url, **kwargs)


class AsyncRetryableHttpClient:
    """
    异步可重试的 HTTP 客户端
    
    包装 httpx.AsyncClient，提供自动重试机制。
    """
    
    # 可重试的 HTTP 状态码
    RETRYABLE_STATUS_CODES = RetryableHttpClient.RETRYABLE_STATUS_CODES
    
    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
        base_delay: float = 1.0,
        max_retry_after: Optional[float] = 60.0,
        retryable_status_codes: Optional[Iterable[int]] = None,
        **client_kwargs
    ):
        """
        初始化异步可重试的 HTTP 客户端
        
        Args:
            max_retries: 最大重试次数（默认 3）
            timeout: 请求超时时间（秒，默认 30）
            base_delay: 基础延迟时间（秒，默认 1）
            max_retry_after: 429 响应允许的最大 Retry-After 秒数，None 表示不限制
            retryable_status_codes: 自定义可重试的 HTTP 状态码集合，默认为类属性
            **client_kwargs: 传递给 httpx.AsyncClient 的其他参数
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_delay = base_delay
        self.max_retry_after = max_retry_after
        self.retryable_status_codes: Set[int] = (
            set(retryable_status_codes)
            if retryable_status_codes is not None
            else set(self.RETRYABLE_STATUS_CODES)
        )
        
        # 设置默认超时
        if 'timeout' not in client_kwargs:
            client_kwargs['timeout'] = timeout
        
        self.client = httpx.AsyncClient(**client_kwargs)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算指数退避延迟时间"""
        return self.base_delay * (2 ** attempt)
    
    def _is_retryable_error(
        self,
        error: Exception,
        response: Optional[httpx.Response] = None
    ) -> bool:
        """判断错误是否可重试"""
        if isinstance(error, (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.NetworkError
        )):
            return True
        
        if isinstance(error, httpx.HTTPStatusError):
            if response and response.status_code in self.retryable_status_codes:
                return True
        
        return False
    
    def _get_retry_after(self, response: httpx.Response) -> Optional[float]:
        """从响应头获取 Retry-After 时间"""
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        
        retry_after = response.headers.get('Retry-After')
        
        if retry_after:
            try:
                # Retry-After 可能是秒数
                return float(retry_after)
            except ValueError:
                # 或者是 HTTP 日期格式
                try:
                    retry_date = parsedate_to_datetime(retry_after)
                    now = datetime.now(timezone.utc)
                    delta = (retry_date - now).total_seconds()
                    return max(0, delta)  # 确保不返回负数
                except Exception as e:
                    logger.warning(
                        f"Failed to parse Retry-After header: "
                        f"{retry_after}, error: {e}"
                    )
        
        return None
    
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        发送异步 HTTP 请求，带自动重试
        
        Args:
            method: HTTP 方法（GET, POST, etc.）
            url: 请求 URL
            **kwargs: 传递给 httpx.request 的其他参数
        
        Returns:
            HTTP 响应对象
        
        Raises:
            httpx.HTTPError: 请求失败且重试次数用尽
        """
        import asyncio
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 发送请求
                response = await self.client.request(method, url, **kwargs)
                
                # 检查 HTTP 状态
                response.raise_for_status()
                
                # 成功，返回响应
                if attempt > 0:
                    logger.info(
                        f"Request succeeded after {attempt} retries: "
                        f"{method} {url}"
                    )
                
                return response
            
            except httpx.HTTPStatusError as e:
                last_error = e
                response = e.response
                
                # 检查是否可重试
                if not self._is_retryable_error(e, response):
                    logger.error(
                        f"Non-retryable HTTP error: "
                        f"{response.status_code} {method} {url}"
                    )
                    raise
                
                # 如果是最后一次尝试，抛出异常
                if attempt >= self.max_retries:
                    logger.error(
                        f"Max retries exceeded: {method} {url}"
                    )
                    raise
                
                # 处理速率限制（429）
                if response.status_code == 429:
                    retry_after = self._get_retry_after(response)
                    if retry_after:
                        if (
                            self.max_retry_after is not None
                            and retry_after > self.max_retry_after
                        ):
                            logger.error(
                                "Rate limit retry time too long (%ss > %ss), not retrying",
                                retry_after,
                                self.max_retry_after,
                            )
                            raise
                        delay = retry_after
                        logger.warning(
                            f"Rate limited (429), waiting {delay}s "
                            f"before retry {attempt + 1}/{self.max_retries}"
                        )
                    else:
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            f"Rate limited (429), using exponential backoff "
                            f"{delay}s before retry {attempt + 1}/{self.max_retries}"
                        )
                else:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"HTTP error {response.status_code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                
                await asyncio.sleep(delay)
            
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.NetworkError
            ) as e:
                last_error = e
                
                # 如果是最后一次尝试，抛出异常
                if attempt >= self.max_retries:
                    logger.error(
                        f"Max retries exceeded for network error: {method} {url}"
                    )
                    raise
                
                # 计算延迟并重试
                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Network error: {type(e).__name__}, retrying in {delay}s "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                
                await asyncio.sleep(delay)
        
        # 不应该到达这里，但为了安全起见
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Unexpected error in retry loop")
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """发送异步 GET 请求"""
        return await self.request('GET', url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """发送异步 POST 请求"""
        return await self.request('POST', url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """发送异步 PUT 请求"""
        return await self.request('PUT', url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """发送异步 DELETE 请求"""
        return await self.request('DELETE', url, **kwargs)
    
    async def patch(self, url: str, **kwargs) -> httpx.Response:
        """发送异步 PATCH 请求"""
        return await self.request('PATCH', url, **kwargs)
