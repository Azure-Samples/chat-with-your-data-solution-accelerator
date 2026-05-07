"""Tests for `BaseAgentsProvider.get_or_create_agent` (CU-010c).

Pillar: Stable Core
Phase: Cleanup audit batch 2 (CU-010c)

The lazy resolver is implemented on the base class (provider-agnostic
algorithm using `self.get_client()` for SDK calls). These tests
exercise it through a minimal concrete subclass that injects a fake
`AgentsClient` and a fake `BaseDatabaseClient`. No Foundry, no DB.

Coverage:
  * cache hit short-circuits DB + Foundry
  * DB hit + Foundry validation -> cached and returned
  * DB hit + Foundry 404 -> falls through to recreate (orphan recovery)
  * cold start -> create + persist + cache
  * concurrent first-requests serialize on a per-key lock (single create)
"""

import asyncio
import logging
from typing import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    ResourceNotFoundError,
    ServiceRequestError,
)

from backend.core.agents.definitions import AgentDefinition
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.settings import AppSettings
from backend.core.types import (
    AdminAuditEntry,
    ChatMessage,
    Conversation,
    MessageRecord,
    RuntimeConfig,
)


_AGENTS_BASE_LOGGER_NAME = "backend.core.providers.agents.base"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubAgentsProvider(BaseAgentsProvider):
    """Minimal concrete subclass exposing an injected fake client."""

    def __init__(
        self,
        settings: MagicMock,
        credential: MagicMock,
        *,
        client: MagicMock,
    ) -> None:
        super().__init__(settings, credential)
        self._injected_client = client

    def get_client(self) -> MagicMock:  # type: ignore[override]
        return self._injected_client

    async def aclose(self) -> None:
        return None


class _StubDB(BaseDatabaseClient):
    """In-memory fake DB so tests don't depend on Cosmos/Postgres."""

    def __init__(
        self,
        *,
        seed: dict[str, str] | None = None,
    ) -> None:
        # NB: not calling super().__init__ -- we don't need credential
        # bookkeeping for an in-memory stub.
        self._rows: dict[str, str] = dict(seed or {})
        self.get_calls: list[str] = []
        self.upsert_calls: list[tuple[str, str]] = []

    async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
        return []

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        return None

    async def create_conversation(
        self, user_id: str, title: str
    ) -> Conversation:
        return Conversation(id="c1", user_id=user_id, title=title)

    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
        return Conversation(id=conversation_id, user_id=user_id, title=title)

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        return None

    async def list_messages(
        self, conversation_id: str, user_id: str
    ) -> Sequence[MessageRecord]:
        return []

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        message: ChatMessage,
    ) -> MessageRecord:
        return MessageRecord(
            id="m1",
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
        )

    async def set_feedback(
        self, message_id: str, user_id: str, feedback: str
    ) -> None:
        return None

    async def get_agent_id(self, name: str) -> str | None:
        self.get_calls.append(name)
        return self._rows.get(name)

    async def upsert_agent_id(self, name: str, agent_id: str) -> None:
        self.upsert_calls.append((name, agent_id))
        self._rows[name] = agent_id

    async def get_runtime_config(self) -> RuntimeConfig | None:
        return None

    async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
        return None

    async def write_admin_audit(self, entry: AdminAuditEntry) -> None:
        return None


def _definition(name: str = "cwyd") -> AgentDefinition:
    return AgentDefinition(
        name=name,
        description="d",
        deployment_attr="gpt_deployment",
        instructions="i",
        tools=("search",),
    )


def _make_settings(deployment: str = "gpt-4o-mini") -> MagicMock:
    settings = MagicMock(spec=AppSettings)
    settings.openai = MagicMock()
    settings.openai.gpt_deployment = deployment
    settings.openai.reasoning_deployment = "o4-mini"
    return settings


def _make_client(*, agent_id: str = "asst_new") -> MagicMock:
    client = MagicMock()
    created = MagicMock()
    created.id = agent_id
    client.create_agent = AsyncMock(return_value=created)
    client.get_agent = AsyncMock(return_value=MagicMock(id=agent_id))
    return client


