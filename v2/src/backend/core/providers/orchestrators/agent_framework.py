"""Microsoft Agent Framework (OSS) orchestrator.

Pillar: Stable Core
Phase: 3

Invokes the CWYD agent through a client-side `agent_framework.Agent`
composed by the agents provider's `build_agent` seam (see
`backend.core.providers.agents.base.BaseAgentsProvider.build_agent`).
The named Prompt Agent is resolved / created server-side; this
orchestrator builds the per-request Knowledge Base retrieval tool,
hands it to `build_agent` as an additive runtime tool, and streams the
agent's response. Construction is dependency-injected: the agents
provider and the database client come from the wiring layer in
`dependencies.py`, keeping the orchestrator free of SDK construction
concerns and trivially testable.

Run loop:
    1. Convert inbound `ChatMessage`s to OSS `Message`s.
    2. Build the server-side Knowledge Base MCP tool when a KB is
       configured; it is authenticated by the project search
       connection (`project_connection_id`), not a per-request bearer.
    3. Resolve the runtime `Agent` via `agents.build_agent(CWYD_AGENT,
       db, extra_tools=[kb_tool])`.
    4. Stream `agent.run(messages, stream=True)` inside `async with
       agent:` and translate each `AgentResponseUpdate.contents` block
       to an `OrchestratorEvent` on the locked channel set:
         * `text`           -> buffered, flushed as a single `answer`
         * `text_reasoning` -> `reasoning` event
         * `function_call`  -> `tool` event with id / arguments
         * citation annots  -> buffered (see step 5)
         * everything else  -> ignored
    5. Build the `Citation`s from the buffered annotations via the shared
       `citations_from_annotations` seam, then run `normalize_kb_citations`
       over the assembled answer + citation list so any native
       `【6:1†source】`-style KB markers in the answer become the
       grouping-ordered `[docN]` and the citation ids match. When a search
       provider is wired, run `enrich_kb_citations` to backfill the friendly
       `title` / `snippet` a KB citation lacks (its annotation carries only
       the raw `mcp://searchindex/<key>` id) by resolving each key through
       `search.get_document_by_key`. Emit one `citation` event per source --
       before the final `answer` -- so the agent path and the `langgraph`
       path surface the same `Citation` wire shape and the same inline
       `[docN]` markers.

The agent's instructions (including any admin override) are applied by
`build_agent` via `_resolve_definition`, so this orchestrator does not
thread a system prompt. The Agent owns its own model deployment in
Foundry, so `run()` consults the injected `llm` only to detect whether
that model emits reasoning summaries (`llm.supports_reasoning()`),
gating the Responses-API `reasoning` option accordingly.
"""

import json
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

from agent_framework import (
    AgentResponseUpdate,
    Annotation,
    ChatOptions,
    Message,
    ToolTypes,
)
from azure.ai.projects.models import MCPTool
from azure.core.exceptions import AzureError

from backend.core.agents.definitions import CWYD_AGENT
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings
from backend.core.tools.citations import (
    build_citations,
    citations_from_annotations,
    enrich_kb_citations,
    filter_to_referenced,
    format_sources_block,
    normalize_kb_citations,
    strip_kb_markers,
)
from backend.core.types import (
    ChatMessage,
    ChatRole,
    Citation,
    OrchestratorChannel,
    OrchestratorEvent,
)

from .registry import registry
from .base import OrchestratorBase

logger = logging.getLogger(__name__)

# The single managed retrieval tool a Foundry IQ Knowledge Base exposes on its
# MCP endpoint. Pinned via `allowed_tools` so the agent may call only KB
# retrieval, never arbitrary server-side tools.
KB_RETRIEVE_TOOL_NAME = "knowledge_base_retrieve"


