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
caches one client per process and closes it on shutdown
(`sdk-singleton-client`).
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, AsyncIterable, Sequence, cast

from azure.core.credentials_async import AsyncTokenCredential
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
)

from backend.core.settings import AppSettings
from backend.core.types import (
    AdminAuditEntry,
    ChatMessage,
    Conversation,
    MessageRecord,
    RuntimeConfig,
)

from .registry import registry
from .base import BaseDatabaseClient

logger = logging.getLogger(__name__)


class CosmosItemType(StrEnum):
    """Closed set of `type=` discriminator values stored on every
    item in the chat-history container.

    Per `.github/copilot-instructions.md` Hard Rule #11 (Python
    bullet) and `.github/instructions/v2-shared.instructions.md`
    §Constants: closed-set string literals must be `StrEnum`, not
    bare `_FOO = "foo"` module constants. `StrEnum` subclasses
    `str`, so the wire shape stays exactly `"conversation"` /
    `"message"` / `"agent"` / `"config"` -- existing tests asserting
    on raw strings continue to pass without modification.

    Agent rows (CU-010b) and runtime-config rows (#35c-1) live in
    the same container as conversations + messages, differentiated
    by their `type=` value. Neither is user-scoped, so both pin to
    the synthetic `_system` partition key. Cardinality is bounded
    by `BUILTIN_AGENTS` (~2 rows today) plus a single runtime-config
    row, so the usual "avoid low-cardinality partitions" guidance
    does not apply -- there is no hot-partition risk on a
    read-mostly handful-of-rows partition. The `ADMIN_AUDIT` value
    (#35f-1) is the append-only admin audit log -- also pinned to
    `_system` because the audit query is non-user-scoped, with
    cardinality bounded by `# of admin PATCH operations`
    (single-tenant CWYD: ~hundreds/year, well under the 20 GB
    partition cap).
    """

    CONVERSATION = "conversation"
    MESSAGE = "message"
    AGENT = "agent"
    CONFIG = "config"
    ADMIN_AUDIT = "admin_audit"


class CosmosSystemPartition(StrEnum):
    """Synthetic partition keys for non-user-scoped rows in the
    chat-history container.

    Per Hard Rule #11 (Python bullet -- "sibling partition keys" are
    explicitly called out as a closed set requiring `StrEnum`, not
    bare module constants). Currently a single member because every
    non-user-scoped surface (agent registry CU-010b1, runtime config
    #35c-2) shares the same `_system` partition; declaring it as an
    enum (a) groups the concept under a named type so a future second
    partition (e.g. tenant-scoped overrides) is a one-line addition
    rather than a fresh module constant, and (b) keeps the wire shape
    stable -- `CosmosSystemPartition.DEFAULT` serializes as the bare
    string `"_system"` because `StrEnum` subclasses `str`. The prior
    `_AGENT_PARTITION` lone-sentinel carve-out no longer applies once
    `_CONFIG_PARTITION` was added in #35c-2 (it created the sibling).
    """

    DEFAULT = "_system"