# ---------------------------------------------------------------------------
# Cache hit -- steady-state path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_db_and_foundry() -> None:
    """The hot path must be a single dict lookup -- no DB read,
    no Foundry round-trip. Validates the cache short-circuit at the
    very top of `get_or_create_agent`."""
    client = _make_client()
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    provider._agent_cache["cwyd"] = "asst_cached"
    db = _StubDB()
    out = await provider.get_or_create_agent(_definition(), db)
    assert out == "asst_cached"
    assert db.get_calls == []
    client.get_agent.assert_not_called()
    client.create_agent.assert_not_called()


# ---------------------------------------------------------------------------
# DB hit + Foundry validation -- restart path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_hit_validates_with_foundry_and_caches() -> None:
    """First request after process restart: DB has the persisted id;
    we validate it via `client.get_agent` (cheap) and cache the result.
    No `create_agent` call."""
    client = _make_client()
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    db = _StubDB(seed={"cwyd": "asst_persisted"})
    out = await provider.get_or_create_agent(_definition(), db)
    assert out == "asst_persisted"
    client.get_agent.assert_awaited_once_with("asst_persisted")
    client.create_agent.assert_not_called()
    # Second call hits the cache, no extra DB or Foundry traffic.
    await provider.get_or_create_agent(_definition(), db)
    assert db.get_calls == ["cwyd"]
    client.get_agent.assert_awaited_once()


# ---------------------------------------------------------------------------
# DB hit + Foundry 404 -- orphan recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_hit_with_foundry_404_falls_through_to_recreate() -> None:
    """The persisted id points at a Foundry agent that has been
    deleted (e.g. environment rebuild). Resolver must NOT raise --
    it must recreate the agent and rewrite the DB row so the next
    request finds a valid id."""
    client = _make_client(agent_id="asst_recreated")
    client.get_agent = AsyncMock(side_effect=ResourceNotFoundError("gone"))
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    db = _StubDB(seed={"cwyd": "asst_stale"})
    out = await provider.get_or_create_agent(_definition(), db)
    assert out == "asst_recreated"
    client.create_agent.assert_awaited_once()
    # Upsert path runs -- DB row rewritten with the new id.
    assert db.upsert_calls == [("cwyd", "asst_recreated")]
    assert db._rows["cwyd"] == "asst_recreated"


# ---------------------------------------------------------------------------
# Cold start -- create + persist + cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cold_start_creates_persists_and_caches() -> None:
    """Fresh deploy: cache empty, DB empty. Resolver must call
    `create_agent` exactly once with the deployment from the
    `deployment_attr` indirection, persist via `upsert_agent_id`,
    and cache for next time."""
    client = _make_client(agent_id="asst_cold")
    provider = _StubAgentsProvider(
        _make_settings(deployment="gpt-4o-mini"),
        MagicMock(),
        client=client,
    )
    db = _StubDB()
    out = await provider.get_or_create_agent(_definition(), db)
    assert out == "asst_cold"
    client.create_agent.assert_awaited_once()
    create_kwargs = client.create_agent.await_args.kwargs
    assert create_kwargs["model"] == "gpt-4o-mini"
    assert create_kwargs["name"] == "cwyd"
    assert create_kwargs["instructions"] == "i"
    # tools are forwarded as a list (SDK contract); the definition
    # holds a tuple for immutability.
    assert create_kwargs["tools"] == ["search"]
    assert db.upsert_calls == [("cwyd", "asst_cold")]
    assert provider._agent_cache["cwyd"] == "asst_cold"


@pytest.mark.asyncio
async def test_cold_start_uses_reasoning_deployment_when_definition_says_so() -> None:
    """The `deployment_attr` indirection lets RAI (or any other
    cheap-model agent) point at `reasoning_deployment` instead of
    `gpt_deployment` without a per-agent env var."""
    client = _make_client(agent_id="asst_rai")
    provider = _StubAgentsProvider(
        _make_settings(deployment="gpt-4o-mini"),
        MagicMock(),
        client=client,
    )
    rai_def = AgentDefinition(
        name="rai",
        description="d",
        deployment_attr="reasoning_deployment",
        instructions="i",
    )
    await provider.get_or_create_agent(rai_def, _StubDB())
    assert client.create_agent.await_args.kwargs["model"] == "o4-mini"


