"""Tests for the databases domain skeleton."""

from typing import Sequence
from unittest.mock import MagicMock

import pytest

from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.settings import AppSettings
from backend.core.types import (
    AdminAuditEntry,
    ChatMessage,
    Conversation,
    MessageRecord,
    RuntimeConfig,
)

# ---------------------------------------------------------------------------
# Minimal concrete subclass for shape tests. NOT registered (so the public
# registry stays empty until the concrete clients register themselves).
# ---------------------------------------------------------------------------


class _StubDatabaseClient(BaseDatabaseClient):
    async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
        return []

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        return None

    async def create_conversation(self, user_id: str, title: str) -> Conversation:
        return Conversation(id="c1", user_id=user_id, title=title)

    async def rename_conversation(
        self, conversation_id: str, user_id: str, title: str
    ) -> Conversation:
        return Conversation(id=conversation_id, user_id=user_id, title=title)

    async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
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

    async def set_feedback(self, message_id: str, user_id: str, feedback: str) -> None:
        return None

    async def get_agent_id(self, name: str) -> str | None:
        return None

    async def upsert_agent_id(self, name: str, agent_id: str) -> None:
        return None

    async def get_runtime_config(self) -> RuntimeConfig | None:
        return None

    async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
        return None

    async def write_admin_audit(self, entry: AdminAuditEntry) -> None:
        return None


# ---------------------------------------------------------------------------
# Registry shape: ABC + registry; concrete clients (cosmosdb, postgres)
# self-register on import.
# ---------------------------------------------------------------------------


def test_registry_domain_and_initially_empty() -> None:
    assert databases_registry.registry.domain == "databases"
    # `cosmosdb` and `postgres` self-register on import.
    assert "cosmosdb" in databases_registry.registry.keys()


def test_create_raises_keyerror_for_unknown_client() -> None:
    with pytest.raises(KeyError) as excinfo:
        databases_registry.registry.get("does_not_exist")
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
        # Implements only one of the abstract methods on purpose.
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


# ---------------------------------------------------------------------------
# Agent registry contract (get_agent_id)
# ---------------------------------------------------------------------------


