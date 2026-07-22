"""Tests for the Agent Framework orchestrator."""

from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import HttpResponseError

from backend.core.agents.definitions import CWYD_AGENT
from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.orchestrators.agent_framework import (
    KB_RETRIEVE_TOOL_NAME,
    AgentFrameworkOrchestrator,
)
from backend.core.settings import (
    AppSettings,
    FoundrySettings,
    OpenAISettings,
    SearchSettings,
)
from backend.core.types import ChatMessage, SearchResult

_AGENT_FW_LOGGER_NAME = "backend.core.providers.orchestrators.agent_framework"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _settings(
    endpoint: str = "https://example.services.ai.azure.com/api/projects/p1",
) -> AppSettings:
    settings = MagicMock(spec=AppSettings)
    settings.foundry = MagicMock(spec=FoundrySettings)
    settings.foundry.project_endpoint = endpoint
    settings.search = MagicMock(spec=SearchSettings)
    settings.search.endpoint = "https://srch.example"
    settings.search.knowledge_base_name = "cwyd-kb"
    settings.search.knowledge_source_name = "cwyd-index-ks"
    settings.search.knowledge_base_api_version = "2025-11-01-preview"
    settings.search.connection_name = "search-conn"
    settings.openai = MagicMock(spec=OpenAISettings)
    settings.openai.temperature = 0.0
    settings.openai.max_tokens = 1000
    return settings


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _reasoning_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text_reasoning", text=text)


def _function_call_block(*, call_id: str, name: str, arguments: Any) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=arguments,
    )


def _mcp_server_tool_call_block(
    *, call_id: str, tool_name: str, arguments: Any
) -> SimpleNamespace:
    """A server-side hosted-MCP tool call.

    Mirrors `agent_framework`'s `Content.from_mcp_server_tool_call(...)`:
    the GA-FULL Foundry-IQ KB retrieval runs in the Responses API and
    streams as a `mcp_server_tool_call` block whose tool name rides on
    `.tool_name` (not `.name`, as a client-side `function_call` does).
    """
    return SimpleNamespace(
        type="mcp_server_tool_call",
        call_id=call_id,
        tool_name=tool_name,
        arguments=arguments,
    )


def _citation_block(
    *,
    file_id: str = "",
    url: str = "",
    title: str = "",
    snippet: str = "",
    tool_name: str = "",
    annotated_regions: list[dict[str, Any]] | None = None,
) -> SimpleNamespace:
    """A streamed text block carrying a native `citation` annotation.

    Mirrors the Foundry / OpenAI Responses client, which attaches
    server-side grounding citations as `Annotation(type="citation", ...)`
    on a text `Content` with empty text -- one block per source.
    """
    annotation: dict[str, Any] = {"type": "citation"}
    if file_id:
        annotation["file_id"] = file_id
    if url:
        annotation["url"] = url
    if title:
        annotation["title"] = title
    if snippet:
        annotation["snippet"] = snippet
    if tool_name:
        annotation["tool_name"] = tool_name
    if annotated_regions is not None:
        annotation["annotated_regions"] = annotated_regions
    return SimpleNamespace(type="text", text="", annotations=[annotation])


def _update(*contents: Any) -> SimpleNamespace:
    return SimpleNamespace(contents=list(contents))


class _FakeAsyncIter:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Any:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class _FakeAgent:
    """Async-context-manager stand-in for `agent_framework.Agent`.

    Records `run(...)` inputs and counts context-manager entry / exit so
    tests can assert the orchestrator drives the agent inside
    `async with` (which owns the chat-client transport).
    """

    def __init__(
        self,
        *,
        updates: list[Any] | None = None,
        run_error: Exception | None = None,
    ) -> None:
        self._updates = updates or []
        self._run_error = run_error
        self.run_calls: list[dict[str, Any]] = []
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> Self:
        self.entered += 1
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        self.exited += 1
        return None

    def run(
        self,
        messages: Any,
        *,
        stream: bool = False,
        options: Any = None,
    ) -> Any:
        self.run_calls.append(
            {"messages": messages, "stream": stream, "options": options}
        )
        if self._run_error is not None:
            raise self._run_error
        return _FakeAsyncIter(self._updates)


