"""
Translation engines package

Provides translation engine implementations for real-time translation.
"""

from engines.translation.base import TranslationEngine
from engines.translation.google_translate import GoogleTranslateEngine

__all__ = [
    'TranslationEngine',
    'GoogleTranslateEngine'
]
