# SPDX-License-Identifier: Apache-2.0
"""Workspace summary generation services."""

from __future__ import annotations

from engines.text_ai.base import TextAIRequest
from engines.text_ai.extractive_engine import ExtractiveEngine
from utils.app_initializer import create_text_ai_engine


class SummaryService:
    """Generate summaries for workspace items and persist them as assets."""

    def __init__(self, workspace_manager, *, settings_manager=None, model_manager=None) -> None:
        self.workspace_manager = workspace_manager
        self.settings_manager = settings_manager
        self.model_manager = model_manager
        self.extractive_engine = ExtractiveEngine()

    def summarize(self, item_id: str, strategy: str = "extractive") -> dict:
        text = self.workspace_manager.get_item_text_content(item_id)
        if not text.strip():
            raise ValueError("Workspace item does not contain readable text")

        preferences = self._get_preferences()
        effective_strategy = strategy or preferences["default_summary_strategy"]
        if effective_strategy == "extractive":
            summary_text = self.extractive_engine.generate(TextAIRequest(text=text))
            self._mark_model_used("extractive-default")
        else:
            summary_text = self._generate_abstractive_summary(text, preferences)

        asset = self.workspace_manager.save_text_asset(
            item_id,
            "summary",
            summary_text,
            filename=f"summary_{effective_strategy}.md",
        )
        return {
            "summary_asset_id": asset.id,
            "summary_text": summary_text,
            "strategy": effective_strategy,
        }

    def _generate_abstractive_summary(self, text: str, preferences: dict) -> str:
        if self.model_manager is None or not hasattr(self.model_manager, "get_text_ai_model"):
            return self.extractive_engine.generate(TextAIRequest(text=text))

        model_id = preferences["default_summary_model"]
        try:
            engine = create_text_ai_engine(self.model_manager, model_id)
            prompt = (
                "Write a concise meeting summary with the most important facts and decisions.\n\n"
                f"{text}"
            )
            generated = engine.generate(TextAIRequest(text=text, prompt=prompt, max_output_tokens=256))
            self._mark_model_used(model_id)
            return generated
        except Exception:
            self._mark_model_used("extractive-default")
            return self.extractive_engine.generate(TextAIRequest(text=text))

    def _get_preferences(self) -> dict:
        defaults = {
            "default_summary_strategy": "extractive",
            "default_summary_model": "flan-t5-small-int8",
        }
        if self.settings_manager is None:
            return defaults
        loader = getattr(self.settings_manager, "get_workspace_ai_preferences", None)
        if not callable(loader):
            return defaults
        loaded = loader()
        if not isinstance(loaded, dict):
            return defaults
        merged = dict(defaults)
        merged.update(loaded)
        return merged

    def _mark_model_used(self, model_id: str) -> None:
        if self.model_manager is None:
            return
        marker = getattr(self.model_manager, "mark_text_ai_model_used", None)
        if callable(marker):
            marker(model_id)