# ---------------------------------------------------------------------------
# Concurrency -- per-key lock prevents double-create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_first_requests_create_exactly_once() -> None:
    """Two concurrent first-requests for the same agent must result
    in a single `create_agent` call -- the per-key lock + the
    double-checked cache inside the lock guarantee this. Without the
    lock we'd orphan one Foundry agent and race on the DB write."""
    create_event = asyncio.Event()
    create_count = {"n": 0}

    async def _slow_create(**_kwargs: object) -> MagicMock:
        create_count["n"] += 1
        # Yield control so the second coroutine reaches the lock.
        await create_event.wait()
        return MagicMock(id="asst_winner")

    client = _make_client()
    client.create_agent = AsyncMock(side_effect=_slow_create)
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    db = _StubDB()
    definition = _definition()

    task_a = asyncio.create_task(
        provider.get_or_create_agent(definition, db)
    )
    task_b = asyncio.create_task(
        provider.get_or_create_agent(definition, db)
    )
    # Let both tasks enter `create_or_get_agent` and queue on the lock.
    await asyncio.sleep(0)
    create_event.set()
    out_a, out_b = await asyncio.gather(task_a, task_b)

    assert out_a == "asst_winner"
    assert out_b == "asst_winner"
    assert create_count["n"] == 1
    assert db.upsert_calls == [("cwyd", "asst_winner")]


# ---------------------------------------------------------------------------
# Phase C2e -- try/except policy sweep for `agents` provider domain
#
# Mirrors the foundry_iq + azure_search wraps landed in C2d:
#   * Provider entry-points catch `azure.core.exceptions.AzureError` (the
#     umbrella for every azure-core SDK transport / service error --
#     `HttpResponseError`, `ServiceRequestError`,
#     `ClientAuthenticationError`, etc.), structured-log via
#     `logger.exception(..., extra={"operation": ..., "provider":
#     "agents", "agent_name": ..., "deployment": ...})`, and re-raise so
#     the router / lifespan layer can translate to a sanitized 503.
#
# `ResourceNotFoundError` keeps its existing orphan-recovery branch:
# stale persisted ids fall through to recreate, NOT re-raise. The
# `AzureError` catch sits AFTER `ResourceNotFoundError` so MRO
# correctly routes 404s to the orphan path and everything else
# (auth, transport, 5xx) to the log+re-raise path.
# ---------------------------------------------------------------------------


def _find_record(
    caplog: pytest.LogCaptureFixture,
    operation: str,
    *,
    level: int = logging.ERROR,
) -> logging.LogRecord:
    """Return the unique log record for `operation` at `level`.

    Centralises the assertion shape used by the C2 sweep tests --
    every wrap site emits exactly one structured log record per
    failure, so a count != 1 is itself a regression signal.
    """
    matches = [
        record
        for record in caplog.records
        if record.name == _AGENTS_BASE_LOGGER_NAME
        and record.levelno == level
        and getattr(record, "operation", None) == operation
    ]
    assert len(matches) == 1, (
        f"expected exactly one {logging.getLevelName(level)} record "
        f"with operation={operation!r}, got {len(matches)}: {matches!r}"
    )
    return matches[0]


