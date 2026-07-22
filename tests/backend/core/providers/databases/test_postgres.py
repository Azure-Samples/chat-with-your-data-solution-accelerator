"""Tests for the PostgreSQL chat-history client.

asyncpg's pool / connection / transaction surface is faked end-to-end
-- no live Postgres required. Tests assert on (a) parameterized SQL
shape (no string interpolation), (b) tenant-isolation (user_id always
in the WHERE clause), (c) lazy schema bootstrap exactly once, and
(d) FK-violation -> KeyError translation in `add_message`.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import asyncio
import json
import uuid

import asyncpg
import pytest

from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.databases.postgres import (
    PostgresClient,
    _POOL_CONNECT_TIMEOUT_SECONDS,
    _SCHEMA_SQL,
)
from backend.core.settings import AppSettings, DatabaseSettings
from backend.core.types import AdminAuditEntry, ChatMessage, RuntimeConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTransaction:
    async def __aenter__(self) -> "_FakeTransaction":
        return self

    async def __aexit__(self, *_a: object) -> None:
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.execute = AsyncMock(return_value=None)
        self.fetchrow = AsyncMock(return_value=None)
        self.fetch = AsyncMock(return_value=[])

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()


def _make_pool() -> tuple[MagicMock, _FakeConnection]:
    """Build a fake `asyncpg.Pool` whose `.acquire()` yields a fake conn."""
    conn = _FakeConnection()
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.close = AsyncMock(return_value=None)

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire  # type: ignore[assignment]
    return pool, conn


def _make_client(pool: MagicMock | None = None) -> PostgresClient:
    settings = MagicMock(spec=AppSettings)
    settings.database = DatabaseSettings(
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint="postgresql://x.postgres.database.azure.com:5432/cwyd?sslmode=require",
        postgres_admin_principal_name="id-cwyd001",
    )
    return PostgresClient(settings=settings, credential=AsyncMock(), pool=pool)


def _conv_row(
    *,
    id: str = "11111111-1111-1111-1111-111111111111",
    user_id: str = "u1",
    title: str = "t",
    created_at: Any = None,
    updated_at: Any = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "user_id": user_id,
        "title": title,
        "created_at": created_at or datetime(2026, 4, 28, tzinfo=timezone.utc),
        "updated_at": updated_at or datetime(2026, 4, 28, tzinfo=timezone.utc),
    }


def _msg_row(
    *,
    id: str = "22222222-2222-2222-2222-222222222222",
    conversation_id: str = "11111111-1111-1111-1111-111111111111",
    user_id: str = "u1",
    role: str = "user",
    content: str = "hi",
    feedback: str | None = None,
    metadata: str = "{}",
) -> dict[str, Any]:
    # `metadata` is a JSON-shaped str -- asyncpg returns a JSONB column as
    # text (no codec registered), so the fake mirrors that wire shape.
    return {
        "id": id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
        "feedback": feedback,
        "metadata": metadata,
    }


_CID = "11111111-1111-1111-1111-111111111111"
_MID = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_postgres_registers_under_expected_key() -> None:
    # Key must equal `settings.database.db_type` Literal value so
    # `databases_registry.registry.get(db_type)(...)` works without name-mapping
    # (Hard Rule #4: no if/elif over provider keys).
    assert "postgresql" in databases_registry.registry.keys()
    assert databases_registry.registry.get("postgresql") is PostgresClient


# ---------------------------------------------------------------------------
# Pool / lifecycle / schema
# ---------------------------------------------------------------------------


def test_pool_property_raises_before_bootstrap() -> None:
    client = _make_client()
    with pytest.raises(RuntimeError, match="not initialized"):
        _ = client.pool


@pytest.mark.asyncio
async def test_pool_property_returns_injected_pool() -> None:
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    assert client.pool is pool


@pytest.mark.asyncio
async def test_aclose_closes_pool() -> None:
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    await client.aclose()
    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_pool_returns_pool_and_runs_schema() -> None:
    """Public counterpart of `_ensure_pool`, used by pgvector DI."""
    pool, conn = _make_pool()
    client = _make_client(pool=pool)
    client._schema_ready = False  # type: ignore[attr-defined]

    returned = await client.ensure_pool()
    assert returned is pool
    assert conn.execute.await_count == 1
    assert "CREATE TABLE IF NOT EXISTS conversations" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_first_use_runs_schema_then_skips_on_subsequent_calls() -> None:
    pool, conn = _make_pool()
    # Force schema_ready=False so bootstrap runs at least once.
    client = _make_client(pool=pool)
    client._schema_ready = False  # type: ignore[attr-defined]

    await client.list_conversations("u1")
    await client.list_conversations("u1")

    # Schema DDL ran exactly once on the conn from `acquire()`.
    assert conn.execute.await_count == 1
    assert "CREATE TABLE IF NOT EXISTS conversations" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_concurrent_ensure_pool_creates_pool_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TOCTOU race in `_ensure_pool` is closed.

    Two coroutines hitting `_ensure_pool` simultaneously must NOT both
    call `asyncpg.create_pool` -- the second one must observe the
    first's pool under the `_init_lock`. Without the lock, both pass
    the `is None` check and both create a pool, leaking one.
    """
    pool, conn = _make_pool()
    create_calls = {"count": 0}

    async def _fake_create_pool(**_kw: Any) -> MagicMock:
        # Yield to the loop so a concurrent caller gets a chance to
        # race past the `is None` check if the lock is missing.
        create_calls["count"] += 1
        await asyncio.sleep(0)
        return pool

    monkeypatch.setattr(
        "backend.core.providers.databases.postgres.asyncpg.create_pool",
        _fake_create_pool,
    )

    client = _make_client()  # no injected pool -> lazy path

    results = await asyncio.gather(
        client._ensure_pool(),  # type: ignore[attr-defined]
        client._ensure_pool(),  # type: ignore[attr-defined]
        client._ensure_pool(),  # type: ignore[attr-defined]
    )

    assert create_calls["count"] == 1
    assert all(r is pool for r in results)
    # Schema DDL also ran exactly once across the three concurrent calls.
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_password_provider_returns_token_from_credential() -> None:
    client = _make_client()
    token_obj = MagicMock()
    token_obj.token = "fake-aad-token"
    client._credential.get_token = AsyncMock(return_value=token_obj)  # type: ignore[attr-defined]

    pwd = await client._password_provider()
    assert pwd == "fake-aad-token"
    client._credential.get_token.assert_awaited_once_with(  # type: ignore[attr-defined]
        "https://ossrdbms-aad.database.windows.net/.default"
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_filters_by_user_and_orders_desc() -> None:
    pool, _ = _make_pool()
    pool.fetch = AsyncMock(return_value=[_conv_row(title="a")])
    client = _make_client(pool=pool)

    convs = await client.list_conversations("u1")

    assert len(convs) == 1
    assert convs[0].title == "a"
    sql = pool.fetch.await_args.args[0]
    assert "WHERE user_id = $1" in sql
    assert "ORDER BY updated_at DESC" in sql
    assert pool.fetch.await_args.args[1] == "u1"


@pytest.mark.asyncio
async def test_get_conversation_returns_none_when_missing() -> None:
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=None)
    client = _make_client(pool=pool)
    assert await client.get_conversation(_CID, "u1") is None


