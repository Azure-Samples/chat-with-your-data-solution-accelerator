"""Azure AI Agent Framework-backed orchestrator.

Pillar: Stable Core
Phase: 3

Wraps `azure.ai.agents.aio.AgentsClient` to delegate the conversation
to a Foundry-hosted Agent. Construction is dependency-injected: both
the `AgentsClient` instance and the target `agent_id` are passed in
by the wiring layer (task #22 in `dependencies.py`). This keeps the
orchestrator free of SDK construction concerns and trivially testable
with a fake client.

`run()` follows the standard Agents flow:

    1. create a thread seeded with the inbound messages
    2. process a run against the configured agent
    3. walk the run's ``run_steps`` and emit ``tool`` /
       ``reasoning`` events for any tool invocations or model
       reasoning traces produced during the run (CU-004c)
    4. read back the assistant message(s) added to the thread
    5. yield a single ``answer`` event per assistant message
       (ADR 0007)

The ``llm`` dependency is unused today -- the Agent owns its own
model deployment in Foundry. We still take it via the ABC contract so
swapping orchestrators is configuration-only.

Reasoning + tool visibility (CU-004c, 2026-05-05): unlike the
LangGraph orchestrator (CU-004b), the agent owns its own model and
its own tool-routing loop, so we can't call
``BaseLLMProvider.complete()`` and inherit reasoning streaming. The
equivalent visibility comes from ``run_steps.list(thread_id, run_id)``
after the run finishes: each ``RunStep`` carries a ``step_details``
union -- ``tool_calls`` steps surface the tools the agent invoked
(emitted on the ``tool`` channel as the agent equivalent of
LangGraph's reasoning panel), ``message_creation`` steps are skipped
(``messages.list`` already covers them), and any ``reasoning_content``
field on the step details is emitted on the ``reasoning`` channel for
o-series-backed agents.
"""

from typing import Any, AsyncIterator, Sequence, cast

from azure.ai.agents.aio import AgentsClient
from azure.ai.agents.models import ListSortOrder, MessageRole

from shared.providers.llm.base import BaseLLMProvider
from shared.settings import AppSettings
from shared.types import ChatMessage, OrchestratorChannel, OrchestratorEvent

from . import registry
from .base import OrchestratorBase


