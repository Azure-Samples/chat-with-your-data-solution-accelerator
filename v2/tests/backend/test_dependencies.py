"""Pillar: Stable Core / Phase: 3.5 (debt #Q6a) — DI provider tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.dependencies import (
    get_agents_provider,
    get_database_client,
    get_search_provider,
)


def _request_with_state(**state_kwargs: object) -> object:
    """Build a stand-in `Request` exposing `request.app.state.<attr>`."""
    state = SimpleNamespace(**state_kwargs)
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


def test_get_search_provider_returns_none_when_unset() -> None:
    """Lifespan may skip search wiring when no endpoint is configured."""
    request = _request_with_state()
    assert get_search_provider(request) is None  # type: ignore[arg-type]


def test_get_search_provider_returns_state_instance_when_set() -> None:
    """When lifespan stashes a provider on app.state, DI hands it out."""
    sentinel = MagicMock(name="search_provider")
    request = _request_with_state(search_provider=sentinel)
    assert get_search_provider(request) is sentinel  # type: ignore[arg-type]


def test_get_database_client_raises_when_missing() -> None:
    """If lifespan didn't run, DI must surface a clear error."""
    request = _request_with_state()
    with pytest.raises(RuntimeError, match="database_client missing"):
        get_database_client(request)  # type: ignore[arg-type]


def test_get_database_client_returns_state_instance_when_set() -> None:
    """When lifespan stashes a database client on app.state, DI hands it out."""
    sentinel = MagicMock(name="database_client")
    request = _request_with_state(database_client=sentinel)
    assert get_database_client(request) is sentinel  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CU-001c: agents provider DI seam (Phase 4 -- agent_framework wiring)
# ---------------------------------------------------------------------------


def test_get_agents_provider_raises_when_missing() -> None:
    """If lifespan didn't run, DI must surface a clear error so callers
    don't silently get None and fall through to a NoneType.AttributeError
    deep inside the orchestrator."""
    request = _request_with_state()
    with pytest.raises(RuntimeError, match="agents_provider missing"):
        get_agents_provider(request)  # type: ignore[arg-type]


def test_get_agents_provider_returns_state_instance_when_set() -> None:
    """When lifespan stashes the FoundryAgentsProvider on app.state, DI
    hands out the same instance for every request -- one HTTP transport
    per process (parity with credential_provider, llm_provider)."""
    sentinel = MagicMock(name="agents_provider")
    request = _request_with_state(agents_provider=sentinel)
    assert get_agents_provider(request) is sentinel  # type: ignore[arg-type]