class _FakeAgentsProvider:
    """Stand-in for the agents provider's `build_agent` seam.

    Records each `build_agent` call's `(definition, db, extra_tools)` and
    returns a pre-seeded `_FakeAgent` (or raises `build_error` to model a
    cold-start create / transport failure).
    """

    def __init__(
        self,
        *,
        agent: _FakeAgent | None = None,
        build_error: Exception | None = None,
    ) -> None:
        self._agent = agent
        self._build_error = build_error
        self.build_calls: list[dict[str, Any]] = []

    async def build_agent(
        self, definition: Any, db: Any, *, extra_tools: Any = None
    ) -> _FakeAgent:
        self.build_calls.append(
            {"definition": definition, "db": db, "extra_tools": extra_tools}
        )
        if self._build_error is not None:
            raise self._build_error
        return self._agent if self._agent is not None else _FakeAgent()


def _make_orchestrator(
    *,
    settings: AppSettings | None = None,
    agents: Any = None,
    db: Any = None,
    search: Any = None,
    supports_reasoning: bool = False,
) -> AgentFrameworkOrchestrator:
    llm = MagicMock(spec=BaseLLMProvider)
    llm.supports_reasoning = AsyncMock(return_value=supports_reasoning)
    return AgentFrameworkOrchestrator(
        settings=settings if settings is not None else _settings(),
        llm=llm,
        agents=agents if agents is not None else _FakeAgentsProvider(),
        db=db if db is not None else object(),
        search=search,
    )


# ---------------------------------------------------------------------------
# Registration + constructor
# ---------------------------------------------------------------------------


def test_agent_framework_is_registered() -> None:
    assert "agent_framework" in orchestrators_registry.registry.keys()
    assert (
        orchestrators_registry.registry.get("agent_framework")
        is AgentFrameworkOrchestrator
    )


def test_create_returns_agent_framework_instance() -> None:
    orch = orchestrators_registry.registry.get("agent_framework")(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agents=_FakeAgentsProvider(),
        db=object(),
    )
    assert isinstance(orch, AgentFrameworkOrchestrator)


def test_constructor_swallows_uniform_extras() -> None:
    """The router forwards a uniform kwarg set to every orchestrator;
    `**_extras` must absorb the ones this orchestrator does not name
    (langgraph-only `system_prompt` plus the legacy `credential` /
    `agent_name` from the shared wiring contract) without raising.
    `search` / `search_top_k` / `search_use_semantic_search` are now named
    parameters (search backs retrieval + citation enrichment; the knobs are
    forwarded to `BaseSearch.search`), so they are consumed, not swallowed."""
    orch = AgentFrameworkOrchestrator(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agents=_FakeAgentsProvider(),
        db=object(),
        search=MagicMock(),
        system_prompt="ignored",
        search_top_k=5,
        search_use_semantic_search=True,
        credential=MagicMock(),
        agent_name="cwyd",
    )
    assert isinstance(orch, AgentFrameworkOrchestrator)


def test_constructor_captures_search_knobs() -> None:
    """The router forwards the effective per-request retrieval knobs
    (`search_top_k` / `search_use_semantic_search`) uniformly; the
    orchestrator captures them -- mirroring `langgraph` -- so `run()` can
    forward them to `BaseSearch.search` on the pgvector grounding path."""
    orch = AgentFrameworkOrchestrator(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agents=_FakeAgentsProvider(),
        db=object(),
        search=MagicMock(),
        search_top_k=7,
        search_use_semantic_search=True,
    )
    assert orch._search_top_k == 7
    assert orch._search_use_semantic_search is True


def test_constructor_uses_effective_sampling_over_env() -> None:
    """The effective `openai_temperature` / `openai_max_tokens` the router
    forwards win over the `settings.openai` env defaults, so an admin
    sampling override reaches the agent's `ChatOptions`."""
    orch = AgentFrameworkOrchestrator(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agents=_FakeAgentsProvider(),
        db=object(),
        openai_temperature=0.5,
        openai_max_tokens=222,
    )
    assert orch._temperature == 0.5
    assert orch._max_tokens == 222


def test_constructor_falls_back_to_env_sampling_when_unset() -> None:
    """With no effective sampling passed, the orchestrator uses the
    `settings.openai` env defaults (`_settings()` sets 0.0 / 1000)."""
    orch = AgentFrameworkOrchestrator(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agents=_FakeAgentsProvider(),
        db=object(),
    )
    assert orch._temperature == 0.0
    assert orch._max_tokens == 1000