@pytest.mark.asyncio
async def test_get_agent_azure_error_logs_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-404 azure-core failure on `client.get_agent` (transport
    drop, 503, auth) MUST surface to the caller -- it is NOT an
    orphan-recovery signal. The wrap logs structured context and
    re-raises so the lifespan / router layer translates it.
    """
    client = _make_client()
    client.get_agent = AsyncMock(
        side_effect=ServiceRequestError("transport drop")
    )
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    db = _StubDB(seed={"cwyd": "asst_persisted"})

    with caplog.at_level(logging.ERROR, logger=_AGENTS_BASE_LOGGER_NAME):
        with pytest.raises(ServiceRequestError):
            await provider.get_or_create_agent(_definition(), db)

    record = _find_record(caplog, "get_agent")
    assert record.provider == "agents"  # type: ignore[attr-defined]
    assert record.agent_name == "cwyd"  # type: ignore[attr-defined]
    # No fall-through to recreate: cache untouched, no upsert written.
    client.create_agent.assert_not_called()
    assert db.upsert_calls == []
    assert "cwyd" not in provider._agent_cache


@pytest.mark.asyncio
async def test_get_agent_resource_not_found_does_not_log_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`ResourceNotFoundError` is intentional control flow (orphan
    recovery), NOT an error condition. The C2e wrap must keep it on
    the silent fall-through path -- emitting an ERROR record here
    would spam logs every time an environment is rebuilt.
    """
    client = _make_client(agent_id="asst_recreated")
    client.get_agent = AsyncMock(side_effect=ResourceNotFoundError("gone"))
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    db = _StubDB(seed={"cwyd": "asst_stale"})

    with caplog.at_level(logging.ERROR, logger=_AGENTS_BASE_LOGGER_NAME):
        out = await provider.get_or_create_agent(_definition(), db)

    assert out == "asst_recreated"
    error_records = [
        r for r in caplog.records
        if r.name == _AGENTS_BASE_LOGGER_NAME and r.levelno == logging.ERROR
    ]
    assert error_records == []


@pytest.mark.asyncio
async def test_create_agent_azure_error_logs_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`client.create_agent` is the cold-start write path. A failure
    here (auth misconfig, quota, 5xx) must NOT silently leave a
    half-built state -- the wrap logs the deployment + agent name
    and re-raises so the caller sees the failure.
    """
    client = _make_client()
    client.create_agent = AsyncMock(
        side_effect=ClientAuthenticationError("bad token")
    )
    provider = _StubAgentsProvider(
        _make_settings(deployment="gpt-4o-mini"),
        MagicMock(),
        client=client,
    )
    db = _StubDB()

    with caplog.at_level(logging.ERROR, logger=_AGENTS_BASE_LOGGER_NAME):
        with pytest.raises(ClientAuthenticationError):
            await provider.get_or_create_agent(_definition(), db)

    record = _find_record(caplog, "create_agent")
    assert record.provider == "agents"  # type: ignore[attr-defined]
    assert record.agent_name == "cwyd"  # type: ignore[attr-defined]
    assert record.deployment == "gpt-4o-mini"  # type: ignore[attr-defined]
    # No DB write, no cache write -- partial state is poison.
    assert db.upsert_calls == []
    assert "cwyd" not in provider._agent_cache


@pytest.mark.asyncio
async def test_create_agent_azure_error_releases_per_key_lock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The per-key lock must release on the failure path so a
    subsequent retry doesn't deadlock on a still-held lock. We
    assert the lock is released by issuing a second call (which
    succeeds) and observing it actually executes `create_agent`.
    """
    call_count = {"n": 0}

    async def _flaky_create(**_kwargs: object) -> MagicMock:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise AzureError("transient 503")
        return MagicMock(id="asst_retry")

    client = _make_client()
    client.create_agent = AsyncMock(side_effect=_flaky_create)
    provider = _StubAgentsProvider(
        _make_settings(), MagicMock(), client=client
    )
    db = _StubDB()

    with caplog.at_level(logging.ERROR, logger=_AGENTS_BASE_LOGGER_NAME):
        with pytest.raises(AzureError):
            await provider.get_or_create_agent(_definition(), db)
        # Retry must succeed -- if the lock leaked the await below
        # would hang forever (test would timeout instead of asserting).
        out = await provider.get_or_create_agent(_definition(), db)

    assert out == "asst_retry"
    assert call_count["n"] == 2
    assert db.upsert_calls == [("cwyd", "asst_retry")]
