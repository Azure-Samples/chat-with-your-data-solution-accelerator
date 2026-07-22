"""Tests for the Cosmos DB chat-history client.

The async iterator + replace/read/delete surface of `azure.cosmos.aio`
is faked end-to-end -- no Cosmos emulator required. Tests assert on
(a) the wire shape (item dict shape sent to the SDK), (b) the
single-partition query parameters (no cross-partition fan-out), and
(c) the type-discriminator gating that prevents a message id from
being mistaken for a conversation id.
"""

from typing import Any, AsyncIterator, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
)

from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.databases.cosmosdb import (
    CosmosDBClient,
    CosmosFixedItemId,
    CosmosItemType,
    CosmosSystemPartition,
)
from backend.core.settings import AppSettings, DatabaseSettings
from backend.core.types import AdminAuditEntry, ChatMessage, RuntimeConfig

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
    container.upsert_item = AsyncMock(side_effect=lambda body: body)
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
    assert "cosmosdb" in databases_registry.registry.keys()
    assert databases_registry.registry.get("cosmosdb") is CosmosDBClient


# ---------------------------------------------------------------------------
# CosmosItemType discriminator
# ---------------------------------------------------------------------------


def test_cosmos_item_type_membership_is_frozen() -> None:
    """The `type=` discriminator is part of the wire contract --
    every persisted item has one, and every read-back path filters
    on it. A new value is a deliberate cross-cutting decision (new
    persistence model in the shared chat-history container), so
    membership is locked here. `CONFIG` is for the runtime-config
    row; `AGENT` is for the agent-id registry; `ADMIN_AUDIT` is for
    the append-only admin-audit log."""
    assert {member.value for member in CosmosItemType} == {
        "conversation",
        "message",
        "agent",
        "config",
        "admin_audit",
    }


def test_cosmos_item_type_config_serializes_as_bare_string() -> None:
    """`StrEnum` member compares equal to its raw string value, so
    the wire serialization stays exactly `"config"` -- existing
    code that reads `body["type"] == "config"` keeps working
    without coupling to the enum import (mirrors the
    `CosmosItemType.AGENT` precedent locked in
    `test_upsert_agent_id_writes_canonical_shape`)."""
    assert CosmosItemType.CONFIG == "config"
    assert CosmosItemType.CONFIG.value == "config"
    assert str(CosmosItemType.CONFIG) == "config"


def test_cosmos_system_partition_membership_is_frozen() -> None:
    """The `_system` synthetic partition is part of the wire
    contract: every non-user-scoped row (agents, runtime
    config) is pinned to it, and `BUILTIN_AGENTS` cardinality
    + the runtime-config singleton both live in this one partition.
    A new member is a deliberate cross-cutting decision (a second
    non-user-scoped surface), so membership is locked here -- the
    Hard Rule #11 sweep that introduced this enum
    relied on it staying a closed set."""
    assert {member.value for member in CosmosSystemPartition} == {"_system"}


def test_cosmos_system_partition_default_serializes_as_bare_string() -> None:
    """`StrEnum` member compares equal to its raw string value, so
    `partition_key=CosmosSystemPartition.DEFAULT` reaches the SDK
    as the bare string `"_system"` -- the wire shape and every
    existing assertion (e.g. `body["userId"] == "_system"` in the
    agent-registry tests) keep working without coupling to the
    enum import."""
    assert CosmosSystemPartition.DEFAULT == "_system"
    assert CosmosSystemPartition.DEFAULT.value == "_system"
    assert str(CosmosSystemPartition.DEFAULT) == "_system"


def test_cosmos_fixed_item_id_membership_is_frozen() -> None:
    """`CosmosFixedItemId` enumerates only the truly-fixed sentinel
    item ids that live under `CosmosSystemPartition.DEFAULT`. Agent
    rows use the agent `name` as their id and so are deliberately
    NOT in this enum -- adding a member here is a deliberate new
    singleton row, not a generic id container. Locked at one
    member (`RUNTIME_CONFIG`); no member was added for agents
    because agent ids are caller-supplied."""
    assert {member.value for member in CosmosFixedItemId} == {"runtime"}


