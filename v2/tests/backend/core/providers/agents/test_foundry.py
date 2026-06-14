"""Tests for the `agents` provider domain (CU-001b).

Pillar: Stable Core
Phase: 4

The `agents` registry domain is the swap-in point for the
`azure.ai.projects.aio.AIProjectClient` consumed by the
`agent_framework` orchestrator. Today only `foundry` is registered;
future entries (e.g. on-prem agents SDK, langgraph-native agents,
in-memory `mock` for tests) plug in by self-registering against the
same `BaseAgentsProvider` ABC -- callers always go through
`agents.create("foundry", ...)`, never new the concrete class
directly (Hard Rule #4).
"""

from unittest.mock import AsyncMock, MagicMock

import logging

import pytest
from azure.core.exceptions import AzureError

from backend.core.agents.definitions import CWYD_AGENT
from backend.core.providers.agents import registry as agents_registry
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.agents.foundry import FoundryAgentsProvider


_FOUNDRY_AGENTS_LOGGER_NAME = "backend.core.providers.agents.foundry"


@pytest.fixture
def fake_settings() -> MagicMock:
    """Minimal settings stub exposing `foundry.project_endpoint`."""
    settings = MagicMock(name="AppSettings")
    settings.foundry.project_endpoint = (
        "https://ai-cwyd001.services.ai.azure.com/api/projects/proj"
    )
    return settings


@pytest.fixture
def fake_credential() -> MagicMock:
    return MagicMock(name="AsyncTokenCredential")


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------


def test_foundry_provider_registered_under_foundry_key() -> None:
    """The registry entry is the public swap-in point. Any rename is a
    breaking config change for every operator's `.env`/Bicep output.
    """
    assert agents_registry.registry.get("foundry") is FoundryAgentsProvider


def test_create_returns_base_agents_provider_subclass(
    fake_settings: MagicMock, fake_credential: MagicMock
) -> None:
    """`agents_registry.registry.get(...)` is the only legitimate construction path
    (Hard Rule #4 + #13); it must yield a `BaseAgentsProvider` so the lifespan
    can call `aclose()` and the router can fetch the client via
    `get_client()`.
    """
    provider = agents_registry.registry.get("foundry")(
        settings=fake_settings, credential=fake_credential
    )
    assert isinstance(provider, BaseAgentsProvider)
    assert isinstance(provider, FoundryAgentsProvider)


# ---------------------------------------------------------------------------
# FoundryAgentsProvider behavior
# ---------------------------------------------------------------------------


def test_get_client_returns_injected_override(
    fake_settings: MagicMock, fake_credential: MagicMock
) -> None:
    """Tests inject a fake `AIProjectClient` via the `client=` kwarg so we
    never open a real HTTP session in unit tests. The override must be
    honored even if the project endpoint is empty.
    """
    fake_settings.foundry.project_endpoint = ""
    fake_client = MagicMock(name="AIProjectClient")
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential, client=fake_client
    )
    assert provider.get_client() is fake_client


def test_get_client_constructs_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
) -> None:
    """When no override is provided, the provider must build an
    `AIProjectClient` against the typed Foundry project endpoint and the
    injected async credential -- no other inputs.
    """
    captured: dict[str, object] = {}

    def _fake_ctor(*, endpoint: str, credential: object) -> MagicMock:
        captured["endpoint"] = endpoint
        captured["credential"] = credential
        client = MagicMock(name="AIProjectClient")
        client.close = AsyncMock()
        return client

    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AIProjectClient", _fake_ctor
    )
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential
    )
    client = provider.get_client()
    assert client is not None
    assert (
        captured["endpoint"]
        == "https://ai-cwyd001.services.ai.azure.com/api/projects/proj"
    )
    assert captured["credential"] is fake_credential


def test_get_client_is_lazy_and_cached(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
) -> None:
    """Lazy: no SDK client constructed at __init__ time (cheap import).
    Cached: subsequent get_client() calls return the same instance so
    the lifespan can `aclose()` exactly one connection.
    """
    call_count = {"n": 0}

    def _fake_ctor(*, endpoint: str, credential: object) -> MagicMock:
        call_count["n"] += 1
        return MagicMock(name=f"AIProjectClient#{call_count['n']}", close=AsyncMock())

    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AIProjectClient", _fake_ctor
    )
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential
    )
    assert call_count["n"] == 0  # lazy
    first = provider.get_client()
    second = provider.get_client()
    assert first is second
    assert call_count["n"] == 1  # cached


def test_get_client_raises_without_project_endpoint(
    fake_settings: MagicMock, fake_credential: MagicMock
) -> None:
    """Misconfiguration (`AZURE_AI_PROJECT_ENDPOINT` empty) must fail
    fast with a remediation hint, not silently construct an
    `AIProjectClient` against `None` and 500 on the first request.
    """
    fake_settings.foundry.project_endpoint = ""
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential
    )
    with pytest.raises(RuntimeError, match="AZURE_AI_PROJECT_ENDPOINT"):
        provider.get_client()


