"""Tests for the PostgreSQL chat-history client (Phase 4 task #28).

Pillar: Stable Core
Phase: 4

asyncpg's pool / connection / transaction surface is faked end-to-end
-- no live Postgres required. Tests assert on (a) parameterized SQL
shape (no string interpolation), (b) tenant-isolation (user_id always
in the WHERE clause), (c) lazy schema bootstrap exactly once, and
(d) FK-violation -> KeyError translation in `add_message`.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from shared.providers import databases
from shared.providers.databases.postgres import PostgresClient
from shared.settings import AppSettings, DatabaseSettings
from shared.types import ChatMessage


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
    return PostgresClient(
        settings=settings, credential=AsyncMock(), pool=pool
    )


def _conv_row(
    *,
    id: str = "11111111-1111-1111-1111-111111111111",
    user_id: str = "u1",
    title: str = "t",
    created_at: Any = None,
    updated_at: Any = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

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
) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "id": id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
        "feedback": feedback,
    }


_CID = "11111111-1111-1111-1111-111111111111"
_MID = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_postgres_registers_under_expected_key() -> None:
    # Key must equal `settings.database.db_type` Literal value so
    # `databases.create(db_type, ...)` works without name-mapping
    # (Hard Rule #4: no if/elif over provider keys).
    assert "postgresql" in databases.registry.keys()
    assert databases.registry.get("postgresql") is PostgresClient


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
    update_calls = [c for c in conn.execute.await_args_list if "UPDATE conversations" in c.args[0]]
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