def test_cosmos_fixed_item_id_runtime_config_serializes_as_bare_string() -> None:
    """`StrEnum` member compares equal to its raw string value, so
    `item=CosmosFixedItemId.RUNTIME_CONFIG` reaches the Cosmos
    SDK as the bare string `"runtime"` -- the wire shape stays
    exactly the documented singleton id."""
    assert CosmosFixedItemId.RUNTIME_CONFIG == "runtime"
    assert CosmosFixedItemId.RUNTIME_CONFIG.value == "runtime"
    assert str(CosmosFixedItemId.RUNTIME_CONFIG) == "runtime"


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
    client, container = _make_client(container_items=[{"id": "m1"}, {"id": "m2"}])

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


@pytest.mark.asyncio
async def test_delete_conversation_logs_when_message_already_gone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Per v2/docs/exception_handling_policy.md, the inner per-message
    `CosmosResourceNotFoundError` catch must log via `logger.debug`
    (not silently `pass`) so the idempotent skip is visible.

    Drives the path where the message-list query returns rows but
    `delete_item` raises NotFound for one of them (e.g., another
    caller already cleaned it up). The outer `delete_item` for the
    conversation parent succeeds.
    """
    client, container = _make_client(container_items=[{"id": "m1"}])
    # First call (message m1) raises NotFound; second call (conversation
    # parent) succeeds with a normal return.
    container.delete_item = AsyncMock(
        side_effect=[
            CosmosResourceNotFoundError(message="message m1 gone"),
            None,
        ]
    )
    with caplog.at_level("DEBUG", logger="backend.core.providers.databases.cosmosdb"):
        await client.delete_conversation("c1", "u1")

    # Both deletes were attempted (the NotFound did not abort the loop).
    assert container.delete_item.await_count == 2
    # The idempotent skip was logged with both ids in the message.
    assert any(
        "message m1 already gone" in rec.getMessage()
        and "conversation c1 purge" in rec.getMessage()
        for rec in caplog.records
    ), f"expected idempotent-skip debug log, got: {[r.getMessage() for r in caplog.records]}"


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
async def test_add_message_round_trips_metadata() -> None:
    """An assistant turn's citations travel into the message item dict and
    read back via `_to_message`. Cosmos stores the dict natively, so the
    value is written as-is (no serialization) and surfaces on the record."""
    client, container = _make_client()
    metadata = {"citations": [{"id": "doc1", "title": "Benefit_Options.pdf"}]}

    rec = await client.add_message(
        conversation_id="c1",
        user_id="u1",
        message=ChatMessage(role="assistant", content="answer", metadata=metadata),
    )

    msg_body = container.create_item.await_args.kwargs["body"]
    # Written into the item dict as the native object (no json.dumps).
    assert msg_body["metadata"] == metadata
    # And surfaced on the returned record (create_item echoes the body).
    assert rec.metadata == metadata


@pytest.mark.asyncio
async def test_to_message_defaults_metadata_to_empty_dict_for_legacy_doc() -> None:
    """A message doc written before the metadata key existed reads back
    with `metadata == {}` rather than raising."""
    legacy_item = {
        "id": "m-legacy",
        "conversationId": "c1",
        "role": "user",
        "content": "q",
        "createdAt": "2026-04-28T00:00:00+00:00",
    }

    record = CosmosDBClient._to_message(legacy_item)

    assert record.metadata == {}


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


# ---------------------------------------------------------------------------
# Agent registry (get_agent_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agent_id_returns_none_when_item_missing() -> None:
    """Cold start -- no row written yet. Must return None, not raise."""
    client, container = _make_client()
    # Default `read_item` already raises CosmosResourceNotFoundError.
    assert await client.get_agent_id("cwyd") is None
    container.read_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_agent_id_uses_synthetic_system_partition() -> None:
    """Agents are not user-scoped -- the lookup must pin to the
    `_system` partition so it does not fan out across user partitions
    (which would multiply RU cost by user count)."""
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": "cwyd",
            "userId": "_system",
            "type": "agent",
            "agentId": "asst_abc123",
        }
    )
    out = await client.get_agent_id("cwyd")
    assert out == "asst_abc123"
    kwargs = container.read_item.await_args.kwargs
    assert kwargs["item"] == "cwyd"
    assert kwargs["partition_key"] == "_system"


@pytest.mark.asyncio
async def test_get_agent_id_refuses_non_agent_typed_item() -> None:
    """Defensive type check: if the same id ever collides with a
    conversation or message id, the resolver must NOT return its
    payload as an agent id (that would cross-wire the orchestrator
    onto a random Foundry agent)."""
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": "cwyd",
            "userId": "u1",
            "type": "conversation",
            "title": "definitely not an agent",
        }
    )
    assert await client.get_agent_id("cwyd") is None


@pytest.mark.asyncio
async def test_get_agent_id_returns_none_when_agent_id_field_missing() -> None:
    """Malformed row (right type, missing payload) must read as
    'not bootstrapped' so the resolver re-creates rather than raising
    a KeyError mid-request."""
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={"id": "cwyd", "userId": "_system", "type": "agent"}
    )
    assert await client.get_agent_id("cwyd") is None


# ---------------------------------------------------------------------------
# Agent registry (upsert_agent_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_agent_id_writes_canonical_shape() -> None:
    """Wire shape: id=name, userId=_system synthetic partition,
    type=CosmosItemType.AGENT (StrEnum -> serializes as the bare
    string `"agent"`), agentId carries the Foundry id, and both
    timestamps are present so an audit query can sort either way.
    """
    client, container = _make_client()
    await client.upsert_agent_id("cwyd", "asst_abc123")

    container.upsert_item.assert_awaited_once()
    body = container.upsert_item.await_args.kwargs["body"]
    assert body["id"] == "cwyd"
    assert body["userId"] == "_system"
    # `StrEnum` member compares equal to its string value; the wire
    # serialization is just `"agent"` (validates the Hard Rule
    # #11 sub-rule end-to-end).
    assert body["type"] == CosmosItemType.AGENT
    assert body["type"] == "agent"
    assert body["agentId"] == "asst_abc123"
    assert "createdAt" in body and "updatedAt" in body


@pytest.mark.asyncio
async def test_upsert_agent_id_uses_upsert_not_create() -> None:
    """Must use `upsert_item` (atomic CREATE-or-REPLACE) rather than
    `create_item` -- otherwise the lazy resolver would
    raise CosmosResourceExistsError on its second-and-later writes
    (e.g. when Foundry 404s a stale id and we rewrite it).
    """
    client, container = _make_client()
    await client.upsert_agent_id("cwyd", "asst_abc123")
    container.upsert_item.assert_awaited_once()
    container.create_item.assert_not_awaited()
    container.replace_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_agent_id_is_idempotent_on_repeat_call() -> None:
    """Two writes with the same (name, agent_id) must not raise
    (the fake `upsert_item` echoes the body, mirroring the SDK's
    REPLACE-on-conflict semantics). New `agent_id` for an existing
    `name` must overwrite the prior `agentId` value -- this is the
    rewrite path the resolver depends on.
    """
    client, container = _make_client()
    await client.upsert_agent_id("cwyd", "asst_old")
    await client.upsert_agent_id("cwyd", "asst_new")
    assert container.upsert_item.await_count == 2
    second_body = container.upsert_item.await_args_list[1].kwargs["body"]
    assert second_body["agentId"] == "asst_new"


# ---------------------------------------------------------------------------
# Runtime config (get_runtime_config)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_runtime_config_returns_none_when_row_missing() -> None:
    """Cold start -- no override row written yet. The Cosmos point-read
    raises `CosmosResourceNotFoundError` and `get_runtime_config()`
    must surface that as `None` (not raise), so the admin router
    falls through to env defaults instead of returning a 500."""
    client, _container = _make_client()
    # Default `read_item` already raises CosmosResourceNotFoundError
    # (set in `_make_client`); no override needed.
    assert await client.get_runtime_config() is None


@pytest.mark.asyncio
async def test_get_runtime_config_point_read_uses_system_partition() -> None:
    """The runtime-config row is not user-scoped, so the point-read
    must target the synthetic `_system` partition (mirrors the
    AGENT row precedent). Reading from a per-user
    partition would silently miss the row and force the resolver
    to over-provision RU on a cross-partition fan-out scan."""
    client, container = _make_client()
    await client.get_runtime_config()
    container.read_item.assert_awaited_once_with(
        item=CosmosFixedItemId.RUNTIME_CONFIG,
        partition_key=CosmosSystemPartition.DEFAULT,
    )


@pytest.mark.asyncio
async def test_get_runtime_config_round_trips_persisted_payload() -> None:
    """Hit path: the stored item carries `payload` as a Pydantic JSON
    dump; `get_runtime_config()` must re-hydrate it into a
    `RuntimeConfig` instance with every field round-tripping
    (booleans included -- explicit False must not collapse into
    None)."""
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
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": CosmosFixedItemId.RUNTIME_CONFIG,
            "userId": CosmosSystemPartition.DEFAULT,
            "type": CosmosItemType.CONFIG,
            "payload": persisted.model_dump(mode="json"),
        }
    )

    rebuilt = await client.get_runtime_config()
    assert rebuilt == persisted


@pytest.mark.asyncio
async def test_get_runtime_config_rejects_wrong_type_discriminator() -> None:
    """Defensive type check: if a future refactor accidentally writes
    a non-config item under the same id, refuse to deserialize its
    `payload` rather than mis-resolving as a `RuntimeConfig`. Same
    invariant `get_agent_id` enforces."""
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": CosmosFixedItemId.RUNTIME_CONFIG,
            "userId": CosmosSystemPartition.DEFAULT,
            "type": CosmosItemType.AGENT,  # wrong discriminator
            "payload": {"orchestrator_name": "langgraph"},
        }
    )
    assert await client.get_runtime_config() is None


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
    client, container = _make_client()
    container.read_item = AsyncMock(
        return_value={
            "id": CosmosFixedItemId.RUNTIME_CONFIG,
            "userId": CosmosSystemPartition.DEFAULT,
            "type": CosmosItemType.CONFIG,
            "payload": {},
        }
    )
    rebuilt = await client.get_runtime_config()
    assert rebuilt == RuntimeConfig()


# ---------------------------------------------------------------------------
# Runtime config (upsert_runtime_config)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_runtime_config_writes_canonical_shape() -> None:
    """Wire shape: id=CosmosFixedItemId.RUNTIME_CONFIG, userId =
    CosmosSystemPartition.DEFAULT (the synthetic `_system`
    partition), type=CosmosItemType.CONFIG (StrEnum -> serializes as
    bare string `"config"`), payload carries the Pydantic JSON dump
    of the RuntimeConfig (mode="json" so `datetime`-shaped strings
    round-trip), and both timestamps are present so an audit query
    can sort either way. Mirrors the `upsert_agent_id` precedent.
    """
    config = RuntimeConfig(
        orchestrator_name="agent_framework",
        openai_temperature=0.7,
        openai_max_tokens=2048,
        search_use_semantic_search=False,
        search_top_k=10,
        log_level="DEBUG",
        updated_at="2026-05-06T12:00:00+00:00",
        updated_by="alice@example.com",
    )
    client, container = _make_client()
    await client.upsert_runtime_config(config)

    container.upsert_item.assert_awaited_once()
    body = container.upsert_item.await_args.kwargs["body"]
    assert body["id"] == CosmosFixedItemId.RUNTIME_CONFIG
    assert body["id"] == "runtime"
    assert body["userId"] == CosmosSystemPartition.DEFAULT
    assert body["userId"] == "_system"
    assert body["type"] == CosmosItemType.CONFIG
    assert body["type"] == "config"
    assert body["payload"] == config.model_dump(mode="json")
    assert "createdAt" in body and "updatedAt" in body


@pytest.mark.asyncio
async def test_upsert_runtime_config_uses_upsert_not_create() -> None:
    """Must use `upsert_item` (atomic CREATE-or-REPLACE) rather than
    `create_item` -- otherwise the second-and-later writes (every
    PATCH after the first) would raise CosmosResourceExistsError
    against the singleton id. Mirrors the `upsert_agent_id`
    invariant locked in `test_upsert_agent_id_uses_upsert_not_create`.
    """
    client, container = _make_client()
    await client.upsert_runtime_config(RuntimeConfig())
    container.upsert_item.assert_awaited_once()
    container.create_item.assert_not_awaited()
    container.replace_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_runtime_config_is_idempotent_on_repeat_call() -> None:
    """Two writes with overlapping fields must not raise (the fake
    `upsert_item` echoes the body, mirroring the SDK's
    REPLACE-on-conflict semantics). The second call's payload must
    win -- this is the rewrite path the PATCH route
    relies on so an operator can change `openai_temperature` from
    0.5 to 0.9 without first clearing the row.
    """
    client, container = _make_client()
    first = RuntimeConfig(openai_temperature=0.5)
    second = RuntimeConfig(openai_temperature=0.9)
    await client.upsert_runtime_config(first)
    await client.upsert_runtime_config(second)
    assert container.upsert_item.await_count == 2
    second_body = container.upsert_item.await_args_list[1].kwargs["body"]
    assert second_body["payload"]["openai_temperature"] == 0.9


@pytest.mark.asyncio
async def test_upsert_runtime_config_serializes_empty_payload_for_cleared_overrides() -> (
    None
):
    """Boundary: a `RuntimeConfig()` with every field `None`
    serializes to a JSON object whose keys are all `null` (NOT an
    empty `{}`) because Pydantic v2's default `model_dump`
    includes Optional fields. This locks the wire shape so the
    next `get_runtime_config` round-trips back to `RuntimeConfig()`
    exactly (validated by the matching get test). The 'cleared all
    overrides' UX path stays a first-class state distinct from
    'no row at all' (cold start).
    """
    client, container = _make_client()
    await client.upsert_runtime_config(RuntimeConfig())
    body = container.upsert_item.await_args.kwargs["body"]
    assert body["payload"] == RuntimeConfig().model_dump(mode="json")


# ---------------------------------------------------------------------------
# Failure-path coverage (provider try/except sweep)
# ---------------------------------------------------------------------------
#
# Per v2/docs/exception_handling_policy.md (Provider-entry-points row),
# every Cosmos SDK call at a provider boundary catches
# `CosmosHttpResponseError` (umbrella for 4xx/5xx including 429 throttle,
# 409 conflict, 412 precondition failure, 503 service unavailable),
# logs structured context via `logger.exception`, and re-raises so the
# router layer can map to a sanitized HTTPException.
#
# The two exceptions to the "log + re-raise" rule are:
# - `delete_conversation` per-message NotFound (idempotent skip,
#   `logger.debug`, swallow).
# - `add_message` parent updatedAt bump (best-effort, `logger.warning`,
#   swallow) -- covered below.
#
# All tests here drive an `AsyncMock(side_effect=CosmosHttpResponseError(...))`
# at the SDK boundary, assert (a) the exception bubbles out unchanged
# (re-raised, not swallowed or wrapped), and (b) the structured log
# fires at ERROR level with the canonical `extra` schema
# {"operation": <method_name>, "provider": "cosmos", ...domain_ids}.

_LOGGER_NAME = "backend.core.providers.databases.cosmosdb"


def _http_error(
    status_code: int = 429, message: str = "throttled"
) -> CosmosHttpResponseError:
    """Construct a `CosmosHttpResponseError` without a real `azure.core`
    HTTP response object. The SDK constructor accepts `status_code` +
    `message` directly, which exercises the same code path the real
    SDK takes when it parses an HTTP failure.
    """
    return CosmosHttpResponseError(status_code=status_code, message=message)


def _find_error_record(caplog: pytest.LogCaptureFixture, operation: str) -> Any:
    """Return the single ERROR record for `operation`, failing the test
    with a useful message if zero or multiple matches surface. Keeping
    this lookup explicit (vs `caplog.records[0]`) protects against
    test pollution from neighbouring code paths emitting their own logs.
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


