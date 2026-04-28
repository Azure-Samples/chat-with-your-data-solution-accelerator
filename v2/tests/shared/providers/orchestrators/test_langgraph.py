"""Tests for the LangGraph orchestrator (Phase 3 task #18).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Sequence
from unittest.mock import MagicMock

import pytest

from shared.providers import orchestrators
from shared.providers.llm.base import BaseLLMProvider
from shared.providers.orchestrators.langgraph import LangGraphOrchestrator
from shared.settings import AppSettings
from shared.types import ChatChunk, ChatMessage, EmbeddingResult, OrchestratorEvent


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeLLM(BaseLLMProvider):
    """Minimal LLM stub returning a canned assistant reply."""

    def __init__(self, reply: str = "hello world") -> None:
        # Deliberately skip BaseLLMProvider.__init__: settings/credential
        # are unused by the stub and the orchestrator only calls .chat().
        self._reply = reply
        self.calls: list[Sequence[ChatMessage]] = []

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatMessage:
        self.calls.append(list(messages))
        return ChatMessage(role="assistant", content=self._reply)

    async def chat_stream(  # pragma: no cover - not exercised in this unit
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(content=self._reply)

    async def embed(  # pragma: no cover - not exercised
        self, inputs: Sequence[str], *, deployment: str | None = None
    ) -> EmbeddingResult:
        return EmbeddingResult(vectors=[], model="fake")

    async def reason(  # pragma: no cover - not exercised
        self, messages: Sequence[ChatMessage], *, deployment: str | None = None
    ) -> AsyncIterator[OrchestratorEvent]:
        raise NotImplementedError
        yield  # type: ignore[unreachable]


class _BlankReplyLLM(_FakeLLM):
    """LLM that returns a non-assistant role (simulates a malformed reply)."""

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatMessage:
        return ChatMessage(role="user", content="not from assistant")


def _make_orchestrator(llm: BaseLLMProvider | None = None) -> LangGraphOrchestrator:
    settings = MagicMock(spec=AppSettings)
    return LangGraphOrchestrator(settings=settings, llm=llm or _FakeLLM())


# ---------------------------------------------------------------------------
# Registration + plumbing
# ---------------------------------------------------------------------------


def test_langgraph_is_registered() -> None:
    assert "langgraph" in orchestrators.registry.keys()
    assert orchestrators.registry.get("langgraph") is LangGraphOrchestrator


def test_create_returns_langgraph_orchestrator_instance() -> None:
    settings = MagicMock(spec=AppSettings)
    orch = orchestrators.create("langgraph", settings=settings, llm=_FakeLLM())
    assert isinstance(orch, LangGraphOrchestrator)


# ---------------------------------------------------------------------------
# run() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_yields_single_answer_event_with_assistant_reply() -> None:
    fake = _FakeLLM(reply="grounded answer")
    orch = _make_orchestrator(fake)
    events = [
        e
        async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    assert len(events) == 1
    assert events[0].channel == "answer"
    assert events[0].content == "grounded answer"


@pytest.mark.asyncio
async def test_run_invokes_llm_with_user_messages() -> None:
    fake = _FakeLLM()
    orch = _make_orchestrator(fake)
    user_msg = ChatMessage(role="user", content="hi")
    _ = [e async for e in orch.run([user_msg])]
    assert len(fake.calls) == 1
    assert fake.calls[0][0].content == "hi"
    assert fake.calls[0][0].role == "user"


@pytest.mark.asyncio
async def test_run_emits_error_event_when_no_assistant_reply() -> None:
    orch = _make_orchestrator(_BlankReplyLLM())
    events = [
        e
        async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    assert len(events) == 1
    assert events[0].channel == "error"
    assert "no assistant reply" in events[0].content.lower()


@pytest.mark.asyncio
async def test_run_accepts_settings_override_kwarg_without_breaking() -> None:
    """`settings_override` is reserved for per-request knobs (task #22+)."""
    orch = _make_orchestrator()
    events = [
        e
        async for e in orch.run(
            [ChatMessage(role="user", content="hi")],
            settings_override={"temperature": 0.7},
        )
    ]
    assert len(events) == 1
    assert events[0].channel == "answer"


# ---------------------------------------------------------------------------
# Citation wiring (audit step 6d / task #23)
# ---------------------------------------------------------------------------


class _FakeSearch:
    """Minimal `BaseSearch` stub returning canned hits."""

    def __init__(self, hits):
        from shared.types import SearchResult

        self.hits = [SearchResult(**h) if isinstance(h, dict) else h for h in hits]
        self.calls: list[str] = []

    async def search(self, query, **_kwargs):
        self.calls.append(query)
        return self.hits


@pytest.mark.asyncio
async def test_run_without_search_emits_no_citation_events() -> None:
    """Pass-through mode -- preserves the original single-answer contract."""
    orch = _make_orchestrator(_FakeLLM(reply="ungrounded"))
    events = [
        e async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    assert [e.channel for e in events] == ["answer"]


@pytest.mark.asyncio
async def test_run_with_search_emits_citations_for_referenced_markers_only() -> None:
    """Only citations whose marker shows up in the reply are emitted."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="From [doc1] we learn the answer.")
    fake_search = _FakeSearch(
        [
            {"id": "src-a", "content": "alpha", "title": "A", "url": "http://a"},
            {"id": "src-b", "content": "beta", "title": "B", "url": "http://b"},
        ]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="what?")])
    ]
    channels = [e.channel for e in events]
    assert channels == ["citation", "answer"]
    citation_ev = events[0]
    assert citation_ev.metadata["id"] == "[doc1]"
    assert citation_ev.metadata["title"] == "A"
    assert citation_ev.metadata["metadata"]["source_id"] == "src-a"
    assert events[1].content == "From [doc1] we learn the answer."
    # Search was called with the latest user text.
    assert fake_search.calls == ["what?"]


@pytest.mark.asyncio
async def test_run_with_search_injects_sources_block_into_llm_prompt() -> None:
    """LangGraph receives a leading system message holding the [docN] block."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    fake_search = _FakeSearch(
        [{"id": "x", "content": "alpha", "title": "A", "url": "http://a"}]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    _ = [e async for e in orch.run([ChatMessage(role="user", content="q?")])]

    assert len(fake_llm.calls) == 1
    sent = fake_llm.calls[0]
    assert sent[0].role == "system"
    assert "[doc1]: alpha" in sent[0].content
    assert sent[1].role == "user"
    assert sent[1].content == "q?"


@pytest.mark.asyncio
async def test_run_with_search_no_hits_skips_citation_block() -> None:
    """Empty search results -- no citations, no system injection, plain answer."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="nothing to cite")
    fake_search = _FakeSearch([])
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="hi")])
    ]
    assert [e.channel for e in events] == ["answer"]
    # No system message was prepended.
    assert all(m.role != "system" for m in fake_llm.calls[0])


@pytest.mark.asyncio
async def test_run_with_search_drops_unreferenced_citations() -> None:
    """Citations whose marker is absent from the reply are filtered out."""
    settings = MagicMock(spec=AppSettings)
    # Reply mentions [doc2] only.
    fake_llm = _FakeLLM(reply="see [doc2] for the details")
    fake_search = _FakeSearch(
        [
            {"id": "a", "content": "alpha", "title": "A", "url": "http://a"},
            {"id": "b", "content": "beta", "title": "B", "url": "http://b"},
        ]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="?")])
    ]
    citation_events = [e for e in events if e.channel == "citation"]
    assert len(citation_events) == 1
    assert citation_events[0].metadata["id"] == "[doc2]"
