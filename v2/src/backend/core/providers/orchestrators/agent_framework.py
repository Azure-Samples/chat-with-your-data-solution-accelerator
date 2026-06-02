"""Microsoft Agent Framework (OSS) orchestrator.

Pillar: Stable Core
Phase: 3

Invokes a Foundry-hosted Agent through the open-source
`agent_framework_foundry.FoundryAgent` client. The agent itself is
provisioned out-of-band (see `backend.core.providers.agents.base.
BaseAgentsProvider.get_or_create_agent`); this class only invokes it
by name. Construction is dependency-injected: the target `agent_name`
and an `AsyncTokenCredential` come from the wiring layer in
`dependencies.py`, keeping the orchestrator free of SDK construction
concerns and trivially testable.

Run loop:
    1. Convert inbound `ChatMessage`s to OSS `Message`s.
    2. Construct a per-request `FoundryAgent` (the project endpoint
       comes from `settings.foundry.project_endpoint`).
    3. Stream `agent.run(messages, stream=True)` and translate each
       `AgentResponseUpdate.contents` block to an `OrchestratorEvent`
       on the locked channel set:
         * `text`           -> buffered, flushed as a single `answer`
         * `text_reasoning` -> `reasoning` event
         * `function_call`  -> `tool` event with id / arguments
         * everything else  -> ignored
    4. Close the `FoundryAgent` (which owns the project client) in a
       `finally` so the per-request transport doesn't leak.

The `llm` dependency is unused -- the Agent owns its own model
deployment in Foundry. We still take it via the ABC contract so
swapping orchestrators is configuration-only.
"""

import json
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

from agent_framework import AgentResponseUpdate, Message
from agent_framework_foundry import FoundryAgent
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.settings import AppSettings
from backend.core.types import ChatMessage, OrchestratorChannel, OrchestratorEvent

from .registry import registry
from .base import OrchestratorBase

logger = logging.getLogger(__name__)


@registry.register("agent_framework")
class AgentFrameworkOrchestrator(OrchestratorBase):
    def __init__(
        self,
        settings: AppSettings,
        llm: BaseLLMProvider,
        *,
        agent_name: str,
        credential: AsyncTokenCredential,
        agent_factory: Any = None,
        **_extras: object,
    ) -> None:
        # `**_extras` swallows kwargs the router passes uniformly to every
        # orchestrator (e.g. `search` for `langgraph`). Avoids name-based
        # dispatch in the caller (Hard Rule #4).
        super().__init__(settings, llm)
        if not agent_name:
            raise ValueError(
                "AgentFrameworkOrchestrator requires a non-empty agent_name."
            )
        endpoint = settings.foundry.project_endpoint
        if not endpoint:
            raise ValueError(
                "AgentFrameworkOrchestrator requires "
                "settings.foundry.project_endpoint."
            )
        self._agent_name = agent_name
        self._credential = credential
        self._project_endpoint = endpoint
        # Test seam: callers (tests) may inject a callable that returns
        # a fake FoundryAgent. Defaults to the real constructor.
        self._agent_factory: Any = agent_factory or _default_agent_factory

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
        try:
            agent = self._agent_factory(
                project_endpoint=self._project_endpoint,
                agent_name=self._agent_name,
                credential=self._credential,
            )
        except AzureError:
            logger.exception(
                "FoundryAgent construction failed",
                extra={
                    "operation": "foundry_agent_init",
                    "provider": "agent_framework",
                    "agent_name": self._agent_name,
                },
            )
            raise

        try:
            answer_parts: list[str] = []
            saw_any_content = False

            try:
                stream = agent.run(oss_messages, stream=True)
                async for update in stream:
                    for event in self._update_to_events(update, answer_parts):
                        saw_any_content = True
                        yield event
            except AzureError as exc:
                logger.exception(
                    "FoundryAgent run failed",
                    extra={
                        "operation": "foundry_agent_run",
                        "provider": "agent_framework",
                        "agent_name": self._agent_name,
                    },
                )
                yield OrchestratorEvent(
                    channel=OrchestratorChannel.ERROR,
                    content=f"Agent run failed: {exc}",
                )
                return

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
        finally:
            close = getattr(agent, "close", None)
            if close is not None:
                try:
                    await close()
                except (AzureError, OSError):
                    logger.warning(
                        "FoundryAgent.close failed",
                        extra={
                            "operation": "foundry_agent_close",
                            "provider": "agent_framework",
                            "agent_name": self._agent_name,
                        },
                    )

    async def aclose(self) -> None:
        # The credential is owned by the wiring layer (stashed on
        # app.state at lifespan startup); the orchestrator must NOT
        # close it. The per-request FoundryAgent is closed in run()'s
        # finally block, so there is nothing else to release here.
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
    ) -> list[OrchestratorEvent]:
        """Map one streaming update's content blocks to events.

        Text blocks are accumulated into `answer_parts` (the caller
        flushes them as a single `answer` event after the stream
        completes); reasoning + function-call blocks are emitted
        immediately so the FE panel updates in stream-order.
        """
        events: list[OrchestratorEvent] = []
        for content in update.contents or []:
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


def _default_agent_factory(
    *,
    project_endpoint: str,
    agent_name: str,
    credential: AsyncTokenCredential,
) -> FoundryAgent:
    return FoundryAgent(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        credential=credential,
        allow_preview=True,
    )
