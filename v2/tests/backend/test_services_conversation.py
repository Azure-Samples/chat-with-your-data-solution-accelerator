"""Unit tests for ``backend.services.conversation``.

Pillar: Stable Core
Phase: 7 (router cleanup -- conversation buffered-response helpers)
"""

from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import MagicMock

import pytest

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
)


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


async def test_persist_turn_appends_to_existing_conversation() -> None:
    existing = Conversation(id="conv-1", user_id="user-1", title="Original title")
    fake = _FakeDB(existing=existing)

    conversation_id = await persist_turn(
        cast(BaseDatabaseClient, fake),
        user_id="user-1",
        conversation_id="conv-1",
        question="A follow-up question",
        answer="A follow-up answer.",
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
    )

    assert conversation_id == "conv-new"
    assert fake.created == [("user-1", "New thread question")]
    assert len(fake.added) == 2


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


def test_build_post_prompt_validator_returns_none_when_prompt_missing() -> None:
    overrides = _make_overrides(post_answering_enabled=True)

    assert build_post_prompt_validator(_stub_llm(), overrides) is None


def test_build_post_prompt_validator_returns_none_when_prompt_whitespace() -> None:
    overrides = _make_overrides(
        post_answering_enabled=True,
        post_answering_prompt="   \n\t  ",
    )

    assert build_post_prompt_validator(_stub_llm(), overrides) is None


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
    assert validator._filter_message == DEFAULT_FILTER_MESSAGE


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
    assert validator._filter_message == DEFAULT_FILTER_MESSAGE
