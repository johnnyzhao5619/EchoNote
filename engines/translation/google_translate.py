"""
Google Translate 翻译引擎实现

使用 Google Cloud Translation API 进行文本翻译
"""

import logging
from typing import List
import httpx

from engines.translation.base import TranslationEngine

logger = logging.getLogger(__name__)


class GoogleTranslateEngine(TranslationEngine):
    """Google Translate 引擎实现"""

    # Google Translate 支持的主要语言
    SUPPORTED_LANGUAGES = [
        'zh', 'zh-CN', 'zh-TW',  # 中文
        'en',  # 英语
        'fr',  # 法语
        'de',  # 德语
        'es',  # 西班牙语
        'it',  # 意大利语
        'ja',  # 日语
        'ko',  # 韩语
        'pt',  # 葡萄牙语
        'ru',  # 俄语
        'ar',  # 阿拉伯语
        'hi',  # 印地语
        'nl',  # 荷兰语
        'pl',  # 波兰语
        'tr',  # 土耳其语
        'vi',  # 越南语
        'id',  # 印尼语
        'th',  # 泰语
        'uk',  # 乌克兰语
        'sv',  # 瑞典语
    ]

    def __init__(self, api_key: str, max_retries: int = 3):
        """
        初始化 Google Translate 引擎

        Args:
            api_key: Google Cloud API Key
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.max_retries = max_retries
        base = "https://translation.googleapis.com"
        self.base_url = f"{base}/language/translate/v2"

        # 创建 HTTP 客户端
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={'Content-Type': 'application/json'}
        )

        logger.info("Google Translate engine initialized")

    def get_name(self) -> str:
        """获取引擎名称"""
        return "google-translate"

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return self.SUPPORTED_LANGUAGES.copy()

    async def translate(
        self, text: str, source_lang: str = 'auto',
        target_lang: str = 'en'
    ) -> str:
        """
        翻译文本

        Args:
            text: 待翻译文本
            source_lang: 源语言代码（'auto' 表示自动检测）
            target_lang: 目标语言代码

        Returns:
            str: 翻译后的文本
        """
        if not text or not text.strip():
            return ""

        # 验证目标语言
        if not self.validate_language(target_lang):
            msg = f"Unsupported target language: {target_lang}"
            logger.error(msg)
            raise ValueError(msg)

        # 准备请求参数
        params = {
            'key': self.api_key,
            'q': text,
            'target': target_lang
        }

        # 如果指定了源语言且不是 auto，添加到参数中
        if source_lang != 'auto':
            if not self.validate_language(source_lang):
                msg = f"Unsupported source language: {source_lang}"
                logger.error(msg)
                raise ValueError(msg)
            params['source'] = source_lang

        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Translation attempt {attempt + 1}/"
                    f"{self.max_retries}"
                )

                # 发送请求
                response = await self.client.post(
                    self.base_url,
                    params=params
                )

                # 检查响应状态
                if response.status_code == 200:
                    data = response.json()

                    # 提取翻译结果
                    if 'data' in data and 'translations' in data['data']:
                        translations = data['data']['translations']
                        if translations:
                            translated = translations[0]['translatedText']
                            logger.debug(
                                f"Translation successful: "
                                f"{text[:50]}... -> {translated[:50]}..."
                            )
                            return translated

                    logger.error(f"Unexpected response format: {data}")
                    msg = "Unexpected response format from API"
                    raise ValueError(msg)

                elif response.status_code == 400:
                    # 客户端错误，不重试
                    error_data = response.json()
                    error_msg = error_data.get(
                        'error', {}
                    ).get('message', 'Unknown error')
                    logger.error(
                        f"Google Translate API error (400): {error_msg}"
                    )
                    raise ValueError(f"Translation failed: {error_msg}")

                elif response.status_code == 403:
                    # 认证错误，不重试
                    logger.error(
                        "Google Translate API authentication failed (403)"
                    )
                    msg = "Invalid API key or insufficient permissions"
                    raise ValueError(msg)

                elif response.status_code == 429:
                    # 速率限制，等待后重试
                    logger.warning(
                        "Google Translate API rate limit exceeded (429)"
                    )
                    if attempt < self.max_retries - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    msg = "Translation failed: Rate limit exceeded"
                    raise ValueError(msg)

                else:
                    # 其他错误，重试
                    logger.warning(
                        f"Google Translate API error "
                        f"({response.status_code})"
                    )
                    if attempt < self.max_retries - 1:
                        import asyncio
                        await asyncio.sleep(1)
                        continue
                    msg = (
                        f"Translation failed with status code: "
                        f"{response.status_code}"
                    )
                    raise ValueError(msg)

            except httpx.RequestError as e:
                # 网络错误，重试
                logger.warning(f"Network error during translation: {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    import asyncio
                    await asyncio.sleep(1)
                    continue

            except Exception as e:
                # 其他错误
                logger.error(f"Translation error: {e}")
                raise

        # 所有重试都失败
        if last_error:
            msg = (
                f"Translation failed after {self.max_retries} "
                f"attempts: {last_error}"
            )
            raise ValueError(msg)
        else:
            msg = f"Translation failed after {self.max_retries} attempts"
            raise ValueError(msg)

    async def detect_language(self, text: str) -> str:
        """
        检测文本语言

        Args:
            text: 待检测文本

        Returns:
            str: 检测到的语言代码
        """
        if not text or not text.strip():
            return "unknown"

        try:
            # 使用 Google Translate API 的语言检测功能
            params = {
                'key': self.api_key,
                'q': text
            }

            response = await self.client.post(
                f"{self.base_url}/detect",
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'detections' in data['data']:
                    detections = data['data']['detections']
                    if detections and detections[0]:
                        language = detections[0][0]['language']
                        confidence = detections[0][0].get('confidence', 0)
                        logger.debug(
                            f"Detected language: {language} "
                            f"(confidence: {confidence})"
                        )
                        return language

            logger.warning("Language detection failed")
            return "unknown"

        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return "unknown"

    def get_config_schema(self) -> dict:
        """获取配置 Schema"""
        return {
            'type': 'object',
            'properties': {
                'api_key': {
                    'type': 'string',
                    'description': 'Google Cloud API Key'
                },
                'max_retries': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 10,
                    'default': 3,
                    'description': '最大重试次数'
                }
            },
            'required': ['api_key']
        }

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
        logger.info("Google Translate engine closed")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