class CosmosFixedItemId(StrEnum):
    """Closed-set fixed item ids for singleton rows under
    `CosmosSystemPartition.DEFAULT`.

    Agent-registry rows use the agent `name` as their id and so are
    NOT enumerated here -- only truly-fixed sentinel ids belong in
    this enum. Per Hard Rule #11 (Python bullet) closed-set string
    literals must be `StrEnum`; a future second sentinel (e.g. a
    feature-flag singleton) joins this enum rather than landing as
    a fresh module constant.
    """

    RUNTIME_CONFIG = "runtime"


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
            metadata=item.get("metadata", {}),
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
        # `parameters` is typed `list[dict[str, object]]` explicitly so
        # the StrEnum value (`CosmosItemType.CONVERSATION` is a `str`
        # subclass) doesn't trip pyright's invariant-list check. Same
        # rationale on every `query_items` call below (Q14c).
        params: list[dict[str, object]] = [
            {"name": "@type", "value": CosmosItemType.CONVERSATION}
        ]
        items = cast(
            AsyncIterable[dict[str, Any]],
            container.query_items(
                query=query,
                parameters=params,
                partition_key=user_id,
            ),
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
        # Per v2/docs/exception_handling_policy.md (Provider-entry-points
        # row): narrow SDK catch -> structured logger.exception ->
        # re-raise so the router layer maps to a sanitized HTTPException
        # (PII/stack-leak protection lives there, not here).
        try:
            stored = await container.create_item(body=item)
        except CosmosHttpResponseError:
            logger.exception(
                "cosmos create_item failed",
                extra={
                    "operation": "create_conversation",
                    "provider": "cosmos",
                    "user_id": user_id,
                },
            )
            raise
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
        try:
            stored = await container.replace_item(
                item=conversation_id, body=existing
            )
        except CosmosHttpResponseError:
            logger.exception(
                "cosmos replace_item failed",
                extra={
                    "operation": "rename_conversation",
                    "provider": "cosmos",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                },
            )
            raise
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
        params: list[dict[str, object]] = [
            {"name": "@type", "value": CosmosItemType.MESSAGE},
            {"name": "@cid", "value": conversation_id},
        ]
        rows = cast(
            AsyncIterable[dict[str, Any]],
            container.query_items(
                query=msg_query, parameters=params, partition_key=user_id
            ),
        )
        async for row in rows:
            try:
                await container.delete_item(
                    item=str(row["id"]), partition_key=user_id
                )
            except CosmosResourceNotFoundError:
                # Idempotent: another caller (or a prior failed sweep) may
                # have already removed this message. Per
                # v2/docs/exception_handling_policy.md, log + continue
                # instead of swallowing silently.
                logger.debug(
                    "cosmos delete_item: message %s already gone "
                    "(idempotent skip during conversation %s purge)",
                    row["id"],
                    conversation_id,
                )
        try:
            await container.delete_item(
                item=conversation_id, partition_key=user_id
            )
        except CosmosResourceNotFoundError:
            # Parent already gone -- delete is idempotent at the
            # conversation level too. Log so the no-op is visible.
            logger.debug(
                "cosmos delete_item: conversation %s already gone "
                "(idempotent skip)",
                conversation_id,
            )
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
        params: list[dict[str, object]] = [
            {"name": "@type", "value": CosmosItemType.MESSAGE},
            {"name": "@cid", "value": conversation_id},
        ]
        items = cast(
            AsyncIterable[dict[str, Any]],
            container.query_items(
                query=query, parameters=params, partition_key=user_id
            ),
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
            # Cosmos stores the JSON object natively (no serialization
            # step, unlike the Postgres JSONB column); a missing key on a
            # legacy doc reads back as `{}` in `_to_message`. Carries the
            # provider-agnostic per-message extras (an assistant turn's
            # citations) so a reloaded conversation rehydrates them.
            "metadata": message.metadata,
        }
        try:
            stored = await container.create_item(body=item)
        except CosmosHttpResponseError:
            logger.exception(
                "cosmos create_item failed",
                extra={
                    "operation": "add_message",
                    "provider": "cosmos",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                },
            )
            raise
        # Best-effort bump of the conversation's `updatedAt` so the
        # history list re-orders. Missing parent (already deleted) is
        # silently ignored -- the message persists and a follow-up
        # `list_conversations` will simply not surface it.
        parent = await self._read_item(conversation_id, user_id)
        if parent is not None and parent.get("type") == CosmosItemType.CONVERSATION:
            parent["updatedAt"] = now
            try:
                await container.replace_item(item=conversation_id, body=parent)
            except CosmosHttpResponseError:
                # Best-effort updatedAt bump (per the docstring above):
                # the message itself already persisted, and a follow-up
                # list_conversations call will surface it via the
                # message timestamps. Transient failures here (throttle,
                # 412 precondition) are non-fatal -> logger.warning,
                # swallow. WARNING (not ERROR/exception) keeps OTel from
                # escalating a known-non-fatal path.
                logger.warning(
                    "cosmos replace_item parent updatedAt bump failed "
                    "(best-effort, swallowed)",
                    extra={
                        "operation": "add_message_parent_bump",
                        "provider": "cosmos",
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                    },
                )
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
                item=name, partition_key=CosmosSystemPartition.DEFAULT
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
            "userId": CosmosSystemPartition.DEFAULT,
            "type": CosmosItemType.AGENT,
            "agentId": agent_id,
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            await container.upsert_item(body=item)
        except CosmosHttpResponseError:
            # `agent_name` (not `name`) in extra: the stdlib LogRecord
            # already owns a `name` attribute, and the standard logging
            # adapters refuse to inject colliding extras.
            logger.exception(
                "cosmos upsert_item failed",
                extra={
                    "operation": "upsert_agent_id",
                    "provider": "cosmos",
                    "agent_name": name,
                    "agent_id": agent_id,
                },
            )
            raise

    async def get_runtime_config(self) -> RuntimeConfig | None:
        container = self._get_container()
        # Direct point-read on (id="runtime", partition="_system") --
        # single-RU lookup, mirrors the `get_agent_id` shape. Cold
        # start (no row written yet) returns None so the admin
        # router's merge falls through to env defaults rather than
        # raising. Defensive type check: a non-config item under the
        # same id (impossible today, future-proofing) refuses to
        # deserialize as a `RuntimeConfig`. Empty `payload` rehydrates
        # as `RuntimeConfig()` (every override cleared) -- distinct
        # from None (no row at all), see test
        # `test_get_runtime_config_returns_empty_runtime_config_for_empty_payload`.
        try:
            item = await container.read_item(
                item=CosmosFixedItemId.RUNTIME_CONFIG,
                partition_key=CosmosSystemPartition.DEFAULT,
            )
        except CosmosResourceNotFoundError:
            return None
        if item.get("type") != CosmosItemType.CONFIG:
            return None
        # `item` is `dict[str, Any]` -- pyright surfaces `payload` as
        # `Any | dict[Unknown, Unknown]` without an explicit cast.
        payload = cast(dict[str, Any], item.get("payload") or {})
        return RuntimeConfig.model_validate(payload)

    async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
        container = self._get_container()
        now = _utcnow_iso()
        # `upsert_item` does CREATE-or-REPLACE atomically on (id,
        # partition_key) -- mirrors `upsert_agent_id`. The full
        # payload is overwritten on every call; merge semantics
        # (RFC 7396) live in the PATCH route (#35c-4), not here.
        # `payload` uses `mode="json"` so any future non-string
        # field types (datetime, UUID, ...) round-trip through the
        # Cosmos JSON wire shape without custom encoders.
        body = {
            "id": CosmosFixedItemId.RUNTIME_CONFIG,
            "userId": CosmosSystemPartition.DEFAULT,
            "type": CosmosItemType.CONFIG,
            "payload": config.model_dump(mode="json"),
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            await container.upsert_item(body=body)
        except CosmosHttpResponseError:
            logger.exception(
                "cosmos upsert_item failed",
                extra={
                    "operation": "upsert_runtime_config",
                    "provider": "cosmos",
                },
            )
            raise

    async def set_feedback(
        self, message_id: str, user_id: str, feedback: str
    ) -> None:
        container = self._get_container()
        existing = await self._read_item(message_id, user_id)
        if existing is None or existing.get("type") != CosmosItemType.MESSAGE:
            raise KeyError(message_id)
        existing["feedback"] = feedback
        try:
            await container.replace_item(item=message_id, body=existing)
        except CosmosHttpResponseError:
            logger.exception(
                "cosmos replace_item failed",
                extra={
                    "operation": "set_feedback",
                    "provider": "cosmos",
                    "message_id": message_id,
                    "user_id": user_id,
                },
            )
            raise

    async def write_admin_audit(self, entry: AdminAuditEntry) -> None:
        container = self._get_container()
        # Storage-assigned id + timestamp -- the router fires and
        # forgets, the audit log is append-only, and a UUID4 is the
        # natural id (collision risk ~1 in 2^122). `create_item`
        # (not `upsert_item`) enforces append-only at the SDK layer
        # so a future bug that re-uses an id surfaces as a 409 rather
        # than silently overwriting a prior audit row.
        before_payload = (
            entry.before.model_dump(mode="json") if entry.before else None
        )
        body = {
            "id": str(uuid.uuid4()),
            "userId": CosmosSystemPartition.DEFAULT,
            "type": CosmosItemType.ADMIN_AUDIT,
            "actor": entry.actor,
            "action": entry.action,
            "before": before_payload,
            "after": entry.after.model_dump(mode="json"),
            "createdAt": _utcnow_iso(),
        }
        try:
            await container.create_item(body=body)
        except CosmosHttpResponseError:
            logger.exception(
                "cosmos create_item failed",
                extra={
                    "operation": "write_admin_audit",
                    "provider": "cosmos",
                    "actor": entry.actor,
                    "action": entry.action,
                },
            )
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._container = None