def test_subclass_missing_get_agent_id_remains_abstract() -> None:
    """`get_agent_id` is part of the ABC contract. A subclass
    that implements every chat-history method but omits the agent
    registry method must still fail to instantiate, otherwise the
    lazy resolver could call into a NotImplementedError at
    runtime.
    """

    class _MissingAgentRegistry(BaseDatabaseClient):
        # Re-implements every chat-history method from `_StubDatabaseClient`
        # but deliberately omits `get_agent_id`.
        async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
            return []

        async def get_conversation(
            self, conversation_id: str, user_id: str
        ) -> Conversation | None:
            return None

        async def create_conversation(self, user_id: str, title: str) -> Conversation:
            return Conversation(id="c1", user_id=user_id, title=title)

        async def rename_conversation(
            self, conversation_id: str, user_id: str, title: str
        ) -> Conversation:
            return Conversation(id=conversation_id, user_id=user_id, title=title)

        async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
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

    with pytest.raises(TypeError):
        _MissingAgentRegistry(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


@pytest.mark.asyncio
async def test_stub_get_agent_id_returns_none_for_missing_name() -> None:
    """The default stub returns None -- this validates the contract
    return type (`str | None`) rather than the storage semantics
    (covered per backend in test_cosmosdb / test_postgres)."""
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    assert await client.get_agent_id("cwyd") is None


# ---------------------------------------------------------------------------
# Agent registry contract (upsert_agent_id)
# ---------------------------------------------------------------------------


def test_subclass_missing_upsert_agent_id_remains_abstract() -> None:
    """`upsert_agent_id` is part of the ABC contract. A
    subclass that implements `get_agent_id` (and every chat-history
    method) but omits the writer must still fail to instantiate --
    otherwise the lazy resolver could read a stale id,
    fail to persist a fresh one, and silently re-create on every
    request."""

    class _MissingUpsert(BaseDatabaseClient):
        async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
            return []

        async def get_conversation(
            self, conversation_id: str, user_id: str
        ) -> Conversation | None:
            return None

        async def create_conversation(self, user_id: str, title: str) -> Conversation:
            return Conversation(id="c1", user_id=user_id, title=title)

        async def rename_conversation(
            self, conversation_id: str, user_id: str, title: str
        ) -> Conversation:
            return Conversation(id=conversation_id, user_id=user_id, title=title)

        async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
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

        async def get_agent_id(self, name: str) -> str | None:
            return None

    with pytest.raises(TypeError):
        _MissingUpsert(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


@pytest.mark.asyncio
async def test_stub_upsert_agent_id_returns_none_and_does_not_raise() -> None:
    """The default stub is a no-op -- this validates the contract
    return type (`None`) rather than the storage semantics (covered
    per backend in test_cosmosdb / test_postgres)."""
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    assert await client.upsert_agent_id("cwyd", "asst_abc123") is None


# ---------------------------------------------------------------------------
# Runtime config contract (get_runtime_config)
# ---------------------------------------------------------------------------


def test_subclass_missing_get_runtime_config_remains_abstract() -> None:
    """`get_runtime_config` is part of the ABC contract. A
    subclass that implements every prior method (chat-history +
    agent registry) but omits the runtime-config reader must still
    fail to instantiate -- otherwise the PATCH route would
    end up calling NotImplementedError at request time and the admin
    UI would surface a 500 instead of a clean 'not configured' state.
    """

    class _MissingGetRuntimeConfig(BaseDatabaseClient):
        async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
            return []

        async def get_conversation(
            self, conversation_id: str, user_id: str
        ) -> Conversation | None:
            return None

        async def create_conversation(self, user_id: str, title: str) -> Conversation:
            return Conversation(id="c1", user_id=user_id, title=title)

        async def rename_conversation(
            self, conversation_id: str, user_id: str, title: str
        ) -> Conversation:
            return Conversation(id=conversation_id, user_id=user_id, title=title)

        async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
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

        async def get_agent_id(self, name: str) -> str | None:
            return None

        async def upsert_agent_id(self, name: str, agent_id: str) -> None:
            return None

        async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
            return None

    with pytest.raises(TypeError):
        _MissingGetRuntimeConfig(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


@pytest.mark.asyncio
async def test_stub_get_runtime_config_returns_none_for_cold_start() -> None:
    """The default stub returns None -- this validates the contract
    return type (`RuntimeConfig | None`) rather than the storage
    semantics (covered per backend in test_cosmosdb /
    test_postgres). `None` means 'no override row persisted yet'
    (cold start); the admin router falls through to env defaults."""
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    assert await client.get_runtime_config() is None


# ---------------------------------------------------------------------------
# Runtime config contract (upsert_runtime_config)
# ---------------------------------------------------------------------------


def test_subclass_missing_upsert_runtime_config_remains_abstract() -> None:
    """`upsert_runtime_config` is part of the ABC contract.
    A subclass that implements `get_runtime_config` (and every prior
    method) but omits the writer must still fail to instantiate --
    otherwise the PATCH route could read a stale config,
    fail to persist the merged update, and silently drop every
    operator override."""

    class _MissingUpsertRuntimeConfig(BaseDatabaseClient):
        async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
            return []

        async def get_conversation(
            self, conversation_id: str, user_id: str
        ) -> Conversation | None:
            return None

        async def create_conversation(self, user_id: str, title: str) -> Conversation:
            return Conversation(id="c1", user_id=user_id, title=title)

        async def rename_conversation(
            self, conversation_id: str, user_id: str, title: str
        ) -> Conversation:
            return Conversation(id=conversation_id, user_id=user_id, title=title)

        async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
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

        async def get_agent_id(self, name: str) -> str | None:
            return None

        async def upsert_agent_id(self, name: str, agent_id: str) -> None:
            return None

        async def get_runtime_config(self) -> RuntimeConfig | None:
            return None

    with pytest.raises(TypeError):
        _MissingUpsertRuntimeConfig(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


@pytest.mark.asyncio
async def test_stub_upsert_runtime_config_returns_none_and_does_not_raise() -> None:
    """The default stub is a no-op -- this validates the contract
    return type (`None`) rather than the storage semantics (covered
    per backend in test_cosmosdb / test_postgres)."""
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    assert await client.upsert_runtime_config(RuntimeConfig()) is None


# ---------------------------------------------------------------------------
# Admin audit contract (write_admin_audit)
# ---------------------------------------------------------------------------


def test_subclass_missing_write_admin_audit_remains_abstract() -> None:
    """`write_admin_audit` is part of the ABC contract. A
    subclass that implements every prior method but omits the audit
    writer must still fail to instantiate -- otherwise the PATCH
    route could silently drop the audit row, defeating
    the "who flipped temperature to 0.7?" forensic question that
    motivated the audit log."""

    class _MissingWriteAdminAudit(BaseDatabaseClient):
        async def list_conversations(self, user_id: str) -> Sequence[Conversation]:
            return []

        async def get_conversation(
            self, conversation_id: str, user_id: str
        ) -> Conversation | None:
            return None

        async def create_conversation(self, user_id: str, title: str) -> Conversation:
            return Conversation(id="c1", user_id=user_id, title=title)

        async def rename_conversation(
            self, conversation_id: str, user_id: str, title: str
        ) -> Conversation:
            return Conversation(id=conversation_id, user_id=user_id, title=title)

        async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
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

        async def get_agent_id(self, name: str) -> str | None:
            return None

        async def upsert_agent_id(self, name: str, agent_id: str) -> None:
            return None

        async def get_runtime_config(self) -> RuntimeConfig | None:
            return None

        async def upsert_runtime_config(self, config: RuntimeConfig) -> None:
            return None

    with pytest.raises(TypeError):
        _MissingWriteAdminAudit(  # type: ignore[abstract]
            settings=MagicMock(spec=AppSettings),
            credential=MagicMock(),
        )


@pytest.mark.asyncio
async def test_stub_write_admin_audit_returns_none_and_does_not_raise() -> None:
    """The default stub is a no-op -- this validates the contract
    return type (`None`) rather than the storage semantics
    (covered per backend in test_cosmosdb / test_postgres). The
    router fires-and-forgets the audit row; the storage layer
    assigns id + created_at on persist (mirrors `add_message`).
    """
    client = _StubDatabaseClient(
        settings=MagicMock(spec=AppSettings),
        credential=MagicMock(),
    )
    entry = AdminAuditEntry(
        actor="u-admin",
        action="patch_config",
        before=None,
        after=RuntimeConfig(openai_temperature=0.7),
    )
    assert await client.write_admin_audit(entry) is None
