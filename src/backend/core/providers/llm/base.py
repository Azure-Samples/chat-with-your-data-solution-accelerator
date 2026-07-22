"""LLM provider ABC.

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

from backend.core.settings import AppSettings
from backend.core.types import (
    ChatChunk,
    ChatMessage,
    EmbeddingResult,
    OrchestratorChannel,
    OrchestratorEvent,
)


class BaseLLMProvider(ABC):
    def __init__(self, settings: AppSettings, credential: AsyncTokenCredential) -> None:
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

        - `OrchestratorChannel.REASONING` -- chain-of-thought tokens
          (rendered in the frontend's collapsible reasoning panel).
        - `OrchestratorChannel.ANSWER` -- the final answer tokens.

        Implementations stream from the given ``deployment``, defaulting
        to the chat deployment when none is passed; the deployment must
        be a reasoning-capable model to emit chain-of-thought summaries.
        """

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Unified streaming completion with auto-routing.

        Concrete on the ABC (not abstract) so every provider gets it
        for free without re-implementing the routing logic. Orchestrators
        and pipelines call THIS method instead of ``chat()`` or
        ``reason()`` directly so adding a new orchestrator library
        never grows per-library reasoning-vs-chat dispatch.

        The base delegates to ``self.chat()`` -- forwarding the optional
        ``temperature`` / ``max_tokens`` sampling parameters -- and
        yields a single ``answer``-channel event with the assistant
        content. ``chat`` failures are surfaced as a single ``error``
        event with ``metadata.code == "complete_chat_failed"`` so the
        SSE consumer never crashes mid-stream.

        A provider MAY override this method to stream reasoning: the
        production ``FoundryIQ`` provider probes the answer model's
        reasoning capability and, when supported, streams a
        chain-of-thought summary on the ``reasoning`` channel alongside
        the ``answer`` tokens. The contract is "yields
        ``OrchestratorEvent`` on the locked channel set" with no other
        guarantees.
        """
        try:
            reply = await self.chat(
                messages,
                deployment=deployment,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 -- surface to SSE error channel
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content=str(exc),
                metadata={"code": "complete_chat_failed"},
            )
            return
        yield OrchestratorEvent(
            channel=OrchestratorChannel.ANSWER, content=reply.content
        )

    async def supports_reasoning(self, deployment: str | None = None) -> bool:
        """Whether the model behind ``deployment`` can emit a reasoning summary.

        Concrete on the ABC with a ``False`` default: a provider reports
        reasoning capability only when it can actually stream a
        chain-of-thought summary for the resolved deployment. Callers
        (``complete()`` and the orchestrators) use the result to decide
        whether to route the answer through the reasoning surface, so a
        provider that cannot reason degrades to plain chat with no
        caller-side branching and no configuration flag.

        ``deployment is None`` means "the default answer deployment"
        (``settings.openai.gpt_deployment``). A provider that determines
        capability by probing the model resolves the concrete deployment
        name before checking.
        """
        return False

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default implementation is a no-op."""
