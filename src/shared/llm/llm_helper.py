"""LLM helper: wraps Azure AI models and embeddings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)


class LLMHelper:
    """Provides configured chat models, embeddings, and Foundry agent nodes."""

    def __init__(self, settings: EnvSettings) -> None:
        self.settings = settings

    def get_chat_model(self):
        # TODO: Phase 2.5 — AzureAIOpenAIApiChatModel from langchain-azure-ai
        raise NotImplementedError

    def get_embeddings_model(self):
        # TODO: Phase 2.5 — embeddings via langchain-azure-ai
        raise NotImplementedError

    def get_foundry_agent_node(self):
        # TODO: Phase 2.5 — AgentServiceFactory.get_agent_node()
        raise NotImplementedError