@pytest.mark.asyncio
async def test_create_conversation_inserts_and_returns_row() -> None:
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=_conv_row(title="hi"))
    client = _make_client(pool=pool)

    conv = await client.create_conversation(user_id="u1", title="hi")

    assert conv.title == "hi"
    sql = pool.fetchrow.await_args.args[0]
    assert sql.startswith("INSERT INTO conversations")
    assert "RETURNING" in sql


@pytest.mark.asyncio
async def test_rename_conversation_raises_keyerror_when_no_row_returned() -> None:
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=None)
    client = _make_client(pool=pool)
    with pytest.raises(KeyError):
        await client.rename_conversation(_CID, "u1", "new")


@pytest.mark.asyncio
async def test_rename_conversation_updates_title_and_bumps_updated_at() -> None:
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=_conv_row(title="new"))
    client = _make_client(pool=pool)
    out = await client.rename_conversation(_CID, "u1", "new")
    assert out.title == "new"
    sql = pool.fetchrow.await_args.args[0]
    assert "UPDATE conversations" in sql
    assert "updated_at = NOW()" in sql


@pytest.mark.asyncio
async def test_delete_conversation_uses_user_filter_and_is_idempotent() -> None:
    pool, _ = _make_pool()
    pool.execute = AsyncMock(return_value="DELETE 0")
    client = _make_client(pool=pool)
    # Must not raise even when nothing is deleted.
    await client.delete_conversation(_CID, "u1")
    sql = pool.execute.await_args.args[0]
    assert "WHERE id = $1 AND user_id = $2" in sql


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_orders_by_created_at_asc_and_filters_by_user() -> None:
    pool, _ = _make_pool()
    pool.fetch = AsyncMock(return_value=[_msg_row(content="a"), _msg_row(content="b")])
    client = _make_client(pool=pool)
    msgs = await client.list_messages(_CID, "u1")
    assert [m.content for m in msgs] == ["a", "b"]
    sql = pool.fetch.await_args.args[0]
    assert "ORDER BY created_at ASC" in sql
    assert "WHERE conversation_id = $1 AND user_id = $2" in sql


@pytest.mark.asyncio
async def test_add_message_inserts_in_transaction_and_bumps_parent() -> None:
    pool, conn = _make_pool()
    conn.fetchrow = AsyncMock(return_value=_msg_row(content="hi"))
    client = _make_client(pool=pool)

    rec = await client.add_message(
        conversation_id=_CID,
        user_id="u1",
        message=ChatMessage(role="user", content="hi"),
    )

    assert rec.content == "hi"
    # INSERT happened on the conn (inside the transaction).
    insert_sql = conn.fetchrow.await_args.args[0]
    assert insert_sql.startswith("INSERT INTO messages")
    # Parent bump ran on the same conn.
    update_calls = [
        c for c in conn.execute.await_args_list if "UPDATE conversations" in c.args[0]
    ]
    assert len(update_calls) == 1