@pytest.mark.asyncio
async def test_create_conversation_logs_and_reraises_on_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, container = _make_client()
    container.create_item = AsyncMock(side_effect=_http_error(429, "throttled"))

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.create_conversation(user_id="u1", title="t")

    record = _find_error_record(caplog, "create_conversation")
    assert record.provider == "cosmos"
    assert record.user_id == "u1"
    # Make sure the SDK was actually invoked (no silent short-circuit).
    container.create_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_rename_conversation_logs_and_reraises_on_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, container = _make_client()
    # _read_item must succeed (returns the existing conversation) so the
    # method reaches the replace_item call we want to fail.
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
    container.replace_item = AsyncMock(
        side_effect=_http_error(412, "precondition failed")
    )

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.rename_conversation("c1", "u1", "new title")

    record = _find_error_record(caplog, "rename_conversation")
    assert record.provider == "cosmos"
    assert record.conversation_id == "c1"
    assert record.user_id == "u1"
    container.replace_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_message_logs_and_reraises_on_http_error_during_create(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The message create_item is the load-bearing call -- if it fails,
    the conversation has no new turn and the caller must learn about it.
    """
    client, container = _make_client()
    container.create_item = AsyncMock(side_effect=_http_error(429, "throttled"))

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.add_message(
                conversation_id="c1",
                user_id="u1",
                message=ChatMessage(role="user", content="hi"),
            )

    record = _find_error_record(caplog, "add_message")
    assert record.provider == "cosmos"
    assert record.conversation_id == "c1"
    assert record.user_id == "u1"
    # The parent-bump replace_item must NOT have been attempted: failure
    # of create_item short-circuits the rest of the method.
    container.replace_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_message_swallows_and_warns_on_parent_bump_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The conversation `updatedAt` bump is best-effort: the message
    already persisted, and the SSE stream must keep flowing. A throttle
    on the parent replace_item must be logged at WARNING and swallowed
    (per the docstring + policy doc), and the message return value must
    be unchanged.
    """
    client, container = _make_client()
    # Parent exists, so the bump path is taken.
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
    # First create_item succeeds; replace_item (parent bump) raises.
    container.replace_item = AsyncMock(side_effect=_http_error(429, "throttled"))

    with caplog.at_level("WARNING", logger=_LOGGER_NAME):
        result = await client.add_message(
            conversation_id="c1",
            user_id="u1",
            message=ChatMessage(role="user", content="hi"),
        )

    # Message was returned despite the bump failure (best-effort intent).
    assert result.role == "user"
    assert result.content == "hi"

    # WARNING-level log fired with the canonical extra schema.
    matches = [
        r
        for r in caplog.records
        if r.levelname == "WARNING"
        and getattr(r, "operation", None) == "add_message_parent_bump"
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 WARNING record for parent bump, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    record = matches[0]
    assert record.provider == "cosmos"
    assert record.conversation_id == "c1"
    assert record.user_id == "u1"
    # The bump was actually attempted (i.e. failure isn't a missing call).
    container.replace_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_agent_id_logs_and_reraises_on_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, container = _make_client()
    container.upsert_item = AsyncMock(side_effect=_http_error(503, "unavailable"))

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.upsert_agent_id(name="contract", agent_id="asst_abc")

    record = _find_error_record(caplog, "upsert_agent_id")
    assert record.provider == "cosmos"
    # `agent_name` (not `name`) on the record because `name` is a
    # stdlib LogRecord attribute the standard adapters won't shadow.
    assert record.agent_name == "contract"
    assert record.agent_id == "asst_abc"
    container.upsert_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_runtime_config_logs_and_reraises_on_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, container = _make_client()
    container.upsert_item = AsyncMock(side_effect=_http_error(429, "throttled"))

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.upsert_runtime_config(RuntimeConfig())

    record = _find_error_record(caplog, "upsert_runtime_config")
    assert record.provider == "cosmos"
    container.upsert_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_feedback_logs_and_reraises_on_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, container = _make_client()
    # _read_item must return an existing message so the method reaches
    # the replace_item call we want to fail.
    container.read_item = AsyncMock(
        return_value={
            "id": "m1",
            "userId": "u1",
            "type": "message",
            "conversationId": "c1",
            "role": "assistant",
            "content": "answer",
        }
    )
    container.replace_item = AsyncMock(side_effect=_http_error(429, "throttled"))

    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.set_feedback(
                message_id="m1", user_id="u1", feedback="positive"
            )

    record = _find_error_record(caplog, "set_feedback")
    assert record.provider == "cosmos"
    assert record.message_id == "m1"
    assert record.user_id == "u1"
    container.replace_item.assert_awaited_once()


# ---------------------------------------------------------------------------
# Admin audit (write_admin_audit)
#
# Append-only audit row written after every successful PATCH /api/admin/config.
# Pinned to the synthetic `_system` partition so admin-audit
# queries are single-partition (no cross-user fan-out). Cardinality is
# bounded by `# of admin PATCH operations` -- single-tenant CWYD deployments
# realistically peak at ~hundreds/year, well under the 20 GB partition cap.
# ---------------------------------------------------------------------------


def test_cosmos_item_type_admin_audit_serializes_as_bare_string() -> None:
    """`StrEnum` member compares equal to its raw string value, so
    the wire shape stays exactly `"admin_audit"` -- existing
    consumers reading `body["type"] == "admin_audit"` keep working
    without coupling to the enum import (mirrors the
    `CosmosItemType.CONFIG` precedent)."""
    assert CosmosItemType.ADMIN_AUDIT == "admin_audit"
    assert CosmosItemType.ADMIN_AUDIT.value == "admin_audit"
    assert str(CosmosItemType.ADMIN_AUDIT) == "admin_audit"


@pytest.mark.asyncio
async def test_write_admin_audit_writes_canonical_shape() -> None:
    """Wire shape: id is a fresh UUID (storage-assigned, mirrors
    `add_message`), userId = `_system` partition (non-user-scoped
    audit row, mirrors AGENT + CONFIG), type = `admin_audit`
    (StrEnum -> bare string), actor / action are the operator
    fingerprint, before / after carry the Pydantic JSON dumps of
    the RuntimeConfig snapshots (`mode="json"` so future
    datetime/UUID fields round-trip), and `createdAt` is an
    ISO-8601 UTC timestamp so an audit query can sort by recency.
    Mirrors the `upsert_runtime_config` write shape, but uses
    `create_item` (not `upsert_item`) because the audit log is
    append-only -- a UUID collision would be a silent log loss."""
    before = RuntimeConfig(openai_temperature=0.1)
    after = RuntimeConfig(openai_temperature=0.9, updated_by="u-admin")
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=before,
        after=after,
    )
    client, container = _make_client()
    await client.write_admin_audit(entry)

    container.create_item.assert_awaited_once()
    body = container.create_item.await_args.kwargs["body"]
    assert body["id"]  # UUID assigned
    assert body["userId"] == CosmosSystemPartition.DEFAULT
    assert body["type"] == CosmosItemType.ADMIN_AUDIT
    assert body["actor"] == "u-admin"
    assert body["action"] == "patch_config"
    assert body["before"] == before.model_dump(mode="json")
    assert body["after"] == after.model_dump(mode="json")
    assert body["createdAt"]  # ISO-8601 timestamp


@pytest.mark.asyncio
async def test_write_admin_audit_serializes_before_as_none_for_first_patch() -> None:
    """The first-ever PATCH against a fresh deployment has no prior
    override row to snapshot, so `entry.before is None`. The wire
    shape must persist `None` (JSON null) -- the audit history is
    truthful about the cold-start moment, not silently filled with
    an empty `RuntimeConfig()` shape that an operator query would
    misread as "every field was already overridden to None"."""
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.5),
    )
    client, container = _make_client()
    await client.write_admin_audit(entry)
    body = container.create_item.await_args.kwargs["body"]
    assert body["before"] is None


