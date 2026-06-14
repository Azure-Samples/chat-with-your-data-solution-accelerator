"""Integration-lane fixtures: boot the real FastAPI app against real Azure.

Pillar: Stable Core
Phase: 6

This conftest powers the opt-in ``@pytest.mark.integration`` lane. Unlike the
mocked unit suite, these fixtures load the real ``v2/.env`` and run the real
application lifespan so requests hit live Azure data-plane services (Foundry
IQ, Azure AI Search, Cosmos DB). The lane is deselected by default via
``addopts = "... -m 'not smoke and not integration'"`` and self-skips when the
environment is not configured, so the standard ``pytest`` run is unaffected.

Boot model: the app is constructed with ``create_app()`` and its lifespan is
entered in-process with ``app.router.lifespan_context(app)`` (which connects
the credential / llm / agents / db / search providers), then driven with an
``httpx.AsyncClient`` over ``ASGITransport`` -- no separate server process and
no extra harness dependency.
"""

import base64
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

import httpx
import pytest
from dotenv import dotenv_values
from fastapi import FastAPI

from backend.app import create_app
from backend.core.settings import DbType, OrchestratorName, get_settings

# v2/ root resolves from this file: v2/tests/integration/conftest.py -> v2/
_V2_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _V2_ROOT / ".env"

# Minimum keys that must be present for the live app to boot in any mode.
# Absent -> the whole lane self-skips with a capability reason.
_REQUIRED_ENV_KEYS = (
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_OPENAI_GPT_DEPLOYMENT",
)


class SSEEvent(NamedTuple):
    """One parsed Server-Sent Event: its ``event:`` type and ``data:`` body."""

    event: str
    data: str


@pytest.fixture(autouse=True)
def _load_real_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Re-load the real ``v2/.env`` after the root ``_reset_env`` stripper.

    The root autouse fixture deletes every ``AZURE_*`` / ``CWYD_*`` var for
    unit isolation; this deeper autouse fixture runs afterwards and restores
    the real values from ``v2/.env`` so the live app boots against the real
    environment. Skips the entire lane when the file or its required keys are
    absent, so the suite self-disables on an unconfigured machine.
    """
    if not _ENV_FILE.is_file():
        pytest.skip(f"requires a populated {_ENV_FILE.name}; not found at {_ENV_FILE}")

    values = {
        key: value
        for key, value in dotenv_values(_ENV_FILE).items()
        if value is not None
    }
    missing = [key for key in _REQUIRED_ENV_KEYS if not values.get(key)]
    if missing:
        pytest.skip("requires a populated v2/.env; missing keys: " + ", ".join(missing))

    for key, value in values.items():
        monkeypatch.setenv(key, value)

    # get_settings() is an lru_cache singleton read by both the lifespan and
    # the request-time dependency; clear it so it re-reads the env just loaded.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def live_app(_load_real_env: None) -> AsyncIterator[FastAPI]:
    """Construct the real app and run its lifespan against live Azure.

    Entering ``app.router.lifespan_context(app)`` executes the same startup
    path as production -- credential acquisition, provider construction, and
    schema checks -- so every request the tests issue reaches real services.
    """
    app = create_app()
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def live_client(live_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An ``httpx.AsyncClient`` bound in-process to the booted live app."""
    transport = httpx.ASGITransport(app=live_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://integration"
    ) as client:
        yield client


@pytest.fixture
def require_cosmos(_load_real_env: None) -> None:
    """Skip a test unless the configured database backend is Cosmos DB."""
    db_type = get_settings().database.db_type
    if db_type != DbType.COSMOSDB:
        pytest.skip(f"requires cosmosdb mode; configured db_type={db_type!r}")


@pytest.fixture
def require_agent_framework(_load_real_env: None) -> None:
    """Skip a test unless the configured orchestrator is ``agent_framework``."""
    name = get_settings().orchestrator.name
    if name != OrchestratorName.AGENT_FRAMEWORK:
        pytest.skip(f"requires agent_framework orchestrator; configured name={name!r}")


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Easy Auth headers carrying an ``admin`` role claim.

    Exercises the real claims parser (`backend.dependencies`) rather than
    overriding the auth dependency. The principal id is a synthetic test
    value, never a real Entra object id (Hard Rule #18).
    """
    principal = {"claims": [{"typ": "roles", "val": "admin"}]}
    encoded = base64.b64encode(json.dumps(principal).encode()).decode()
    return {
        "x-ms-client-principal-id": "integration-admin",
        "x-ms-client-principal": encoded,
    }


@pytest.fixture
def non_admin_headers() -> dict[str, str]:
    """Easy Auth headers carrying a non-admin role claim.

    Drives a deterministic ``403`` from the admin role gate in any
    environment: a valid claims blob is present (so the local-dev no-header
    bypass does not apply) but it lacks the ``admin`` role. The principal id
    is a synthetic test value (Hard Rule #18).
    """
    principal = {"claims": [{"typ": "roles", "val": "reader"}]}
    encoded = base64.b64encode(json.dumps(principal).encode()).decode()
    return {
        "x-ms-client-principal-id": "integration-reader",
        "x-ms-client-principal": encoded,
    }


@pytest.fixture
def user_headers() -> dict[str, str]:
    """Easy Auth headers carrying only a (synthetic) user id, no admin role."""
    return {"x-ms-client-principal-id": "integration-user"}


@pytest.fixture
def collect_sse() -> Callable[..., Awaitable[list[SSEEvent]]]:
    """Return an async helper that POSTs for an SSE stream and parses events.

    Frames are parsed per the SSE wire format: ``event:`` sets the type,
    ``data:`` lines accumulate (newline-joined), and a blank line flushes one
    ``SSEEvent``. The caller asserts on the resulting channel sequence.
    """

    async def _collect(
        client: httpx.AsyncClient,
        path: str,
        *,
        json_body: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
    ) -> list[SSEEvent]:
        request_headers = {"accept": "text/event-stream", **(headers or {})}
        events: list[SSEEvent] = []
        event_type = "message"
        data_lines: list[str] = []
        async with client.stream(
            "POST", path, json=json_body, headers=request_headers
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line == "":
                    if data_lines:
                        events.append(SSEEvent(event_type, "\n".join(data_lines)))
                    event_type = "message"
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())
        if data_lines:
            events.append(SSEEvent(event_type, "\n".join(data_lines)))
        return events

    return _collect
