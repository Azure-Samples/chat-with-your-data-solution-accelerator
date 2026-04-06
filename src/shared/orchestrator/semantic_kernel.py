"""Semantic Kernel orchestration strategy.

Uses: semantic-kernel (Kernel, plugins, FunctionChoiceBehavior)
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import OrchestratorBase

logger = logging.getLogger(__name__)


class SemanticKernelOrchestrator(OrchestratorBase):
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> AsyncIterator[str]:
        # TODO: Phase 2.5 — Semantic Kernel strategy
        raise NotImplementedError("Semantic Kernel orchestrator not yet implemented")
        yield  # noqa: unreachable
