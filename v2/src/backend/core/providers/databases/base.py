"""Database client ABC.

Pillar: Stable Core
Phase: 4

Every concrete database client (`cosmosdb`, `postgres`, future
swap-ins like Redis) inherits from `BaseDatabaseClient`
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

from abc import ABC, abstractmethod
from typing import Sequence

from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import (
    AdminAuditEntry,
    ChatMessage,
    Conversation,
    MessageRecord,
    RuntimeConfig,
)


class BaseDatabaseClient(ABC):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
    ) -> None:
        self._settings = settings
        self._credential = credential

    # ---- Conversations --------------------------------------------------

    @abstractmethod
    async def list_conversations(
        self, user_id: str
    ) -> Sequence[Conversation]:
        """Return all conversations owned by `user_id`, newest first."""

    @abstractmethod
    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> "Conversation | None":
        """Return one conversation or `None` if missing / not owned."""

    @abstractmethod
    async def create_conversation(
        self, user_id: str, title: str
    ) -> Conversation:
        """Create a new empty conversation; returns the stored row."""

    @abstractmethod
    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
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
    ) -> Sequence[MessageRecord]:
        """Return all messages in `conversation_id`, oldest first."""

    @abstractmethod
    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        message: ChatMessage,
    ) -> MessageRecord:
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

    # ---- Agent registry (CU-010b) ---------------------------------------
    #
    # `name` is the `AgentDefinition.name` (e.g. "cwyd", "rai"). The
    # value persisted is the Foundry-side agent id returned by
    # `client.create_agent(...)`. Used by the lazy resolver added in
    # CU-010c (`BaseAgentsProvider.get_or_create_agent`) so agent
    # identity survives container restarts without an env-var seam
    # (see ADR 0008).

    @abstractmethod
    async def get_agent_id(self, name: str) -> str | None:
        """Return the persisted Foundry agent id for `name`, or
        `None` if no row has been written yet (cold start). Must be
        idempotent and side-effect free."""

    @abstractmethod
    async def upsert_agent_id(self, name: str, agent_id: str) -> None:
        """Persist `agent_id` against `name`. Idempotent: a second
        call with the same `(name, agent_id)` must not raise, and a
        call with a new `agent_id` for an existing `name` must
        replace the prior value (the lazy resolver in CU-010c does
        this when Foundry returns 404 for a stale persisted id).
        """

    # ---- Runtime config (#35c) ------------------------------------------
    #
    # The admin API (`PATCH /api/admin/config`, #35c-7) persists a
    # singleton `RuntimeConfig` row that overrides selected env
    # defaults at request time. The reader returns `None` on cold
    # start (no row yet) so the admin merge falls through to env
    # defaults rather than raising. The writer (#35c-3) is
    # idempotent and overwrites any prior payload.

    @abstractmethod
    async def get_runtime_config(self) -> RuntimeConfig | None:
        """Return the persisted singleton `RuntimeConfig`, or `None`
        if no override row has been written yet (cold start). Must
        be idempotent and side-effect free."""

    @abstractmethod
    async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
        """Persist `config` as the singleton runtime-config row.
        Idempotent: a second call with the same `config` must not
        raise, and a call with a new `config` must replace the
        prior payload (the PATCH route in #35c-4 does this on
        every operator update). The full payload is overwritten --
        merge semantics belong in the route, not the storage layer.
        """

    # ---- Admin audit log (#35f) ----------------------------------------
    #
    # Append-only audit row written by the admin router after every
    # successful `PATCH /api/admin/config` (#35f-3, T+8). The router
    # populates `actor / action / before / after`; the storage layer
    # assigns the row id + `created_at` on persist so callers fire
    # and forget without minting timestamps. Errors propagate -- the
    # PATCH route would rather surface a 500 than silently drop the
    # audit row.

    @abstractmethod
    async def write_admin_audit(self, entry: AdminAuditEntry) -> None:
        """Append `entry` to the admin audit log. The storage layer
        assigns the row id + `created_at` (ISO-8601 UTC) on persist
        (mirrors `add_message`). Idempotency is **not** required:
        the audit log is append-only by design, and two PATCHes
        with identical bodies are still two distinct events.
        """

    # ---- Lifecycle ------------------------------------------------------

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default no-op."""
        return None
