"""CosmosDB conversation client for chat history."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)


class CosmosConversationClient:
    def __init__(self, settings: EnvSettings) -> None:
        self.settings = settings
        # TODO: Phase 2 — initialize CosmosClient

    async def create_conversation(self, user_id: str, title: str = "") -> dict:
        raise NotImplementedError

    async def get_conversations(self, user_id: str, limit: int = 25, offset: int = 0) -> list[dict]:
        raise NotImplementedError

    async def get_conversation(self, user_id: str, conversation_id: str) -> list[dict]:
        raise NotImplementedError

    async def add_message(self, conversation_id: str, role: str, content: str) -> dict:
        raise NotImplementedError

    async def update_conversation_title(self, conversation_id: str, title: str) -> None:
        raise NotImplementedError

    async def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        raise NotImplementedError

    async def delete_all_conversations(self, user_id: str) -> None:
        raise NotImplementedError