@pytest.mark.asyncio
async def test_add_message_translates_fk_violation_to_keyerror() -> None:
    pool, conn = _make_pool()
    conn.fetchrow = AsyncMock(
        side_effect=asyncpg.ForeignKeyViolationError("fk_violation")
    )
    client = _make_client(pool=pool)
    with pytest.raises(KeyError):
        await client.add_message(
            conversation_id=_CID,
            user_id="u1",
            message=ChatMessage(role="user", content="hi"),
        )


@pytest.mark.asyncio
async def test_add_message_round_trips_metadata_as_jsonb() -> None:
    """An assistant turn's citations travel into storage via the JSONB
    `metadata` column: the INSERT carries the column, the bound parameter
    is the JSON-serialized dict (JSONB accepts a JSON str), and the
    RETURNING row parses back into `MessageRecord.metadata`."""
    pool, conn = _make_pool()
    metadata = {"citations": [{"id": "doc1", "title": "Benefit_Options.pdf"}]}
    conn.fetchrow = AsyncMock(
        return_value=_msg_row(
            role="assistant", content="answer", metadata=json.dumps(metadata)
        )
    )
    client = _make_client(pool=pool)

    rec = await client.add_message(
        conversation_id=_CID,
        user_id="u1",
        message=ChatMessage(role="assistant", content="answer", metadata=metadata),
    )

    insert_sql = conn.fetchrow.await_args.args[0]
    assert insert_sql.startswith("INSERT INTO messages")
    assert "metadata" in insert_sql
    # The dict is bound as a JSON-shaped str (not the raw dict).
    assert json.dumps(metadata) in conn.fetchrow.await_args.args
    # The read path parses the JSONB str back into the dict.
    assert rec.metadata == metadata


@pytest.mark.asyncio
async def test_list_messages_selects_and_parses_metadata() -> None:
    """`list_messages` includes `metadata` in the SELECT and parses each
    JSONB str back into a dict so a reloaded conversation carries it."""
    pool, _ = _make_pool()
    pool.fetch = AsyncMock(
        return_value=[
            _msg_row(role="user", content="q"),
            _msg_row(
                role="assistant",
                content="a",
                metadata='{"citations": [{"id": "doc1"}]}',
            ),
        ]
    )
    client = _make_client(pool=pool)

    msgs = await client.list_messages(_CID, "u1")

    sql = pool.fetch.await_args.args[0]
    assert "metadata" in sql
    assert msgs[0].metadata == {}
    assert msgs[1].metadata == {"citations": [{"id": "doc1"}]}


@pytest.mark.asyncio
async def test_set_feedback_updates_value_with_user_filter() -> None:
    pool, _ = _make_pool()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    client = _make_client(pool=pool)
    await client.set_feedback(_MID, "u1", "positive")
    sql = pool.execute.await_args.args[0]
    assert sql.startswith("UPDATE messages SET feedback = $1")
    assert "AND user_id = $3" in sql


@pytest.mark.asyncio
async def test_set_feedback_raises_keyerror_when_no_row_updated() -> None:
    pool, _ = _make_pool()
    pool.execute = AsyncMock(return_value="UPDATE 0")
    client = _make_client(pool=pool)
    with pytest.raises(KeyError):
        await client.set_feedback(_MID, "u1", "positive")


# ---------------------------------------------------------------------------
# Bootstrap guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_pool_raises_without_endpoint() -> None:
    client = _make_client()
    client._settings.database = DatabaseSettings(  # type: ignore[attr-defined]
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint="postgresql://x.postgres.database.azure.com:5432/cwyd?sslmode=require",
        postgres_admin_principal_name="id-cwyd001",
    )
    client._settings.database.postgres_endpoint = ""  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="AZURE_POSTGRES_ENDPOINT"):
        await client.list_conversations("u1")


@pytest.mark.asyncio
async def test_ensure_pool_raises_without_admin_principal() -> None:
    client = _make_client()
    client._settings.database = DatabaseSettings(  # type: ignore[attr-defined]
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint="postgresql://x.postgres.database.azure.com:5432/cwyd?sslmode=require",
        postgres_admin_principal_name="id-cwyd001",
    )
    client._settings.database.postgres_admin_principal_name = ""  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME"):
        await client.list_conversations("u1")


# ---------------------------------------------------------------------------
# Agent registry (get_agent_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agent_id_returns_none_when_row_missing() -> None:
    """Cold start -- no row written yet. fetchrow returns None on miss
    and the wrapper must surface that as None, not raise."""
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=None)
    client = _make_client(pool=pool)
    assert await client.get_agent_id("cwyd") is None


@pytest.mark.asyncio
async def test_get_agent_id_returns_persisted_id_on_hit() -> None:
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value={"agent_id": "asst_abc123"})
    client = _make_client(pool=pool)
    assert await client.get_agent_id("cwyd") == "asst_abc123"


@pytest.mark.asyncio
async def test_get_agent_id_uses_parameterized_sql() -> None:
    """`name` must never be string-interpolated -- a malicious agent
    name (operator-controlled in a future admin UI) could otherwise
    inject SQL. Asserts a $1 placeholder + bound argument."""
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=None)
    client = _make_client(pool=pool)
    await client.get_agent_id("cwyd")
    sql, *args = pool.fetchrow.await_args.args
    assert "FROM agents" in sql
    assert "WHERE name = $1" in sql
    assert args == ["cwyd"]


