"""PostgreSQL Flexible Server-backed database client.

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
`pgvector` search provider can DI-inject it -- one pool per process,
no parallel connection management.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence, cast

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import (
    AadScope,
    AdminAuditEntry,
    ChatMessage,
    Conversation,
    MessageRecord,
    RuntimeConfig,
)

from .registry import registry
from .base import BaseDatabaseClient

logger = logging.getLogger(__name__)

# Try/except policy
#
# Per v2/docs/exception_handling_policy.md (Provider entry-points + Lifespan
# rows): every `asyncpg` call at a provider boundary is wrapped with a narrow
# `asyncpg.PostgresError` catch (the umbrella for all SQL-layer failures --
# foreign-key, serialization, deadlock, admin shutdown, etc.), structured-
# logged via `logger.exception(..., extra={"operation": ..., "provider":
# "postgres", ...domain_ids})`, and re-raised so the router layer can
# map to a sanitized HTTPException.
#
# Two carve-outs in this file:
# - The lazy `_ensure_pool()` init path treats failures as lifespan-style
#   loud failures. `asyncpg.create_pool` can fail with non-Postgres errors
#   (DNS, TLS, AAD token errors surfacing as OSError), so the catch widens
#   to `(asyncpg.PostgresError, OSError)` -- the only place the broader
#   tuple is justified.
# - `add_message` keeps its inner `asyncpg.ForeignKeyViolationError ->
#   KeyError(conversation_id)` translation untouched (callers depend on
#   that semantic). The outer wrap catches all *other* PostgresError
#   variants on either the INSERT or the parent updated_at UPDATE, while
#   the inner KeyError bubbles past it unchanged (KeyError is not a
#   PostgresError).


# Bounded startup connect timeout (seconds) handed to `asyncpg.create_pool`.
# Caps how long a first-connection attempt waits before raising, so an
# unreachable server fails fast during lifespan startup instead of hanging
# the pool build indefinitely.
_POOL_CONNECT_TIMEOUT_SECONDS: float = 10.0


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
    feedback        TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_messages_conv_created
    ON messages (conversation_id, created_at);
-- `metadata` carries provider-agnostic per-message extras (an assistant
-- turn stores its citations here so a reloaded conversation rehydrates
-- them). `CREATE TABLE IF NOT EXISTS` no-ops on a `messages` table that
-- predates the column, so the additive `ADD COLUMN IF NOT EXISTS`
-- back-fills an existing table idempotently -- preserving the
-- lazy-bootstrap contract (no separate migration step).
ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

-- Agent registry. `name` is the AgentDefinition.name
-- ("cwyd", "rai"). Used by the lazy resolver so agent
-- identity survives container restarts without an env-var seam
-- (see ADR 0008). Lazy-bootstrapped here alongside conversations +
-- messages so a fresh deployment needs no separate migration.
CREATE TABLE IF NOT EXISTS agents (
    name        TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Runtime config. Single-row table -- the admin API
-- (`PATCH /api/admin/config`) overrides selected env defaults
-- at request time, and there is exactly one override document. The
-- `CHECK (id = 1)` constraint enforces the singleton at the DB layer
-- so a future bug in the writer cannot accumulate stray rows. The
-- payload is stored as JSONB rather than per-column scalars so the
-- `RuntimeConfig` Pydantic model can grow new optional overrides
-- without a DDL migration. Lazy-bootstrapped alongside the other
-- tables so a fresh deployment needs no separate post_provision step.
CREATE TABLE IF NOT EXISTS runtime_config (
    id          INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    payload     JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Admin audit log. Append-only forensic trail of
-- successful `PATCH /api/admin/config` mutations. Mirrors the
-- cosmos `ADMIN_AUDIT` item type so a single audit
-- contract works across providers. Row id is a writer-generated
-- UUID4 (no `gen_random_uuid()` -- avoids the `pgcrypto` extension
-- dependency on a fresh deployment) and `created_at` defaults to
-- `NOW()` so the writer never trusts an app-side clock. `before`
-- is nullable -- the very first PATCH against an unseeded override
-- row legitimately has no prior state. The `(created_at DESC)`
-- index makes forensic queries ("show me the last N admin
-- changes") cheap without a full table scan; cardinality is
-- bounded by # of admin PATCHes (single-tenant CWYD: ~hundreds/
-- year) so the index stays small.
CREATE TABLE IF NOT EXISTS admin_audit (
    id          UUID PRIMARY KEY,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    before      JSONB,
    after       JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_admin_audit_created
    ON admin_audit (created_at DESC);
"""


