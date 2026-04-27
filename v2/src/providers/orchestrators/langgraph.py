"""LangGraph-backed orchestrator.

Pillar: Stable Core
Phase: 3

Builds a `StateGraph` with a single LLM node today. The graph is
compiled once per orchestrator instance and re-used across requests
(no mutable per-request state held on `self`). Tool nodes (`ToolNode`)
wire in via task #20 once the cross-cutting tool helpers
(`shared/tools/`) land -- adding them is a `graph.add_node(...)` +
`add_conditional_edges(...)` change, no rewrite of `run()`.

`run()` invokes the compiled graph with `ainvoke` and surfaces the
assistant reply as a single `answer` event on the SSE channel
(ADR 0007). Token-level streaming is a follow-up: it'll move the LLM
node to `chat_stream` and pump `astream_events` from the graph.
"""
from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Annotated, Any, AsyncIterator, Sequence, TypedDict

from langgraph.graph import END, START, StateGraph

from shared.types import ChatMessage, OrchestratorEvent

from . import registry
from .base import OrchestratorBase

if TYPE_CHECKING:
    from providers.llm.base import BaseLLMProvider
    from shared.settings import AppSettings


class _GraphState(TypedDict):
    """Shape of the value flowing through the LangGraph state machine.

    `messages` carries an append-only conversation log. The
    `operator.add` reducer makes multi-node writes (e.g., `llm` and the
    future `tools` node added in task #20) merge instead of overwrite.
    Without this reducer, the second writer would silently clobber the
    first -- a class of bug LangGraph specifically protects against
    when you declare a channel reducer.
    """

    messages: Annotated[list[ChatMessage], operator.add]


@registry.register("langgraph")
class LangGraphOrchestrator(OrchestratorBase):
    def __init__(
        self,
        settings: "AppSettings",
        llm: "BaseLLMProvider",
    ) -> None:
        super().__init__(settings, llm)
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        graph: StateGraph = StateGraph(_GraphState)
        graph.add_node("llm", self._llm_node)
        graph.add_edge(START, "llm")
        graph.add_edge("llm", END)
        return graph.compile()

    async def _llm_node(self, state: _GraphState) -> _GraphState:
        reply = await self._llm.chat(state["messages"])
        # Return only the delta -- the `operator.add` reducer on
        # `messages` appends it to the existing log.
        return {"messages": [reply]}

    # ------------------------------------------------------------------
    # OrchestratorBase implementation
    # ------------------------------------------------------------------

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        result: _GraphState = await self._graph.ainvoke(
            {"messages": list(messages)}
        )
        # The LLM node appends the assistant reply as the last message.
        # Empty input (no messages) would still produce a reply, but a
        # missing reply is a hard error -- emit a typed error event so
        # the SSE consumer can surface it.
        all_messages = result["messages"]
        if not all_messages or all_messages[-1].role != "assistant":
            yield OrchestratorEvent(
                channel="error",
                content="LangGraph run produced no assistant reply.",
            )
            return
        yield OrchestratorEvent(
            channel="answer",
            content=all_messages[-1].content,
        )
