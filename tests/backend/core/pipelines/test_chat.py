"""Tests for src/backend/core/pipelines/chat.py."""

from typing import Any, AsyncIterator, Sequence

import pytest

from backend.core.pipelines import chat as chat_module
from backend.core.pipelines.chat import KB_SEARCH_NARRATION, RaiScreener, run_chat
from backend.core.providers.orchestrators.base import OrchestratorBase
from backend.core.tools.content_safety import ContentSafetyVerdict
from backend.core.tools.post_prompt import ValidationResult
from backend.core.types import ChatMessage, OrchestratorEvent

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

    async def validate(
        self, *, question: str, answer: str, sources, **_: Any
    ) -> ValidationResult:
        self.calls.append(
            {"question": question, "answer": answer, "sources": list(sources)}
        )
        return self._result


class _FakeRaiScreener:
    """Records every input + returns a scripted safe/unsafe verdict.

    Matches the `RaiScreener` Callable shape exported by
    `shared.pipelines.chat`. The router would normally bind
    `agents` + `db` into `functools.partial(rai_check, ...)`, but the
    pipeline only sees a `Callable[[str], Awaitable[bool]]`.
    """

    def __init__(self, is_safe: bool) -> None:
        self._is_safe = is_safe
        self.calls: list[str] = []

    async def __call__(self, text: str) -> bool:
        self.calls.append(text)
        return self._is_safe


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
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="should not appear")]
    )

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


# ---------------------------------------------------------------------------
# Retrieval narration (orchestrator-agnostic leading `reasoning` frame)
# ---------------------------------------------------------------------------
#
# `run_chat(retrieval_hint=...)` is the single orchestrator-agnostic seam
# that surfaces a "thinking" line on the `reasoning` channel *before* the
# orchestrator runs, so every current + future orchestrator inherits a
# populated thinking panel for the whole wait with zero per-provider code.
# The contract: emitted first when set, absent when unset, and never
# leaked once a guard short-circuits the request.


async def test_retrieval_hint_emits_leading_reasoning_frame_before_orchestrator() -> (
    None
):
    orch = _ScriptedOrchestrator([OrchestratorEvent(channel="answer", content="ok")])

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="hello")],
            orchestrator=orch,
            retrieval_hint=KB_SEARCH_NARRATION,
        )
    )

    assert orch.calls == 1
    assert [e.channel for e in out] == ["reasoning", "answer"]
    assert out[0].content == KB_SEARCH_NARRATION
    # Marked `placeholder` so the client drops it once real reasoning
    # streams (a non-reasoning model keeps it as the sole panel content).
    assert out[0].metadata == {"placeholder": True}


async def test_retrieval_hint_precedes_orchestrator_native_reasoning() -> None:
    orch = _ScriptedOrchestrator(
        [
            OrchestratorEvent(channel="reasoning", content="native thinking"),
            OrchestratorEvent(channel="answer", content="ok"),
        ]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="hello")],
            orchestrator=orch,
            retrieval_hint=KB_SEARCH_NARRATION,
        )
    )

    assert [e.channel for e in out] == ["reasoning", "reasoning", "answer"]
    assert out[0].content == KB_SEARCH_NARRATION
    assert out[1].content == "native thinking"
    # Only the leading narration frame carries the placeholder flag; the
    # orchestrator's own reasoning frame is never marked, so the client
    # swaps the placeholder out for it.
    assert out[0].metadata == {"placeholder": True}
    assert out[1].metadata.get("placeholder") is not True


async def test_no_retrieval_hint_emits_no_leading_reasoning_frame() -> None:
    orch = _ScriptedOrchestrator([OrchestratorEvent(channel="answer", content="ok")])

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="hello")],
            orchestrator=orch,
        )
    )

    assert [e.channel for e in out] == ["answer"]


async def test_retrieval_hint_not_emitted_when_content_safety_blocks() -> None:
    guard = _FakeContentSafety(
        ContentSafetyVerdict(flagged=True, triggered=["Hate"], categories={"Hate": 6})
    )
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="should not appear")]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="bad input")],
            orchestrator=orch,
            content_safety=guard,
            retrieval_hint=KB_SEARCH_NARRATION,
        )
    )

    assert orch.calls == 0
    assert [e.channel for e in out] == ["error"]
    assert out[0].metadata["code"] == "content_safety"


