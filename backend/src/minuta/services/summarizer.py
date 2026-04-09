"""LLM summarization service with multiple provider support."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx
from openai import AsyncAzureOpenAI

from minuta.models.config import AppSettings
from minuta.models.meeting import SummarySection

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist ein professioneller Meeting-Assistent. Analysiere das folgende Meeting-Transkript und erstelle eine strukturierte Zusammenfassung auf Deutsch (Schweizer Deutsch Konventionen: ss statt ß).

Antworte im folgenden JSON-Format:
{
  "title": "Kurzer Meeting-Titel",
  "key_points": ["Hauptpunkt 1", "Hauptpunkt 2"],
  "action_items": ["Aktion 1 (verantwortlich: Person)", "Aktion 2"],
  "decisions": ["Entscheidung 1", "Entscheidung 2"],
  "sections": [{"heading": "Abschnitt 1", "content": "Zusammenfassung..."}],
  "participants_mentioned": ["Name1", "Name2"]
}

Halte die Zusammenfassung professionell, praezise und actionable."""


@dataclass
class SummaryResult:
    title: str = ""
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    sections: list[SummarySection] = field(default_factory=list)
    participants_mentioned: list[str] = field(default_factory=list)
    full_text: str = ""
    model: str = ""
    token_count: int = 0


class BaseSummarizer(ABC):
    @abstractmethod
    async def summarize(
        self, transcript: str, language: str = "de", model_override: str | None = None
    ) -> SummaryResult:
        ...


class OllamaSummarizer(BaseSummarizer):
    def __init__(self, base_url: str, model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def summarize(
        self, transcript: str, language: str = "de", model_override: str | None = None
    ) -> SummaryResult:
        model = model_override or self.model
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Meeting-Transkript:\n\n{transcript}"},
                    ],
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["message"]["content"]
            return _parse_summary_json(content, model)


class AzureSummarizer(BaseSummarizer):
    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str, timeout: int):
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self.deployment = deployment
        self.timeout = timeout

    async def summarize(
        self, transcript: str, language: str = "de", model_override: str | None = None
    ) -> SummaryResult:
        model = model_override or self.deployment
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Meeting-Transkript:\n\n{transcript}"},
            ],
            response_format={"type": "json_object"},
            timeout=self.timeout,
        )
        content = response.choices[0].message.content or "{}"
        result = _parse_summary_json(content, model)
        result.token_count = response.usage.total_tokens if response.usage else 0
        return result


class LangdockSummarizer(BaseSummarizer):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def summarize(
        self, transcript: str, language: str = "de", model_override: str | None = None
    ) -> SummaryResult:
        model = model_override or self.model
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Meeting-Transkript:\n\n{transcript}"},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            result = _parse_summary_json(content, model)
            result.token_count = data.get("usage", {}).get("total_tokens", 0)
            return result


def _parse_summary_json(content: str, model: str) -> SummaryResult:
    """Parse LLM JSON response into SummaryResult."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Failed to parse summary JSON, using raw text")
        return SummaryResult(
            title="Meeting Zusammenfassung",
            full_text=content,
            model=model,
        )

    sections = [
        SummarySection(heading=s.get("heading", ""), content=s.get("content", ""))
        for s in data.get("sections", [])
    ]

    # Build full text with **bold** headings (compatible with N8N Notion parser)
    lines = []
    if data.get("key_points"):
        lines.append("**Hauptpunkte**")
        for p in data["key_points"]:
            lines.append(f"- {p}")
    if data.get("action_items"):
        lines.append("")
        lines.append("**Action Items**")
        for a in data["action_items"]:
            lines.append(f"- {a}")
    if data.get("decisions"):
        lines.append("")
        lines.append("**Entscheidungen**")
        for d in data["decisions"]:
            lines.append(f"- {d}")
    for sec in sections:
        lines.append("")
        lines.append(f"**{sec.heading}**")
        lines.append(sec.content)

    return SummaryResult(
        title=data.get("title", "Meeting Zusammenfassung"),
        key_points=data.get("key_points", []),
        action_items=data.get("action_items", []),
        decisions=data.get("decisions", []),
        sections=sections,
        participants_mentioned=data.get("participants_mentioned", []),
        full_text="\n".join(lines),
        model=model,
    )


def create_summarizer(provider: str, settings: AppSettings) -> BaseSummarizer:
    """Factory for creating the right summarizer based on provider."""
    if provider == "ollama":
        cfg = settings.summarization.ollama
        return OllamaSummarizer(cfg.base_url, cfg.model, cfg.timeout_seconds)
    elif provider == "azure":
        cfg = settings.summarization.azure
        return AzureSummarizer(
            cfg.endpoint, cfg.api_key, cfg.deployment, cfg.api_version, cfg.timeout_seconds
        )
    elif provider == "langdock":
        cfg = settings.summarization.langdock
        return LangdockSummarizer(cfg.base_url, cfg.api_key, cfg.model, cfg.timeout_seconds)
    else:
        raise ValueError(f"Unknown summarization provider: {provider}")
