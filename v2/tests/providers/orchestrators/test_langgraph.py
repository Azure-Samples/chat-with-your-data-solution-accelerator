"""Tests for the LangGraph orchestrator (Phase 3 task #18).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Sequence
from unittest.mock import MagicMock

import pytest

from providers import orchestrators
from providers.llm.base import BaseLLMProvider
from providers.orchestrators.langgraph import LangGraphOrchestrator
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
