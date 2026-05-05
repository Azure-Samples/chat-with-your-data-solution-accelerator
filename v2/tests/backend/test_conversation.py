"""Pillar: Stable Core / Phase: 3 (task #22a) — tests for the conversation router."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Sequence

import httpx
import pytest

from backend.app import create_app
from backend.dependencies import (
    get_agents_provider,
    get_app_settings,
    get_llm_provider,
)
from shared.providers import orchestrators
from shared.providers.orchestrators.base import OrchestratorBase
from shared.types import ChatMessage, OrchestratorEvent

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeOrchestrator(OrchestratorBase):
    """Yields a scripted sequence of events on each ``run()``."""

    scripted: list[OrchestratorEvent] = []
    last_kwargs: dict[str, Any] = {}

    def __init__(self, settings: Any, llm: Any, **extras: Any) -> None:  # noqa: D401
        super().__init__(settings, llm)
        type(self).last_kwargs = dict(extras)

    async def run(  # type: ignore[override]
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        for ev in type(self).scripted:
            yield ev


class _BoomOrchestrator(OrchestratorBase):
    """Raises mid-stream to exercise the SSE error channel."""

    def __init__(self, settings: Any, llm: Any, **_extras: Any) -> None:
        super().__init__(settings, llm)

    async def run(  # type: ignore[override]
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel="answer", content="partial ")
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeSettings:
    class _O:
        name = "fake"
        agent_id = ""

    orchestrator = _O()


class _FakeAgentsProvider:
    """Stand-in for `FoundryAgentsProvider` in router tests.

    `get_client()` returns a sentinel object so we can assert the
    router forwards the *exact* client instance into
    `orchestrators.create(...)` (CU-001d).
    """

    def __init__(self, client: object | None = None) -> None:
        self.client = client if client is not None else object()
        self.get_client_calls = 0

    def get_client(self) -> object:
        self.get_client_calls += 1
        return self.client


@pytest.fixture
def app_with_fakes(monkeypatch: pytest.MonkeyPatch):
    """Build the app, register fakes in the orchestrator registry, and DI-override settings + llm + agents."""
    monkeypatch.setitem(orchestrators.registry._items, "fake", _FakeOrchestrator)
    monkeypatch.setitem(orchestrators.registry._items, "boom", _BoomOrchestrator)

    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: _FakeSettings()
    app.dependency_overrides[get_llm_provider] = lambda: object()
    # Always override the agents provider: ASGITransport doesn't run
    # lifespan, so `app.state.agents_provider` is never set. Without
    # this default the router's `agents.get_client()` would 500 even
    # for orchestrators that don't use it (langgraph swallows the
    # kwarg via `**_extras` -- Hard Rule #4: no name dispatch).
    app.dependency_overrides[get_agents_provider] = lambda: _FakeAgentsProvider()
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_json_mode_concatenates_answer_and_dedupes_citations(app_with_fakes) -> None:
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="reasoning", content="thinking"),
        OrchestratorEvent(channel="answer", content="Hello, "),
        OrchestratorEvent(channel="answer", content="world!"),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1", "url": "https://x/1"},
        ),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1 dup", "url": "https://x/1"},
        ),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc2", "title": "Doc 2", "url": "https://x/2"},
        ),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": "c-1",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "Hello, world!"
    assert body["conversation_id"] == "c-1"
    assert [c["id"] for c in body["citations"]] == ["doc1", "doc2"]


async def test_sse_mode_emits_one_frame_per_event(app_with_fakes) -> None:
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="reasoning", content="step 1"),
        OrchestratorEvent(channel="answer", content="ok"),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    text = resp.text
    frames = [f for f in text.split("\n\n") if f]
    assert len(frames) == 2
    assert frames[0].startswith("event: reasoning\n")
    assert frames[1].startswith("event: answer\n")
    # Body of the second frame parses as JSON with the answer content.
    data_line = [ln for ln in frames[1].splitlines() if ln.startswith("data: ")][0]
    assert json.loads(data_line[len("data: ") :]) == {"content": "ok", "metadata": {}}


async def test_sse_mode_surfaces_orchestrator_exception_as_error_event(app_with_fakes) -> None:
    # Use the boom orchestrator instead of the scripted fake. The ad-hoc
    # settings type still mirrors `OrchestratorSettings` so the router's
    # CU-001d kwarg forwarding (`agent_id=settings.orchestrator.agent_id`)
    # works.
    app_with_fakes.dependency_overrides[get_app_settings] = lambda: type(
        "S",
        (),
        {"orchestrator": type("O", (), {"name": "boom", "agent_id": ""})()},
    )()

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    frames = [f for f in resp.text.split("\n\n") if f]
    assert frames[0].startswith("event: answer\n")
    assert frames[-1].startswith("event: error\n")
    data_line = [ln for ln in frames[-1].splitlines() if ln.startswith("data: ")][0]
    assert json.loads(data_line[len("data: ") :])["content"] == "boom"


async def test_empty_messages_returns_422(app_with_fakes) -> None:
    async with _client(app_with_fakes) as client:
        resp = await client.post("/api/conversation", json={"messages": []})
    assert resp.status_code == 422


async def test_router_forwards_search_provider_to_orchestrator(
    app_with_fakes,
) -> None:
    """Phase 3.5 Q6c: chat route must pass the DI'd search provider into
    orchestrator construction so production langgraph runs in retrieval mode."""
    from backend.dependencies import get_search_provider

    sentinel_search = object()
    app_with_fakes.dependency_overrides[get_search_provider] = lambda: sentinel_search

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("search") is sentinel_search


async def test_router_uses_registry_dispatch_no_hardcoded_provider_names() -> None:
    """Greppable gate: no `if/elif` over orchestrator names in the router."""
    import inspect

    from backend.routers import conversation as conv_module

    src = inspect.getsource(conv_module)
    for forbidden in ("== \"langgraph\"", "== 'langgraph'", "== \"agent_framework\"", "== 'agent_framework'"):
        assert forbidden not in src, f"Forbidden hard-coded provider check: {forbidden}"
    assert "orchestrators.create(" in src


async def test_router_routes_through_chat_pipeline(
    app_with_fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase-3 audit step 6c: router must call ``pipelines.chat.run_chat``,
    not ``orchestrator.run`` directly. This gives content-safety and
    post-prompt a wiring point once they reach DI."""
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="answer", content="ok"),
    ]

    calls: list[dict[str, Any]] = []

    from backend.routers import conversation as conv_module
    from shared.pipelines import chat as chat_pipeline

    real_run_chat = chat_pipeline.run_chat

    def _spy_run_chat(messages, **kwargs):
        calls.append({"messages": list(messages), "kwargs": kwargs})
        return real_run_chat(messages, **kwargs)

    monkeypatch.setattr(conv_module, "run_chat", _spy_run_chat)

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["content"] == "ok"
    assert len(calls) == 1, "router did not delegate to pipelines.chat.run_chat"
    # The orchestrator is passed as a keyword arg, never positionally.
    assert "orchestrator" in calls[0]["kwargs"]
    assert isinstance(calls[0]["kwargs"]["orchestrator"], _FakeOrchestrator)


