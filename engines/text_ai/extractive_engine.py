# SPDX-License-Identifier: Apache-2.0
"""Deterministic extractive summarization engine."""

from __future__ import annotations

import re
from collections import Counter

from engines.text_ai.base import TextAIEngine, TextAIRequest


class ExtractiveEngine(TextAIEngine):
    """Lightweight sentence-ranking summarizer that does not require model weights."""

    _STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
    }

    def __init__(self) -> None:
        super().__init__("extractive-default", None)

    def generate(self, request: TextAIRequest) -> str:
        text = (request.text or "").strip()
        if not text:
            return ""

        sentences = self._split_sentences(text)
        if len(sentences) <= 3:
            return "\n".join(sentences)

        word_scores = Counter(
            token
            for token in self._tokenize(text)
            if token not in self._STOP_WORDS and len(token) > 1
        )
        ranked = []
        for index, sentence in enumerate(sentences):
            tokens = self._tokenize(sentence)
            score = sum(word_scores.get(token, 0) for token in tokens)
            score += max(len(sentences) - index, 1) * 0.1
            ranked.append((score, index, sentence))

        top_sentences = sorted(ranked, key=lambda item: item[0], reverse=True)[:3]
        top_sentences.sort(key=lambda item: item[1])
        return "\n".join(sentence for _, _, sentence in top_sentences)

    def _split_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[。！？.!?])\s+|\n+", text)
        return [part.strip() for part in parts if part and part.strip()]

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text.lower())
