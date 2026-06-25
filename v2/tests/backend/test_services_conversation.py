"""Unit tests for ``backend.services.conversation``.

Pillar: Stable Core
Phase: 7 (router cleanup -- conversation buffered-response helpers)
"""

from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import Request

from backend.core.agents.presets import (
    DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    DEFAULT_POST_ANSWERING_PROMPT,
)
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.tools.post_prompt import DEFAULT_FILTER_MESSAGE, PostPromptValidator
from backend.core.types import (
    ChatMessage,
    ChatRole,
    Citation,
    Conversation,
    MessageRecord,
    OrchestratorChannel,
    OrchestratorEvent,
    RuntimeConfig,
)
from backend.models.conversation import ConversationResponse
from backend.services.conversation import (
    build_post_prompt_validator,
    collect_response,
    persist_turn,
    persisting_sse_stream,
)
from backend.services.sse import format_sse


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


class _FakeDB:
    """Minimal recorder standing in for ``BaseDatabaseClient``.

    Implements only the three methods ``persist_turn`` touches and
    records every call so tests can assert the create / append sequence
    without a live Cosmos DB or PostgreSQL backend.
    """

    def __init__(self, *, existing: Conversation | None = None) -> None:
        self._existing = existing
        self.created: list[tuple[str, str]] = []
        self.added: list[tuple[str, str, ChatMessage]] = []

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        existing = self._existing
        if (
            existing is not None
            and existing.id == conversation_id
            and existing.user_id == user_id
        ):
            return existing
        return None

    async def create_conversation(self, user_id: str, title: str) -> Conversation:
        self.created.append((user_id, title))
        return Conversation(id="conv-new", user_id=user_id, title=title)

    async def add_message(
        self, conversation_id: str, user_id: str, message: ChatMessage
    ) -> MessageRecord:
        self.added.append((conversation_id, user_id, message))
        return MessageRecord(
            id=f"msg-{len(self.added)}",
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
        )


async def test_persist_turn_creates_conversation_titled_with_question() -> None:
    fake = _FakeDB()

    conversation_id = await persist_turn(
        cast(BaseDatabaseClient, fake),
        user_id="user-1",
        conversation_id=None,
        question="What is CWYD?",
        answer="A chat-with-your-data accelerator.",
        citations=[],
    )

    assert conversation_id == "conv-new"
    assert fake.created == [("user-1", "What is CWYD?")]
    assert len(fake.added) == 2
    first_conv, first_user, first_msg = fake.added[0]
    second_conv, second_user, second_msg = fake.added[1]
    assert (first_conv, first_user) == ("conv-new", "user-1")
    assert (second_conv, second_user) == ("conv-new", "user-1")
    assert first_msg.role is ChatRole.USER
    assert first_msg.content == "What is CWYD?"
    assert second_msg.role is ChatRole.ASSISTANT
    assert second_msg.content == "A chat-with-your-data accelerator."
    # No citations on this turn -- both messages carry empty metadata.
    assert first_msg.metadata == {}
    assert second_msg.metadata == {}


async def test_persist_turn_appends_to_existing_conversation() -> None:
    existing = Conversation(id="conv-1", user_id="user-1", title="Original title")
    fake = _FakeDB(existing=existing)

    conversation_id = await persist_turn(
        cast(BaseDatabaseClient, fake),
        user_id="user-1",
        conversation_id="conv-1",
        question="A follow-up question",
        answer="A follow-up answer.",
        citations=[],
    )

    assert conversation_id == "conv-1"
    assert fake.created == []
    assert [conv for conv, _user, _msg in fake.added] == ["conv-1", "conv-1"]
    assert [msg.role for _conv, _user, msg in fake.added] == [
        ChatRole.USER,
        ChatRole.ASSISTANT,
    ]


async def test_persist_turn_creates_new_when_conversation_id_unresolved() -> None:
    fake = _FakeDB(existing=None)

    conversation_id = await persist_turn(
        cast(BaseDatabaseClient, fake),
        user_id="user-1",
        conversation_id="stale-or-forged",
        question="New thread question",
        answer="New thread answer.",
        citations=[],
    )

    assert conversation_id == "conv-new"
    assert fake.created == [("user-1", "New thread question")]
    assert len(fake.added) == 2


async def test_persist_turn_stores_citations_in_assistant_metadata() -> None:
    fake = _FakeDB()
    citations = [
        Citation(id="doc-1", title="Benefit_Options.pdf", url="https://example/1"),
        Citation(id="doc-2", title="Northwind.pdf"),
    ]

    await persist_turn(
        cast(BaseDatabaseClient, fake),
        user_id="user-1",
        conversation_id=None,
        question="What is covered?",
        answer="Your plan covers ...",
        citations=citations,
    )

    _user_conv, _user_user, user_msg = fake.added[0]
    _asst_conv, _asst_user, assistant_msg = fake.added[1]
    # The user message carries no metadata; the assistant message carries
    # the grounding citations serialized under the "citations" key.
    assert user_msg.metadata == {}
    assert assistant_msg.role is ChatRole.ASSISTANT
    stored = assistant_msg.metadata["citations"]
    assert [c["id"] for c in stored] == ["doc-1", "doc-2"]
    assert stored[0]["title"] == "Benefit_Options.pdf"
    assert stored[0]["url"] == "https://example/1"


