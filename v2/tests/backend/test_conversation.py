"""Pillar: Stable Core / Phase: 3 (task #22a) — tests for the conversation router."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Sequence

import httpx
import pytest

from backend.app import create_app
from backend.dependencies import get_app_settings, get_llm_provider
from providers import orchestrators
from providers.orchestrators.base import OrchestratorBase
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

    orchestrator = _O()


@pytest.fixture
def app_with_fakes(monkeypatch: pytest.MonkeyPatch):
    """Build the app, register fakes in the orchestrator registry, and DI-override settings + llm."""
    monkeypatch.setitem(orchestrators.registry._items, "fake", _FakeOrchestrator)
    monkeypatch.setitem(orchestrators.registry._items, "boom", _BoomOrchestrator)

    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: _FakeSettings()
    app.dependency_overrides[get_llm_provider] = lambda: object()
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
    # Use the boom orchestrator instead of the scripted fake.
    app_with_fakes.dependency_overrides[get_app_settings] = lambda: type(
        "S", (), {"orchestrator": type("O", (), {"name": "boom"})()}
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
    from pipelines import chat as chat_pipeline

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