# Narrow asyncpg Protocols.
#
# `asyncpg` ships no type stubs, so every method call would otherwise leak
# `Unknown` through pyright `--strict`. Rather than scattering `cast()`
# calls across every CRUD method, we cast the resolved pool ONCE inside
# `_ensure_pool()` to the protocols below; every downstream call site
# inherits a fully-typed surface. The protocols intentionally describe
# only the methods this module uses -- the real classes carry many more.
#
# Test fakes (`_make_pool`, `_FakeConnection`, `_FakeTransaction` in
# `tests/shared/providers/databases/test_postgres.py`) already match
# this shape structurally; Protocol is structural so no test edit is
# required.


class _Record(Protocol):
    def __getitem__(self, key: str) -> Any: ...


class _Transaction(Protocol):
    async def __aenter__(self) -> "_Transaction": ...
    async def __aexit__(self, *exc: object) -> None: ...


class _Connection(Protocol):
    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetchrow(self, query: str, *args: Any) -> _Record | None: ...
    async def fetch(self, query: str, *args: Any) -> list[_Record]: ...
    def transaction(self) -> _Transaction: ...


class _AcquireCtx(Protocol):
    async def __aenter__(self) -> _Connection: ...
    async def __aexit__(self, *exc: object) -> None: ...


class _Pool(Protocol):
    def acquire(self) -> _AcquireCtx: ...
    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetchrow(self, query: str, *args: Any) -> _Record | None: ...
    async def fetch(self, query: str, *args: Any) -> list[_Record]: ...
    async def close(self) -> None: ...


def _to_iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _row_to_conversation(row: _Record) -> Conversation:
    return Conversation(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        title=str(row["title"] or ""),
        created_at=_to_iso(row["created_at"]),
        updated_at=_to_iso(row["updated_at"]),
    )


def _row_to_message(row: _Record) -> MessageRecord:
    feedback = row["feedback"]
    # asyncpg returns a JSONB column as a JSON-shaped `str` (no codec
    # registered, matching the runtime_config / admin_audit read paths);
    # parse it back into the dict `MessageRecord.metadata` expects. A
    # legacy NULL (column added but never written) falls back to `{}`.
    raw_metadata = row["metadata"]
    return MessageRecord(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        role=row["role"],
        content=str(row["content"]),
        created_at=_to_iso(row["created_at"]),
        feedback=str(feedback) if feedback is not None else None,
        metadata=json.loads(raw_metadata) if raw_metadata else {},
    )


