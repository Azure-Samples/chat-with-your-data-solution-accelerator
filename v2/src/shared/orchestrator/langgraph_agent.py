"""LangGraph-based agent orchestrator.

Replaces the deprecated ZeroShotAgent + LLMChain + AgentExecutor pattern
with a modern LangGraph StateGraph using tool-calling.

Uses: langchain, langgraph, langchain-openai
"""

from __future__ import annotations

import logging

from .base import OrchestratorBase

logger = logging.getLogger(__name__)


class LangGraphAgent(OrchestratorBase):
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> list[dict]:
        # TODO: Phase 2.5 — implement LangGraph StateGraph with ToolNodes
        raise NotImplementedError("LangGraph agent not yet implemented")
