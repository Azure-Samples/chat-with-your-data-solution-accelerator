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

from unittest.mock import AsyncMock, MagicMock

import logging

import pytest
from azure.core.exceptions import AzureError

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
        "backend.core.providers.agents.foundry.AgentsClient", _fake_ctor
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
        "backend.core.providers.agents.foundry.AgentsClient", _fake_ctor
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
        "backend.core.providers.agents.foundry.AgentsClient",
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
    on `AgentsClient.close()` must NOT crash the lifespan shutdown
    sequence (the container is going away regardless). The wrap
    swallows `(AzureError, OSError)`, logs at WARNING with structured
    extras, and clears the cached client so a subsequent restart
    rebuilds cleanly.
    """
    failing = MagicMock(
        name="AgentsClient",
        close=AsyncMock(side_effect=AzureError("transport drop")),
    )
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AgentsClient",
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
        name="AgentsClient",
        close=AsyncMock(side_effect=OSError("broken pipe")),
    )
    monkeypatch.setattr(
        "backend.core.providers.agents.foundry.AgentsClient",
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