# ---------------------------------------------------------------------------
# CU-001d: agents_client + agent_id forwarded uniformly to every orchestrator
# ---------------------------------------------------------------------------


async def test_router_forwards_agents_client_and_agent_id_to_orchestrator(
    app_with_fakes,
) -> None:
    """Router must (a) call `agents_provider.get_client()` and pass the
    returned client as `agents_client=`, and (b) pass
    `agent_id=settings.orchestrator.agent_id` -- both forwarded
    *uniformly* into `orchestrators.create(...)` so dispatch stays
    name-free (Hard Rule #4).
    """
    sentinel_client = object()
    fake_provider = _FakeAgentsProvider(client=sentinel_client)
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider

    class _SettingsWithAgentId:
        class _O:
            name = "fake"
            agent_id = "asst_abc123"

        orchestrator = _O()

    app_with_fakes.dependency_overrides[get_app_settings] = lambda: _SettingsWithAgentId()

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("agents_client") is sentinel_client
    assert _FakeOrchestrator.last_kwargs.get("agent_id") == "asst_abc123"
    # The router resolves the client through the provider's lazy seam,
    # not by pulling a private attribute -- preserves the Stable Core
    # invariant that the AgentsClient lifecycle is provider-owned.
    assert fake_provider.get_client_calls == 1


async def test_router_dispatches_both_orchestrator_kinds_with_same_kwargs(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parametrize across `langgraph`/`agent_framework` to prove the
    router treats orchestrator selection as a registry key, not a
    branch. Both registrations resolve to `_FakeOrchestrator` here so
    we can read back `last_kwargs` for each name.
    """
    monkeypatched_keys = ["langgraph", "agent_framework"]
    # Re-register both real keys against the fake so the router's
    # `orchestrators.create(name, ...)` resolves without hitting the
    # real implementations (which would need an Azure transport).
    # `monkeypatch.setitem` restores the originals on test teardown.
    for name in monkeypatched_keys:
        monkeypatch.setitem(
            orchestrators.registry._items, name, _FakeOrchestrator
        )

    sentinel_client = object()
    fake_provider = _FakeAgentsProvider(client=sentinel_client)
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider

    for name in monkeypatched_keys:

        class _S:
            class _O:
                pass

            orchestrator = _O()

        _S.orchestrator.name = name  # type: ignore[attr-defined]
        _S.orchestrator.agent_id = "asst_xyz"  # type: ignore[attr-defined]
        app_with_fakes.dependency_overrides[get_app_settings] = lambda s=_S: s()

        _FakeOrchestrator.scripted = [
            OrchestratorEvent(channel="answer", content=name)
        ]
        _FakeOrchestrator.last_kwargs = {}

        async with _client(app_with_fakes) as client:
            resp = await client.post(
                "/api/conversation",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )

        assert resp.status_code == 200, f"{name} failed: {resp.text}"
        assert resp.json()["content"] == name
        # Same kwargs forwarded regardless of orchestrator key.
        assert _FakeOrchestrator.last_kwargs.get("agents_client") is sentinel_client
        assert _FakeOrchestrator.last_kwargs.get("agent_id") == "asst_xyz"
        assert "search" in _FakeOrchestrator.last_kwargs