async def test_collect_response_ignores_unknown_channels() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.REASONING, content="thinking..."),
        OrchestratorEvent(channel=OrchestratorChannel.TOOL, content="search(...)"),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="answer"),
    ]

    result = await collect_response(_gen(events), conversation_id=None)

    assert result.content == "answer"
    assert result.citations == []


# ---------------------------------------------------------------------------
# build_post_prompt_validator -- runtime-overrides -> PostPromptValidator | None
# ---------------------------------------------------------------------------


def _stub_llm() -> BaseLLMProvider:
    """A ``BaseLLMProvider``-shaped MagicMock.

    ``build_post_prompt_validator`` only forwards the instance into
    the ``PostPromptValidator`` constructor; ``.validate()`` is never
    invoked here, so a spec'd MagicMock satisfies the type without
    pulling in real Azure SDK dependencies.
    """
    return cast(BaseLLMProvider, MagicMock(spec=BaseLLMProvider))


def _make_overrides(**kwargs: object) -> RuntimeConfig:
    return RuntimeConfig.model_validate(kwargs)


def test_build_post_prompt_validator_returns_none_when_overrides_missing() -> None:
    assert build_post_prompt_validator(_stub_llm(), None) is None


def test_build_post_prompt_validator_returns_none_when_enabled_is_none() -> None:
    overrides = _make_overrides(post_answering_prompt="Validate {answer}.")

    assert build_post_prompt_validator(_stub_llm(), overrides) is None


def test_build_post_prompt_validator_returns_none_when_enabled_is_false() -> None:
    overrides = _make_overrides(
        post_answering_enabled=False,
        post_answering_prompt="Validate {answer}.",
    )

    assert build_post_prompt_validator(_stub_llm(), overrides) is None


def test_build_post_prompt_validator_uses_default_prompt_when_override_missing() -> None:
    # Enabling without an override prompt now uses the populated JSON
    # default (ADR 0030) so enabling the feature actually validates.
    llm = _stub_llm()
    overrides = _make_overrides(post_answering_enabled=True)

    validator = build_post_prompt_validator(llm, overrides)

    assert isinstance(validator, PostPromptValidator)
    assert validator._validation_prompt == DEFAULT_POST_ANSWERING_PROMPT
    assert validator._filter_message == DEFAULT_POST_ANSWERING_FILTER_MESSAGE


def test_build_post_prompt_validator_uses_default_prompt_when_override_whitespace() -> None:
    overrides = _make_overrides(
        post_answering_enabled=True,
        post_answering_prompt="   \n\t  ",
    )

    validator = build_post_prompt_validator(_stub_llm(), overrides)

    assert isinstance(validator, PostPromptValidator)
    assert validator._validation_prompt == DEFAULT_POST_ANSWERING_PROMPT


def test_build_post_prompt_validator_uses_default_filter_when_override_blank() -> None:
    llm = _stub_llm()
    overrides = _make_overrides(
        post_answering_enabled=True,
        post_answering_prompt="Check: {question} / {answer} / {sources}",
    )

    validator = build_post_prompt_validator(llm, overrides)

    assert isinstance(validator, PostPromptValidator)
    assert validator._llm is llm
    assert validator._validation_prompt == "Check: {question} / {answer} / {sources}"
    assert validator._filter_message == DEFAULT_POST_ANSWERING_FILTER_MESSAGE


def test_build_post_prompt_validator_honors_custom_filter_message() -> None:
    llm = _stub_llm()
    overrides = _make_overrides(
        post_answering_enabled=True,
        post_answering_prompt="Check: {answer}",
        post_answering_filter_message="Refusing per policy.",
    )

    validator = build_post_prompt_validator(llm, overrides)

    assert isinstance(validator, PostPromptValidator)
    assert validator._filter_message == "Refusing per policy."


def test_build_post_prompt_validator_treats_empty_filter_as_default() -> None:
    llm = _stub_llm()
    overrides = _make_overrides(
        post_answering_enabled=True,
        post_answering_prompt="Check: {answer}",
        post_answering_filter_message="",
    )

    validator = build_post_prompt_validator(llm, overrides)

    assert isinstance(validator, PostPromptValidator)
    assert validator._filter_message == DEFAULT_POST_ANSWERING_FILTER_MESSAGE


