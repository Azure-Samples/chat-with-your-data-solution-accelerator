"""Tests for ``backend.services.sse``."""

import json
from collections.abc import AsyncIterator

from backend.core.types import OrchestratorChannel, OrchestratorEvent
from backend.services.sse import SSE_MEDIA_TYPE, format_sse, sse_stream, wants_sse


def test_sse_media_type_is_event_stream() -> None:
    assert SSE_MEDIA_TYPE == "text/event-stream"


def test_sse_media_type_is_a_str() -> None:
    assert isinstance(SSE_MEDIA_TYPE, str)


def test_format_sse_returns_utf8_bytes_with_event_and_data_lines() -> None:
    frame = format_sse(
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="hi")
    )
    assert isinstance(frame, bytes)
    text = frame.decode("utf-8")
    assert text.startswith(f"event: {OrchestratorChannel.ANSWER}\n")
    assert text.endswith("\n\n")
    assert "data: " in text


def test_format_sse_payload_roundtrips_through_json() -> None:
    event = OrchestratorEvent(
        channel=OrchestratorChannel.CITATION,
        content="see source",
        metadata={"id": "c-1", "title": "doc"},
    )
    frame = format_sse(event).decode("utf-8")
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload == {
        "content": "see source",
        "metadata": {"id": "c-1", "title": "doc"},
    }


def test_format_sse_preserves_non_ascii_content() -> None:
    frame = format_sse(
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="caf\u00e9")
    )
    text = frame.decode("utf-8")
    assert "caf\u00e9" in text


def test_wants_sse_returns_false_for_none() -> None:
    assert wants_sse(None) is False


def test_wants_sse_returns_false_for_empty_string() -> None:
    assert wants_sse("") is False


def test_wants_sse_returns_true_for_exact_media_type() -> None:
    assert wants_sse("text/event-stream") is True


def test_wants_sse_matches_case_insensitively() -> None:
    assert wants_sse("TEXT/EVENT-STREAM") is True


def test_wants_sse_matches_inside_multi_value_accept_header() -> None:
    assert wants_sse("text/event-stream, application/json;q=0.9") is True


def test_wants_sse_returns_false_for_unrelated_media_type() -> None:
    assert wants_sse("application/json") is False


class _AlwaysConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


class _DisconnectAfterFirstRequest:
    def __init__(self) -> None:
        self._calls = 0

    async def is_disconnected(self) -> bool:
        self._calls += 1
        return self._calls > 1


async def test_sse_stream_yields_one_frame_per_event() -> None:
    async def events() -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="one")
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="two")

    frames = [
        frame
        async for frame in sse_stream(events(), _AlwaysConnectedRequest())  # type: ignore[arg-type]
    ]
    assert len(frames) == 2
    assert frames[0].startswith(f"event: {OrchestratorChannel.ANSWER}\n".encode())
    assert b'"content": "one"' in frames[0]
    assert b'"content": "two"' in frames[1]


async def test_sse_stream_aborts_when_client_disconnects() -> None:
    async def events() -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="first")
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="second")
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="third")

    frames = [
        frame
        async for frame in sse_stream(events(), _DisconnectAfterFirstRequest())  # type: ignore[arg-type]
    ]
    assert len(frames) == 1
    assert b'"content": "first"' in frames[0]


async def test_sse_stream_emits_error_frame_when_source_raises() -> None:
    async def events() -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="partial")
        raise RuntimeError("kaboom")

    frames = [
        frame
        async for frame in sse_stream(events(), _AlwaysConnectedRequest())  # type: ignore[arg-type]
    ]
    assert len(frames) == 2
    assert b'"content": "partial"' in frames[0]
    assert frames[1].startswith(f"event: {OrchestratorChannel.ERROR}\n".encode())
    assert b'"content": "kaboom"' in frames[1]
