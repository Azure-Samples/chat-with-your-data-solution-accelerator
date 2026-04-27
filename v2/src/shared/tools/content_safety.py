"""Content safety guardrail.

Pillar: Stable Core
Phase: 3

Thin wrapper around `azure.ai.contentsafety.aio.ContentSafetyClient`.
Exposes a single async `screen()` method that returns a typed verdict
the orchestrator / conversation router consumes -- no SDK types leak
out of this module so the rest of the codebase stays SDK-agnostic.

NOT a registry domain (per development_plan.md task #20). Tools are
imported directly:

    from shared.tools.content_safety import ContentSafetyGuard

The client is dependency-injected (constructor takes a built
`ContentSafetyClient`); production wiring builds the singleton in
`backend/app.py` lifespan alongside the LLM provider (ADR 0005).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from azure.ai.contentsafety.aio import ContentSafetyClient


# Severity threshold above which content is flagged. Azure Content
# Safety reports severity 0/2/4/6 (0 = safe, 2 = low, 4 = medium,
# 6 = high). Default trips on `medium` or worse, matching the v1
# default (`enable_content_safety: true` with no per-category tuning).
DEFAULT_SEVERITY_THRESHOLD = 4


class ContentSafetyVerdict(BaseModel):
    """Structured result of a `ContentSafetyGuard.screen()` call."""

    flagged: bool
    categories: dict[str, int] = Field(default_factory=dict)
    triggered: list[str] = Field(default_factory=list)


class ContentSafetyGuard:
    def __init__(
        self,
        client: "ContentSafetyClient",
        *,
        severity_threshold: int = DEFAULT_SEVERITY_THRESHOLD,
    ) -> None:
        if severity_threshold < 0:
            raise ValueError("severity_threshold must be >= 0")
        self._client = client
        self._threshold = severity_threshold

    async def screen(self, text: str) -> ContentSafetyVerdict:
        """Run the input through Azure Content Safety.

        Empty / whitespace-only input is a no-op (returns `flagged=False`)
        -- the SDK rejects empty payloads and we don't want a guard call
        on an idle prompt to error out.
        """
        if not text or not text.strip():
            return ContentSafetyVerdict(flagged=False)
        result = await self._client.analyze_text(
            AnalyzeTextOptions(text=text, categories=list(TextCategory))
        )
        categories: dict[str, int] = {}
        triggered: list[str] = []
        for analysis in result.categories_analysis or []:
            name = str(analysis.category)
            severity = int(analysis.severity or 0)
            categories[name] = severity
            if severity >= self._threshold:
                triggered.append(name)
        return ContentSafetyVerdict(
            flagged=bool(triggered),
            categories=categories,
            triggered=triggered,
        )
