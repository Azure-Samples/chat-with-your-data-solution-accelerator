"""Tests for the LangGraph orchestrator."""

from typing import AsyncIterator, Sequence
from unittest.mock import MagicMock

import pytest

from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.orchestrators.langgraph import LangGraphOrchestrator
from backend.core.settings import AppSettings
from backend.core.types import (
    ChatChunk,
    ChatMessage,
    EmbeddingResult,
    OrchestratorEvent,
    SearchResult,
)

# Canned query embedding returned by ``_FakeLLM.embed`` so search-wiring
# tests can assert the orchestrator forwards the vector to ``search``.
_FAKE_QUERY_VECTOR: list[float] = [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeLLM(BaseLLMProvider):
    """Minimal LLM stub returning a canned assistant reply."""

    def __init__(self, reply: str = "hello world") -> None:
        # Deliberately skip BaseLLMProvider.__init__: settings/credential
        # are unused by the stub and the orchestrator only calls
        # ``.complete()`` (overridden below to bypass the inherited
        # routing, which would otherwise dereference ``self._settings``).
        self._reply = reply
        self.calls: list[Sequence[ChatMessage]] = []
        self.embed_calls: list[Sequence[str]] = []
        self.complete_calls: list[dict[str, float | int | None]] = []

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

    async def embed(
        self, inputs: Sequence[str], *, deployment: str | None = None
    ) -> EmbeddingResult:
        self.embed_calls.append(list(inputs))
        return EmbeddingResult(vectors=[_FAKE_QUERY_VECTOR], model="fake")

    async def reason(  # pragma: no cover - not exercised
        self, messages: Sequence[ChatMessage], *, deployment: str | None = None
    ) -> AsyncIterator[OrchestratorEvent]:
        raise NotImplementedError
        yield  # type: ignore[unreachable]

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        # Override the base implementation (which would dereference
        # ``self._settings``) to mirror the non-reasoning path: record
        # the call and yield a single ``answer`` event with the canned
        # reply. Subclasses can override this to inject reasoning /
        # error events for the streaming tests.
        self.calls.append(list(messages))
        self.complete_calls.append(
            {"temperature": temperature, "max_tokens": max_tokens}
        )
        yield OrchestratorEvent(channel="answer", content=self._reply)


class _BlankReplyLLM(_FakeLLM):
    """LLM that returns no answer chunks (simulates an empty response)."""

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        # Yield nothing on the answer channel -- triggers the "no
        # assistant reply" error event in ``run()``.
        if False:
            yield  # pragma: no cover - pacify the AsyncIterator return type
        return


def _make_orchestrator(llm: BaseLLMProvider | None = None) -> LangGraphOrchestrator:
    settings = MagicMock(spec=AppSettings)
    return LangGraphOrchestrator(settings=settings, llm=llm or _FakeLLM())


# ---------------------------------------------------------------------------
# Registration + plumbing
# ---------------------------------------------------------------------------


def test_langgraph_is_registered() -> None:
    assert "langgraph" in orchestrators_registry.registry.keys()
    assert orchestrators_registry.registry.get("langgraph") is LangGraphOrchestrator


def test_create_returns_langgraph_orchestrator_instance() -> None:
    settings = MagicMock(spec=AppSettings)
    orch = orchestrators_registry.registry.get("langgraph")(
        settings=settings, llm=_FakeLLM()
    )
    assert isinstance(orch, LangGraphOrchestrator)


# ---------------------------------------------------------------------------
# run() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_yields_single_answer_event_with_assistant_reply() -> None:
    fake = _FakeLLM(reply="grounded answer")
    orch = _make_orchestrator(fake)
    events = [e async for e in orch.run([ChatMessage(role="user", content="ping")])]
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
    events = [e async for e in orch.run([ChatMessage(role="user", content="ping")])]
    assert len(events) == 1
    assert events[0].channel == "error"
    assert "no assistant reply" in events[0].content.lower()


@pytest.mark.asyncio
async def test_run_accepts_settings_override_kwarg_without_breaking() -> None:
    """`settings_override` is reserved for per-request knobs."""
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
# Citation wiring
# ---------------------------------------------------------------------------


class _FakeSearch:
    """Minimal `BaseSearch` stub returning canned hits."""

    def __init__(self, hits):
        self.hits = [SearchResult(**h) if isinstance(h, dict) else h for h in hits]
        self.calls: list[str] = []
        self.kwargs_calls: list[dict[str, object]] = []

    async def search(self, query, **kwargs):
        self.calls.append(query)
        self.kwargs_calls.append(dict(kwargs))
        return self.hits


@pytest.mark.asyncio
async def test_run_without_search_emits_no_citation_events() -> None:
    """Pass-through mode -- preserves the original single-answer contract."""
    orch = _make_orchestrator(_FakeLLM(reply="ungrounded"))
    events = [e async for e in orch.run([ChatMessage(role="user", content="ping")])]
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

    events = [e async for e in orch.run([ChatMessage(role="user", content="what?")])]
    channels = [e.channel for e in events]
    # Production emits all retrieved citations then the answer.
    assert channels == ["citation", "citation", "answer"]
    citation_ids = [e.metadata["id"] for e in events if e.channel == "citation"]
    assert citation_ids == ["[doc1]", "[doc2]"]
    assert events[-1].content == "From [doc1] we learn the answer."
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


# ---------------------------------------------------------------------------
# System-prompt injection (effective cwyd_agent_instructions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_injects_system_prompt_as_leading_system_message() -> None:
    """The configured system prompt is prepended as the first system
    message so the model sees its instructions before the user turn."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    orch = LangGraphOrchestrator(
        settings=settings, llm=fake_llm, system_prompt="You are CWYD."
    )

    _ = [e async for e in orch.run([ChatMessage(role="user", content="q?")])]

    sent = fake_llm.calls[0]
    assert sent[0].role == "system"
    assert sent[0].content == "You are CWYD."
    assert sent[1].role == "user"
    assert sent[1].content == "q?"


@pytest.mark.asyncio
async def test_run_system_prompt_precedes_sources_block() -> None:
    """With both a system prompt and search hits, the prompt comes first,
    then the [docN] sources block, then the user turn."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    fake_search = _FakeSearch(
        [{"id": "x", "content": "alpha", "title": "A", "url": "http://a"}]
    )
    orch = LangGraphOrchestrator(
        settings=settings,
        llm=fake_llm,
        search=fake_search,
        system_prompt="You are CWYD.",
    )

    _ = [e async for e in orch.run([ChatMessage(role="user", content="q?")])]

    sent = fake_llm.calls[0]
    assert sent[0].role == "system"
    assert sent[0].content == "You are CWYD."
    assert sent[1].role == "system"
    assert "[doc1]: alpha" in sent[1].content
    assert sent[2].role == "user"
    assert sent[2].content == "q?"


