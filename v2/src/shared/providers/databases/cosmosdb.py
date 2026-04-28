"""Azure Cosmos DB-backed database client.

Pillar: Stable Core
Phase: 4

Wraps `azure.cosmos.aio.CosmosClient`. Single container holds both
conversations and messages, differentiated by a `type` discriminator
(per cosmosdb-best-practices `model-type-discriminator`). Partition
key is `/userId` -- every conversation + every message for one user
lives in the same logical partition, so listing conversations and
listing messages are single-partition queries (no cross-partition
fan-out). The 20 GB logical-partition cap maps to "one user's
lifetime chat history", which is realistic for this workload; an HPK
upgrade can land later without changing the registry key.

Authentication is `AsyncTokenCredential` only (Hard Rule #2 / ADR
0002). The Bicep module assigns the user-assigned managed identity
the **Cosmos DB Built-in Data Contributor** role (RBAC, no shared
keys).

Item shapes::

    Conversation: {id, userId, type:"conversation", title,
                   createdAt, updatedAt}
    Message:      {id, userId, conversationId, type:"message",
                   role, content, createdAt, feedback?}

Lifecycle: the underlying `CosmosClient` owns an HTTP session.
`aclose()` releases it. The FastAPI lifespan in `backend/app.py`
(task #29) caches one client per process and closes it on shutdown
(`sdk-singleton-client`).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Sequence

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from shared.types import ChatMessage, Conversation, MessageRecord

from . import registry
from .base import BaseDatabaseClient

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential
    from azure.cosmos.aio import ContainerProxy

    from shared.settings import AppSettings


_TYPE_CONVERSATION = "conversation"
_TYPE_MESSAGE = "message"


def _utcnow_iso() -> str:
    """ISO-8601 UTC timestamp with explicit ``+00:00`` offset.

    Cosmos DB treats strings as opaque; using ISO-8601 keeps the wire
    shape stable across providers (PostgreSQL formats the same way
    via `isoformat()`).
    """
    return datetime.now(timezone.utc).isoformat()


@registry.register("cosmosdb")
class CosmosDBClient(BaseDatabaseClient):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
        *,
        client: CosmosClient | None = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests to inject a fake CosmosClient. Production path
        # constructs lazily so no HTTP session opens at import.
        self._client: CosmosClient | None = client
        self._container: "ContainerProxy | None" = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_container(self) -> "ContainerProxy":
        if self._container is not None:
            return self._container
        cfg = self._settings.database
        endpoint = cfg.cosmos_endpoint
        if not endpoint:
            raise RuntimeError(
                "AZURE_COSMOS_ENDPOINT is not set. CosmosDBClient requires "
                "a Cosmos DB account endpoint."
            )
        if self._client is None:
            self._client = CosmosClient(
                url=endpoint, credential=self._credential
            )
        database = self._client.get_database_client(cfg.cosmos_database_name)
        self._container = database.get_container_client(cfg.cosmos_container_name)
        return self._container

    @staticmethod
    def _to_conversation(item: dict[str, Any]) -> Conversation:
        return Conversation(
            id=str(item["id"]),
            user_id=str(item["userId"]),
            title=str(item.get("title", "")),
            created_at=str(item.get("createdAt", "")),
            updated_at=str(item.get("updatedAt", "")),
        )

    @staticmethod
    def _to_message(item: dict[str, Any]) -> MessageRecord:
        feedback = item.get("feedback")
        return MessageRecord(
            id=str(item["id"]),
            conversation_id=str(item["conversationId"]),
            role=item.get("role", "user"),
            content=str(item.get("content", "")),
            created_at=str(item.get("createdAt", "")),
            feedback=str(feedback) if feedback is not None else None,
        )

    async def _read_item(
        self, item_id: str, user_id: str
    ) -> dict[str, Any] | None:
        container = self._get_container()
        try:
            return await container.read_item(item=item_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
        container = self._get_container()
        # Single-partition query (`partition_key=user_id`) so RU cost is
        # bounded; ORDER BY uses the default range index on `/updatedAt`.
        query = (
            "SELECT * FROM c WHERE c.type = @type "
            "ORDER BY c.updatedAt DESC"
        )
        params = [{"name": "@type", "value": _TYPE_CONVERSATION}]
        items = container.query_items(
            query=query,
            parameters=params,
            partition_key=user_id,
        )
        out: list[Conversation] = []
        async for item in items:
            out.append(self._to_conversation(item))
        return out

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        item = await self._read_item(conversation_id, user_id)
        if item is None or item.get("type") != _TYPE_CONVERSATION:
            return None
        return self._to_conversation(item)

    async def create_conversation(
        self, user_id: str, title: str
    ) -> Conversation:
        container = self._get_container()
        now = _utcnow_iso()
        item = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "type": _TYPE_CONVERSATION,
            "title": title,
            "createdAt": now,
            "updatedAt": now,
        }
        stored = await container.create_item(body=item)
        return self._to_conversation(stored)

    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
        container = self._get_container()
        existing = await self._read_item(conversation_id, user_id)
        if existing is None or existing.get("type") != _TYPE_CONVERSATION:
            raise KeyError(conversation_id)
        existing["title"] = title
        existing["updatedAt"] = _utcnow_iso()
        stored = await container.replace_item(
            item=conversation_id, body=existing
        )
        return self._to_conversation(stored)

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        container = self._get_container()
        # Delete all messages in the conversation first (single-partition
        # query, then per-id deletes -- there is no bulk-delete-by-query
        # in the SDK as of azure-cosmos 4.14).
        msg_query = (
            "SELECT c.id FROM c WHERE c.type = @type "
            "AND c.conversationId = @cid"
        )
        params = [
            {"name": "@type", "value": _TYPE_MESSAGE},
            {"name": "@cid", "value": conversation_id},
        ]
        async for row in container.query_items(
            query=msg_query, parameters=params, partition_key=user_id
        ):
            try:
                await container.delete_item(
                    item=str(row["id"]), partition_key=user_id
                )
            except CosmosResourceNotFoundError:
                pass
        try:
            await container.delete_item(
                item=conversation_id, partition_key=user_id
            )
        except CosmosResourceNotFoundError:
            return None

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def list_messages(
        self, conversation_id: str, user_id: str
    ) -> Sequence[MessageRecord]:
        container = self._get_container()
        query = (
            "SELECT * FROM c WHERE c.type = @type "
            "AND c.conversationId = @cid "
            "ORDER BY c.createdAt ASC"
        )
        params = [
            {"name": "@type", "value": _TYPE_MESSAGE},
            {"name": "@cid", "value": conversation_id},
        ]
        items = container.query_items(
            query=query, parameters=params, partition_key=user_id
        )
        out: list[MessageRecord] = []
        async for item in items:
            out.append(self._to_message(item))
        return out

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        message: ChatMessage,
    ) -> MessageRecord:
        container = self._get_container()
        now = _utcnow_iso()
        item = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "conversationId": conversation_id,
            "type": _TYPE_MESSAGE,
            "role": message.role,
            "content": message.content,
            "createdAt": now,
        }
        stored = await container.create_item(body=item)
        # Best-effort bump of the conversation's `updatedAt` so the
        # history list re-orders. Missing parent (already deleted) is
        # silently ignored -- the message persists and a follow-up
        # `list_conversations` will simply not surface it.
        parent = await self._read_item(conversation_id, user_id)
        if parent is not None and parent.get("type") == _TYPE_CONVERSATION:
            parent["updatedAt"] = now
            await container.replace_item(item=conversation_id, body=parent)
        return self._to_message(stored)

    async def set_feedback(
        self, message_id: str, user_id: str, feedback: str
    ) -> None:
        container = self._get_container()
        existing = await self._read_item(message_id, user_id)
        if existing is None or existing.get("type") != _TYPE_MESSAGE:
            raise KeyError(message_id)
        existing["feedback"] = feedback
        await container.replace_item(item=message_id, body=existing)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._container = None