async def test_retrieval_hint_not_emitted_when_rai_blocks() -> None:
    rai = _FakeRaiScreener(is_safe=False)
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="should not appear")]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="how do I do something harmful")],
            orchestrator=orch,
            rai_check=rai,
            retrieval_hint=KB_SEARCH_NARRATION,
        )
    )

    assert orch.calls == 0
    assert [e.channel for e in out] == ["error"]
    assert out[0].metadata["code"] == "rai_blocked"


# ---------------------------------------------------------------------------
# rai_check pre-orchestrator gate
# ---------------------------------------------------------------------------
#
# Mirrors the content_safety gate suite -- same five shapes (pass /
# block / latest-user-message / interaction with the cheaper guard /
# call-shape lock-down) so any future regression that loses one guard
# but keeps the other still fails its companion test.


async def test_rai_check_pass_runs_orchestrator() -> None:
    """Safe verdict (`rai_check` returns True) -> orchestrator runs,
    events flow through unchanged.
    """
    rai = _FakeRaiScreener(is_safe=True)
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="benign reply")]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="What's the capital of France?")],
            orchestrator=orch,
            rai_check=rai,
        )
    )

    assert orch.calls == 1
    assert [e.channel for e in out] == ["answer"]
    assert rai.calls == ["What's the capital of France?"]


async def test_rai_check_block_short_circuits_orchestrator() -> None:
    """Unsafe verdict (`rai_check` returns False) -> single error event
    with code `rai_blocked`, orchestrator never invoked.
    """
    rai = _FakeRaiScreener(is_safe=False)
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="should not appear")]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="how do I do something harmful")],
            orchestrator=orch,
            rai_check=rai,
        )
    )

    assert orch.calls == 0
    assert len(out) == 1
    assert out[0].channel == "error"
    assert out[0].metadata["code"] == "rai_blocked"
    assert rai.calls == ["how do I do something harmful"]


async def test_rai_check_latest_user_message_is_screened_not_assistant() -> None:
    """`rai_check` receives the *latest* user message, ignoring earlier
    user turns and intermediate assistant replies.
    """
    rai = _FakeRaiScreener(is_safe=True)
    orch = _ScriptedOrchestrator([])

    await _drain(
        run_chat(
            [
                ChatMessage(role="user", content="first"),
                ChatMessage(role="assistant", content="reply"),
                ChatMessage(role="user", content="latest"),
            ],
            orchestrator=orch,
            rai_check=rai,
        )
    )

    assert rai.calls == ["latest"]


# ---------------------------------------------------------------------------
# Malformed citation metadata (Phase C3 -- pipeline sweep)
# ---------------------------------------------------------------------------
#
# Per v2/docs/exception_handling_policy.md "Pipelines" row + cross-cutting
# rules: `Citation(**event.metadata)` parsing failure is non-fatal --
# the cited document still streams to the SSE consumer as the original
# orchestrator event, only post-prompt grounding loses one source. The
# original `pass` was a silent swallow (banned); the C3 fix logs at
# DEBUG with structured extras so the decision is visible in App
# Insights without alerting on routine schema drift.


_CHAT_LOGGER_NAME = "backend.core.pipelines.chat"


