"""Database factory for chat history: CosmosDB or PostgreSQL.

Both backends are installed together so the admin UI
can switch between them at runtime without redeploying.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cosmosdb import CosmosConversationClient
from .postgres import PostgresConversationClient

if TYPE_CHECKING:
    from src.shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)

_BACKENDS = {
    "cosmosdb": CosmosConversationClient,
    "postgresql": PostgresConversationClient,
}


class DatabaseFactory:
    @staticmethod
    def get_client(settings: EnvSettings):
        db_type = settings.database.database_type.lower()
        client_cls = _BACKENDS.get(db_type)
        if client_cls is None:
            raise ValueError(
                f"Unsupported database type: {db_type}. "
                f"Available: {list(_BACKENDS.keys())}"
            )
        return client_cls(settings)

    @staticmethod
    def get_available_backends() -> list[str]:
        """Return the list of backend names for the admin UI."""
        return list(_BACKENDS.keys())