@pytest.mark.asyncio
async def test_schema_sql_creates_agents_table() -> None:
    """The lazy bootstrap (`_SCHEMA_SQL`) must include the agents
    table -- otherwise the very first `get_agent_id` against a fresh
    deployment raises `UndefinedTable`. Schema
    bootstrap stays lazy (no post_provision change required)."""
    assert "CREATE TABLE IF NOT EXISTS agents" in _SCHEMA_SQL
    assert "name        TEXT PRIMARY KEY" in _SCHEMA_SQL
    assert "agent_id    TEXT NOT NULL" in _SCHEMA_SQL


# ---------------------------------------------------------------------------
# Agent registry (upsert_agent_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_agent_id_emits_upsert_sql_with_on_conflict() -> None:
    """Single-round-trip atomic CREATE-or-REPLACE -- the lazy
    resolver depends on this so a stale Foundry id can be rewritten
    without first deleting the old row. Asserts the canonical
    `INSERT ... ON CONFLICT (name) DO UPDATE` shape and that the
    update path picks up `EXCLUDED.agent_id` (not the stale value)."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    await client.upsert_agent_id("cwyd", "asst_abc123")

    pool.execute.assert_awaited_once()
    sql, *args = pool.execute.await_args.args
    assert "INSERT INTO agents" in sql
    assert "ON CONFLICT (name) DO UPDATE" in sql
    assert "agent_id = EXCLUDED.agent_id" in sql
    assert args == ["cwyd", "asst_abc123"]


@pytest.mark.asyncio
async def test_upsert_agent_id_uses_parameterized_sql() -> None:
    """`name` and `agent_id` must be bound via $1/$2 -- never
    interpolated. A malicious agent name (operator-controlled in a
    future admin UI) could otherwise inject SQL via either column."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    await client.upsert_agent_id("cwyd'; DROP TABLE agents;--", "asst_x")
    sql, *args = pool.execute.await_args.args
    assert "$1" in sql and "$2" in sql
    # No echoed-into-SQL substring of the bound name -- proves binding,
    # not interpolation.
    assert "DROP TABLE" not in sql
    assert args == ["cwyd'; DROP TABLE agents;--", "asst_x"]


@pytest.mark.asyncio
async def test_upsert_agent_id_is_idempotent_on_repeat_call() -> None:
    """Two writes with the same key must not raise (the ON CONFLICT
    branch fires); a subsequent write with a new agent_id must be
    forwarded through to the SQL bind args so the UPDATE path picks
    it up. Validates the rewrite path the resolver relies on."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    await client.upsert_agent_id("cwyd", "asst_old")
    await client.upsert_agent_id("cwyd", "asst_new")
    assert pool.execute.await_count == 2
    _sql, *second_bound = pool.execute.await_args_list[1].args
    assert second_bound == ["cwyd", "asst_new"]


# ---------------------------------------------------------------------------
# Runtime config (get_runtime_config)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_runtime_config_returns_none_when_row_missing() -> None:
    """Cold start -- no override row written yet. fetchrow returns
    None on miss and the wrapper must surface that as None, not
    raise. The admin router then falls through to env defaults."""
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=None)
    client = _make_client(pool=pool)
    assert await client.get_runtime_config() is None


@pytest.mark.asyncio
async def test_get_runtime_config_round_trips_persisted_payload() -> None:
    """Hit path: the JSONB column carries the Pydantic dump as a
    string (asyncpg returns JSONB as `str` by default unless a
    custom codec is registered). `get_runtime_config()` must
    `model_validate_json` it back into a `RuntimeConfig` with
    every field round-tripping (booleans included -- explicit
    False must not collapse into None)."""
    persisted = RuntimeConfig(
        orchestrator_name="agent_framework",
        openai_temperature=0.7,
        openai_max_tokens=2048,
        search_use_semantic_search=False,
        search_top_k=10,
        log_level="DEBUG",
        updated_at="2026-05-06T12:00:00+00:00",
        updated_by="alice@example.com",
    )
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value={"payload": persisted.model_dump_json()})
    client = _make_client(pool=pool)
    rebuilt = await client.get_runtime_config()
    assert rebuilt == persisted


@pytest.mark.asyncio
async def test_get_runtime_config_uses_singleton_id_filter() -> None:
    """The runtime-config table is single-row by construction
    (PRIMARY KEY DEFAULT 1, CHECK (id = 1) -- see schema test).
    The SELECT must filter on `id = 1` so a future schema where
    the table accidentally accumulates extra rows still picks up
    the canonical singleton, never an arbitrary row."""
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value=None)
    client = _make_client(pool=pool)
    await client.get_runtime_config()
    sql, *args = pool.fetchrow.await_args.args
    assert "FROM runtime_config" in sql
    assert "WHERE id = 1" in sql
    # No bound args -- the singleton id is hard-coded, not
    # operator-controlled, so binding adds no security value.
    assert args == []


@pytest.mark.asyncio
async def test_get_runtime_config_returns_empty_runtime_config_for_empty_payload() -> (
    None
):
    """Boundary: a persisted row with an empty payload (every
    override cleared) must rehydrate as a `RuntimeConfig()` with
    every field `None` -- the merge then falls through
    to env defaults across the board. Asserting this guards the
    'cleared all overrides' UX path against silently returning
    None (cold start) instead."""
    pool, _ = _make_pool()
    pool.fetchrow = AsyncMock(return_value={"payload": "{}"})
    client = _make_client(pool=pool)
    rebuilt = await client.get_runtime_config()
    assert rebuilt == RuntimeConfig()


# ---------------------------------------------------------------------------
# Runtime config (upsert_runtime_config)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_runtime_config_emits_canonical_upsert_sql() -> None:
    """Single-round-trip atomic CREATE-or-REPLACE keyed on the
    singleton `id = 1`. `EXCLUDED.payload` lets the PATCH route
    rewrite the row without first reading + deleting it.
    `updated_at = NOW()` is bumped on every write so an audit can
    distinguish "first written" from "most recently overridden".
    """
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    await client.upsert_runtime_config(RuntimeConfig(openai_temperature=0.7))

    pool.execute.assert_awaited_once()
    sql, *args = pool.execute.await_args.args
    assert "INSERT INTO runtime_config" in sql
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert "payload = EXCLUDED.payload" in sql
    assert "updated_at = NOW()" in sql
    # Singleton id is hard-coded in the SQL (not bound) -- only the
    # JSONB payload is parameterized via $1, mirroring
    # `test_get_runtime_config_uses_singleton_id_filter`.
    assert len(args) == 1
    assert args[0] == RuntimeConfig(openai_temperature=0.7).model_dump_json()


@pytest.mark.asyncio
async def test_upsert_runtime_config_uses_parameterized_jsonb_binding() -> None:
    """`payload` must be bound via $1 -- never interpolated. A
    malicious string sneaked into a future RuntimeConfig field
    (e.g. `log_level="'); DROP TABLE runtime_config;--"`) could
    otherwise inject SQL via the JSON serialization. Asserts the
    $1 placeholder + bound argument pattern."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    payload = RuntimeConfig(log_level="'); DROP TABLE runtime_config;--")
    await client.upsert_runtime_config(payload)
    sql, *args = pool.execute.await_args.args
    assert "$1" in sql
    assert "DROP TABLE" not in sql
    assert args == [payload.model_dump_json()]


