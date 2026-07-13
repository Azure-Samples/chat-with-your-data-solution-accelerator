"""LangGraph-backed orchestrator.

Builds a `StateGraph` with a single LLM node, compiled once per
orchestrator instance and re-used across requests (no mutable
per-request state held on `self`). The graph is held for future
tool-node wiring (``ToolNode`` + ``add_conditional_edges``) and is
**deliberately bypassed** for the LLM call: live token
+ reasoning streaming is incompatible with
``StateGraph.ainvoke``'s buffer-then-return contract, and the unified
LLM-layer factory ``BaseLLMProvider.complete()`` already
auto-routes between ``chat()`` and ``reason()`` so the orchestrator
never has to branch on model class.

``run()`` calls ``self.llm.complete(...)`` directly, propagates
``reasoning`` / ``error`` events to the SSE channel as they arrive,
accumulates ``answer`` chunks into a single buffered event (ADR 0007
single-answer contract preserved), then emits ``citation`` events for
the markers actually referenced in the answer.

Citation wiring: when an optional
``BaseSearch`` provider is supplied at construction time, ``run()``
retrieves grounding documents for the latest user message, injects
them as a numbered ``[doc1] / [doc2] / ...`` system message via
``shared.tools.citations.format_sources_block``, and emits one
``citation`` event per marker actually referenced in the assistant
reply (filtered through ``filter_to_referenced``). When ``search`` is
``None`` the orchestrator stays in pass-through mode -- no retrieval,
no citation events -- so the existing single-answer contract is
preserved for callers that haven't wired search through DI yet.
"""

import operator
from typing import Annotated, Any, AsyncIterator, Sequence, TypedDict

from langgraph.graph import (  # pyright: ignore[reportMissingTypeStubs]
    END,
    START,
    StateGraph,
)

from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings
from backend.core.tools.citations import (
    build_citations,
    filter_to_referenced,
    format_sources_block,
)
from backend.core.types import (
    ChatMessage,
    ChatRole,
    OrchestratorChannel,
    OrchestratorEvent,
)

from .registry import registry
from .base import OrchestratorBase


class _GraphState(TypedDict):
    """Shape of the value flowing through the LangGraph state machine.

    `messages` carries an append-only conversation log. The
    `operator.add` reducer makes multi-node writes (e.g., `llm` and a
    future `tools` node) merge instead of overwrite.
    Without this reducer, the second writer would silently clobber the
    first -- a class of bug LangGraph specifically protects against
    when you declare a channel reducer.
    """

    messages: Annotated[list[ChatMessage], operator.add]