@registry.register("agent_framework")
class AgentFrameworkOrchestrator(OrchestratorBase):
    def __init__(
        self,
        settings: AppSettings,
        llm: BaseLLMProvider,
        *,
        agents: BaseAgentsProvider,
        db: BaseDatabaseClient,
        search: BaseSearch | None = None,
        search_top_k: int | None = None,
        search_use_semantic_search: bool | None = None,
        openai_temperature: float | None = None,
        openai_max_tokens: int | None = None,
        **_extras: object,
    ) -> None:
        # `**_extras` swallows kwargs the router passes uniformly to every
        # orchestrator (`system_prompt` for `langgraph`, plus `credential` /
        # `agent_name` from the shared wiring contract). Avoids name-based
        # dispatch in the caller (Hard Rule #4).
        super().__init__(settings, llm)
        self._agents = agents
        self._db = db
        # The injected search provider backs citation enrichment: an
        # agent_framework KB citation carries only a raw
        # mcp://searchindex/<key> id, so run() resolves each key through
        # search.get_document_by_key to backfill the friendly title /
        # snippet the langgraph path already ships. In practice this is the
        # AzureSearch handler -- the agent_framework + pgvector cell is
        # rejected upstream, never reaching here.
        self._search = search
        # Effective per-request retrieval knobs (admin-saved overrides or
        # the `settings.search` defaults) the router forwards uniformly to
        # every orchestrator; captured to forward to `BaseSearch.search`,
        # where `None` means "use the provider default" -- symmetric with
        # the `langgraph` orchestrator.
        self._search_top_k = search_top_k
        self._search_use_semantic_search = search_use_semantic_search
        # The CWYD orchestrator always drives the `cwyd` agent; the
        # provider's `build_agent` resolves / creates it and applies any
        # admin instruction override via `_resolve_definition`.
        self._definition = CWYD_AGENT
        # Foundry IQ Knowledge Base coordinates are infra-pinned (not
        # per-request), so capture them once here rather than holding a
        # reference to `settings` and reaching through it later. The KB
        # MCP endpoint is authenticated server-side via the project
        # search connection (`connection_name`), so no per-request bearer
        # is minted.
        search_settings = settings.search
        self._search_endpoint = search_settings.endpoint
        self._kb_name = search_settings.knowledge_base_name
        self._kb_api_version = search_settings.knowledge_base_api_version
        self._connection_name = search_settings.connection_name
        # Sampling knobs carry the effective admin-configured values the
        # router forwards (`openai_temperature` / `openai_max_tokens`),
        # falling back to the `settings.openai` env defaults when a caller
        # constructs the orchestrator without them. The Foundry agent owns
        # its model deployment, so these are the only inference knobs the
        # agent path honors; they are threaded into every `agent.run(...)`
        # via `ChatOptions`.
        self._temperature = (
            openai_temperature
            if openai_temperature is not None
            else settings.openai.temperature
        )
        self._max_tokens = (
            openai_max_tokens
            if openai_max_tokens is not None
            else settings.openai.max_tokens
        )

    # ------------------------------------------------------------------
    # OrchestratorBase implementation
    # ------------------------------------------------------------------

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        # Build the KB retrieval tool only when a Knowledge Base is
        # configured. The tool is authenticated server-side via the
        # project search connection (`project_connection_id`), so there
        # is no per-request bearer to mint and no caller-owned HTTP
        # client to manage -- the Responses API runs the MCP call under
        # the connection's identity. The dict form (`.as_dict()`) is the
        # wire shape the runtime agent forwards to the Responses API.
        kb_tool = self._build_kb_tool()
        extra_tools: list[ToolTypes] | None = (
            [kb_tool.as_dict()] if kb_tool is not None else None
        )

        # When no server-side KB tool is available (a pgvector deployment,
        # where `_build_kb_tool()` returns None) but a search provider is
        # wired, ground app-side like the `langgraph` path: embed the
        # latest user query, retrieve from the search backend, and prepend
        # the `[docN]` sources block to the latest user turn. The Agents
        # Responses thread drops system messages (`_to_oss_messages`), so
        # the grounding context rides the user turn rather than a system
        # message; `build_citations` / `format_sources_block` /
        # `filter_to_referenced` are the same shared seam the `langgraph`
        # path uses, so the emitted citation wire shape is identical across
        # orchestrators (Hard Rule #20).
        retrieved_citations: list[Citation] = []
        grounded_messages: Sequence[ChatMessage] = messages
        if kb_tool is None and self._search is not None:
            query = next(
                (m.content for m in reversed(messages) if m.role is ChatRole.USER),
                "",
            )
            if query:
                embedding = await self.llm.embed([query])
                query_vector = (
                    embedding.vectors[0] if embedding.vectors else None
                )
                sources = await self._search.search(
                    query,
                    top_k=self._search_top_k,
                    use_semantic_search=self._search_use_semantic_search,
                    vector=query_vector,
                )
                if sources:
                    retrieved_citations = build_citations(sources)
                    block = format_sources_block(sources)
                    # Prepend the [docN] block to the latest user turn so
                    # the model reads the grounding immediately before the
                    # question it must answer from.
                    rebuilt = list(messages)
                    for i in range(len(rebuilt) - 1, -1, -1):
                        if rebuilt[i].role is ChatRole.USER:
                            rebuilt[i] = ChatMessage(
                                role=ChatRole.USER,
                                content=f"Sources:\n{block}\n\n{rebuilt[i].content}",
                            )
                            break
                    grounded_messages = rebuilt

        oss_messages = self._to_oss_messages(grounded_messages)

        try:
            agent = await self._agents.build_agent(
                self._definition, self._db, extra_tools=extra_tools
            )
        except AzureError as exc:
            # `build_agent` already logged the structured failure at its
            # SDK boundary and re-raised; translate it into a terminal
            # error event so the SSE stream closes cleanly rather than
            # surfacing a half-built agent.
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content=f"Agent initialization failed: {exc}",
            )
            return

        answer_parts: list[str] = []
        citation_annotations: list[Annotation] = []
        saw_any_content = False

        # `agent_framework.Agent` is an async context manager; entering it
        # owns the chat-client transport and `__aexit__` releases it on
        # both the success path and the error `return` below.
        async with agent:
            try:
                if await self.llm.supports_reasoning():
                    # Reasoning models reject `temperature` and prefer
                    # `max_output_tokens`, so omit both sampling knobs and
                    # ask only for the reasoning summary -- symmetric with
                    # the `langgraph` path's `reason()`, which passes
                    # neither. `FoundryChatClient` honors a Responses-API
                    # `reasoning` option (`agent_framework_foundry`
                    # translates it to `Reasoning(effort=..., summary=...)`)
                    # so the model emits reasoning-summary deltas the run
                    # surfaces as `text_reasoning` content, which
                    # `_update_to_events` already forwards on the reasoning
                    # channel. `reasoning` lives on the OpenAI-specific
                    # options subclass, not the base `ChatOptions`
                    # TypedDict, so it is set past that SDK boundary.
                    options = ChatOptions()
                    options["reasoning"] = {  # pyright: ignore[reportGeneralTypeIssues]
                        "effort": "medium",
                        "summary": "auto",
                    }
                else:
                    options = ChatOptions(
                        temperature=self._temperature,
                        max_tokens=self._max_tokens,
                    )
                stream = agent.run(
                    oss_messages,
                    stream=True,
                    options=options,
                )
                async for update in stream:
                    for event in self._update_to_events(
                        update, answer_parts, citation_annotations
                    ):
                        saw_any_content = True
                        yield event
            except AzureError as exc:
                logger.exception(
                    "agent_framework agent run failed",
                    extra={
                        "operation": "agent_run",
                        "provider": "agent_framework",
                        "agent_name": self._definition.name,
                    },
                )
                yield OrchestratorEvent(
                    channel=OrchestratorChannel.ERROR,
                    content=f"Agent run failed: {exc}",
                )
                return

        answer = "".join(answer_parts)
        if retrieved_citations:
            # pgvector app-side grounding path: the model cited the
            # injected [docN] sources block, so keep only the markers it
            # actually referenced -- symmetric with the langgraph path.
            # There are no native KB annotations to normalize or enrich
            # here; build_citations already carries title / snippet.
            citations = filter_to_referenced(answer, retrieved_citations)
        else:
            # Foundry IQ KB path: citations ride native annotations.
            citations = citations_from_annotations(citation_annotations)
            # Converge on the langgraph path's wire shape: rewrite any native
            # 【N:M†source】 KB markers in the answer to the grouping-ordered
            # [docN] and renumber the citation ids to match.
            answer, citations = normalize_kb_citations(answer, citations)
            # Backfill the friendly title / snippet a KB citation lacks (its
            # annotation carries only the raw mcp://searchindex/<key> id) by
            # resolving each key through the search provider's by-key lookup;
            # langgraph-shaped citations and unresolved keys pass through
            # unchanged. Best-effort: a transient lookup failure degrades to
            # the normalized raw-id citations rather than failing an answer
            # already fully assembled (get_document_by_key has logged the SDK
            # failure at its own boundary).
            search = self._search
            if search is not None:
                try:
                    citations = await enrich_kb_citations(
                        citations, search.get_document_by_key
                    )
                except AzureError:
                    logger.warning(
                        "agent_framework citation enrichment skipped "
                        "after lookup failure",
                        extra={
                            "operation": "enrich_citations",
                            "provider": "agent_framework",
                            "agent_name": self._definition.name,
                        },
                    )

        for citation in citations:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.CITATION,
                metadata=citation.model_dump(),
            )

        if answer:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ANSWER, content=answer
            )
        elif not saw_any_content:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content="Agent produced no assistant reply.",
            )

    async def aclose(self) -> None:
        # The per-request `Agent` is closed by the `async with` in
        # `run()`, and the agents provider + credential are owned by the
        # wiring layer (stashed on app.state at lifespan startup). There
        # is nothing for the orchestrator to release here.
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_kb_tool(self) -> MCPTool | None:
        """Build the Foundry IQ Knowledge Base retrieval tool.

        Returns a server-side `MCPTool` bound to the KB's managed MCP
        endpoint and the project search connection, or `None` when the
        KB is unconfigured (empty Search endpoint, knowledge-base name,
        or connection name -- e.g. a pgvector deployment, where
        `agent_framework` is rejected upstream rather than reaching this
        path). The tool carries `project_connection_id` so the Responses
        API authenticates the retrieval call server-side under the
        connection's identity; the caller serializes it via `.as_dict()`
        before attaching it to the runtime agent.
        """
        endpoint = self._search_endpoint.rstrip("/")
        if not endpoint or not self._kb_name or not self._connection_name:
            return None
        url = (
            f"{endpoint}/knowledgebases/{self._kb_name}/mcp"
            f"?api-version={self._kb_api_version}"
        )
        return MCPTool(
            server_label=self._kb_name,
            server_url=url,
            require_approval="never",
            allowed_tools=[KB_RETRIEVE_TOOL_NAME],
            project_connection_id=self._connection_name,
        )

    @staticmethod
    def _to_oss_messages(messages: Sequence[ChatMessage]) -> list[Message]:
        """Convert CWYD ChatMessages to OSS `Message`s, dropping
        roles the Agents Responses API doesn't accept on a thread:
        `system` lives in the agent's `instructions` (set at agent
        create-time), and `tool` outputs are not yet wired.
        """
        out: list[Message] = []
        for msg in messages:
            if msg.role == "user":
                out.append(Message("user", [msg.content]))
            elif msg.role == "assistant":
                out.append(Message("assistant", [msg.content]))
        return out

    def _update_to_events(
        self,
        update: AgentResponseUpdate,
        answer_parts: list[str],
        citation_annotations: list[Annotation],
    ) -> list[OrchestratorEvent]:
        """Map one streaming update's content blocks to events.

        Text blocks are accumulated into `answer_parts` (the caller
        flushes them as a single `answer` event after the stream
        completes); reasoning, function-call, and server-side MCP
        tool-call blocks are emitted immediately so the FE panel updates
        in stream-order. Native citation annotations ride on text blocks
        (often with empty text, one per grounded source) and are
        accumulated into `citation_annotations`; the caller maps them
        through the shared `citations_from_annotations` seam once the
        stream completes.
        """
        events: list[OrchestratorEvent] = []
        for content in update.contents or []:
            annotations = getattr(content, "annotations", None)
            if annotations:
                citation_annotations.extend(annotations)
            ctype = getattr(content, "type", None)
            if ctype == "text":
                text = getattr(content, "text", "") or ""
                if text:
                    answer_parts.append(text)
            elif ctype == "text_reasoning":
                text = getattr(content, "text", "") or ""
                if text:
                    # Drop native `【N:M†source】` KB markers before the
                    # reasoning event: the reasoning panel has no `[docN]`
                    # rendering, so unstripped markers show as garbage. The
                    # answer-side `normalize_kb_citations` owns rewriting
                    # markers to `[docN]`; the reasoning channel only removes
                    # them.
                    events.append(
                        OrchestratorEvent(
                            channel=OrchestratorChannel.REASONING,
                            content=strip_kb_markers(text),
                        )
                    )
            elif ctype in ("function_call", "mcp_server_tool_call"):
                # Client-side function tools surface as `function_call`
                # (name on `.name`); the server-side Foundry-IQ KB
                # retrieval runs in the Responses API and surfaces as
                # `mcp_server_tool_call` (name on `.tool_name`). Both map
                # to a raw `tool` event; the during-the-wait KB-search
                # narration is emitted upstream by the shared `run_chat`
                # pipeline, so no per-call narration is produced here.
                name = (
                    getattr(content, "name", "")
                    or getattr(content, "tool_name", "")
                    or "tool"
                )
                call_id = getattr(content, "call_id", "") or ""
                arguments = self._arguments_to_string(
                    getattr(content, "arguments", None)
                )
                metadata: dict[str, Any] = {
                    "id": call_id,
                    "type": "function",
                }
                if arguments:
                    metadata["arguments"] = arguments
                events.append(
                    OrchestratorEvent(
                        channel=OrchestratorChannel.TOOL,
                        content=str(name),
                        metadata=metadata,
                    )
                )
        return events

    @staticmethod
    def _arguments_to_string(arguments: Any) -> str:
        if arguments is None:
            return ""
        if isinstance(arguments, str):
            return arguments
        try:
            return json.dumps(arguments)
        except (TypeError, ValueError):
            return str(arguments)