@pytest.mark.asyncio
async def test_run_without_system_prompt_injects_no_system_message() -> None:
    """`system_prompt=None` (the default) preserves pass-through mode --
    no leading system message is fabricated."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm)

    _ = [e async for e in orch.run([ChatMessage(role="user", content="hi")])]

    assert all(m.role != "system" for m in fake_llm.calls[0])


# ---------------------------------------------------------------------------
# Search-knob forwarding (effective search_top_k / search_use_semantic_search)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_forwards_search_knobs_to_search_provider() -> None:
    """The effective `search_top_k` / `search_use_semantic_search`
    threaded in at construction are forwarded into `BaseSearch.search`."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    fake_search = _FakeSearch(
        [{"id": "x", "content": "alpha", "title": "A", "url": "http://a"}]
    )
    orch = LangGraphOrchestrator(
        settings=settings,
        llm=fake_llm,
        search=fake_search,
        search_top_k=7,
        search_use_semantic_search=True,
    )

    _ = [e async for e in orch.run([ChatMessage(role="user", content="q?")])]

    assert fake_search.kwargs_calls == [
        {"top_k": 7, "use_semantic_search": True, "vector": _FAKE_QUERY_VECTOR}
    ]


@pytest.mark.asyncio
async def test_run_defaults_search_knobs_to_none_when_unset() -> None:
    """Without explicit knobs, `run()` forwards `None` for both so the
    provider falls back to its `settings.search` defaults."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    fake_search = _FakeSearch(
        [{"id": "x", "content": "alpha", "title": "A", "url": "http://a"}]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    _ = [e async for e in orch.run([ChatMessage(role="user", content="q?")])]

    assert fake_search.kwargs_calls == [
        {"top_k": None, "use_semantic_search": None, "vector": _FAKE_QUERY_VECTOR}
    ]


@pytest.mark.asyncio
async def test_run_embeds_query_and_passes_vector_to_search() -> None:
    """The latest user query is embedded and the resulting vector is
    forwarded to ``BaseSearch.search`` so pgvector runs dense retrieval
    (without a vector it falls back to AND-semantics full-text search)."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="ok")
    fake_search = _FakeSearch(
        [{"id": "x", "content": "alpha", "title": "A", "url": "http://a"}]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    _ = [
        e
        async for e in orch.run(
            [ChatMessage(role="user", content="remote work policy?")]
        )
    ]

    assert fake_llm.embed_calls == [["remote work policy?"]]
    assert fake_search.kwargs_calls[0]["vector"] == _FAKE_QUERY_VECTOR


@pytest.mark.asyncio
async def test_run_with_search_no_hits_skips_citation_block() -> None:
    """Empty search results -- no citations, no system injection, plain answer."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM(reply="nothing to cite")
    fake_search = _FakeSearch([])
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    events = [e async for e in orch.run([ChatMessage(role="user", content="hi")])]
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

    events = [e async for e in orch.run([ChatMessage(role="user", content="?")])]
    citation_events = [e for e in events if e.channel == "citation"]
    # Production emits all retrieved citations regardless of reply markers.
    assert len(citation_events) == 2
    assert {e.metadata["id"] for e in citation_events} == {"[doc1]", "[doc2]"}


# ---------------------------------------------------------------------------
# streaming via BaseLLMProvider.complete()
# ---------------------------------------------------------------------------


class _ReasoningLLM(_FakeLLM):
    """LLM that streams reasoning + answer events (mimics o-series)."""

    def __init__(self, events: list[OrchestratorEvent]) -> None:
        super().__init__(reply="")
        self._events = events

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        self.calls.append(list(messages))
        for ev in self._events:
            yield ev


@pytest.mark.asyncio
async def test_run_streams_reasoning_events_live_then_buffers_answer() -> None:
    """``reasoning`` events pass through verbatim in order; ``answer``
    chunks are accumulated into a single trailing event so the SSE
    single-answer contract (ADR 0007) survives the streaming switch."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _ReasoningLLM(
        [
            OrchestratorEvent(channel="reasoning", content="step 1 "),
            OrchestratorEvent(channel="reasoning", content="step 2"),
            OrchestratorEvent(channel="answer", content="Final "),
            OrchestratorEvent(channel="answer", content="answer."),
        ]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm)

    events = [e async for e in orch.run([ChatMessage(role="user", content="hi")])]

    channels = [(e.channel, e.content) for e in events]
    assert channels == [
        ("reasoning", "step 1 "),
        ("reasoning", "step 2"),
        ("answer", "Final answer."),
    ]