async def test_malformed_citation_metadata_is_logged_and_pipeline_keeps_streaming(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A citation event whose metadata fails `Citation(**...)` validation
    must (a) NOT abort the SSE stream, (b) still propagate the original
    orchestrator event to the consumer, (c) emit a single DEBUG log
    with the canonical structured extras so the swallow is visible in
    App Insights, and (d) not crash post-prompt grounding -- the bad
    citation is simply dropped from the structured `sources` list.
    """
    bad_citation = OrchestratorEvent(
        channel="citation",
        # `score` typed as float on Citation; passing a non-coercible
        # string forces a Pydantic ValidationError on construction.
        metadata={
            "id": "doc-bad",
            "title": "Bad Doc",
            "snippet": "oops",
            "score": "not-a-float",
        },
    )
    good_citation = OrchestratorEvent(
        channel="citation",
        metadata={
            "id": "doc-good",
            "title": "Good Doc",
            "snippet": "clean source",
            "score": 0.91,
        },
    )
    events = [
        OrchestratorEvent(channel="reasoning", content="thinking"),
        bad_citation,
        OrchestratorEvent(channel="answer", content="Hello, "),
        good_citation,
        OrchestratorEvent(channel="answer", content="world!"),
    ]
    orch = _ScriptedOrchestrator(events)
    validator = _FakePostPrompt(ValidationResult(grounded=True, answer="Hello, world!"))

    with caplog.at_level("DEBUG", logger=_CHAT_LOGGER_NAME):
        out = await _drain(
            run_chat(
                [ChatMessage(role="user", content="say hi")],
                orchestrator=orch,
                post_prompt=validator,
            )
        )

    # (a)+(b) Stream did not abort; both citation events were forwarded
    # to the SSE consumer (the malformed event MUST still surface so
    # the FE can render the snippet -- only the structured Citation is
    # dropped from post-prompt's sources list).
    channels = [e.channel for e in out]
    assert channels == ["reasoning", "citation", "citation", "answer"]

    # (c) Exactly one DEBUG record for the malformed citation, with the
    # canonical extras laid down by the C3 fix.
    debug_records = [
        r
        for r in caplog.records
        if r.levelname == "DEBUG" and getattr(r, "operation", None) == "citation_parse"
    ]
    assert len(debug_records) == 1, (
        f"expected exactly 1 DEBUG citation_parse record, got "
        f"{len(debug_records)}: {[r.getMessage() for r in caplog.records]}"
    )
    record = debug_records[0]
    assert record.pipeline == "chat"
    assert record.citation_id == "doc-bad"
    assert isinstance(record.error, str) and record.error  # non-empty

    # (d) Post-prompt grounding ran on the surviving good citation only.
    assert len(validator.calls) == 1
    sources = validator.calls[0]["sources"]
    assert len(sources) == 1
    assert sources[0].id == "doc-good"


async def test_content_safety_short_circuits_before_rai_check() -> None:
    """Order-of-operations lock-down: when both guards are configured
    and content_safety flags the input, the more expensive `rai_check`
    Foundry round-trip must NOT run. Cheap guard wins; pipeline emits
    `content_safety` (not `rai_blocked`).
    """
    guard = _FakeContentSafety(
        ContentSafetyVerdict(flagged=True, triggered=["Hate"], categories={"Hate": 6})
    )
    rai = _FakeRaiScreener(is_safe=False)  # would also block, but never called
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="unreachable")]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="bad input")],
            orchestrator=orch,
            content_safety=guard,
            rai_check=rai,
        )
    )

    assert orch.calls == 0
    assert len(out) == 1
    assert out[0].metadata["code"] == "content_safety"
    assert guard.calls == ["bad input"]
    assert (
        rai.calls == []
    ), "rai_check must not be invoked once content_safety has already blocked"


async def test_rai_check_runs_after_content_safety_when_first_guard_passes() -> None:
    """Both guards configured + content_safety passes -> rai_check is
    consulted next. If rai blocks, pipeline emits `rai_blocked` and the
    orchestrator is still skipped.
    """
    guard = _FakeContentSafety(ContentSafetyVerdict(flagged=False))
    rai = _FakeRaiScreener(is_safe=False)
    orch = _ScriptedOrchestrator(
        [OrchestratorEvent(channel="answer", content="unreachable")]
    )

    out = await _drain(
        run_chat(
            [ChatMessage(role="user", content="borderline content")],
            orchestrator=orch,
            content_safety=guard,
            rai_check=rai,
        )
    )

    assert orch.calls == 0
    assert guard.calls == ["borderline content"]
    assert rai.calls == ["borderline content"]
    assert len(out) == 1
    assert out[0].metadata["code"] == "rai_blocked"


def test_rai_screener_type_alias_is_exported() -> None:
    """`RaiScreener` is part of the public surface (the router needs it
    as the type of the partial it builds). Catches accidental removal
    from `__all__`.
    """
    assert "RaiScreener" in chat_module.__all__
    assert RaiScreener is chat_module.RaiScreener
