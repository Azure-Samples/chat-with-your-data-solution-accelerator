"""Database client ABC.

Pillar: Stable Core
Phase: 4

Every concrete database client (`cosmosdb` task #27, `postgres` task
#28, future swap-ins like Redis) inherits from `BaseDatabaseClient`
and self-registers via `@registry.register("<key>")`.

Per Q10 design: chat-history CRUD lives **on the database client** --
there is no separate `chat_history` provider domain. A future expansion
(vector-store metadata, config storage) layers more methods on the same
client.

Constructors take `AppSettings` + an `AsyncTokenCredential` (managed
identity in production, AzureCli in local dev) -- never an API key
or connection string with embedded secrets (Hard Rule #2).

Lifecycle: clients hold an SDK connection (CosmosClient, asyncpg pool).
Callers invoke `await client.aclose()` during shutdown -- the FastAPI
lifespan in `backend/app.py` does this for the cached singleton.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings
    from shared.types import ChatMessage, Conversation, MessageRecord


class BaseDatabaseClient(ABC):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
    ) -> None:
        self._settings = settings
        self._credential = credential

    # ---- Conversations --------------------------------------------------

    @abstractmethod
    async def list_conversations(
        self, user_id: str
    ) -> "Sequence[Conversation]":
        """Return all conversations owned by `user_id`, newest first."""

    @abstractmethod
    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> "Conversation | None":
        """Return one conversation or `None` if missing / not owned."""

    @abstractmethod
    async def create_conversation(
        self, user_id: str, title: str
    ) -> "Conversation":
        """Create a new empty conversation; returns the stored row."""

    @abstractmethod
    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> "Conversation":
        """Rename `conversation_id`. Raises `KeyError` if not found."""

    @abstractmethod
    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        """Delete `conversation_id` and all its messages. Idempotent."""

    # ---- Messages -------------------------------------------------------

    @abstractmethod
    async def list_messages(
        self, conversation_id: str, user_id: str
    ) -> "Sequence[MessageRecord]":
        """Return all messages in `conversation_id`, oldest first."""

    @abstractmethod
    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        message: "ChatMessage",
    ) -> "MessageRecord":
        """Append `message` to `conversation_id`. Returns the stored row
        (with assigned id + timestamp)."""

    @abstractmethod
    async def set_feedback(
        self,
        message_id: str,
        user_id: str,
        feedback: str,
    ) -> None:
        """Attach / overwrite feedback (e.g. ``"positive"``,
        ``"negative"``) on `message_id`."""

    # ---- Lifecycle ------------------------------------------------------

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default no-op."""
        return None
