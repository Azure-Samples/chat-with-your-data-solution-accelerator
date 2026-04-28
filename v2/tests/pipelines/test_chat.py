"""Pillar: Stable Core / Phase: 3 (#22b) — tests for v2/src/pipelines/chat.py."""
from __future__ import annotations

from typing import Any, AsyncIterator, Sequence

import pytest

from pipelines.chat import run_chat
from providers.orchestrators.base import OrchestratorBase
from shared.tools.content_safety import ContentSafetyVerdict
from shared.tools.post_prompt import ValidationResult
from shared.types import ChatMessage, OrchestratorEvent

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _ScriptedOrchestrator(OrchestratorBase):
    def __init__(self, events: list[OrchestratorEvent]) -> None:
        super().__init__(settings=object(), llm=object())  # type: ignore[arg-type]
        self._events = events
        self.calls = 0

    async def run(  # type: ignore[override]
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        self.calls += 1
        for ev in self._events:
            yield ev


class _FakeContentSafety:
    def __init__(self, verdict: ContentSafetyVerdict) -> None:
        self._verdict = verdict
        self.calls: list[str] = []

    async def screen(self, text: str) -> ContentSafetyVerdict:
        self.calls.append(text)
        return self._verdict


class _FakePostPrompt:
    def __init__(self, result: ValidationResult) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def validate(self, *, question: str, answer: str, sources, **_: Any) -> ValidationResult:
        self.calls.append({"question": question, "answer": answer, "sources": list(sources)})
        return self._result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def _drain(gen) -> list[OrchestratorEvent]:
    return [ev async for ev in gen]


async def test_passthrough_without_guards_yields_orchestrator_events_verbatim() -> None:
    events = [
        OrchestratorEvent(channel="reasoning", content="thinking"),
        OrchestratorEvent(channel="answer", content="hi"),
    ]
    orch = _ScriptedOrchestrator(events)

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="hello")],
            orchestrator=orch,
        )
    )

    assert out == events
    assert orch.calls == 1


async def test_content_safety_block_short_circuits_orchestrator() -> None:
    guard = _FakeContentSafety(
        ContentSafetyVerdict(flagged=True, triggered=["Hate"], categories={"Hate": 6})
    )
    orch = _ScriptedOrchestrator([OrchestratorEvent(channel="answer", content="should not appear")])

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="bad input")],
            orchestrator=orch,
            content_safety=guard,
        )
    )

    assert orch.calls == 0
    assert len(out) == 1
    assert out[0].channel == "error"
    assert out[0].metadata["code"] == "content_safety"
    assert out[0].metadata["triggered"] == ["Hate"]
    assert guard.calls == ["bad input"]


async def test_content_safety_pass_runs_orchestrator() -> None:
    guard = _FakeContentSafety(ContentSafetyVerdict(flagged=False))
    orch = _ScriptedOrchestrator([OrchestratorEvent(channel="answer", content="ok")])

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="benign")],
            orchestrator=orch,
            content_safety=guard,
        )
    )

    assert orch.calls == 1
    assert [e.channel for e in out] == ["answer"]


async def test_post_prompt_grounded_emits_buffered_answer_at_end() -> None:
    events = [
        OrchestratorEvent(channel="reasoning", content="step 1"),
        OrchestratorEvent(channel="answer", content="Hello, "),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1", "snippet": "src content"},
        ),
        OrchestratorEvent(channel="answer", content="world!"),
    ]
    orch = _ScriptedOrchestrator(events)
    validator = _FakePostPrompt(ValidationResult(grounded=True, answer="Hello, world!"))

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="say hi")],
            orchestrator=orch,
            post_prompt=validator,
        )
    )

    # No `answer` event during streaming; one at end.
    channels = [e.channel for e in out]
    assert channels == ["reasoning", "citation", "answer"]
    assert out[-1].content == "Hello, world!"
    assert validator.calls[0]["question"] == "say hi"
    assert validator.calls[0]["answer"] == "Hello, world!"
    assert len(validator.calls[0]["sources"]) == 1
    assert validator.calls[0]["sources"][0].id == "doc1"


async def test_post_prompt_not_grounded_replaces_answer_with_filter_message() -> None:
    events = [
        OrchestratorEvent(channel="answer", content="hallucinated answer"),
    ]
    orch = _ScriptedOrchestrator(events)
    validator = _FakePostPrompt(
        ValidationResult(grounded=False, answer="Sorry, ungrounded.")
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="q")],
            orchestrator=orch,
            post_prompt=validator,
        )
    )

    channels = [e.channel for e in out]
    assert channels == ["reasoning", "answer"]
    assert out[0].metadata["code"] == "post_prompt_filtered"
    assert out[1].content == "Sorry, ungrounded."


async def test_latest_user_message_is_screened_not_assistant() -> None:
    guard = _FakeContentSafety(ContentSafetyVerdict(flagged=False))
    orch = _ScriptedOrchestrator([])

    await _drain(
        run_chat(
            [
                ChatMessage(role="user", content="first"),
                ChatMessage(role="assistant", content="reply"),
                ChatMessage(role="user", content="latest"),
            ],
            orchestrator=orch,
            content_safety=guard,
        )
    )

    assert guard.calls == ["latest"]