@registry.register("postgresql")
class PostgresClient(BaseDatabaseClient):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        pool: "asyncpg.Pool | None" = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests + the pgvector search provider to inject
        # an existing pool. Production path constructs lazily so no
        # connection opens at import.
        self._pool: "asyncpg.Pool | None" = pool
        # Single lock guards both lazy pool construction AND the schema
        # bootstrap. Two coroutines hitting `_ensure_pool` simultaneously
        # would otherwise both pass the `is None` check and both call
        # `asyncpg.create_pool`, leaking one pool.
        self._init_lock = asyncio.Lock()
        self._schema_ready = pool is not None

    # Lifecycle / pool

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
        by every CRUD method. The pgvector search provider
        calls this from `lifespan` so it can DI-inject a single pool
        per process.
        """
        await self._ensure_pool()
        # Cast the protocol back to the public asyncpg.Pool surface for
        # pgvector consumers; storage type is the same object either way.
        return cast("asyncpg.Pool", self._pool)

    async def _password_provider(self) -> str:
        """asyncpg-compatible async callable that returns a fresh AAD
        token. asyncpg invokes this on each new connection, so token
        expiry is handled transparently across the pool's lifetime."""
        token = await self._credential.get_token(AadScope.POSTGRES_FLEX)
        return token.token

    async def _ensure_pool(self) -> _Pool:
        # Fast path: pool already built and schema applied.
        if self._pool is not None and self._schema_ready:
            return cast(_Pool, self._pool)
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
                try:
                    self._pool = await asyncpg.create_pool(  # pyright: ignore[reportUnknownMemberType]
                        dsn=endpoint,
                        user=user,
                        password=self._password_provider,
                        min_size=1,
                        max_size=10,
                        timeout=_POOL_CONNECT_TIMEOUT_SECONDS,
                    )
                except (asyncpg.PostgresError, OSError):
                    # Lifespan policy: log loud + re-raise. Container restart
                    # loop is the recovery path. Endpoint host is logged (not
                    # the full DSN) so credentials/tokens never reach the log.
                    logger.exception(
                        "asyncpg pool creation failed",
                        extra={
                            "operation": "create_pool",
                            "provider": "postgres",
                            "endpoint": endpoint,
                        },
                    )
                    raise
            typed_pool = cast(_Pool, self._pool)
            if not self._schema_ready:
                async with typed_pool.acquire() as conn:
                    try:
                        await conn.execute(_SCHEMA_SQL)
                    except asyncpg.PostgresError:
                        # Lifespan policy: schema bootstrap is required for
                        # the app to function. Log + re-raise; container
                        # restart loop retries.
                        logger.exception(
                            "asyncpg schema bootstrap failed",
                            extra={
                                "operation": "ensure_schema",
                                "provider": "postgres",
                            },
                        )
                        raise
                self._schema_ready = True
        return typed_pool

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

    # Conversations

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

    async def create_conversation(self, user_id: str, title: str) -> Conversation:
        pool = await self._ensure_pool()
        try:
            row = await pool.fetchrow(
                "INSERT INTO conversations (id, user_id, title) "
                "VALUES ($1, $2, $3) "
                "RETURNING id, user_id, title, created_at, updated_at",
                uuid.uuid4(),
                user_id,
                title,
            )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg create_conversation failed",
                extra={
                    "operation": "create_conversation",
                    "provider": "postgres",
                    "user_id": user_id,
                },
            )
            raise
        assert row is not None
        return _row_to_conversation(row)

    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
        pool = await self._ensure_pool()
        try:
            row = await pool.fetchrow(
                "UPDATE conversations SET title = $1, updated_at = NOW() "
                "WHERE id = $2 AND user_id = $3 "
                "RETURNING id, user_id, title, created_at, updated_at",
                title,
                uuid.UUID(conversation_id),
                user_id,
            )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg rename_conversation failed",
                extra={
                    "operation": "rename_conversation",
                    "provider": "postgres",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                },
            )
            raise
        if row is None:
            raise KeyError(conversation_id)
        return _row_to_conversation(row)

    async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        pool = await self._ensure_pool()
        # ON DELETE CASCADE removes child messages atomically. Returns
        # silently on missing rows (idempotent), matching the cosmosdb
        # client's behavior. Idempotency is row-not-found semantics; an
        # SDK-level failure (deadlock, admin shutdown, FK trigger error)
        # is still loud per policy.
        try:
            await pool.execute(
                "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
                uuid.UUID(conversation_id),
                user_id,
            )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg delete_conversation failed",
                extra={
                    "operation": "delete_conversation",
                    "provider": "postgres",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                },
            )
            raise

    # Messages

    async def list_messages(
        self, conversation_id: str, user_id: str
    ) -> Sequence[MessageRecord]:
        pool = await self._ensure_pool()
        rows = await pool.fetch(
            "SELECT id, conversation_id, user_id, role, content, "
            "created_at, feedback, metadata FROM messages "
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
        # The outer try catches OTHER asyncpg.PostgresError variants
        # (serialization failure, deadlock, admin shutdown) on either
        # the INSERT or the UPDATE; KeyError from the inner FK
        # translation bubbles past unchanged.
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        # `metadata` binds as a JSON-shaped `str`; asyncpg
                        # accepts that for a JSONB column out of the box
                        # (same contract as runtime_config / admin_audit).
                        row = await conn.fetchrow(
                            "INSERT INTO messages "
                            "(id, conversation_id, user_id, role, content, "
                            "metadata) "
                            "VALUES ($1, $2, $3, $4, $5, $6) "
                            "RETURNING id, conversation_id, user_id, role, "
                            "content, created_at, feedback, metadata",
                            uuid.uuid4(),
                            uuid.UUID(conversation_id),
                            user_id,
                            message.role,
                            message.content,
                            json.dumps(message.metadata),
                        )
                    except asyncpg.ForeignKeyViolationError as exc:
                        raise KeyError(conversation_id) from exc
                    await conn.execute(
                        "UPDATE conversations SET updated_at = NOW() "
                        "WHERE id = $1 AND user_id = $2",
                        uuid.UUID(conversation_id),
                        user_id,
                    )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg add_message failed",
                extra={
                    "operation": "add_message",
                    "provider": "postgres",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                },
            )
            raise
        assert row is not None
        return _row_to_message(row)

    async def set_feedback(self, message_id: str, user_id: str, feedback: str) -> None:
        pool = await self._ensure_pool()
        # `WHERE user_id` keeps tenants isolated -- a message id leaked
        # across users still won't match.
        try:
            result = await pool.execute(
                "UPDATE messages SET feedback = $1 " "WHERE id = $2 AND user_id = $3",
                feedback,
                uuid.UUID(message_id),
                user_id,
            )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg set_feedback failed",
                extra={
                    "operation": "set_feedback",
                    "provider": "postgres",
                    "message_id": message_id,
                    "user_id": user_id,
                },
            )
            raise
        # asyncpg returns the command tag like "UPDATE 1" / "UPDATE 0".
        if result.endswith(" 0"):
            raise KeyError(message_id)

    # Agent registry

    async def get_agent_id(self, name: str) -> str | None:
        pool = await self._ensure_pool()
        # Parameterized; never interpolate `name` into SQL. PK lookup
        # is a single index probe (~one disk page worst case).
        row = await pool.fetchrow(
            "SELECT agent_id FROM agents WHERE name = $1",
            name,
        )
        return str(row["agent_id"]) if row else None

    async def upsert_agent_id(self, name: str, agent_id: str) -> None:
        pool = await self._ensure_pool()
        # `ON CONFLICT (name) DO UPDATE` makes this an atomic
        # CREATE-or-REPLACE in a single round-trip. `EXCLUDED.agent_id`
        # references the value the INSERT would have written, so the
        # update path picks up the new id when the lazy resolver
        # rewrites a stale Foundry agent id. `updated_at` is
        # bumped on every conflict; `created_at` keeps its original
        # value so an audit can distinguish "first bootstrapped at"
        # from "most recently rewritten".
        try:
            await pool.execute(
                "INSERT INTO agents (name, agent_id) VALUES ($1, $2) "
                "ON CONFLICT (name) DO UPDATE SET "
                "agent_id = EXCLUDED.agent_id, updated_at = NOW()",
                name,
                agent_id,
            )
        except asyncpg.PostgresError:
            # `agent_name` (not `name`) avoids collision with the stdlib
            # `LogRecord.name` attribute -- standard log adapters refuse
            # to overwrite reserved record fields. Same convention as
            # cosmosdb.upsert_agent_id (C2b).
            logger.exception(
                "asyncpg upsert_agent_id failed",
                extra={
                    "operation": "upsert_agent_id",
                    "provider": "postgres",
                    "agent_name": name,
                    "agent_id": agent_id,
                },
            )
            raise

    # Runtime config

    async def get_runtime_config(self) -> RuntimeConfig | None:
        pool = await self._ensure_pool()
        # Hard-coded `id = 1` filter: the runtime_config table is
        # single-row by construction (PRIMARY KEY DEFAULT 1, CHECK
        # (id = 1) -- see _SCHEMA_SQL). The id is not
        # operator-controlled, so binding adds no security value;
        # asserted in the test
        # `test_get_runtime_config_uses_singleton_id_filter`.
        # asyncpg returns JSONB columns as `str` by default (no codec
        # registered); `model_validate_json` round-trips it back into
        # a `RuntimeConfig`. Cold start (no row) returns None so the
        # admin merge falls through to env defaults.
        row = await pool.fetchrow("SELECT payload FROM runtime_config WHERE id = 1")
        if row is None:
            return None
        return RuntimeConfig.model_validate_json(row["payload"])

    async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
        pool = await self._ensure_pool()
        # Single-round-trip atomic CREATE-or-REPLACE on the singleton
        # `id = 1` row (CHECK constraint enforces the singleton at
        # the DB layer). `EXCLUDED.payload` lets the PATCH route
        # rewrite the row without first reading + deleting it.
        # The id is hard-coded in the SQL (not bound) -- it is not
        # operator-controlled, so binding adds no security value;
        # only the JSONB payload is parameterized via $1. asyncpg
        # accepts a JSON-shaped `str` for JSONB columns out of the
        # box (no codec registration); `model_dump_json()` produces
        # exactly that shape and round-trips through `model_validate_json`
        # in `get_runtime_config`.
        try:
            await pool.execute(
                "INSERT INTO runtime_config (id, payload) VALUES (1, $1) "
                "ON CONFLICT (id) DO UPDATE SET "
                "payload = EXCLUDED.payload, updated_at = NOW()",
                config.model_dump_json(),
            )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg upsert_runtime_config failed",
                extra={
                    "operation": "upsert_runtime_config",
                    "provider": "postgres",
                },
            )
            raise

    # Admin audit log

    async def write_admin_audit(self, entry: AdminAuditEntry) -> None:
        pool = await self._ensure_pool()
        # Append-only INSERT with 5 bound parameters. `created_at`
        # is intentionally omitted from the column list -- the DB
        # default (`NOW()`) fills it in so the writer never trusts
        # an app-side clock (clock-skew across containers is
        # surprisingly common in ACA cold starts). The id is a
        # writer-generated UUID4 (mirrors the cosmos impl)
        # so the same id schema works across providers and
        # avoids the `pgcrypto` extension dependency that
        # `gen_random_uuid()` would otherwise pull in. asyncpg's
        # JSONB codec accepts a JSON-shaped `str` directly
        # (no codec registration), so `model_dump_json()` is bound
        # as-is for `after`; `before` binds as Python `None` -> SQL
        # NULL when the audit captures the very first PATCH against
        # an unseeded override row (truthful first-PATCH receipt,
        # distinct from an empty `RuntimeConfig()`).
        before_payload = entry.before.model_dump_json() if entry.before else None
        try:
            await pool.execute(
                "INSERT INTO admin_audit "
                "(id, actor, action, before, after) "
                "VALUES ($1, $2, $3, $4, $5)",
                str(uuid.uuid4()),
                entry.actor,
                entry.action,
                before_payload,
                entry.after.model_dump_json(),
            )
        except asyncpg.PostgresError:
            logger.exception(
                "asyncpg write_admin_audit failed",
                extra={
                    "operation": "write_admin_audit",
                    "provider": "postgres",
                    "actor": entry.actor,
                    "action": entry.action,
                },
            )
            raise
