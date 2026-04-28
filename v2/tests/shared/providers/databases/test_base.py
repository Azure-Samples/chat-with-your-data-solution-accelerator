"""Tests for the databases domain skeleton (Phase 4 task #27).

Pillar: Stable Core
Phase: 4
"""
from __future__ import annotations

from typing import Sequence
from unittest.mock import MagicMock

import pytest

from shared.providers import databases
from shared.providers.databases.base import BaseDatabaseClient
from shared.settings import AppSettings
from shared.types import ChatMessage, Conversation, MessageRecord


# ---------------------------------------------------------------------------
# Minimal concrete subclass for shape tests. NOT registered (so the public
# registry stays empty until task #27 lands the cosmosdb client and #28
# lands postgres).
# ---------------------------------------------------------------------------


class _StubDatabaseClient(BaseDatabaseClient):
    async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
        return []

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        return None

    async def create_conversation(
        self, user_id: str, title: str
    ) -> Conversation:
        return Conversation(id="c1", user_id=user_id, title=title)

    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
        return Conversation(id=conversation_id, user_id=user_id, title=title)

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        return None

    async def list_messages(
        self, conversation_id: str, user_id: str
    ) -> Sequence[MessageRecord]:
        return []

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        message: ChatMessage,
    ) -> MessageRecord:
        return MessageRecord(
            id="m1",
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
        )

    async def set_feedback(
        self, message_id: str, user_id: str, feedback: str
    ) -> None:
        return None


# ---------------------------------------------------------------------------
# Registry shape (task #27 deliverable -- ABC + registry, no concrete clients
# yet; cosmosdb registers later in task #27, postgres in task #28).
# ---------------------------------------------------------------------------


def test_registry_domain_and_initially_empty() -> None:
    assert databases.registry.domain == "databases"
    # `cosmosdb` self-registers in task #27; `postgres` lands in task #28.
    assert "cosmosdb" in databases.registry.keys()


def test_create_raises_keyerror_for_unknown_client() -> None:
    with pytest.raises(KeyError) as excinfo:
        databases.create("does_not_exist")
    msg = str(excinfo.value)
    assert "does_not_exist" in msg
    assert "databases" in msg


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------


def test_base_database_client_cannot_be_instantiated() -> None:
    """`BaseDatabaseClient` is abstract -- direct instantiation must fail."""
    with pytest.raises(TypeError):
        BaseDatabaseClient(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


def test_subclass_must_implement_all_abstract_methods() -> None:
    """A subclass that omits any chat-history method must remain abstract."""

    class _Partial(BaseDatabaseClient):
        # Implements only one of the eight abstract methods on purpose.
        async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
            return []

    with pytest.raises(TypeError):
        _Partial(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


# ---------------------------------------------------------------------------
# Stub round-trip (proves the contract types match)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_subclass_round_trips_chat_message() -> None:
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    record = await client.add_message(
        conversation_id="c1",
        user_id="u1",
        message=ChatMessage(role="user", content="hello"),
    )
    assert record.conversation_id == "c1"
    assert record.role == "user"
    assert record.content == "hello"


@pytest.mark.asyncio
async def test_stub_aclose_is_noop_by_default() -> None:
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    assert await client.aclose() is None
