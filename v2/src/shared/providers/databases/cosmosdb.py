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

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Sequence

from azure.core.credentials_async import AsyncTokenCredential
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from shared.settings import AppSettings
from shared.types import ChatMessage, Conversation, MessageRecord

from . import registry
from .base import BaseDatabaseClient


class CosmosItemType(StrEnum):
    """Closed set of `type=` discriminator values stored on every
    item in the chat-history container.

    Per `.github/copilot-instructions.md` Hard Rule #11 (Python
    bullet) and `.github/instructions/v2-shared.instructions.md`
    §Constants: closed-set string literals must be `StrEnum`, not
    bare `_FOO = "foo"` module constants. `StrEnum` subclasses
    `str`, so the wire shape stays exactly `"conversation"` /
    `"message"` / `"agent"` -- existing tests asserting on raw
    strings continue to pass without modification.

    Agent rows (CU-010b) live in the same container as conversations
    + messages, differentiated by `type="agent"`. They are not
    user-scoped, so they pin to a synthetic `_system` partition
    key. Cardinality is bounded by `BUILTIN_AGENTS` (~2 rows today)
    so the usual "avoid low-cardinality partitions" guidance does
    not apply -- there is no hot-partition risk on a read-mostly
    two-row partition.
    """

    CONVERSATION = "conversation"
    MESSAGE = "message"
    AGENT = "agent"


# Single-value sentinel for the agent-registry partition. Exempt from
# the StrEnum rule per Hard Rule #11 -- no siblings, no closed set.
_AGENT_PARTITION = "_system"


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
        settings: AppSettings,
        credential: AsyncTokenCredential,
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

    def _get_container(self) -> ContainerProxy:
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
        params = [{"name": "@type", "value": CosmosItemType.CONVERSATION}]
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
        if item is None or item.get("type") != CosmosItemType.CONVERSATION:
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
            "type": CosmosItemType.CONVERSATION,
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
        if existing is None or existing.get("type") != CosmosItemType.CONVERSATION:
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
            {"name": "@type", "value": CosmosItemType.MESSAGE},
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
            {"name": "@type", "value": CosmosItemType.MESSAGE},
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
            "type": CosmosItemType.MESSAGE,
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
        if parent is not None and parent.get("type") == CosmosItemType.CONVERSATION:
            parent["updatedAt"] = now
            await container.replace_item(item=conversation_id, body=parent)
        return self._to_message(stored)

    # ------------------------------------------------------------------
    # Agent registry (CU-010b)
    # ------------------------------------------------------------------

    async def get_agent_id(self, name: str) -> str | None:
        container = self._get_container()
        # Direct point-read on (id=name, partition=_system) -- single-RU
        # lookup, no cross-partition fan-out, no query-engine cost.
        # Defensive type check: if a future refactor accidentally writes
        # a non-agent item under the same id, refuse to return its
        # `agentId` rather than silently mis-resolving.
        try:
            item = await container.read_item(
                item=name, partition_key=_AGENT_PARTITION
            )
        except CosmosResourceNotFoundError:
            return None
        if item.get("type") != CosmosItemType.AGENT:
            return None
        agent_id = item.get("agentId")
        return str(agent_id) if agent_id else None

    async def upsert_agent_id(self, name: str, agent_id: str) -> None:
        container = self._get_container()
        now = _utcnow_iso()
        # `upsert_item` does CREATE-or-REPLACE atomically on (id,
        # partition_key). No read-then-write race on a stale id (the
        # lazy resolver in CU-010c writes a new id when Foundry 404s
        # the persisted one). `userId` is the partition key value;
        # `_system` keeps agent rows out of every per-tenant
        # partition. `createdAt` is set on every write -- on REPLACE
        # paths it gets clobbered, which is acceptable for a
        # registry row whose lifecycle event we care about is
        # `updatedAt` (kept distinct so a future audit can sort by
        # "most recently re-created").
        item = {
            "id": name,
            "userId": _AGENT_PARTITION,
            "type": CosmosItemType.AGENT,
            "agentId": agent_id,
            "createdAt": now,
            "updatedAt": now,
        }
        await container.upsert_item(body=item)

    async def set_feedback(
        self, message_id: str, user_id: str, feedback: str
    ) -> None:
        container = self._get_container()
        existing = await self._read_item(message_id, user_id)
        if existing is None or existing.get("type") != CosmosItemType.MESSAGE:
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
