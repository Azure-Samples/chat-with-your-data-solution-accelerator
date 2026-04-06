"""LangGraph-based agent orchestrator.

Replaces the deprecated ZeroShotAgent + LLMChain + AgentExecutor pattern
with a modern LangGraph StateGraph using tool-calling.

Uses: langchain, langgraph, langchain-openai
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import OrchestratorBase

logger = logging.getLogger(__name__)


class LangGraphAgent(OrchestratorBase):
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> AsyncIterator[str]:
        # TODO: Phase 2.5 — implement LangGraph StateGraph with ToolNodes
        raise NotImplementedError("LangGraph agent not yet implemented")
        yield  # noqa: unreachable — makes this an async generator