@pytest.mark.asyncio
async def test_upsert_runtime_config_is_idempotent_on_repeat_call() -> None:
    """Two writes with overlapping fields must not raise (the
    ON CONFLICT branch fires); a subsequent write with a new
    payload must be forwarded through to the SQL bind args so
    the UPDATE path picks it up. Validates the rewrite path the
    PATCH route relies on."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    first = RuntimeConfig(openai_temperature=0.5)
    second = RuntimeConfig(openai_temperature=0.9)
    await client.upsert_runtime_config(first)
    await client.upsert_runtime_config(second)
    assert pool.execute.await_count == 2
    _sql, *second_bound = pool.execute.await_args_list[1].args
    assert second_bound == [second.model_dump_json()]


@pytest.mark.asyncio
async def test_schema_sql_creates_runtime_config_table() -> None:
    """Lazy bootstrap (`_SCHEMA_SQL`) must include the
    runtime_config table -- otherwise the very first
    `get_runtime_config` against a fresh deployment raises
    `UndefinedTable`. Schema bootstrap stays lazy (no
    post_provision change required)."""
    assert "CREATE TABLE IF NOT EXISTS runtime_config" in _SCHEMA_SQL
    assert "id          INTEGER PRIMARY KEY DEFAULT 1" in _SCHEMA_SQL
    assert "CHECK (id = 1)" in _SCHEMA_SQL
    assert "payload     JSONB NOT NULL" in _SCHEMA_SQL


# ---------------------------------------------------------------------------
# Admin audit (write_admin_audit; postgres impl)
#
# Append-only audit log mirroring the cosmos impl. The table is
# bootstrapped lazily via `_SCHEMA_SQL` (no separate post_provision step)
# and the row id is generated by the writer (uuid4) -- not by a SQL
# default -- so the same id schema works across cosmos + postgres.
#
# Contract:
# - SQL is canonical INSERT with 5 bound parameters (id, actor, action,
#   before, after). `created_at` is filled in by the DB default
#   (`NOW()`) so the writer never trusts a clock from the app.
# - All operator-controlled values (actor, action) are bound, never
#   string-interpolated -- closes the SQL-injection seam.
# - `before` JSONB binds as Python `None` (-> SQL NULL) when the audit
#   captures the very first PATCH against an unseeded override row.
# - PostgresError is caught + logged + re-raised, matching the policy
#   in v2/docs/exception_handling_policy.md (provider entry-point row).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_sql_creates_admin_audit_table() -> None:
    """Lazy bootstrap (`_SCHEMA_SQL`) must include the admin_audit
    table -- otherwise the very first PATCH against a fresh
    deployment raises `UndefinedTable`. Schema bootstrap stays
    lazy (no post_provision change required). The `(created_at DESC)`
    index makes forensic queries ("show me the last N admin
    changes") cheap without a full table scan."""
    assert "CREATE TABLE IF NOT EXISTS admin_audit" in _SCHEMA_SQL
    assert "id          UUID PRIMARY KEY" in _SCHEMA_SQL
    assert "actor       TEXT NOT NULL" in _SCHEMA_SQL
    assert "action      TEXT NOT NULL" in _SCHEMA_SQL
    assert "before      JSONB" in _SCHEMA_SQL
    assert "after       JSONB NOT NULL" in _SCHEMA_SQL
    assert "created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()" in _SCHEMA_SQL
    assert (
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_created\n"
        "    ON admin_audit (created_at DESC);" in _SCHEMA_SQL
    )


@pytest.mark.asyncio
async def test_write_admin_audit_emits_canonical_insert_sql() -> None:
    """Append-only INSERT with 5 bound parameters. `created_at` is
    intentionally absent from the column list -- the DB default
    (`NOW()`) fills it in so the writer never trusts an app-side
    clock. The id is a writer-generated UUID4 (matching the cosmos
    impl) so the same id schema works across providers."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    after = RuntimeConfig(openai_temperature=0.5)
    entry = AdminAuditEntry(
        actor="u-admin", action="patch_config", before=None, after=after
    )
    await client.write_admin_audit(entry)

    pool.execute.assert_awaited_once()
    sql, *args = pool.execute.await_args.args
    assert "INSERT INTO admin_audit" in sql
    assert "(id, actor, action, before, after)" in sql
    assert "VALUES ($1, $2, $3, $4, $5)" in sql
    assert "created_at" not in sql  # DB default fills this in
    assert len(args) == 5
    # id is a stringified UUID4 -- mirrors the cosmos `str(uuid.uuid4())`
    # call so a single forensic query joining cosmos + postgres
    # exports works without provider-specific casting.
    assert isinstance(args[0], str)
    uuid.UUID(args[0])  # raises ValueError if not a valid UUID
    assert args[1] == "u-admin"
    assert args[2] == "patch_config"
    assert args[3] is None  # before-is-None -> SQL NULL
    assert args[4] == after.model_dump_json()


@pytest.mark.asyncio
async def test_write_admin_audit_uses_parameterized_binding() -> None:
    """`actor` + `action` come from the request principal + a fixed
    set of action discriminators, but the audit writer must never
    interpolate them into the SQL string -- a future bug that
    sources `actor` from a header could otherwise inject SQL.
    Asserts the adversarial value lands in the bound args and
    nowhere in the SQL text."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    adversarial = "'); DROP TABLE admin_audit;--"
    entry = AdminAuditEntry(
        actor=adversarial,
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.5),
    )
    await client.write_admin_audit(entry)
    sql, *args = pool.execute.await_args.args
    assert "DROP TABLE" not in sql
    assert adversarial not in sql
    assert args[1] == adversarial