@pytest.mark.asyncio
async def test_write_admin_audit_assigns_distinct_ids_per_call() -> None:
    """Append-only invariant: two writes of the same logical entry
    must end up as two distinct rows. UUID4 collision risk is
    negligible (~1 in 2^122) but the test pins the contract so a
    future refactor that hard-codes the id (e.g. accidentally
    pinning to the `_system` partition's `RUNTIME_CONFIG`
    sentinel) is caught immediately."""
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.5),
    )
    client, container = _make_client()
    await client.write_admin_audit(entry)
    await client.write_admin_audit(entry)
    assert container.create_item.await_count == 2
    first_id = container.create_item.await_args_list[0].kwargs["body"]["id"]
    second_id = container.create_item.await_args_list[1].kwargs["body"]["id"]
    assert first_id != second_id


@pytest.mark.asyncio
async def test_write_admin_audit_logs_and_reraises_on_sdk_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SDK boundary policy (v2/docs/exception_handling_policy.md):
    every SDK call wrapped in try/except logs structured context
    and re-raises -- the audit row reaching the DB or not is a
    correctness-critical signal the route layer must observe (the
    PATCH route will let the audit-write failure bubble
    up rather than silently dropping the audit row).
    """
    client, container = _make_client()
    container.create_item = AsyncMock(
        side_effect=CosmosHttpResponseError(message="boom")
    )
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.5),
    )
    with caplog.at_level("ERROR", logger=_LOGGER_NAME):
        with pytest.raises(CosmosHttpResponseError):
            await client.write_admin_audit(entry)
    record = _find_error_record(caplog, "write_admin_audit")
    assert record.provider == "cosmos"
