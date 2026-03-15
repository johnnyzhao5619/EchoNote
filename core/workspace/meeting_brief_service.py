# SPDX-License-Identifier: Apache-2.0
"""Structured meeting brief generation for workspace items."""

from __future__ import annotations

import re

from engines.text_ai.base import TextAIRequest
from engines.text_ai.extractive_engine import ExtractiveEngine
from utils.app_initializer import create_text_ai_engine

from core.workspace.summary_service import SummaryService


class MeetingBriefService:
    """Generate structured meeting outputs and persist them as workspace assets."""

    def __init__(self, workspace_manager, *, settings_manager=None, model_manager=None) -> None:
        self.workspace_manager = workspace_manager
        self.settings_manager = settings_manager
        self.model_manager = model_manager
        self.summary_service = SummaryService(
            workspace_manager,
            settings_manager=settings_manager,
            model_manager=model_manager,
        )
        self.extractive_engine = ExtractiveEngine()

    def generate(self, item_id: str, template: str | None = None) -> dict:
        text = self.workspace_manager.get_item_text_content(item_id)
        if not text.strip():
            raise ValueError("Workspace item does not contain readable text")

        preferences = self._get_preferences()
        effective_template = template or preferences["default_meeting_template"]
        summary_result = self.summary_service.summarize(
            item_id,
            strategy=preferences["default_summary_strategy"],
        )
        sections = self._build_sections(text, preferences, effective_template)

        meeting_brief_text = "\n\n".join(
            [
                "# Summary",
                summary_result["summary_text"],
                "# Decisions",
                sections["decisions"],
                "# Action Items",
                sections["action_items"],
                "# Next Steps",
                sections["next_steps"],
            ]
        )

        meeting_brief_asset = self.workspace_manager.save_text_asset(
            item_id,
            "meeting_brief",
            meeting_brief_text,
            filename="meeting_brief.md",
        )
        decisions_asset = self.workspace_manager.save_text_asset(
            item_id,
            "decisions",
            sections["decisions"],
            filename="decisions.md",
        )
        action_items_asset = self.workspace_manager.save_text_asset(
            item_id,
            "action_items",
            sections["action_items"],
            filename="action_items.md",
        )
        next_steps_asset = self.workspace_manager.save_text_asset(
            item_id,
            "next_steps",
            sections["next_steps"],
            filename="next_steps.md",
        )

        return {
            "summary_asset_id": summary_result["summary_asset_id"],
            "meeting_brief_asset_id": meeting_brief_asset.id,
            "decisions_asset_id": decisions_asset.id,
            "action_items_asset_id": action_items_asset.id,
            "next_steps_asset_id": next_steps_asset.id,
            "template": effective_template,
        }

    def _build_sections(self, text: str, preferences: dict, template: str) -> dict:
        generated = self._try_generate_with_gguf(text, preferences, template)
        if generated is not None:
            return generated

        sentences = self._split_sentences(text)
        decisions = self._select_sentences(
            sentences,
            keywords=("decide", "decided", "decision", "agreed", "决定", "结论"),
        )
        action_items = self._select_sentences(
            sentences,
            keywords=("will", "action", "todo", "follow up", "负责", "需要"),
        )
        next_steps = self._select_sentences(
            sentences,
            keywords=("next", "follow-up", "review", "下一步", "后续"),
        )

        return {
            "decisions": decisions or "No explicit decisions detected.",
            "action_items": action_items or "No explicit action items detected.",
            "next_steps": next_steps or "No explicit next steps detected.",
        }

    def _try_generate_with_gguf(self, text: str, preferences: dict, template: str) -> dict | None:
        if self.model_manager is None or not hasattr(self.model_manager, "get_text_ai_model"):
            return None

        model_id = preferences["default_meeting_model"]
        runtime_command = preferences.get("gguf_runtime_command") or []
        if not runtime_command or model_id == "extractive-default":
            return None

        try:
            engine = create_text_ai_engine(
                self.model_manager,
                model_id,
                {"command": runtime_command},
            )
            prompt = (
                "Create a structured meeting brief with sections: Summary, Decisions, "
                "Action Items, Next Steps.\n"
                f"Template: {template}\n\n{text}"
            )
            generated = engine.generate(TextAIRequest(text=text, prompt=prompt, max_output_tokens=512))
            marker = getattr(self.model_manager, "mark_text_ai_model_used", None)
            if callable(marker):
                marker(model_id)
            parsed = self._parse_structured_output(generated)
            return parsed or None
        except Exception:
            return None

    def _parse_structured_output(self, text: str) -> dict | None:
        if not text.strip():
            return None
        sections = {
            "decisions": self._extract_section(text, "decisions"),
            "action_items": self._extract_section(text, "action items"),
            "next_steps": self._extract_section(text, "next steps"),
        }
        if not any(sections.values()):
            return None
        return {
            "decisions": sections["decisions"] or "No explicit decisions detected.",
            "action_items": sections["action_items"] or "No explicit action items detected.",
            "next_steps": sections["next_steps"] or "No explicit next steps detected.",
        }

    def _extract_section(self, text: str, name: str) -> str:
        pattern = rf"{name}\s*:?(.*?)(?:\n[A-Z][A-Za-z ]+:|\Z)"
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    def _split_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[。！？.!?])\s+|\n+", text)
        return [part.strip() for part in parts if part and part.strip()]

    def _select_sentences(self, sentences: list[str], *, keywords: tuple[str, ...]) -> str:
        matches = [
            sentence
            for sentence in sentences
            if any(keyword.lower() in sentence.lower() for keyword in keywords)
        ]
        if matches:
            return "\n".join(matches[:4])
        return self.extractive_engine.generate(TextAIRequest(text="\n".join(sentences[:4])))

    def _get_preferences(self) -> dict:
        defaults = {
            "default_summary_strategy": "extractive",
            "default_meeting_model": "extractive-default",
            "default_meeting_template": "standard",
            "gguf_runtime_command": [],
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
