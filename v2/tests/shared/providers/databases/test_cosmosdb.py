"""Tests for the Cosmos DB chat-history client (Phase 4 task #27).

Pillar: Stable Core
Phase: 4

The async iterator + replace/read/delete surface of `azure.cosmos.aio`
is faked end-to-end -- no Cosmos emulator required. Tests assert on
(a) the wire shape (item dict shape sent to the SDK), (b) the
single-partition query parameters (no cross-partition fan-out), and
(c) the type-discriminator gating that prevents a message id from
being mistaken for a conversation id.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from shared.providers import databases
from shared.providers.databases.cosmosdb import CosmosDBClient
from shared.settings import AppSettings, DatabaseSettings
from shared.types import ChatMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAsyncIter:
    def __init__(self, items: Iterable[dict[str, Any]]) -> None:
        self._items = list(items)

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        async def gen() -> AsyncIterator[dict[str, Any]]:
            for it in self._items:
                yield it

        return gen()


def _make_client(
    *,
    container_items: list[dict[str, Any]] | None = None,
) -> tuple[CosmosDBClient, MagicMock]:
    """Build a `CosmosDBClient` whose container is a hand-rolled mock.

    Returns (client, container_mock) so individual tests can assert on
    `container_mock.create_item.await_args` etc.
    """
    settings = MagicMock(spec=AppSettings)
    settings.database = DatabaseSettings(
        db_type="cosmosdb",
        index_store="AzureSearch",
        cosmos_endpoint="https://example.documents.azure.com:443/",
        cosmos_account_name="cosno-test",
    )
    container = MagicMock()
    container.create_item = AsyncMock(side_effect=lambda body: body)
    container.replace_item = AsyncMock(side_effect=lambda item, body: body)
    container.delete_item = AsyncMock(return_value=None)
    container.read_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(message="not found")
    )
    container.query_items = MagicMock(
        return_value=_FakeAsyncIter(container_items or [])
    )

    fake_cosmos_client = MagicMock()
    fake_cosmos_client.close = AsyncMock(return_value=None)

    client = CosmosDBClient(
        settings=settings, credential=MagicMock(), client=fake_cosmos_client
    )
    # Skip lazy bootstrap so tests don't poke into private internals via
    # the database/container chain.
    client._container = container  # type: ignore[attr-defined]
    return client, container


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_cosmosdb_registers_under_expected_key() -> None:
    assert "cosmosdb" in databases.registry.keys()
    assert databases.registry.get("cosmosdb") is CosmosDBClient


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_conversation_writes_discriminated_item() -> None:
    client, container = _make_client()

    conv = await client.create_conversation(user_id="u1", title="hi")

    assert conv.user_id == "u1"
    assert conv.title == "hi"
    assert conv.id  # uuid assigned
    assert conv.created_at and conv.updated_at
    body = container.create_item.await_args.kwargs["body"]
    assert body["type"] == "conversation"
    assert body["userId"] == "u1"
    assert body["title"] == "hi"
    assert body["createdAt"] == body["updatedAt"]


@pytest.mark.asyncio
async def test_list_conversations_uses_single_partition_query() -> None:
    client, container = _make_client(
        container_items=[
            {
                "id": "c1",
                "userId": "u1",
                "type": "conversation",
                "title": "first",
                "createdAt": "2026-04-28T00:00:00+00:00",
                "updatedAt": "2026-04-28T00:01:00+00:00",
            }
        ]
    )

    convs = await client.list_conversations(user_id="u1")

    assert len(convs) == 1
    assert convs[0].id == "c1"
    assert convs[0].title == "first"
    call = container.query_items.call_args
    # Single-partition query (no cross-partition flag) and parameterized
    # type filter (no string interpolation).
    assert call.kwargs["partition_key"] == "u1"
    assert {"name": "@type", "value": "conversation"} in call.kwargs["parameters"]


@pytest.mark.asyncio
async def test_get_conversation_returns_none_when_missing() -> None:
    client, _ = _make_client()
    # Default fake `read_item` raises NotFound -> get returns None.
    assert await client.get_conversation("missing", "u1") is None


@pytest.mark.asyncio
async def test_get_conversation_ignores_message_typed_items() -> None:
    """A message id must NOT be returned as a conversation."""
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": "m1",
            "userId": "u1",
            "type": "message",
            "conversationId": "c1",
            "role": "user",
            "content": "hi",
        }
    )
    assert await client.get_conversation("m1", "u1") is None


@pytest.mark.asyncio
async def test_rename_conversation_raises_keyerror_when_missing() -> None:
    client, _ = _make_client()
    with pytest.raises(KeyError):
        await client.rename_conversation("missing", "u1", "new title")


@pytest.mark.asyncio
async def test_rename_conversation_bumps_updated_at_and_title() -> None:
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": "c1",
            "userId": "u1",
            "type": "conversation",
            "title": "old",
            "createdAt": "2026-04-28T00:00:00+00:00",
            "updatedAt": "2026-04-28T00:00:00+00:00",
        }
    )
    out = await client.rename_conversation("c1", "u1", "new")

    assert out.title == "new"
    body = container.replace_item.await_args.kwargs["body"]
    assert body["title"] == "new"
    assert body["updatedAt"] != "2026-04-28T00:00:00+00:00"


@pytest.mark.asyncio
async def test_delete_conversation_purges_messages_then_parent() -> None:
    client, container = _make_client(
        container_items=[{"id": "m1"}, {"id": "m2"}]
    )

    await client.delete_conversation("c1", "u1")

    # 2 messages + 1 conversation = 3 deletes, all in user partition.
    assert container.delete_item.await_count == 3
    for call in container.delete_item.await_args_list:
        assert call.kwargs["partition_key"] == "u1"


@pytest.mark.asyncio
async def test_delete_conversation_is_idempotent_on_missing_parent() -> None:
    client, container = _make_client(container_items=[])
    container.delete_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(message="gone")
    )
    # Must not raise.
    await client.delete_conversation("missing", "u1")


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_message_writes_message_and_bumps_parent() -> None:
    client, container = _make_client()
    # Parent exists for the second `read_item` call inside add_message.
    container.read_item = AsyncMock(
        return_value={
            "id": "c1",
            "userId": "u1",
            "type": "conversation",
            "title": "t",
            "createdAt": "2026-04-28T00:00:00+00:00",
            "updatedAt": "2026-04-28T00:00:00+00:00",
        }
    )

    rec = await client.add_message(
        conversation_id="c1",
        user_id="u1",
        message=ChatMessage(role="user", content="hi"),
    )

    assert rec.conversation_id == "c1"
    assert rec.role == "user"
    assert rec.content == "hi"
    assert rec.id  # uuid assigned

    msg_body = container.create_item.await_args.kwargs["body"]
    assert msg_body["type"] == "message"
    assert msg_body["conversationId"] == "c1"
    # Parent bump replaced the parent doc.
    parent_body = container.replace_item.await_args.kwargs["body"]
    assert parent_body["id"] == "c1"
    assert parent_body["updatedAt"] != "2026-04-28T00:00:00+00:00"


@pytest.mark.asyncio
async def test_add_message_silently_skips_parent_bump_when_missing() -> None:
    client, container = _make_client()
    # Default read_item raises NotFound -> parent bump skipped, message
    # still persisted.
    rec = await client.add_message(
        conversation_id="missing",
        user_id="u1",
        message=ChatMessage(role="user", content="hi"),
    )
    assert rec.content == "hi"
    container.replace_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_messages_orders_by_created_at_asc() -> None:
    client, container = _make_client(
        container_items=[
            {
                "id": "m1",
                "userId": "u1",
                "type": "message",
                "conversationId": "c1",
                "role": "user",
                "content": "a",
                "createdAt": "2026-04-28T00:00:00+00:00",
            },
            {
                "id": "m2",
                "userId": "u1",
                "type": "message",
                "conversationId": "c1",
                "role": "assistant",
                "content": "b",
                "createdAt": "2026-04-28T00:00:01+00:00",
            },
        ]
    )

    msgs = await client.list_messages(conversation_id="c1", user_id="u1")
    assert [m.id for m in msgs] == ["m1", "m2"]
    query = container.query_items.call_args.kwargs["query"]
    assert "ORDER BY c.createdAt ASC" in query


@pytest.mark.asyncio
async def test_set_feedback_raises_keyerror_when_message_missing() -> None:
    client, _ = _make_client()
    with pytest.raises(KeyError):
        await client.set_feedback("missing", "u1", "positive")


@pytest.mark.asyncio
async def test_set_feedback_writes_value_back() -> None:
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": "m1",
            "userId": "u1",
            "type": "message",
            "conversationId": "c1",
            "role": "user",
            "content": "hi",
        }
    )
    await client.set_feedback("m1", "u1", "positive")
    body = container.replace_item.await_args.kwargs["body"]
    assert body["feedback"] == "positive"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aclose_closes_underlying_client() -> None:
    client, _ = _make_client()
    inner = client._client  # type: ignore[attr-defined]
    await client.aclose()
    inner.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_container_raises_without_endpoint() -> None:
    settings = MagicMock(spec=AppSettings)
    settings.database = DatabaseSettings(
        db_type="cosmosdb",
        index_store="AzureSearch",
        cosmos_endpoint="https://x.documents.azure.com:443/",
    )
    # Force the missing-endpoint guard by clearing post-construction.
    settings.database.cosmos_endpoint = ""
    client = CosmosDBClient(settings=settings, credential=MagicMock())
    with pytest.raises(RuntimeError, match="AZURE_COSMOS_ENDPOINT"):
        await client.list_conversations("u1")
