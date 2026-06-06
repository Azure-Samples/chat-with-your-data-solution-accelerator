"""Unit tests for ``backend.services.conversation``.

Pillar: Stable Core
Phase: 7 (router cleanup -- conversation buffered-response helpers)
"""

from collections.abc import AsyncIterator

import pytest

from backend.core.types import Citation, OrchestratorChannel, OrchestratorEvent
from backend.models.conversation import ConversationResponse
from backend.services.conversation import collect_response


async def _gen(events: list[OrchestratorEvent]) -> AsyncIterator[OrchestratorEvent]:
    for event in events:
        yield event


async def test_collect_response_concatenates_answer_chunks() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="Hello, "),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="world!"),
    ]

    result = await collect_response(_gen(events), conversation_id="conv-123")

    assert isinstance(result, ConversationResponse)
    assert result.content == "Hello, world!"
    assert result.citations == []
    assert result.conversation_id == "conv-123"


async def test_collect_response_materializes_unique_citations() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="see "),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-1", "title": "First", "url": "https://example.com/1"},
        ),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-2", "title": "Second", "url": "https://example.com/2"},
        ),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="refs."),
    ]

    result = await collect_response(_gen(events), conversation_id=None)

    assert result.content == "see refs."
    assert len(result.citations) == 2
    assert isinstance(result.citations[0], Citation)
    assert [c.id for c in result.citations] == ["doc-1", "doc-2"]
    assert result.citations[0].title == "First"
    assert result.conversation_id is None


async def test_collect_response_deduplicates_citations_by_id() -> None:
    events = [
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-1", "title": "First"},
        ),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-1", "title": "First (duplicate)"},
        ),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-2", "title": "Second"},
        ),
    ]

    result = await collect_response(_gen(events), conversation_id=None)

    assert [c.id for c in result.citations] == ["doc-1", "doc-2"]
    assert result.citations[0].title == "First"


async def test_collect_response_skips_citation_without_string_id() -> None:
    events = [
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"title": "no-id"},
        ),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": 42, "title": "non-string-id"},
        ),
    ]

    result = await collect_response(_gen(events), conversation_id=None)

    assert result.citations == []


async def test_collect_response_raises_runtime_error_on_error_channel() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="partial..."),
        OrchestratorEvent(channel=OrchestratorChannel.ERROR, content="kaboom"),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="never seen"),
    ]

    with pytest.raises(RuntimeError, match="kaboom"):
        await collect_response(_gen(events), conversation_id="conv-err")


async def test_collect_response_ignores_unknown_channels() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.REASONING, content="thinking..."),
        OrchestratorEvent(channel=OrchestratorChannel.TOOL, content="search(...)"),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="answer"),
    ]

    result = await collect_response(_gen(events), conversation_id=None)

    assert result.content == "answer"
    assert result.citations == []