# ---------------------------------------------------------------------------
# run() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_invokes_build_agent_with_definition_and_db() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("hello"))])
    provider = _FakeAgentsProvider(agent=agent)
    db = object()
    orch = _make_orchestrator(agents=provider, db=db)

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert len(provider.build_calls) == 1
    call = provider.build_calls[0]
    assert call["definition"] is CWYD_AGENT
    assert call["db"] is db


@pytest.mark.asyncio
async def test_run_skips_system_and_tool_messages_when_forwarding_to_agent() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    _ = [
        ev
        async for ev in orch.run(
            [
                ChatMessage(role="system", content="you are helpful"),
                ChatMessage(role="user", content="hi"),
                ChatMessage(role="tool", content='{"result": 42}'),
                ChatMessage(role="assistant", content="prior reply"),
            ]
        )
    ]

    forwarded = agent.run_calls[0]["messages"]
    # Only user + assistant survive; system + tool are dropped.
    roles = [m.role for m in forwarded]
    assert roles == ["user", "assistant"]


@pytest.mark.asyncio
async def test_run_buffers_text_chunks_into_single_answer_event() -> None:
    agent = _FakeAgent(
        updates=[
            _update(_text_block("Hello, ")),
            _update(_text_block("world!")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    answer_events = [e for e in events if e.channel == "answer"]
    assert len(answer_events) == 1
    assert answer_events[0].content == "Hello, world!"


@pytest.mark.asyncio
async def test_run_emits_reasoning_events_for_text_reasoning_blocks() -> None:
    agent = _FakeAgent(
        updates=[
            _update(_reasoning_block("looking up docs")),
            _update(_text_block("Final answer.")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("reasoning", "looking up docs"),
        ("answer", "Final answer."),
    ]


@pytest.mark.asyncio
async def test_run_strips_native_kb_markers_from_reasoning_events() -> None:
    """A native 【N:M†source】 KB marker a reasoning summary emits must be
    stripped before the `reasoning` event: the FE reasoning panel has no
    `[docN]` rendering, so an unstripped marker shows as raw garbage. The
    answer-side `normalize_kb_citations` owns marker rewriting; the
    reasoning channel only removes them.
    """
    agent = _FakeAgent(
        updates=[
            _update(_reasoning_block("Checking the policy 【6:1†source】 next.")),
            _update(_text_block("Final answer.")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    reasoning = [e.content for e in events if e.channel == "reasoning"]
    assert reasoning == ["Checking the policy next."]
    # No native marker leaks onto any channel.
    assert all("【" not in e.content for e in events)


@pytest.mark.asyncio
async def test_run_emits_tool_events_for_function_call_blocks() -> None:
    agent = _FakeAgent(
        updates=[
            _update(
                _function_call_block(
                    call_id="call_1",
                    name="search_documents",
                    arguments={"q": "foundry"},
                ),
            ),
            _update(_text_block("done")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("tool", "search_documents"),
        ("answer", "done"),
    ]
    tool_event = events[0]
    assert tool_event.metadata == {
        "id": "call_1",
        "type": "function",
        "arguments": '{"q": "foundry"}',
    }


@pytest.mark.asyncio
async def test_run_emits_tool_event_without_narration_for_kb_function_call() -> None:
    """A `knowledge_base_retrieve` client-side function-call yields only the
    raw `tool` event (id / arguments) and no `reasoning` narration. The
    during-the-wait KB-search narration is emitted upstream by the shared
    `run_chat` pipeline, so the orchestrator no longer narrates per call --
    regression guard (the per-call narration fired only after
    server-side retrieval had completed, so it never showed during the wait)."""
    agent = _FakeAgent(
        updates=[
            _update(
                _function_call_block(
                    call_id="call_kb",
                    name=KB_RETRIEVE_TOOL_NAME,
                    arguments={"query": "foundry"},
                ),
            ),
            _update(_text_block("Here is the answer.")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("tool", KB_RETRIEVE_TOOL_NAME),
        ("answer", "Here is the answer."),
    ]
    assert all(e.channel != "reasoning" for e in events)


@pytest.mark.asyncio
async def test_run_emits_tool_event_without_narration_for_kb_mcp_server_tool_call() -> (
    None
):
    """Server-side Foundry-IQ KB retrieval (GA-FULL `MCPTool`) streams as a
    `mcp_server_tool_call` block, not a client-side `function_call`. The
    orchestrator emits only the raw `tool` event for it (with id / arguments)
    and no `reasoning` narration -- the during-the-wait narration is emitted
    upstream by the shared `run_chat` pipeline. Tool-event mapping
    on this `mcp_server_tool_call` content shape stays a regression guard."""
    agent = _FakeAgent(
        updates=[
            _update(
                _mcp_server_tool_call_block(
                    call_id="mcp_kb",
                    tool_name=KB_RETRIEVE_TOOL_NAME,
                    arguments={"query": "benefits"},
                ),
            ),
            _update(_text_block("Grounded answer.")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("tool", KB_RETRIEVE_TOOL_NAME),
        ("answer", "Grounded answer."),
    ]
    assert events[0].metadata == {
        "id": "mcp_kb",
        "type": "function",
        "arguments": '{"query": "benefits"}',
    }
    assert all(e.channel != "reasoning" for e in events)


@pytest.mark.asyncio
async def test_run_emits_tool_event_for_non_kb_mcp_server_tool_call() -> None:
    """A non-KB `mcp_server_tool_call` yields a bare `tool` event with no
    KB narration (the narration is reserved for the KB retrieve tool)."""
    agent = _FakeAgent(
        updates=[
            _update(
                _mcp_server_tool_call_block(
                    call_id="mcp_1",
                    tool_name="some_other_tool",
                    arguments={"x": 1},
                ),
            ),
            _update(_text_block("done")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("tool", "some_other_tool"),
        ("answer", "done"),
    ]


@pytest.mark.asyncio
async def test_run_serializes_string_arguments_as_is() -> None:
    agent = _FakeAgent(
        updates=[
            _update(
                _function_call_block(
                    call_id="call_2",
                    name="fetch_url",
                    arguments='{"url":"https://x"}',
                ),
            ),
            _update(_text_block("done")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert events[0].metadata["arguments"] == '{"url":"https://x"}'


@pytest.mark.asyncio
async def test_run_emits_error_event_when_stream_raises_azure_error() -> None:
    agent = _FakeAgent(run_error=HttpResponseError("quota exceeded"))
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert len(events) == 1
    assert events[0].channel == "error"
    assert "quota exceeded" in events[0].content


@pytest.mark.asyncio
async def test_run_emits_error_event_when_no_content_returned() -> None:
    agent = _FakeAgent(updates=[])  # empty stream
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert len(events) == 1
    assert events[0].channel == "error"
    assert "no assistant reply" in events[0].content.lower()


@pytest.mark.asyncio
async def test_run_closes_agent_via_async_with() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert agent.entered == 1
    assert agent.exited == 1


@pytest.mark.asyncio
async def test_run_closes_agent_even_when_stream_raises() -> None:
    agent = _FakeAgent(run_error=HttpResponseError("boom"))
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert agent.entered == 1
    assert agent.exited == 1


@pytest.mark.asyncio
async def test_run_emits_error_event_when_build_agent_fails() -> None:
    provider = _FakeAgentsProvider(build_error=HttpResponseError("invalid endpoint"))
    orch = _make_orchestrator(agents=provider)

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    # build_agent failure surfaces as a terminal error event (not a raise),
    # so the SSE stream closes cleanly.
    assert len(events) == 1
    assert events[0].channel == "error"
    assert "initialization failed" in events[0].content.lower()


@pytest.mark.asyncio
async def test_aclose_is_a_noop() -> None:
    orch = _make_orchestrator()
    # Must not raise -- the per-request Agent is closed inside run()'s
    # async-with, and the provider + credential are owned by the wiring
    # layer.
    await orch.aclose()


# ---------------------------------------------------------------------------
# _build_kb_tool() -- Foundry IQ Knowledge Base MCP tool construction
# ---------------------------------------------------------------------------


def _settings_with_search(
    *,
    endpoint: str = "https://srch.example",
    kb_name: str = "cwyd-kb",
    api_version: str = "2025-11-01-preview",
    connection_name: str = "search-conn",
) -> AppSettings:
    settings = _settings()
    settings.search.endpoint = endpoint
    settings.search.knowledge_base_name = kb_name
    settings.search.knowledge_base_api_version = api_version
    settings.search.connection_name = connection_name
    return settings


def test_build_kb_tool_returns_none_when_search_endpoint_missing() -> None:
    orch = _make_orchestrator(settings=_settings_with_search(endpoint=""))
    assert orch._build_kb_tool() is None


def test_build_kb_tool_returns_none_when_kb_name_missing() -> None:
    orch = _make_orchestrator(settings=_settings_with_search(kb_name=""))
    assert orch._build_kb_tool() is None


def test_build_kb_tool_returns_none_when_connection_name_missing() -> None:
    orch = _make_orchestrator(settings=_settings_with_search(connection_name=""))
    assert orch._build_kb_tool() is None


def test_build_kb_tool_constructs_managed_mcp_url_with_api_version() -> None:
    orch = _make_orchestrator(
        settings=_settings_with_search(
            endpoint="https://srch.example/",  # trailing slash trimmed
            kb_name="cwyd-kb",
            api_version="2025-11-01-preview",
        )
    )
    tool = orch._build_kb_tool()
    assert tool is not None
    payload = tool.as_dict()
    assert payload["server_label"] == "cwyd-kb"
    assert payload["server_url"] == (
        "https://srch.example/knowledgebases/cwyd-kb/mcp"
        "?api-version=2025-11-01-preview"
    )


def test_build_kb_tool_sets_require_approval_never_and_allowed_tools() -> None:
    orch = _make_orchestrator(settings=_settings_with_search())
    tool = orch._build_kb_tool()
    assert tool is not None
    payload = tool.as_dict()
    assert payload["require_approval"] == "never"
    assert payload["allowed_tools"] == ["knowledge_base_retrieve"]
    assert payload["type"] == "mcp"


def test_build_kb_tool_sets_project_connection_id() -> None:
    orch = _make_orchestrator(settings=_settings_with_search(connection_name="my-conn"))
    tool = orch._build_kb_tool()
    assert tool is not None
    assert tool.as_dict()["project_connection_id"] == "my-conn"


# ---------------------------------------------------------------------------
# run() KB tool wiring -- server-side MCP tool forwarded via build_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_forwards_kb_tool_as_dict_to_build_agent() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    provider = _FakeAgentsProvider(agent=agent)
    orch = _make_orchestrator(
        settings=_settings_with_search(
            endpoint="https://srch.example",
            kb_name="cwyd-kb",
            api_version="2025-11-01-preview",
            connection_name="search-conn",
        ),
        agents=provider,
    )

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    extra_tools = provider.build_calls[0]["extra_tools"]
    assert extra_tools is not None
    assert len(extra_tools) == 1
    payload = extra_tools[0]
    # Forwarded as the serialized wire shape (`.as_dict()`), not the SDK
    # object, so the Responses API receives a server-side MCP tool spec.
    assert payload["type"] == "mcp"
    assert payload["server_url"] == (
        "https://srch.example/knowledgebases/cwyd-kb/mcp"
        "?api-version=2025-11-01-preview"
    )
    assert payload["project_connection_id"] == "search-conn"
    assert payload["allowed_tools"] == ["knowledge_base_retrieve"]


@pytest.mark.asyncio
async def test_run_skips_kb_tool_when_unconfigured() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    provider = _FakeAgentsProvider(agent=agent)
    orch = _make_orchestrator(
        settings=_settings_with_search(endpoint=""),  # KB not configured
        agents=provider,
    )

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert provider.build_calls[0]["extra_tools"] is None


# ---------------------------------------------------------------------------
# run() sampling knobs -- temperature / max_tokens via ChatOptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_threads_temperature_and_max_tokens_via_options() -> None:
    settings = _settings()
    settings.openai.temperature = 0.5
    settings.openai.max_tokens = 256
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(
        settings=settings, agents=_FakeAgentsProvider(agent=agent)
    )

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    options = agent.run_calls[0]["options"]
    assert options is not None
    assert options["temperature"] == 0.5
    assert options["max_tokens"] == 256


@pytest.mark.asyncio
async def test_run_passes_default_sampling_knobs_via_options() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(
        agents=_FakeAgentsProvider(agent=agent)
    )  # default _settings()

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    options = agent.run_calls[0]["options"]
    assert options is not None
    assert options["temperature"] == 0.0
    assert options["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_run_requests_reasoning_summary_when_model_supports_it() -> None:
    """A reasoning-capable answer model -> the agent run carries a
    Responses-API `reasoning` option so the model emits a reasoning
    summary, detected via `llm.supports_reasoning()` (the same capability
    the `langgraph` path consults)."""
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(
        agents=_FakeAgentsProvider(agent=agent), supports_reasoning=True
    )

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    options = agent.run_calls[0]["options"]
    assert options is not None
    assert options["reasoning"] == {"effort": "medium", "summary": "auto"}
    # Reasoning models reject `temperature` and prefer `max_output_tokens`,
    # so the orchestrator omits both sampling knobs in reasoning mode --
    # symmetric with the langgraph path's `reason()`, which passes neither.
    assert "temperature" not in options
    assert "max_tokens" not in options


@pytest.mark.asyncio
async def test_run_omits_reasoning_option_when_model_lacks_reasoning() -> None:
    """A non-reasoning answer model -> the agent run carries no
    `reasoning` option -- the Responses API rejects it for non-reasoning
    deployments, so the orchestrator must not send it unasked."""
    agent = _FakeAgent(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(
        agents=_FakeAgentsProvider(agent=agent), supports_reasoning=False
    )

    _ = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    options = agent.run_calls[0]["options"]
    assert options is not None
    assert "reasoning" not in options


# ---------------------------------------------------------------------------
# run() citation emission -- native annotations mapped via the shared seam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_emits_citation_event_from_annotations() -> None:
    agent = _FakeAgent(
        updates=[
            _update(
                _text_block("PTO accrues monthly."),
                _citation_block(
                    file_id="doc-1",
                    url="benefits.pdf",
                    title="Benefits Guide",
                    snippet="PTO accrues.",
                    tool_name="knowledge_base_retrieve",
                ),
            ),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    citation_events = [e for e in events if e.channel == "citation"]
    assert len(citation_events) == 1
    meta = citation_events[0].metadata
    # The id is normalized to [docN]; the raw KB source key persists in
    # metadata.source_id / metadata.file_id below.
    assert meta["id"] == "[doc1]"
    assert meta["title"] == "Benefits Guide"
    assert meta["url"] == "benefits.pdf"
    assert meta["snippet"] == "PTO accrues."
    assert meta["metadata"]["source_id"] == "doc-1"
    assert meta["metadata"]["file_id"] == "doc-1"
    assert meta["metadata"]["tool_name"] == "knowledge_base_retrieve"


@pytest.mark.asyncio
async def test_run_emits_citations_before_answer() -> None:
    agent = _FakeAgent(
        updates=[
            _update(_text_block("Grounded answer.")),
            _update(_citation_block(file_id="doc-1", title="Source")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    # Parity with the langgraph path: citations precede the final answer.
    assert [e.channel for e in events] == ["citation", "answer"]


@pytest.mark.asyncio
async def test_run_dedupes_citations_across_updates() -> None:
    agent = _FakeAgent(
        updates=[
            _update(_citation_block(file_id="doc-1", title="First")),
            _update(_text_block("answer")),
            _update(_citation_block(file_id="doc-1", title="ignored repeat")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    citation_events = [e for e in events if e.channel == "citation"]
    assert len(citation_events) == 1
    assert citation_events[0].metadata["id"] == "[doc1]"  # normalized to [docN]
    assert citation_events[0].metadata["title"] == "First"  # first wins


@pytest.mark.asyncio
async def test_run_merges_annotated_regions_across_updates() -> None:
    agent = _FakeAgent(
        updates=[
            _update(
                _citation_block(
                    file_id="doc-1",
                    annotated_regions=[
                        {"type": "text_span", "start_index": 0, "end_index": 5}
                    ],
                )
            ),
            _update(
                _citation_block(
                    file_id="doc-1",
                    annotated_regions=[
                        {"type": "text_span", "start_index": 9, "end_index": 14}
                    ],
                )
            ),
            _update(_text_block("answer")),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    citation_events = [e for e in events if e.channel == "citation"]
    assert len(citation_events) == 1
    regions = citation_events[0].metadata["metadata"]["annotated_regions"]
    assert [(r["start_index"], r["end_index"]) for r in regions] == [
        (0, 5),
        (9, 14),
    ]


@pytest.mark.asyncio
async def test_run_normalizes_native_kb_markers_in_answer_and_ids() -> None:
    """The agent path emits the langgraph path's wire shape: native
    `【N:M†source】` markers in the streamed answer are rewritten to the
    grouping-ordered `[docN]` (never parsing the misleading `N:M`), and the
    citation ids are renumbered to match. Wires `normalize_kb_citations` into
    `run` -- a parity guard at the orchestrator seam."""
    marker_a = "【6:1†source】"  # attributed to the first-grouped source
    marker_b = "【6:0†source】"  # attributed to the second-grouped source
    answer = f"Alpha {marker_a} and beta {marker_b}."
    start_a = answer.index(marker_a)
    start_b = answer.index(marker_b)
    agent = _FakeAgent(
        updates=[
            _update(
                _text_block(answer),
                _citation_block(
                    file_id="src-A",
                    title="Alpha.pdf",
                    annotated_regions=[
                        {
                            "type": "text_span",
                            "start_index": start_a,
                            "end_index": start_a + len(marker_a),
                        }
                    ],
                ),
                _citation_block(
                    file_id="src-B",
                    title="Beta.pdf",
                    annotated_regions=[
                        {
                            "type": "text_span",
                            "start_index": start_b,
                            "end_index": start_b + len(marker_b),
                        }
                    ],
                ),
            ),
        ]
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    answer_events = [e for e in events if e.channel == "answer"]
    assert len(answer_events) == 1
    # Markers map by grouping order, not N:M: src-A (marker 6:1) -> [doc1],
    # src-B (marker 6:0) -> [doc2]. No native bracket survives.
    assert answer_events[0].content == "Alpha [doc1] and beta [doc2]."

    citation_events = [e for e in events if e.channel == "citation"]
    assert [e.metadata["id"] for e in citation_events] == ["[doc1]", "[doc2]"]


@pytest.mark.asyncio
async def test_run_emits_no_citation_events_when_no_annotations() -> None:
    agent = _FakeAgent(updates=[_update(_text_block("Plain answer."))])
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent))

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    assert [e.channel for e in events] == ["answer"]


@pytest.mark.asyncio
async def test_run_enriches_kb_citations_via_search_lookup() -> None:
    """A KB citation carries only a raw `mcp://searchindex/<key>` id; `run`
    resolves the key through the injected search provider's by-key lookup
    and backfills the friendly title / snippet / url (fallback b).
    The langgraph path already ships friendly fields, so both orchestrators
    end at the same citation shape."""
    key = "abc123"
    raw_id = f"mcp://searchindex/{key}"
    agent = _FakeAgent(
        updates=[
            _update(
                _text_block("PTO accrues monthly."),
                _citation_block(
                    file_id=raw_id,
                    url=raw_id,
                    title=raw_id,
                    tool_name="knowledge_base_retrieve",
                ),
            ),
        ]
    )
    document = SearchResult(
        id=key,
        content="PTO accrues monthly for full-time employees.",
        title="Benefit_Options.pdf",
        url="https://blob/benefit_options.pdf",
    )
    search = MagicMock()
    search.get_document_by_key = AsyncMock(return_value=document)
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent), search=search)

    events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    # The bare Search document key (scheme stripped) drives the lookup.
    search.get_document_by_key.assert_awaited_once_with(key)
    citation_events = [e for e in events if e.channel == "citation"]
    assert len(citation_events) == 1
    meta = citation_events[0].metadata
    # The id stays the normalized [docN] marker; the friendly fields are
    # backfilled from the resolved document.
    assert meta["id"] == "[doc1]"
    assert meta["title"] == "Benefit_Options.pdf"
    assert meta["snippet"] == "PTO accrues monthly for full-time employees."
    assert meta["url"] == "https://blob/benefit_options.pdf"
    # The raw KB key is preserved on metadata for traceability.
    assert meta["metadata"]["source_id"] == raw_id


@pytest.mark.asyncio
async def test_run_keeps_raw_citations_when_enrichment_lookup_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Enrichment is best-effort: a transient by-key lookup failure degrades
    to the normalized raw-id citation rather than failing an answer that is
    already fully assembled. The SDK failure is logged, not swallowed."""
    raw_id = "mcp://searchindex/abc123"
    agent = _FakeAgent(
        updates=[
            _update(
                _text_block("PTO accrues monthly."),
                _citation_block(file_id=raw_id, url=raw_id, title=raw_id),
            ),
        ]
    )
    search = MagicMock()
    search.get_document_by_key = AsyncMock(
        side_effect=HttpResponseError(message="500 server error")
    )
    orch = _make_orchestrator(agents=_FakeAgentsProvider(agent=agent), search=search)

    with caplog.at_level("WARNING", logger=_AGENT_FW_LOGGER_NAME):
        events = [ev async for ev in orch.run([ChatMessage(role="user", content="hi")])]

    # The answer + citation still stream; only the cosmetic backfill is lost.
    assert [e.channel for e in events] == ["citation", "answer"]
    meta = [e for e in events if e.channel == "citation"][0].metadata
    assert meta["id"] == "[doc1]"
    assert meta["title"] == raw_id  # raw id retained, no friendly backfill
    # The degrade is logged (operation tag on the structured extra).
    assert any(
        getattr(record, "operation", None) == "enrich_citations"
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# run() pgvector grounding -- app-side retrieval when no KB tool is built
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_grounds_on_pgvector_when_kb_unconfigured() -> None:
    """On a pgvector deployment (`_build_kb_tool()` returns None) with a
    search provider wired, run() embeds the query, retrieves with the
    vector + effective knobs, injects the [docN] sources block into the
    user turn, attaches no server-side KB tool, and emits only the
    citations the answer actually references -- mirroring the langgraph
    path (no native KB annotations on this path)."""
    query_vector = [0.1, 0.2, 0.3]
    llm = MagicMock(spec=BaseLLMProvider)
    llm.supports_reasoning = AsyncMock(return_value=False)
    llm.embed = AsyncMock(return_value=SimpleNamespace(vectors=[query_vector]))
    search = MagicMock()
    search.search = AsyncMock(
        return_value=[
            SearchResult(
                id="k1",
                content="Remote work is allowed three days a week.",
                title="Policy.txt",
                url="https://files/Policy.txt",
                score=0.9,
            ),
            SearchResult(
                id="k2",
                content="Unrelated content.",
                title="Other.txt",
                url="https://files/Other.txt",
                score=0.4,
            ),
        ]
    )
    agent = _FakeAgent(updates=[_update(_text_block("You can work remotely [doc1]."))])
    provider = _FakeAgentsProvider(agent=agent)
    orch = AgentFrameworkOrchestrator(
        settings=_settings_with_search(endpoint=""),  # KB unconfigured
        llm=llm,
        agents=provider,
        db=object(),
        search=search,
        search_top_k=5,
        search_use_semantic_search=False,
    )

    events = [
        ev
        async for ev in orch.run(
            [ChatMessage(role="user", content="How many remote days?")]
        )
    ]

    # Embedded the query and retrieved with the vector + effective knobs.
    llm.embed.assert_awaited_once()
    search.search.assert_awaited_once()
    search_kwargs = search.search.call_args.kwargs
    assert search_kwargs["vector"] == query_vector
    assert search_kwargs["top_k"] == 5
    assert search_kwargs["use_semantic_search"] is False

    # No server-side KB tool was attached (pgvector path).
    assert provider.build_calls[0]["extra_tools"] is None

    # The [docN] sources block + the original question both reached the
    # agent on the user turn.
    agent_text = " ".join(
        getattr(content, "text", "")
        for message in agent.run_calls[0]["messages"]
        for content in getattr(message, "contents", [])
    )
    assert "[doc1]: Remote work is allowed three days a week." in agent_text
    assert "How many remote days?" in agent_text

    # All retrieved citations are emitted (pgvector path keeps positional
    # [docN] indexing in sync with the array the frontend resolves by position).
    citation_events = [e for e in events if e.channel == "citation"]
    assert len(citation_events) == 2
    assert citation_events[0].metadata["id"] == "[doc1]"
    assert citation_events[1].metadata["id"] == "[doc2]"

    # The answer streams unchanged.
    answer_events = [e for e in events if e.channel == "answer"]
    assert len(answer_events) == 1
    assert answer_events[0].content == "You can work remotely [doc1]."