@pytest.mark.asyncio
async def test_write_admin_audit_assigns_distinct_uuid_per_call() -> None:
    """Two consecutive PATCHes from the same actor must produce
    distinct row ids -- otherwise a UNIQUE / PRIMARY KEY violation
    on a future re-PATCH would silently lose the second audit row.
    Each call gets a fresh `uuid.uuid4()`."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.5),
    )
    await client.write_admin_audit(entry)
    await client.write_admin_audit(entry)
    # `await_args_list[i].args` is the full positional tuple
    # `(sql, id, actor, action, before, after)` -- index 1 is id,
    # index 2 is actor, etc.
    first_args = pool.execute.await_args_list[0].args
    second_args = pool.execute.await_args_list[1].args
    assert first_args[2] == "u-admin"  # actor passthrough
    assert second_args[2] == "u-admin"
    assert first_args[1] != second_args[1]  # distinct UUID4 per call


@pytest.mark.asyncio
async def test_write_admin_audit_serializes_before_as_json_string_when_set() -> None:
    """When the previous override row exists, `before` must be
    bound as the JSON-serialized form (asyncpg's JSONB codec
    accepts a `str`). Mirrors the `upsert_runtime_config`
    `model_dump_json()` -> JSONB pattern so a single round-trip
    via `model_validate_json` deserializes the audit row."""
    pool, _ = _make_pool()
    client = _make_client(pool=pool)
    before = RuntimeConfig(openai_temperature=0.3)
    after = RuntimeConfig(openai_temperature=0.7)
    entry = AdminAuditEntry(
        actor="u-admin", action="patch_config", before=before, after=after
    )
    await client.write_admin_audit(entry)
    _sql, *args = pool.execute.await_args.args
    assert args[3] == before.model_dump_json()
    assert args[4] == after.model_dump_json()


@pytest.mark.asyncio
async def test_write_admin_audit_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed audit write must surface as `PostgresError` (re-
    raised, not swallowed) with a structured ERROR log carrying
    `operation="write_admin_audit"`, `provider="postgres"`,
    `actor=<entry.actor>`, `action=<entry.action>`. The caller
    (router in T+8) decides whether to translate to 500 or treat
    as best-effort -- the provider's job is loud failure."""
    pool, _ = _make_pool()
    pool.execute = AsyncMock(side_effect=_pg_error("audit write failed"))
    client = _make_client(pool=pool)
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.5),
    )

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.write_admin_audit(entry)

    record = _find_error_record(caplog, "write_admin_audit")
    assert getattr(record, "provider", None) == "postgres"
    assert getattr(record, "actor", None) == "u-admin"
    assert getattr(record, "action", None) == "patch_config"


