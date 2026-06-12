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
    5. Map the buffered native citation annotations through the shared
       `citations_from_annotations` seam and emit one `citation` event
       per source -- before the final `answer` -- so the agent path and
       the `langgraph` path surface the same `Citation` wire shape.

The agent's instructions (including any admin override) are applied by
`build_agent` via `_resolve_definition`, so this orchestrator does not
thread a system prompt. The `llm` dependency is unused -- the Agent
owns its own model deployment in Foundry. We still take it via the ABC
contract so swapping orchestrators is configuration-only.
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
from backend.core.settings import AppSettings
from backend.core.tools.citations import citations_from_annotations
from backend.core.types import ChatMessage, OrchestratorChannel, OrchestratorEvent

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
        **_extras: object,
    ) -> None:
        # `**_extras` swallows kwargs the router passes uniformly to every
        # orchestrator (e.g. `search` / `system_prompt` / `search_top_k`
        # for `langgraph`, plus `credential` / `agent_name` from the
        # shared wiring contract). Avoids name-based dispatch in the
        # caller (Hard Rule #4).
        super().__init__(settings, llm)
        self._agents = agents
        self._db = db
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
        search = settings.search
        self._search_endpoint = search.endpoint
        self._kb_name = search.knowledge_base_name
        self._kb_api_version = search.knowledge_base_api_version
        self._connection_name = search.connection_name
        # Sampling knobs are infra/admin-configured (not per-request), so
        # capture them once here -- same rationale as the KB scalars
        # above. The Foundry agent owns its model deployment, so these are
        # the only inference knobs the agent path honors; they are
        # threaded into every `agent.run(...)` via `ChatOptions`.
        openai = settings.openai
        self._temperature = openai.temperature
        self._max_tokens = openai.max_tokens

    # ------------------------------------------------------------------
    # OrchestratorBase implementation
    # ------------------------------------------------------------------

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        oss_messages = self._to_oss_messages(messages)

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
                stream = agent.run(
                    oss_messages,
                    stream=True,
                    options=ChatOptions(
                        temperature=self._temperature,
                        max_tokens=self._max_tokens,
                    ),
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

        for citation in citations_from_annotations(citation_annotations):
            yield OrchestratorEvent(
                channel=OrchestratorChannel.CITATION,
                metadata=citation.model_dump(),
            )

        answer = "".join(answer_parts)
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
        completes); reasoning + function-call blocks are emitted
        immediately so the FE panel updates in stream-order. Native
        citation annotations ride on text blocks (often with empty
        text, one per grounded source) and are accumulated into
        `citation_annotations`; the caller maps them through the shared
        `citations_from_annotations` seam once the stream completes.
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
                    events.append(
                        OrchestratorEvent(
                            channel=OrchestratorChannel.REASONING,
                            content=text,
                        )
                    )
            elif ctype == "function_call":
                name = getattr(content, "name", "") or "tool"
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
