"""PostgreSQL Flexible Server-backed database client.

Pillar: Stable Core
Phase: 4

Wraps an `asyncpg` connection pool. Two tables: `conversations` and
`messages` (FK + ON DELETE CASCADE), both keyed by UUID. The schema
is created lazily on first use (`CREATE TABLE IF NOT EXISTS`) so a
fresh deployment doesn't need a separate migration step -- the
`post_provision.py` hook only enables the `vector` extension.

Authentication is `AsyncTokenCredential` only (Hard Rule #2 / ADR
0002). Postgres Flex is configured for Entra-only auth (passwords
disabled at the Bicep level); we hand asyncpg an **async password
provider** that calls the credential each time the pool needs a fresh
connection, so token expiry is handled transparently across the
pool's lifetime.

The internal `_pool` is exposed via the `pool` property so the
`pgvector` search provider (task #30) can DI-inject it -- one pool
per process, no parallel connection management (per development plan
\u00a74 task #30).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Sequence

import asyncpg

from shared.types import ChatMessage, Conversation, MessageRecord

from . import registry
from .base import BaseDatabaseClient

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


_POSTGRES_AAD_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id           UUID PRIMARY KEY,
    user_id      TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
    ON conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    feedback        TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_conv_created
    ON messages (conversation_id, created_at);
"""


def _to_iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _row_to_conversation(row: "asyncpg.Record | dict[str, Any]") -> Conversation:
    return Conversation(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        title=str(row["title"] or ""),
        created_at=_to_iso(row["created_at"]),
        updated_at=_to_iso(row["updated_at"]),
    )


def _row_to_message(row: "asyncpg.Record | dict[str, Any]") -> MessageRecord:
    feedback = row["feedback"]
    return MessageRecord(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        role=row["role"],
        content=str(row["content"]),
        created_at=_to_iso(row["created_at"]),
        feedback=str(feedback) if feedback is not None else None,
    )