@pytest.mark.asyncio
async def test_run_propagates_error_events_from_complete() -> None:
    """An ``error`` event from ``complete()`` short-circuits the run --
    no synthetic ``no assistant reply`` event is emitted on top of it."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _ReasoningLLM(
        [
            OrchestratorEvent(channel="reasoning", content="thinking..."),
            OrchestratorEvent(
                channel="error",
                content="upstream blew up",
                metadata={"code": "reason_stream_failed"},
            ),
        ]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm)

    events = [e async for e in orch.run([ChatMessage(role="user", content="hi")])]

    assert [e.channel for e in events] == ["reasoning", "error"]
    assert events[-1].metadata["code"] == "reason_stream_failed"
    assert events[-1].content == "upstream blew up"


@pytest.mark.asyncio
async def test_run_forwards_sampling_to_complete() -> None:
    """run() forwards the effective `openai_temperature` / `openai_max_tokens`
    knobs to `complete()` so the admin sampling settings reach the model."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _FakeLLM()
    orch = LangGraphOrchestrator(
        settings=settings,
        llm=fake_llm,
        openai_temperature=0.4,
        openai_max_tokens=99,
    )
    _ = [e async for e in orch.run([ChatMessage(role="user", content="hi")])]
    assert fake_llm.complete_calls == [{"temperature": 0.4, "max_tokens": 99}]


@pytest.mark.asyncio
async def test_run_filters_citations_against_assembled_answer() -> None:
    """Citation filtering uses the *assembled* answer, so a marker that
    spans two streamed chunks (e.g. ``[`` + ``doc1]``) still matches."""
    settings = MagicMock(spec=AppSettings)
    fake_llm = _ReasoningLLM(
        [
            OrchestratorEvent(channel="answer", content="See ["),
            OrchestratorEvent(channel="answer", content="doc1] for details."),
        ]
    )
    fake_search = _FakeSearch(
        [{"id": "src-a", "content": "alpha", "title": "A", "url": "http://a"}]
    )
    orch = LangGraphOrchestrator(settings=settings, llm=fake_llm, search=fake_search)

    events = [e async for e in orch.run([ChatMessage(role="user", content="?")])]

    channels = [e.channel for e in events]
    assert channels == ["citation", "answer"]
    assert events[0].metadata["id"] == "[doc1]"
    assert events[-1].content == "See [doc1] for details."
