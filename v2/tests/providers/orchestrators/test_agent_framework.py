"""Tests for the Agent Framework orchestrator (Phase 3 task #19).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from providers import orchestrators
from providers.llm.base import BaseLLMProvider
from providers.orchestrators.agent_framework import AgentFrameworkOrchestrator
from shared.settings import AppSettings
from shared.types import ChatMessage


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _text_block(value: str) -> SimpleNamespace:
    return SimpleNamespace(text=SimpleNamespace(value=value))


def _thread_msg(role: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(role=role, content=[_text_block(text)])


class _FakeAsyncIter:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> "_FakeAsyncIter":
        return self

    async def __anext__(self) -> Any:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _make_agents_client(
    *,
    list_messages: list[Any] | None = None,
    run_status: str = "completed",
    run_last_error: str = "",
    run_id: str = "run-1",
) -> MagicMock:
    client = MagicMock()
    thread = SimpleNamespace(id="thread-1")
    client.threads.create = AsyncMock(return_value=thread)
    client.messages.create = AsyncMock(return_value=None)
    client.runs.create_and_process = AsyncMock(
        return_value=SimpleNamespace(
            id=run_id, status=run_status, last_error=run_last_error
        )
    )
    client.messages.list = MagicMock(
        return_value=_FakeAsyncIter(list_messages or [])
    )
    return client


def _make_orchestrator(
    *, agents_client: Any = None, agent_id: str = "asst_xyz"
) -> AgentFrameworkOrchestrator:
    return AgentFrameworkOrchestrator(
        settings=MagicMock(spec=AppSettings),
        llm=MagicMock(spec=BaseLLMProvider),
        agents_client=agents_client or _make_agents_client(),
        agent_id=agent_id,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_agent_framework_is_registered() -> None:
    assert "agent_framework" in orchestrators.registry.keys()
    assert (
        orchestrators.registry.get("agent_framework") is AgentFrameworkOrchestrator
    )


def test_create_returns_agent_framework_instance() -> None:
    orch = orchestrators.create(
        "agent_framework",
        settings=MagicMock(spec=AppSettings),
        llm=MagicMock(spec=BaseLLMProvider),
        agents_client=_make_agents_client(),
        agent_id="asst_xyz",
    )
    assert isinstance(orch, AgentFrameworkOrchestrator)


def test_constructor_rejects_empty_agent_id() -> None:
    with pytest.raises(ValueError, match="agent_id"):
        AgentFrameworkOrchestrator(
            settings=MagicMock(spec=AppSettings),
            llm=MagicMock(spec=BaseLLMProvider),
            agents_client=_make_agents_client(),
            agent_id="",
        )


# ---------------------------------------------------------------------------
# run() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_creates_thread_posts_messages_and_processes_run() -> None:
    client = _make_agents_client(
        list_messages=[
            _thread_msg("user", "ping"),
            _thread_msg("assistant", "pong"),
        ]
    )
    orch = _make_orchestrator(agents_client=client)
    events = [
        e
        async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    client.threads.create.assert_awaited_once()
    client.messages.create.assert_awaited_once()
    create_kwargs = client.messages.create.await_args.kwargs
    assert create_kwargs["thread_id"] == "thread-1"
    assert create_kwargs["content"] == "ping"
    client.runs.create_and_process.assert_awaited_once_with(
        thread_id="thread-1", agent_id="asst_xyz"
    )
    # Defensive: messages.list must be scoped to this run's id.
    list_kwargs = client.messages.list.call_args.kwargs
    assert list_kwargs["thread_id"] == "thread-1"
    assert list_kwargs["run_id"] == "run-1"
    assert len(events) == 1
    assert events[0].channel == "answer"
    assert events[0].content == "pong"


@pytest.mark.asyncio
async def test_run_skips_system_and_tool_messages() -> None:
    """`system` belongs in agent instructions; `tool` lands in task #20."""
    client = _make_agents_client(
        list_messages=[_thread_msg("assistant", "ok")]
    )
    orch = _make_orchestrator(agents_client=client)
    _ = [
        e
        async for e in orch.run(
            [
                ChatMessage(role="system", content="you are helpful"),
                ChatMessage(role="user", content="hi"),
                ChatMessage(role="tool", content="{\"result\": 42}"),
            ]
        )
    ]
    # Only the user message should have been posted to the thread.
    assert client.messages.create.await_count == 1
    posted = client.messages.create.await_args.kwargs
    assert posted["content"] == "hi"


@pytest.mark.asyncio
async def test_run_yields_one_answer_event_per_assistant_message() -> None:
    client = _make_agents_client(
        list_messages=[
            _thread_msg("user", "ping"),
            _thread_msg("assistant", "first"),
            _thread_msg("assistant", "second"),
        ]
    )
    orch = _make_orchestrator(agents_client=client)
    events = [
        e
        async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    assert [e.content for e in events] == ["first", "second"]
    assert all(e.channel == "answer" for e in events)


@pytest.mark.asyncio
async def test_run_emits_error_event_when_run_status_failed() -> None:
    client = _make_agents_client(
        run_status="failed", run_last_error="quota exceeded"
    )
    orch = _make_orchestrator(agents_client=client)
    events = [
        e
        async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    assert len(events) == 1
    assert events[0].channel == "error"
    assert "quota exceeded" in events[0].content


@pytest.mark.asyncio
async def test_run_emits_error_event_when_no_assistant_message_returned() -> None:
    client = _make_agents_client(
        list_messages=[_thread_msg("user", "ping")]
    )
    orch = _make_orchestrator(agents_client=client)
    events = [
        e
        async for e in orch.run([ChatMessage(role="user", content="ping")])
    ]
    assert len(events) == 1
    assert events[0].channel == "error"
    assert "no assistant reply" in events[0].content.lower()


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_client() -> None:
    client = _make_agents_client()
    client.close = AsyncMock()
    orch = _make_orchestrator(agents_client=client)
    await orch.aclose()
    client.close.assert_not_called()