# ---------------------------------------------------------------------------
# Failure-path coverage (Phase C2c -- provider try/except sweep)
# ---------------------------------------------------------------------------
#
# Per v2/docs/exception_handling_policy.md (Provider entry-points + Lifespan
# rows), every `asyncpg` call at a provider boundary catches
# `asyncpg.PostgresError` (the umbrella for SQL-layer failures: foreign
# key, serialization, deadlock, admin shutdown, etc.), logs structured
# context via `logger.exception`, and re-raises so the router layer can
# map to a sanitized HTTPException.
#
# Two carve-outs validated below:
# - `_ensure_pool` widens the catch to `(asyncpg.PostgresError, OSError)`
#   on `asyncpg.create_pool` so DNS/TLS-class failures (which surface as
#   `OSError` from the underlying connection layer, not as a Postgres
#   protocol error) are also captured.
# - `add_message` keeps its inner `ForeignKeyViolationError -> KeyError`
#   translation untouched; the outer wrap captures *other* PostgresError
#   variants on either the INSERT or the parent `updated_at` UPDATE.
#
# All tests drive an `AsyncMock(side_effect=asyncpg.PostgresError(...))`
# at the SDK boundary, assert (a) the exception bubbles out unchanged
# (re-raised, not swallowed or wrapped), and (b) the structured log
# fires at ERROR level with the canonical `extra` schema
# {"operation": <name>, "provider": "postgres", ...domain_ids}.

_LOGGER_NAME = "backend.core.providers.databases.postgres"


def _pg_error(message: str = "boom") -> asyncpg.PostgresError:
    """Construct a generic asyncpg.PostgresError. The base class accepts
    a single string message and is what the SDK raises for any SQL-layer
    failure not modeled by a more specific subclass.
    """
    return asyncpg.PostgresError(message)


def _find_error_record(caplog: pytest.LogCaptureFixture, operation: str) -> Any:
    """Return the single ERROR record for `operation`, failing the test
    with a useful message if zero or multiple matches surface. Same
    helper shape as the cosmosdb tests for consistency.
    """
    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR" and getattr(r, "operation", None) == operation
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record for operation={operation!r}, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    return matches[0]


# --- Lifespan-style init wraps -------------------------------------------


@pytest.mark.asyncio
async def test_create_pool_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`asyncpg.create_pool` failure during lazy `_ensure_pool` is logged
    loud + re-raised (lifespan policy). Endpoint host appears in the log
    payload; credentials never do.
    """

    async def _fail_create_pool(**_kw: Any) -> Any:
        raise _pg_error("AAD token rejected")

    monkeypatch.setattr(
        "backend.core.providers.databases.postgres.asyncpg.create_pool",
        _fail_create_pool,
    )
    client = _make_client()  # no injected pool -> lazy path forced

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.list_conversations("u1")  # any CRUD triggers init

    record = _find_error_record(caplog, "create_pool")
    assert record.provider == "postgres"
    # Endpoint logged for triage; raw DSN string never logged in full.
    assert record.endpoint.endswith(
        "postgres.database.azure.com:5432/cwyd?sslmode=require"
    )


@pytest.mark.asyncio
async def test_create_pool_widens_catch_to_oserror(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS / TLS / connection failures surface from the asyncio transport
    layer as `OSError`, not as `asyncpg.PostgresError`. The catch widens
    only here (per the in-file policy comment) so a DNS resolution
    failure still produces a structured log line instead of a bare
    transport stack trace.
    """

    async def _fail_create_pool(**_kw: Any) -> Any:
        raise OSError("Name or service not known")

    monkeypatch.setattr(
        "backend.core.providers.databases.postgres.asyncpg.create_pool",
        _fail_create_pool,
    )
    client = _make_client()

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(OSError):
            await client.list_conversations("u1")

    record = _find_error_record(caplog, "create_pool")
    assert record.provider == "postgres"