@registry.register("postgresql")
class PostgresClient(BaseDatabaseClient):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
        *,
        pool: "asyncpg.Pool | None" = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests + the pgvector search provider (task #30) to inject
        # an existing pool. Production path constructs lazily so no
        # connection opens at import.
        self._pool: "asyncpg.Pool | None" = pool
        # Single lock guards both lazy pool construction AND the schema
        # bootstrap. Two coroutines hitting `_ensure_pool` simultaneously
        # would otherwise both pass the `is None` check and both call
        # `asyncpg.create_pool`, leaking one pool. Hardened in #32c.
        self._init_lock = asyncio.Lock()
        self._schema_ready = pool is not None

    # ------------------------------------------------------------------
    # Lifecycle / pool
    # ------------------------------------------------------------------

    @property
    def pool(self) -> "asyncpg.Pool":
        """Return the live pool (raises if not yet bootstrapped)."""
        if self._pool is None:
            raise RuntimeError(
                "PostgresClient pool is not initialized. Await any client "
                "method (e.g. `list_conversations`) at least once first, "
                "or call `await client.ensure_pool()` explicitly."
            )
        return self._pool

    async def ensure_pool(self) -> "asyncpg.Pool":
        """Bootstrap the pool + schema and return it.

        Public counterpart of the lazy `_ensure_pool()` used internally
        by every CRUD method. The pgvector search provider (task #30)
        calls this from `lifespan` so it can DI-inject a single pool
        per process (per development plan \u00a74 task #30).
        """
        return await self._ensure_pool()

    async def _password_provider(self) -> str:
        """asyncpg-compatible async callable that returns a fresh AAD
        token. asyncpg invokes this on each new connection, so token
        expiry is handled transparently across the pool's lifetime."""
        token = await self._credential.get_token(_POSTGRES_AAD_SCOPE)
        return token.token

    async def _ensure_pool(self) -> "asyncpg.Pool":
        # Fast path: pool already built and schema applied.
        if self._pool is not None and self._schema_ready:
            return self._pool
        # Slow path: serialize pool creation + schema bootstrap behind a
        # single lock so concurrent first-use callers cannot race
        # `asyncpg.create_pool` (TOCTOU) and leak a pool.
        async with self._init_lock:
            if self._pool is None:
                cfg = self._settings.database
                endpoint = cfg.postgres_endpoint
                if not endpoint:
                    raise RuntimeError(
                        "AZURE_POSTGRES_ENDPOINT is not set. PostgresClient "
                        "requires a libpq URI from the Bicep deployment."
                    )
                user = cfg.postgres_admin_principal_name
                if not user:
                    raise RuntimeError(
                        "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME is not set. "
                        "PostgresClient requires the Entra principal name "
                        "to connect as."
                    )
                self._pool = await asyncpg.create_pool(
                    dsn=endpoint,
                    user=user,
                    password=self._password_provider,
                    min_size=1,
                    max_size=10,
                )
            if not self._schema_ready:
                async with self._pool.acquire() as conn:
                    await conn.execute(_SCHEMA_SQL)
                self._schema_ready = True
        return self._pool

    async def _ensure_schema(self) -> None:
        # Retained as a thin wrapper for callers that already hold a
        # bootstrapped pool (e.g. an externally-injected one). Routes
        # through `_ensure_pool` so the same `_init_lock` is used.
        if self._schema_ready:
            return
        await self._ensure_pool()

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
        pool = await self._ensure_pool()
        rows = await pool.fetch(
            "SELECT id, user_id, title, created_at, updated_at "
            "FROM conversations WHERE user_id = $1 "
            "ORDER BY updated_at DESC",
            user_id,
        )
        return [_row_to_conversation(r) for r in rows]

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        pool = await self._ensure_pool()
        row = await pool.fetchrow(
            "SELECT id, user_id, title, created_at, updated_at "
            "FROM conversations WHERE id = $1 AND user_id = $2",
            uuid.UUID(conversation_id),
            user_id,
        )
        return _row_to_conversation(row) if row else None

    async def create_conversation(
        self, user_id: str, title: str
    ) -> Conversation:
        pool = await self._ensure_pool()
        row = await pool.fetchrow(
            "INSERT INTO conversations (id, user_id, title) "
            "VALUES ($1, $2, $3) "
            "RETURNING id, user_id, title, created_at, updated_at",
            uuid.uuid4(),
            user_id,
            title,
        )
        assert row is not None
        return _row_to_conversation(row)

    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
        pool = await self._ensure_pool()
        row = await pool.fetchrow(
            "UPDATE conversations SET title = $1, updated_at = NOW() "
            "WHERE id = $2 AND user_id = $3 "
            "RETURNING id, user_id, title, created_at, updated_at",
            title,
            uuid.UUID(conversation_id),
            user_id,
        )
        if row is None:
            raise KeyError(conversation_id)
        return _row_to_conversation(row)

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        pool = await self._ensure_pool()
        # ON DELETE CASCADE removes child messages atomically. Returns
        # silently on missing rows (idempotent), matching the cosmosdb
        # client's behavior.
        await pool.execute(
            "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
            uuid.UUID(conversation_id),
            user_id,
        )

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def list_messages(
        self, conversation_id: str, user_id: str
    ) -> Sequence[MessageRecord]:
        pool = await self._ensure_pool()
        rows = await pool.fetch(
            "SELECT id, conversation_id, user_id, role, content, "
            "created_at, feedback FROM messages "
            "WHERE conversation_id = $1 AND user_id = $2 "
            "ORDER BY created_at ASC",
            uuid.UUID(conversation_id),
            user_id,
        )
        return [_row_to_message(r) for r in rows]

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        message: ChatMessage,
    ) -> MessageRecord:
        pool = await self._ensure_pool()
        # Single transaction: insert the message + bump the parent's
        # updated_at so the history list re-orders. If the parent has
        # been deleted concurrently, the UPDATE no-ops (zero rows) and
        # the FK on the INSERT raises -- caller treats that as KeyError.
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    row = await conn.fetchrow(
                        "INSERT INTO messages "
                        "(id, conversation_id, user_id, role, content) "
                        "VALUES ($1, $2, $3, $4, $5) "
                        "RETURNING id, conversation_id, user_id, role, "
                        "content, created_at, feedback",
                        uuid.uuid4(),
                        uuid.UUID(conversation_id),
                        user_id,
                        message.role,
                        message.content,
                    )
                except asyncpg.ForeignKeyViolationError as exc:
                    raise KeyError(conversation_id) from exc
                await conn.execute(
                    "UPDATE conversations SET updated_at = NOW() "
                    "WHERE id = $1 AND user_id = $2",
                    uuid.UUID(conversation_id),
                    user_id,
                )
        assert row is not None
        return _row_to_message(row)

    async def set_feedback(
        self, message_id: str, user_id: str, feedback: str
    ) -> None:
        pool = await self._ensure_pool()
        # `WHERE user_id` keeps tenants isolated -- a message id leaked
        # across users still won't match.
        result = await pool.execute(
            "UPDATE messages SET feedback = $1 "
            "WHERE id = $2 AND user_id = $3",
            feedback,
            uuid.UUID(message_id),
            user_id,
        )
        # asyncpg returns the command tag like "UPDATE 1" / "UPDATE 0".
        if isinstance(result, str) and result.endswith(" 0"):
            raise KeyError(message_id)
