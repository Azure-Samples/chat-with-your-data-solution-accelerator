"""Tests for the Agent Framework orchestrator (Phase 3 task #19).

Pillar: Stable Core
Phase: 3
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.providers import orchestrators
from shared.providers.llm.base import BaseLLMProvider
from shared.providers.orchestrators.agent_framework import AgentFrameworkOrchestrator
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
    run_steps: list[Any] | None = None,
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
    # CU-004c: every successful run walks `run_steps.list(...)` to
    # surface tool / reasoning visibility. Default to an empty iterator
    # so existing tests (written before CU-004c) stay green.
    client.run_steps.list = MagicMock(
        return_value=_FakeAsyncIter(run_steps or [])
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


# ---------------------------------------------------------------------------
# CU-004c: run_steps -> reasoning + tool events
# ---------------------------------------------------------------------------


def _function_tool_call(
    *, call_id: str, name: str, arguments: str
) -> SimpleNamespace:
    """Build a `RunStepFunctionToolCall`-shaped SimpleNamespace."""
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _tool_calls_step(*, calls: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(
        step_details=SimpleNamespace(type="tool_calls", tool_calls=calls)
    )


def _message_creation_step(*, message_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        step_details=SimpleNamespace(
            type="message_creation",
            message_creation=SimpleNamespace(message_id=message_id),
        )
    )


def _reasoning_step(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        step_details=SimpleNamespace(
            type="message_creation", reasoning_content=text
        )
    )


@pytest.mark.asyncio
async def test_run_emits_tool_events_for_tool_calls_steps() -> None:
    """Each tool call in a `tool_calls` step yields one `tool` event."""
    client = _make_agents_client(
        list_messages=[_thread_msg("assistant", "done")],
        run_steps=[
            _tool_calls_step(
                calls=[
                    _function_tool_call(
                        call_id="call_1",
                        name="search_documents",
                        arguments='{"q":"foundry"}',
                    ),
                    _function_tool_call(
                        call_id="call_2",
                        name="fetch_url",
                        arguments='{"url":"https://x"}',
                    ),
                ]
            ),
        ],
    )
    orch = _make_orchestrator(agents_client=client)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="hi")])
    ]

    channels = [(e.channel, e.content) for e in events]
    assert channels == [
        ("tool", "function"),
        ("tool", "function"),
        ("answer", "done"),
    ]
    # Metadata carries id + arguments for the FE to render.
    assert events[0].metadata == {
        "id": "call_1",
        "type": "function",
        "arguments": '{"q":"foundry"}',
    }
    assert events[1].metadata["id"] == "call_2"
    # The run_steps walk was scoped to the current run id.
    list_kwargs = client.run_steps.list.call_args.kwargs
    assert list_kwargs["thread_id"] == "thread-1"
    assert list_kwargs["run_id"] == "run-1"


@pytest.mark.asyncio
async def test_run_skips_message_creation_steps() -> None:
    """`message_creation` steps must NOT yield events -- the assistant
    message is surfaced as an `answer` by the subsequent messages.list
    walk; emitting a duplicate would double-bill the FE."""
    client = _make_agents_client(
        list_messages=[_thread_msg("assistant", "the answer")],
        run_steps=[_message_creation_step(message_id="msg-1")],
    )
    orch = _make_orchestrator(agents_client=client)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert [(e.channel, e.content) for e in events] == [("answer", "the answer")]


@pytest.mark.asyncio
async def test_run_emits_reasoning_events_before_answer() -> None:
    """Reasoning content on a step is emitted on the `reasoning`
    channel BEFORE the trailing answer events (FE ordering)."""
    client = _make_agents_client(
        list_messages=[_thread_msg("assistant", "Final answer.")],
        run_steps=[_reasoning_step("step 1: looked up docs")],
    )
    orch = _make_orchestrator(agents_client=client)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert [(e.channel, e.content) for e in events] == [
        ("reasoning", "step 1: looked up docs"),
        ("answer", "Final answer."),
    ]


@pytest.mark.asyncio
async def test_run_handles_sdk_without_run_steps_attribute() -> None:
    """Older SDK versions may not expose `agents.run_steps`; we must
    silently skip the step walk and still produce the answer event."""
    client = _make_agents_client(
        list_messages=[_thread_msg("assistant", "ok")]
    )
    # Strip the surface entirely (older SDK).
    del client.run_steps
    orch = _make_orchestrator(agents_client=client)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert [(e.channel, e.content) for e in events] == [("answer", "ok")]


@pytest.mark.asyncio
async def test_run_steps_walk_skipped_when_run_failed() -> None:
    """A failed run short-circuits before reaching the run_steps walk
    (no point surfacing partial reasoning when the user already saw an
    error event)."""
    client = _make_agents_client(
        run_status="failed",
        run_last_error="quota exceeded",
        run_steps=[
            _tool_calls_step(
                calls=[
                    _function_tool_call(
                        call_id="call_x", name="any", arguments="{}"
                    )
                ]
            )
        ],
    )
    orch = _make_orchestrator(agents_client=client)

    events = [
        e async for e in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert [e.channel for e in events] == ["error"]
    client.run_steps.list.assert_not_called()