@pytest.mark.asyncio
async def test_create_pool_uses_bounded_connect_timeout_and_fails_fast(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`asyncpg.create_pool` is handed a bounded `timeout=` so an
    unreachable server fails fast during lifespan startup instead of
    hanging the pool build forever. A timing-out connect
    surfaces as `TimeoutError` (an `OSError` subclass in py3.11), so the
    existing lifespan catch logs loud + re-raises promptly.
    """
    captured: dict[str, Any] = {}

    async def _fake_create_pool(**kwargs: Any) -> Any:
        captured.update(kwargs)
        raise TimeoutError("connect timed out")

    monkeypatch.setattr(
        "backend.core.providers.databases.postgres.asyncpg.create_pool",
        _fake_create_pool,
    )
    client = _make_client()  # no injected pool -> lazy slow path forced

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(TimeoutError):
            await client.ensure_pool()

    # (a) A bounded connect timeout is passed to `create_pool`.
    assert captured["timeout"] == _POOL_CONNECT_TIMEOUT_SECONDS
    # (b) The timing-out connect is logged loud + re-raised (fail-fast),
    #     not swallowed into an infinite hang.
    record = _find_error_record(caplog, "create_pool")
    assert record.provider == "postgres"


@pytest.mark.asyncio
async def test_ensure_schema_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Schema bootstrap failure is a lifespan-style failure: log loud +
    re-raise so the container restart loop is the recovery path.
    """
    pool, conn = _make_pool()
    conn.execute = AsyncMock(side_effect=_pg_error("permission denied"))
    client = _make_client(pool=pool)
    client._schema_ready = False  # type: ignore[attr-defined]

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.list_conversations("u1")

    record = _find_error_record(caplog, "ensure_schema")
    assert record.provider == "postgres"


# --- Write-path wraps ----------------------------------------------------


@pytest.mark.asyncio
async def test_create_conversation_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool, _conn = _make_pool()
    pool.fetchrow = AsyncMock(side_effect=_pg_error("serialization failure"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.create_conversation("u1", "title")

    record = _find_error_record(caplog, "create_conversation")
    assert record.provider == "postgres"
    assert record.user_id == "u1"
    pool.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_rename_conversation_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool, _conn = _make_pool()
    pool.fetchrow = AsyncMock(side_effect=_pg_error("deadlock"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.rename_conversation(_CID, "u1", "new title")

    record = _find_error_record(caplog, "rename_conversation")
    assert record.provider == "postgres"
    assert record.conversation_id == _CID
    assert record.user_id == "u1"


@pytest.mark.asyncio
async def test_delete_conversation_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`delete_conversation` is idempotent on row-not-found (returns
    silently), but an SDK-level failure (deadlock, admin shutdown) is
    still loud per policy.
    """
    pool, _conn = _make_pool()
    pool.execute = AsyncMock(side_effect=_pg_error("admin shutdown"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.delete_conversation(_CID, "u1")

    record = _find_error_record(caplog, "delete_conversation")
    assert record.provider == "postgres"
    assert record.conversation_id == _CID
    assert record.user_id == "u1"


@pytest.mark.asyncio
async def test_add_message_logs_and_reraises_on_postgres_error_during_insert(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-FK PostgresError on the message INSERT must surface via the
    OUTER wrap (the inner try only converts ForeignKeyViolationError to
    KeyError). The parent `updated_at` UPDATE must NOT be attempted: the
    transaction context exits via the exception before reaching it.
    """
    pool, conn = _make_pool()
    conn.fetchrow = AsyncMock(side_effect=_pg_error("serialization failure"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.add_message(
                conversation_id=_CID,
                user_id="u1",
                message=ChatMessage(role="user", content="hi"),
            )

    record = _find_error_record(caplog, "add_message")
    assert record.provider == "postgres"
    assert record.conversation_id == _CID
    assert record.user_id == "u1"
    # The parent UPDATE must NOT have been attempted: the INSERT failed
    # first, the transaction unwound, the outer except caught.
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_message_preserves_fk_to_keyerror_translation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The inner `ForeignKeyViolationError -> KeyError(conversation_id)`
    translation must survive C2c untouched. The KeyError is NOT a
    PostgresError, so it bubbles past the new outer wrap unchanged
    and the structured ERROR log is NOT emitted (no SDK error to log).
    """
    pool, conn = _make_pool()
    conn.fetchrow = AsyncMock(
        side_effect=asyncpg.ForeignKeyViolationError("parent missing")
    )
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(KeyError) as excinfo:
            await client.add_message(
                conversation_id=_CID,
                user_id="u1",
                message=ChatMessage(role="user", content="hi"),
            )

    assert excinfo.value.args[0] == _CID
    # No add_message ERROR record should have been emitted: the FK
    # branch translates to KeyError before the outer except sees it.
    assert not [
        r for r in caplog.records if getattr(r, "operation", None) == "add_message"
    ]


@pytest.mark.asyncio
async def test_set_feedback_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool, _conn = _make_pool()
    pool.execute = AsyncMock(side_effect=_pg_error("deadlock"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.set_feedback(_MID, "u1", "positive")

    record = _find_error_record(caplog, "set_feedback")
    assert record.provider == "postgres"
    assert record.message_id == _MID
    assert record.user_id == "u1"


@pytest.mark.asyncio
async def test_upsert_agent_id_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool, _conn = _make_pool()
    pool.execute = AsyncMock(side_effect=_pg_error("connection reset"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.upsert_agent_id(name="contract", agent_id="asst_abc")

    record = _find_error_record(caplog, "upsert_agent_id")
    assert record.provider == "postgres"
    # `agent_name` (not `name`) avoids stdlib LogRecord.name collision.
    assert record.agent_name == "contract"
    assert record.agent_id == "asst_abc"


@pytest.mark.asyncio
async def test_upsert_runtime_config_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool, _conn = _make_pool()
    pool.execute = AsyncMock(side_effect=_pg_error("admin shutdown"))
    client = _make_client(pool=pool)

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await client.upsert_runtime_config(RuntimeConfig())

    record = _find_error_record(caplog, "upsert_runtime_config")
    assert record.provider == "postgres"