@pytest.mark.asyncio
async def test_aclose_closes_constructed_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
) -> None:
    """Lifespan shutdown must drain the SDK transport. We close clients
    we constructed; the close is idempotent so repeated lifespan starts
    don't blow up.
    """
    constructed = MagicMock(name="AIProjectClient", close=AsyncMock())
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AIProjectClient",
        lambda *, endpoint, credential: constructed,
    )
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential
    )
    provider.get_client()  # trigger construction
    await provider.aclose()
    constructed.close.assert_awaited_once()
    # Second close is a no-op (idempotent).
    await provider.aclose()
    constructed.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_override(
    fake_settings: MagicMock, fake_credential: MagicMock
) -> None:
    """If the caller (e.g. a test) injected an `AgentsClient`, they own
    its lifecycle -- the provider must NOT close it.
    """
    fake_client = MagicMock(name="AIProjectClient", close=AsyncMock())
    provider = FoundryAgentsProvider(
        settings=fake_settings,
        credential=fake_credential,
        client=fake_client,
    )
    provider.get_client()
    await provider.aclose()
    fake_client.close.assert_not_called()


# ---------------------------------------------------------------------------
# Phase C2e -- shutdown best-effort with structured warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aclose_swallows_azure_error_and_warns(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shutdown is best-effort per the policy doc: a transport drop
    on `AIProjectClient.close()` must NOT crash the lifespan shutdown
    sequence (the container is going away regardless). The wrap
    swallows `(AzureError, OSError)`, logs at WARNING with structured
    extras, and clears the cached client so a subsequent restart
    rebuilds cleanly.
    """
    failing = MagicMock(
        name="AIProjectClient",
        close=AsyncMock(side_effect=AzureError("transport drop")),
    )
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AIProjectClient",
        lambda *, endpoint, credential: failing,
    )
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential
    )
    provider.get_client()  # trigger construction

    with caplog.at_level(
        logging.WARNING, logger=_FOUNDRY_AGENTS_LOGGER_NAME
    ):
        await provider.aclose()

    failing.close.assert_awaited_once()
    matches = [
        r
        for r in caplog.records
        if r.name == _FOUNDRY_AGENTS_LOGGER_NAME
        and r.levelno == logging.WARNING
        and getattr(r, "operation", None) == "aclose"
    ]
    assert len(matches) == 1, (
        f"expected exactly one WARNING record with operation='aclose', "
        f"got {len(matches)}: {matches!r}"
    )
    assert matches[0].provider == "foundry_agents"  # type: ignore[attr-defined]
    # Cached client cleared so a restart can construct cleanly without
    # leaking the failing handle.
    assert provider._client is None  # type: ignore[attr-defined]
    # Second close is a no-op now that the client handle was cleared.
    await provider.aclose()
    failing.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_swallows_os_error_and_warns(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mirror of the AzureError path for the OS-level transport
    failure mode (e.g. broken pipe during shutdown). Same swallow,
    same WARNING shape -- both error families are best-effort during
    shutdown.
    """
    failing = MagicMock(
        name="AIProjectClient",
        close=AsyncMock(side_effect=OSError("broken pipe")),
    )
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AIProjectClient",
        lambda *, endpoint, credential: failing,
    )
    provider = FoundryAgentsProvider(
        settings=fake_settings, credential=fake_credential
    )
    provider.get_client()

    with caplog.at_level(
        logging.WARNING, logger=_FOUNDRY_AGENTS_LOGGER_NAME
    ):
        await provider.aclose()

    failing.close.assert_awaited_once()
    matches = [
        r
        for r in caplog.records
        if r.name == _FOUNDRY_AGENTS_LOGGER_NAME
        and r.levelno == logging.WARNING
        and getattr(r, "operation", None) == "aclose"
    ]
    assert len(matches) == 1
    assert provider._client is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# build_agent -- runtime-agent construction seam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_composes_chat_client_and_agent(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
) -> None:
    """build_agent resolves the named agent (DB hit -> validate via
    `agents.get`), then composes a `FoundryChatClient` bound to the
    project endpoint + the agent's own model deployment, wrapped in an
    `agent_framework.Agent` carrying the resolved name / instructions /
    description. This is the DRY seam every runtime caller shares.
    """
    fake_settings.openai.gpt_deployment = "gpt-test-deploy"
    fake_client = MagicMock(name="AIProjectClient")
    fake_client.agents.get = AsyncMock(return_value=MagicMock())
    fake_client.agents.create_version = AsyncMock(return_value=MagicMock())

    chat_client_sentinel = MagicMock(name="FoundryChatClient-instance")
    agent_sentinel = MagicMock(name="Agent-instance")
    chat_captured: dict[str, object] = {}
    agent_captured: dict[str, object] = {}

    def _fake_chat_client(**kwargs: object) -> MagicMock:
        chat_captured.update(kwargs)
        return chat_client_sentinel

    def _fake_agent(**kwargs: object) -> MagicMock:
        agent_captured.update(kwargs)
        return agent_sentinel

    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.FoundryChatClient",
        _fake_chat_client,
    )
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.Agent", _fake_agent
    )

    db = MagicMock(name="db")
    db.get_agent_id = AsyncMock(return_value="cwyd")
    db.upsert_agent_id = AsyncMock()

    provider = FoundryAgentsProvider(
        settings=fake_settings,
        credential=fake_credential,
        client=fake_client,
    )
    agent = await provider.build_agent(CWYD_AGENT, db)

    assert agent is agent_sentinel
    # Chat client bound to the typed project endpoint + the agent's own
    # deployment + the injected async credential -- no other inputs.
    assert (
        chat_captured["project_endpoint"]
        == fake_settings.foundry.project_endpoint
    )
    assert chat_captured["model"] == "gpt-test-deploy"
    assert chat_captured["credential"] is fake_credential
    # Agent wraps that chat client and carries the resolved identity.
    assert agent_captured["client"] is chat_client_sentinel
    assert agent_captured["name"] == "cwyd"
    assert agent_captured["instructions"] == CWYD_AGENT.instructions
    assert agent_captured["description"] == CWYD_AGENT.description
    assert agent_captured["tools"] is None
    # DB hit -> existing named agent validated, never re-created.
    fake_client.agents.get.assert_awaited_once_with("cwyd")
    fake_client.agents.create_version.assert_not_called()