# ---------------------------------------------------------------------------
# persisting_sse_stream -- streaming persist wrapper + terminal control frame
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal ``Request`` stand-in exposing only ``is_disconnected``."""

    def __init__(self, *, disconnected: bool = False) -> None:
        self._disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self._disconnected


class _FailingDB:
    """``BaseDatabaseClient`` stand-in whose writes always raise.

    Models a storage outage so the wrapper's persist-failure handling
    can be asserted without a live backend.
    """

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        return None

    async def create_conversation(self, user_id: str, title: str) -> Conversation:
        raise RuntimeError("storage unavailable")

    async def add_message(
        self, conversation_id: str, user_id: str, message: ChatMessage
    ) -> MessageRecord:
        raise RuntimeError("storage unavailable")


async def _drain(stream: AsyncIterator[bytes]) -> list[bytes]:
    return [frame async for frame in stream]


async def test_persisting_sse_stream_persists_and_emits_conversation_frame() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="Hello, "),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="world!"),
    ]
    fake = _FakeDB()

    frames = await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest()),
            db=cast(BaseDatabaseClient, fake),
            user_id="user-1",
            conversation_id=None,
            question="Say hi?",
        )
    )

    # Every orchestrator event is framed, then a terminal conversation frame.
    assert frames[:2] == [format_sse(events[0]), format_sse(events[1])]
    assert frames[-1] == b'event: conversation\ndata: {"conversation_id": "conv-new"}\n\n'
    # The turn is persisted: new conversation titled with the question,
    # then user-then-assistant messages carrying the full answer.
    assert fake.created == [("user-1", "Say hi?")]
    assert [msg.role for _conv, _user, msg in fake.added] == [
        ChatRole.USER,
        ChatRole.ASSISTANT,
    ]
    assert fake.added[0][2].content == "Say hi?"
    assert fake.added[1][2].content == "Hello, world!"


async def test_persisting_sse_stream_persists_citations_in_assistant_metadata() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="Grounded "),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-1", "title": "First", "url": "https://example/1"},
        ),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-1", "title": "First (dup)"},
        ),
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="answer."),
    ]
    fake = _FakeDB()

    await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest()),
            db=cast(BaseDatabaseClient, fake),
            user_id="user-1",
            conversation_id=None,
            question="Grounded?",
        )
    )

    _conv, _user, assistant_msg = fake.added[1]
    stored = assistant_msg.metadata["citations"]
    # Deduplicated by id -- the second doc-1 citation is dropped.
    assert [c["id"] for c in stored] == ["doc-1"]
    assert stored[0]["title"] == "First"


async def test_persisting_sse_stream_appends_to_existing_conversation() -> None:
    existing = Conversation(id="conv-1", user_id="user-1", title="Original title")
    fake = _FakeDB(existing=existing)
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="A reply."),
    ]

    frames = await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest()),
            db=cast(BaseDatabaseClient, fake),
            user_id="user-1",
            conversation_id="conv-1",
            question="A follow-up?",
        )
    )

    assert fake.created == []
    assert [conv for conv, _user, _msg in fake.added] == ["conv-1", "conv-1"]
    assert frames[-1] == b'event: conversation\ndata: {"conversation_id": "conv-1"}\n\n'


async def test_persisting_sse_stream_skips_persist_when_error_event_seen() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="partial"),
        OrchestratorEvent(
            channel=OrchestratorChannel.ERROR,
            content="blocked",
            metadata={"code": "rai_blocked"},
        ),
    ]
    fake = _FakeDB()

    frames = await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest()),
            db=cast(BaseDatabaseClient, fake),
            user_id="user-1",
            conversation_id=None,
            question="Something blocked?",
        )
    )

    # Both event frames are delivered, but nothing is persisted and no
    # conversation control frame is emitted.
    assert frames == [format_sse(events[0]), format_sse(events[1])]
    assert fake.created == []
    assert fake.added == []
    assert all(not frame.startswith(b"event: conversation") for frame in frames)


async def test_persisting_sse_stream_skips_persist_on_disconnect() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="never read"),
    ]
    fake = _FakeDB()

    frames = await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest(disconnected=True)),
            db=cast(BaseDatabaseClient, fake),
            user_id="user-1",
            conversation_id=None,
            question="Walked away?",
        )
    )

    assert frames == []
    assert fake.created == []
    assert fake.added == []


async def test_persisting_sse_stream_skips_persist_when_answer_empty() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.REASONING, content="thinking..."),
        OrchestratorEvent(
            channel=OrchestratorChannel.CITATION,
            metadata={"id": "doc-1", "title": "Only a citation"},
        ),
    ]
    fake = _FakeDB()

    frames = await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest()),
            db=cast(BaseDatabaseClient, fake),
            user_id="user-1",
            conversation_id=None,
            question="No answer text?",
        )
    )

    assert fake.created == []
    assert fake.added == []
    assert all(not frame.startswith(b"event: conversation") for frame in frames)


async def test_persisting_sse_stream_swallows_persist_failure() -> None:
    events = [
        OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content="delivered"),
    ]
    failing = _FailingDB()

    frames = await _drain(
        persisting_sse_stream(
            _gen(events),
            cast(Request, _FakeRequest()),
            db=cast(BaseDatabaseClient, failing),
            user_id="user-1",
            conversation_id=None,
            question="Storage down?",
        )
    )

    # The answer frame is delivered; the persistence failure is swallowed
    # so no conversation control frame follows and nothing propagates.
    assert frames == [format_sse(events[0])]
    assert all(not frame.startswith(b"event: conversation") for frame in frames)
