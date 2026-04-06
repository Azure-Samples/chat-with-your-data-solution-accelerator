"""Azure AI Agent Service orchestration strategy.

Uses the azure-ai-agents SDK to invoke managed serverless agents
in Azure AI Foundry with built-in tool execution.
"""

from __future__ import annotations

import logging

from .base import OrchestratorBase

logger = logging.getLogger(__name__)


class AzureAgentsOrchestrator(OrchestratorBase):
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> list[dict]:
        # TODO: Phase 2.5 — implement Azure AI Agent Service orchestration
        raise NotImplementedError("Azure AI Agent Service orchestrator not yet implemented")