@registry.register("agent_framework")
class AgentFrameworkOrchestrator(OrchestratorBase):
    def __init__(
        self,
        settings: AppSettings,
        llm: BaseLLMProvider,
        *,
        agents_client: AgentsClient,
        agent_id: str,
        **_extras: object,
    ) -> None:
        # `**_extras` swallows kwargs the router passes uniformly to every
        # orchestrator (e.g. `search` for `langgraph`). Avoids name-based
        # dispatch in the caller (Hard Rule #4).
        super().__init__(settings, llm)
        if not agent_id:
            raise ValueError(
                "AgentFrameworkOrchestrator requires a non-empty agent_id "
                "(create the agent in Foundry and pass its id here)."
            )
        self._agents = agents_client
        self._agent_id = agent_id

    # ------------------------------------------------------------------
    # OrchestratorBase implementation
    # ------------------------------------------------------------------

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        thread = await self._agents.threads.create()
        for msg in messages:
            agent_role = self._to_agent_role(msg.role)
            if agent_role is None:
                # `system` lives in the agent's instructions (set at
                # create-time), not on the thread. `tool` outputs are
                # wired in task #20. Silently dropping is safer than
                # demoting to `user` -- demotion would feed prompt or
                # tool-JSON back to the agent as user input.
                continue
            await self._agents.messages.create(
                thread_id=thread.id,
                role=agent_role,
                content=msg.content,
            )
        run = await self._agents.runs.create_and_process(
            thread_id=thread.id, agent_id=self._agent_id
        )
        if getattr(run, "status", None) == "failed":
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content=f"Agent run failed: {getattr(run, 'last_error', 'unknown')}",
            )
            return
        # CU-004c: surface reasoning + tool visibility from the run's
        # steps before the final answer events. Yielded in chronological
        # order (matches the SSE consumer's expectation of "reasoning
        # then answer").
        async for step_event in self._emit_run_step_events(
            thread_id=thread.id, run_id=run.id
        ):
            yield step_event
        # Filter by `run_id` so we only surface messages produced by
        # *this* run, not any prior assistant turns that may exist on
        # a reused thread. Defensive: today the wiring uses a fresh
        # thread per call, but this protects against future regressions.
        seen_assistant = False
        async for thread_msg in self._agents.messages.list(
            thread_id=thread.id,
            run_id=run.id,
            order=ListSortOrder.ASCENDING,
        ):
            if thread_msg.role != MessageRole.AGENT:
                continue
            content = self._extract_text(thread_msg)
            if not content:
                continue
            seen_assistant = True
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ANSWER, content=content
            )
        if not seen_assistant:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content="Agent produced no assistant reply.",
            )

    async def aclose(self) -> None:
        # The AgentsClient is owned by the wiring layer (task #22); the
        # orchestrator must NOT close it -- other callers may still hold
        # a reference. Override the no-op base only when the orchestrator
        # owns disposable resources of its own.
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _emit_run_step_events(
        self, *, thread_id: str, run_id: str
    ) -> AsyncIterator[OrchestratorEvent]:
        """Walk a run's steps and emit reasoning / tool events.

        Iterates ``run_steps.list(thread_id, run_id, ASCENDING)`` and
        translates each ``RunStep`` into ``OrchestratorEvent``s on the
        locked channel set:

        * ``step.step_details.type == "tool_calls"`` -> one ``tool``
          event per tool call (the agent equivalent of LangGraph's
          ``reasoning`` panel: shows what the agent decided to do).
          Content is the tool name; ``metadata`` carries the tool
          ``id``, ``type`` and a serialized ``arguments`` snippet.
        * ``step.step_details.type == "message_creation"`` -> skipped
          (the assistant message is surfaced by the subsequent
          ``messages.list`` walk as an ``answer`` event).
        * Any ``reasoning_content`` string surfaced by the SDK on the
          step or its details is emitted on the ``reasoning`` channel
          (o-series-backed agents).

        Defensive about SDK shape: every attribute access goes through
        ``getattr(..., default)`` because the Agents SDK occasionally
        renames union discriminators between minor versions and we
        don't want a missing field to crash a successful run -- worst
        case we emit fewer events than ideal, never more.
        """
        run_steps = getattr(self._agents, "run_steps", None)
        if run_steps is None:
            return  # SDK older than the run_steps surface; skip silently.
        async for step in run_steps.list(
            thread_id=thread_id,
            run_id=run_id,
            order=ListSortOrder.ASCENDING,
        ):
            details = getattr(step, "step_details", None)
            if details is None:
                continue
            # Reasoning trace (o-series-backed agents). Surface first so
            # the FE panel updates before any tool-call traces.
            reasoning = getattr(details, "reasoning_content", None) or getattr(
                step, "reasoning_content", None
            )
            if reasoning:
                yield OrchestratorEvent(
                    channel=OrchestratorChannel.REASONING, content=str(reasoning)
                )
            details_type = getattr(details, "type", None)
            if details_type == "tool_calls":
                # `tool_calls` is a heterogeneous SDK union (function /
                # code_interpreter / file_search / bing_grounding); cast
                # to `list[Any]` so the `getattr(call, ...)` cascade
                # below doesn't leak `Unknown` into pyright.
                tool_calls = cast(
                    list[Any], getattr(details, "tool_calls", None) or []
                )
                for call in tool_calls:
                    name = (
                        getattr(call, "type", None)
                        or getattr(call, "name", None)
                        or "tool"
                    )
                    metadata: dict[str, Any] = {
                        "id": getattr(call, "id", ""),
                        "type": getattr(call, "type", ""),
                    }
                    arguments = self._extract_tool_arguments(call)
                    if arguments:
                        metadata["arguments"] = arguments
                    yield OrchestratorEvent(
                        channel=OrchestratorChannel.TOOL,
                        content=str(name),
                        metadata=metadata,
                    )

    @staticmethod
    def _extract_tool_arguments(tool_call: Any) -> str:
        """Pull a printable arguments string out of a tool-call union.

        The SDK's tool-call detail shape varies by tool kind
        (``function`` carries ``function.arguments``; built-in tools
        like ``code_interpreter`` / ``file_search`` carry their own
        sub-objects). We only need a short trace here, so we try the
        common ``function.arguments`` path and fall back to ``str()``
        of any nested detail object so the trace is non-empty for
        every tool kind.
        """
        function = getattr(tool_call, "function", None)
        if function is not None:
            args = getattr(function, "arguments", None)
            if args:
                return str(args)
        for attr in ("code_interpreter", "file_search", "bing_grounding"):
            sub = getattr(tool_call, attr, None)
            if sub is not None:
                return str(sub)
        return ""

    @staticmethod
    def _to_agent_role(role: str) -> MessageRole | None:
        # Returns None for roles the Agents API doesn't accept on a
        # thread message:
        #   - `system`: belongs in the agent's `instructions` (set at
        #     create-time), NOT on per-thread messages.
        #   - `tool`: tool-call outputs are wired via task #20
        #     (`shared/tools/`); until then, drop them.
        if role == "user":
            return MessageRole.USER
        if role == "assistant":
            return MessageRole.AGENT
        return None

    @staticmethod
    def _extract_text(thread_msg: Any) -> str:
        """Pull the text out of a `ThreadMessage`.

        Agent message content is a list of typed blocks (text, image,
        file). We concatenate all text blocks in order; non-text blocks
        are ignored (citations are surfaced separately by task #23).
        """
        parts: list[str] = []
        for block in getattr(thread_msg, "content", []) or []:
            text_block = getattr(block, "text", None)
            value = getattr(text_block, "value", None) if text_block is not None else None
            if value:
                parts.append(value)
        return "".join(parts)
