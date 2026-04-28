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
    3. read back the assistant message(s) added to the thread
    4. yield a single `answer` event per assistant message (ADR 0007)

The `llm` dependency is unused today -- the Agent owns its own model
deployment in Foundry. We still take it via the ABC contract so
swapping orchestrators is configuration-only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence

from azure.ai.agents.models import ListSortOrder, MessageRole

from shared.types import ChatMessage, OrchestratorEvent

from . import registry
from .base import OrchestratorBase

if TYPE_CHECKING:
    from azure.ai.agents.aio import AgentsClient

    from providers.llm.base import BaseLLMProvider
    from shared.settings import AppSettings


@registry.register("agent_framework")
class AgentFrameworkOrchestrator(OrchestratorBase):
    def __init__(
        self,
        settings: "AppSettings",
        llm: "BaseLLMProvider",
        *,
        agents_client: "AgentsClient",
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
                channel="error",
                content=f"Agent run failed: {getattr(run, 'last_error', 'unknown')}",
            )
            return
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
            yield OrchestratorEvent(channel="answer", content=content)
        if not seen_assistant:
            yield OrchestratorEvent(
                channel="error",
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