@pytest.mark.asyncio
async def test_build_agent_forwards_extra_tools(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
) -> None:
    """Runtime tools the caller attaches (e.g. the KB retrieval tool the
    orchestrator builds per request) reach the client-side Agent's
    `tools=` as a list, additive to anything baked server-side.
    """
    fake_settings.openai.gpt_deployment = "gpt-test-deploy"
    fake_client = MagicMock(name="AIProjectClient")
    fake_client.agents.get = AsyncMock(return_value=MagicMock())

    agent_captured: dict[str, object] = {}

    def _fake_agent(**kwargs: object) -> MagicMock:
        agent_captured.update(kwargs)
        return MagicMock(name="Agent-instance")

    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.FoundryChatClient",
        lambda **kwargs: MagicMock(name="FoundryChatClient-instance"),
    )
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.Agent", _fake_agent
    )

    db = MagicMock(name="db")
    db.get_agent_id = AsyncMock(return_value="cwyd")

    provider = FoundryAgentsProvider(
        settings=fake_settings,
        credential=fake_credential,
        client=fake_client,
    )
    tool_a = object()
    tool_b = object()
    await provider.build_agent(CWYD_AGENT, db, extra_tools=[tool_a, tool_b])

    assert agent_captured["tools"] == [tool_a, tool_b]


@pytest.mark.asyncio
async def test_build_agent_wraps_azure_error_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings: MagicMock,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A `FoundryChatClient` / `Agent` construction failure crosses the
    SDK boundary -- build_agent must log at ERROR with structured extras
    (operation='build_agent', provider, agent_name, deployment) and
    re-raise so the caller maps it to a sanitized 503, never returning a
    half-built agent.
    """
    fake_settings.openai.gpt_deployment = "gpt-test-deploy"
    fake_client = MagicMock(name="AIProjectClient")
    fake_client.agents.get = AsyncMock(return_value=MagicMock())

    def _boom(**kwargs: object) -> MagicMock:
        raise AzureError("project endpoint unreachable")

    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.FoundryChatClient", _boom
    )

    db = MagicMock(name="db")
    db.get_agent_id = AsyncMock(return_value="cwyd")

    provider = FoundryAgentsProvider(
        settings=fake_settings,
        credential=fake_credential,
        client=fake_client,
    )
    with caplog.at_level(logging.ERROR, logger=_FOUNDRY_AGENTS_LOGGER_NAME):
        with pytest.raises(AzureError, match="project endpoint unreachable"):
            await provider.build_agent(CWYD_AGENT, db)

    matches = [
        r
        for r in caplog.records
        if r.name == _FOUNDRY_AGENTS_LOGGER_NAME
        and r.levelno == logging.ERROR
        and getattr(r, "operation", None) == "build_agent"
    ]
    assert len(matches) == 1
    assert matches[0].provider == "foundry_agents"  # type: ignore[attr-defined]
    assert matches[0].agent_name == "cwyd"  # type: ignore[attr-defined]
    assert matches[0].deployment == "gpt-test-deploy"  # type: ignore[attr-defined]
