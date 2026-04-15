"""Orchestrator router: dispatches to the configured strategy.

All orchestrators are installed together so the admin UI
can switch between them at runtime without redeploying.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .azure_agents import AzureAgentsOrchestrator
from .base import OrchestratorBase
from .langgraph_agent import LangGraphAgent
from .openai_functions import OpenAIFunctionsOrchestrator
from .semantic_kernel import SemanticKernelOrchestrator

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)

_STRATEGIES: dict[str, type[OrchestratorBase]] = {
    "langchain": LangGraphAgent,
    "openai_function": OpenAIFunctionsOrchestrator,
    "semantic_kernel": SemanticKernelOrchestrator,
    "azure_agents": AzureAgentsOrchestrator,
}


class Orchestrator:
    @staticmethod
    def get_strategy(settings: EnvSettings) -> OrchestratorBase:
        strategy_name = settings.orchestration_strategy
        strategy_cls = _STRATEGIES.get(strategy_name)
        if strategy_cls is None:
            raise ValueError(
                f"Unknown orchestration strategy: {strategy_name}. "
                f"Available: {list(_STRATEGIES.keys())}"
            )
        logger.info("Using orchestration strategy: %s", strategy_name)
        return strategy_cls(settings)

    @staticmethod
    def get_available_strategies() -> list[str]:
        """Return the list of strategy names for the admin UI."""
        return list(_STRATEGIES.keys())