@registry.register("langgraph")
class LangGraphOrchestrator(OrchestratorBase):
    def __init__(
        self,
        settings: AppSettings,
        llm: BaseLLMProvider,
        search: BaseSearch | None = None,
        system_prompt: str | None = None,
        search_top_k: int | None = None,
        search_use_semantic_search: bool | None = None,
        openai_temperature: float | None = None,
        openai_max_tokens: int | None = None,
        **_extras: object,
    ) -> None:
        # `**_extras` swallows kwargs the router passes uniformly to every
        # orchestrator (e.g. `credential`, `agent_name` for `agent_framework`).
        # Avoids name-based dispatch in the caller (Hard Rule #4).
        # `system_prompt` carries the effective `cwyd_agent_instructions`
        # (admin-saved override or the `CWYD_AGENT.instructions` default);
        # `run()` injects it as the leading system message.
        # `search_top_k` / `search_use_semantic_search` carry the effective
        # per-request retrieval knobs (admin-saved overrides or the
        # `settings.search` defaults); `run()` forwards them to
        # `BaseSearch.search`, where `None` means "use the provider default".
        # `openai_temperature` / `openai_max_tokens` carry the effective
        # sampling knobs; `run()` forwards them to `complete()`, where
        # `None` means "send no sampling param (use the model default)".
        super().__init__(settings, llm)
        self._search = search
        self._system_prompt = system_prompt
        self._search_top_k = search_top_k
        self._search_use_semantic_search = search_use_semantic_search
        self._openai_temperature = openai_temperature
        self._openai_max_tokens = openai_max_tokens
        self._graph = self._build_graph()

    # Graph construction

    def _build_graph(self) -> Any:
        # `StateGraph[_GraphState]` would be the precise generic, but
        # langgraph ships partial stubs whose type parameters leak
        # `Unknown` into every downstream call. Cast to `Any` at the
        # construction site so call sites stay readable; the runtime
        # behavior is unchanged.
        graph: Any = StateGraph(_GraphState)
        graph.add_node("llm", self._llm_node)
        graph.add_edge(START, "llm")
        graph.add_edge("llm", END)
        return graph.compile()

    async def _llm_node(self, state: _GraphState) -> _GraphState:
        reply = await self.llm.chat(state["messages"])
        # Return only the delta -- the `operator.add` reducer on
        # `messages` appends it to the existing log.
        return {"messages": [reply]}

    # OrchestratorBase implementation

    @staticmethod
    def _latest_user_text(messages: Sequence[ChatMessage]) -> str:
        for msg in reversed(messages):
            if msg.role is ChatRole.USER:
                return msg.content
        return ""

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        # Leading system messages, assembled in priority order:
        #   1. the configured system prompt (admin-editable
        #      `cwyd_agent_instructions`, threaded in at construction;
        #      defaults to `CWYD_AGENT.instructions` when no override is
        #      saved), then
        #   2. the optional `[docN]` sources block, emitted only when a
        #      search provider is wired and returns hits.
        # Both precede the inbound conversation so the model sees its
        # instructions and grounding before the user turn. Citation
        # events are emitted only for markers actually referenced in the
        # final answer.
        system_messages: list[ChatMessage] = []
        if self._system_prompt:
            system_messages.append(
                ChatMessage(role=ChatRole.SYSTEM, content=self._system_prompt)
            )

        citations = []
        if self._search is not None:
            query = self._latest_user_text(messages)
            if query:
                # Embed the query so the search provider can run dense
                # vector retrieval. pgvector needs the vector -- without
                # one it falls back to AND-semantics full-text search that
                # cannot match a multi-term question against small chunks;
                # AzureSearch uses the vector for hybrid (text + vector)
                # scoring on top of its semantic re-ranker.
                embedding = await self.llm.embed([query])
                query_vector = embedding.vectors[0] if embedding.vectors else None
                sources = await self._search.search(
                    query,
                    top_k=self._search_top_k,
                    use_semantic_search=self._search_use_semantic_search,
                    vector=query_vector,
                )
                if sources:
                    citations = build_citations(sources)
                    block = format_sources_block(sources)
                    system_messages.append(
                        ChatMessage(role=ChatRole.SYSTEM, content=f"Sources:\n{block}")
                    )

        graph_messages: list[ChatMessage] = [*system_messages, *messages]

        # Stream events through the LLM-layer factory.
        # `complete()` auto-routes to `chat()` / `reason()`
        # based on the configured deployment, so o-series `reasoning`
        # tokens flow live to the SSE channel without per-orchestrator
        # branching. The compiled graph is bypassed for the LLM call --
        # future tool-node wiring reintroduces it for tool routing.
        answer_parts: list[str] = []
        saw_error = False
        async for event in self.llm.complete(
            graph_messages,
            temperature=self._openai_temperature,
            max_tokens=self._openai_max_tokens,
        ):
            if event.channel == OrchestratorChannel.ANSWER:
                answer_parts.append(event.content)
            elif event.channel == OrchestratorChannel.ERROR:
                saw_error = True
                yield event  # surface upstream LLM errors immediately
            else:
                # `reasoning` (and any future LLM-emitted channel) is
                # passed through verbatim so the FE reasoning panel
                # lights up while the model is still thinking.
                yield event

        if saw_error and not answer_parts:
            # Upstream already emitted a typed error event; nothing
            # more to assemble.
            return

        answer = "".join(answer_parts)
        if not answer:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content="LangGraph run produced no assistant reply.",
            )
            return

        for citation in citations:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.CITATION,
                metadata=citation.model_dump(),
            )
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content=answer)
