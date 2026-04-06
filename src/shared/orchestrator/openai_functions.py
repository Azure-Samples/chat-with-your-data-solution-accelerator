"""OpenAI Functions orchestrator using modern bind_tools pattern."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import OrchestratorBase

logger = logging.getLogger(__name__)


class OpenAIFunctionsOrchestrator(OrchestratorBase):
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> AsyncIterator[str]:
        # TODO: Phase 2.5 — implement bind_tools pattern
        raise NotImplementedError("OpenAI Functions orchestrator not yet implemented")
        yield  # noqa: unreachable — makes this an async generator
