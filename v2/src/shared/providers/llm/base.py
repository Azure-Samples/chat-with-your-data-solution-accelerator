"""LLM provider ABC.

Pillar: Stable Core
Phase: 2

Every concrete provider (`foundry_iq`, future swap-ins) inherits from
`BaseLLMProvider` and self-registers via `@registry.register("<key>")`.
Constructors take `AppSettings` + an `AsyncTokenCredential`; provider
classes never read env vars directly (settings is the boundary).

Lifecycle: providers may hold an SDK client (e.g. `AIProjectClient`)
that owns an HTTP transport. Callers are expected to invoke
`await provider.aclose()` during shutdown -- the FastAPI lifespan in
`backend/app.py` does this for the cached singleton.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Sequence

from azure.core.credentials_async import AsyncTokenCredential

from shared.settings import AppSettings
from shared.types import (
    ChatChunk,
    ChatMessage,
    EmbeddingResult,
    OrchestratorEvent,
)


class BaseLLMProvider(ABC):
    def __init__(
        self, settings: AppSettings, credential: AsyncTokenCredential
    ) -> None:
        self._settings = settings
        self._credential = credential

    @abstractmethod
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatMessage:
        """Single-shot chat completion. Returns the assistant message."""

    @abstractmethod
    def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Streamed chat completion. Yields deltas as `ChatChunk`s.

        Implementations are typically `async def` with `yield` -- the
        ABC declares the return type as `AsyncIterator[ChatChunk]` to
        match PEP 525 async generators.
        """

    @abstractmethod
    async def embed(
        self,
        inputs: Sequence[str],
        *,
        deployment: str | None = None,
    ) -> EmbeddingResult:
        """Embed one or more inputs into a dense vector."""

    @abstractmethod
    def reason(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Reasoning-model (o-series) completion.

        Yields `OrchestratorEvent`s on two channels:

        - `channel="reasoning"` -- chain-of-thought tokens (rendered in
          the frontend's collapsible reasoning panel).
        - `channel="answer"` -- the final answer tokens.

        Implementations route to the configured reasoning deployment.
        Wired end-to-end by task #25 in v2/docs/development_plan.md
        (Phase 7).
        """

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Unified streaming completion with auto-routing.

        Concrete on the ABC (not abstract) so every provider gets it
        for free without re-implementing the routing logic. Orchestrators
        and pipelines call THIS method instead of ``chat()`` or
        ``reason()`` directly so adding a new orchestrator library
        never grows per-library reasoning-vs-chat dispatch (CU-004a,
        2026-05-05 user direction).

        Routing rule:

        * When the resolved deployment matches
          ``settings.openai.reasoning_deployment`` (and the latter is
          non-empty), delegate to ``self.reason()`` and propagate every
          event it yields (``reasoning`` / ``answer`` / ``error``
          channels).
        * Otherwise, delegate to ``self.chat()`` and yield a single
          ``answer``-channel event with the assistant content. ``chat``
          failures are surfaced as a single ``error`` event with
          ``metadata.code == "complete_chat_failed"`` so the SSE
          consumer never crashes mid-stream.

        A provider MAY override this method to add provider-specific
        step-trace ``reasoning`` events (e.g. tool-call traces). The
        contract is "yields ``OrchestratorEvent`` on the locked channel
        set" with no other guarantees.
        """
        reasoning_deployment = self._settings.openai.reasoning_deployment
        chosen = deployment or self._settings.openai.gpt_deployment
        if reasoning_deployment and chosen == reasoning_deployment:
            async for event in self.reason(messages, deployment=chosen):
                yield event
            return
        try:
            reply = await self.chat(messages, deployment=deployment)
        except Exception as exc:  # noqa: BLE001 -- surface to SSE error channel
            yield OrchestratorEvent(
                channel="error",
                content=str(exc),
                metadata={"code": "complete_chat_failed"},
            )
            return
        yield OrchestratorEvent(channel="answer", content=reply.content)

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default implementation is a no-op."""
