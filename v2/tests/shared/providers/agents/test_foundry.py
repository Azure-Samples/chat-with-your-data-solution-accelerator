"""Tests for the `agents` provider domain (CU-001b).

Pillar: Stable Core
Phase: 4

The `agents` registry domain is the swap-in point for the
`azure.ai.agents.aio.AgentsClient` consumed by the
`agent_framework` orchestrator. Today only `foundry` is registered;
future entries (e.g. on-prem agents SDK, langgraph-native agents,
in-memory `mock` for tests) plug in by self-registering against the
same `BaseAgentsProvider` ABC -- callers always go through
`agents.create("foundry", ...)`, never new the concrete class
directly (Hard Rule #4).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.providers import agents
from shared.providers.agents.base import BaseAgentsProvider
from shared.providers.agents.foundry import FoundryAgentsProvider


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
    assert agents.registry.get("foundry") is FoundryAgentsProvider


def test_create_returns_base_agents_provider_subclass(
    fake_settings: MagicMock, fake_credential: MagicMock
) -> None:
    """`agents.create(...)` is the only legitimate construction path
    (Hard Rule #4); it must yield a `BaseAgentsProvider` so the lifespan
    can call `aclose()` and the router can fetch the client via
    `get_client()`.
    """
    provider = agents.create(
        "foundry", settings=fake_settings, credential=fake_credential
    )
    assert isinstance(provider, BaseAgentsProvider)
    assert isinstance(provider, FoundryAgentsProvider)


# ---------------------------------------------------------------------------
# FoundryAgentsProvider behavior
# ---------------------------------------------------------------------------


def test_get_client_returns_injected_override(
    fake_settings: MagicMock, fake_credential: MagicMock
) -> None:
    """Tests inject a fake `AgentsClient` via the `client=` kwarg so we
    never open a real HTTP session in unit tests. The override must be
    honored even if the project endpoint is empty.
    """
    fake_settings.foundry.project_endpoint = ""
    fake_client = MagicMock(name="AgentsClient")
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
    `AgentsClient` against the typed Foundry project endpoint and the
    injected async credential -- no other inputs.
    """
    captured: dict[str, object] = {}

    def _fake_ctor(*, endpoint: str, credential: object) -> MagicMock:
        captured["endpoint"] = endpoint
        captured["credential"] = credential
        client = MagicMock(name="AgentsClient")
        client.close = AsyncMock()
        return client

    monkeypatch.setattr(
        "shared.providers.agents.foundry.AgentsClient", _fake_ctor
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
        return MagicMock(name=f"AgentsClient#{call_count['n']}", close=AsyncMock())

    monkeypatch.setattr(
        "shared.providers.agents.foundry.AgentsClient", _fake_ctor
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
    `AgentsClient` against `None` and 500 on the first request.
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
    constructed = MagicMock(name="AgentsClient", close=AsyncMock())
    monkeypatch.setattr(
        "shared.providers.agents.foundry.AgentsClient",
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
    fake_client = MagicMock(name="AgentsClient", close=AsyncMock())
    provider = FoundryAgentsProvider(
        settings=fake_settings,
        credential=fake_credential,
        client=fake_client,
    )
    provider.get_client()
    await provider.aclose()
    fake_client.close.assert_not_called()
