"""Foundry IQ-backed LLM provider.

Pillar: Stable Core
Phase: 2

Wraps `azure.ai.projects.aio.AIProjectClient`, which exposes an
`AsyncOpenAI`-compatible client via the **async** `get_openai_client()`
method (it returns `Awaitable[AsyncOpenAI]`, NOT the client directly --
a recurring foot-gun the Q14a fix corrected once and cached).
Foundry IQ routes the call to the right Azure OpenAI deployment under
the project account -- no per-deployment endpoints, no per-deployment
keys.

Why we don't `from openai import ...`: hard rule #7 bans direct openai
SDK usage in `v2/src/{shared,providers,pipelines}/**`. We *use* the
client object returned by Foundry, but never import its type, so the
ban is structurally enforced (grep stays clean). We DO declare narrow
`Protocol` shapes locally for the response objects we read so pyright
`--strict` can verify our access pattern without coupling to the
openai stubs (Q14a, 2026-05-05).
"""

from typing import Any, AsyncIterator, Protocol, Sequence, cast

from azure.ai.projects.aio import AIProjectClient
from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import (
    ChatChunk,
    ChatMessage,
    EmbeddingResult,
    OrchestratorChannel,
    OrchestratorEvent,
)

from . import registry
from .base import BaseLLMProvider


# ---------------------------------------------------------------------------
# Narrow Protocols for the openai-compatible response shapes we consume.
# Defined locally (not imported from `openai`) per Hard Rule #7. These
# describe ONLY the attributes this module reads; the actual SDK objects
# carry many more fields. Annotated `Any` for sub-fields the openai
# stubs themselves leave under-typed (Foundry IQ surfaces vendor
# extensions like `reasoning_content` that aren't in the public stubs).
# ---------------------------------------------------------------------------


class _ChatMessageView(Protocol):
    content: str | None


class _ChatChoice(Protocol):
    message: _ChatMessageView
    finish_reason: str | None


class _ChatResponse(Protocol):
    choices: list[_ChatChoice]


class _StreamDelta(Protocol):
    # `content` and `reasoning_content` are accessed via `getattr(..., None)`
    # because Foundry IQ surfaces them as vendor extensions; we keep them
    # off the Protocol so pyright doesn't expect them on every shape.
    pass


class _StreamChoice(Protocol):
    delta: _StreamDelta
    finish_reason: str | None


class _StreamEvent(Protocol):
    choices: list[_StreamChoice]


class _EmbeddingItem(Protocol):
    embedding: list[float]


class _EmbeddingResponse(Protocol):
    data: list[_EmbeddingItem]


class _ChatCompletions(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class _ChatNamespace(Protocol):
    completions: _ChatCompletions


class _Embeddings(Protocol):
    async def create(self, **kwargs: Any) -> _EmbeddingResponse: ...


class _OpenAIClient(Protocol):
    chat: _ChatNamespace
    embeddings: _Embeddings


class _ProjectClientView(Protocol):
    """Narrow view of `AIProjectClient` covering only what we call.

    The SDK's own type for `get_openai_client()` is
    ``(*, api_version=..., connection_name=..., **kwargs: Unknown) ->
    Awaitable[AsyncOpenAI]`` -- the trailing `**kwargs: Unknown`
    leaks `reportUnknownMemberType` through `--strict`. Casting the
    project client to this protocol at the boundary tells pyright
    "yes, we know it returns an awaitable client; we don't care about
    the kwargs surface."
    """

    async def get_openai_client(self) -> _OpenAIClient: ...


@registry.register("foundry_iq")
class FoundryIQ(BaseLLMProvider):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        project_client: AIProjectClient | None = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests to inject a fake AIProjectClient. Production path
        # constructs lazily so we don't open an HTTP session at import.
        self._project_client_override = project_client
        self._project_client: AIProjectClient | None = project_client
        # Q14a: cache the awaited AsyncOpenAI handle so we don't re-await
        # `get_openai_client()` on every call. The SDK returns a fresh
        # `Awaitable[AsyncOpenAI]` per call but the underlying client is
        # designed to be reused.
        self._openai_client: _OpenAIClient | None = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_project_client(self) -> AIProjectClient:
        if self._project_client is not None:
            return self._project_client
        endpoint = self._settings.foundry.project_endpoint
        if not endpoint:
            raise RuntimeError(
                "AZURE_AI_PROJECT_ENDPOINT is not set. FoundryIQ requires a "
                "Foundry project endpoint to construct AIProjectClient."
            )
        self._project_client = AIProjectClient(
            endpoint=endpoint, credential=self._credential
        )
        return self._project_client

    async def _get_openai_client(self) -> _OpenAIClient:
        """Return the cached `AsyncOpenAI`-compatible client, awaiting on first use.

        `AIProjectClient.get_openai_client()` is async (returns
        `Awaitable[AsyncOpenAI]`); calling it without `await` returned
        a coroutine that pyright `--strict` flagged as a
        `reportAttributeAccessIssue` and that would crash production at
        the first attribute access (the test mocks were sync, hiding
        the bug). Caching the resolved client also avoids re-awaiting
        on every chat / embed call.
        """
        if self._openai_client is None:
            project = cast(_ProjectClientView, self._get_project_client())
            self._openai_client = await project.get_openai_client()
        return self._openai_client

    def _resolve_deployment(self, override: str | None, *, kind: str) -> str:
        if override:
            return override
        cfg = self._settings.openai
        chosen = {
            "chat": cfg.gpt_deployment,
            "reason": cfg.reasoning_deployment,
            "embed": cfg.embedding_deployment,
        }[kind]
        if not chosen:
            raise RuntimeError(
                f"No {kind} deployment configured. Set the matching "
                f"AZURE_OPENAI_*_DEPLOYMENT env var or pass deployment=..."
            )
        return chosen

    @staticmethod
    def _to_openai_messages(
        messages: Sequence[ChatMessage],
    ) -> list[dict[str, Any]]:
        return [m.model_dump(exclude_none=True) for m in messages]

    # ------------------------------------------------------------------
    # BaseLLMProvider implementation
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatMessage:
        # Resolve config BEFORE opening the SDK client so missing-env
        # errors don't get masked by SDK auth / network failures.
        model = self._resolve_deployment(deployment, kind="chat")
        oai = await self._get_openai_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(messages),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = cast(
            _ChatResponse, await oai.chat.completions.create(**kwargs)
        )
        choice = response.choices[0].message
        return ChatMessage(role="assistant", content=choice.content or "")

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        model = self._resolve_deployment(deployment, kind="chat")
        oai = await self._get_openai_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(messages),
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        stream = cast(
            AsyncIterator[_StreamEvent],
            await oai.chat.completions.create(**kwargs),
        )
        async for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta
            yield ChatChunk(
                content=getattr(delta, "content", "") or "",
                finish_reason=event.choices[0].finish_reason,
            )

    async def embed(
        self,
        inputs: Sequence[str],
        *,
        deployment: str | None = None,
    ) -> EmbeddingResult:
        model = self._resolve_deployment(deployment, kind="embed")
        oai = await self._get_openai_client()
        response = await oai.embeddings.create(
            model=model, input=list(inputs)
        )
        return EmbeddingResult(
            vectors=[item.embedding for item in response.data],
            model=model,
        )

    async def reason(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Stream from a reasoning (o-series) deployment.

        Yields ``reasoning``-channel events for chain-of-thought tokens
        and ``answer``-channel events for the final answer tokens
        (ADR 0007). Implementation reads ``reasoning_content`` and
        ``content`` deltas from the streamed Chat Completions response;
        the OpenAI-compatible client returned by Foundry IQ surfaces
        both fields for o-series deployments.

        ``temperature`` / ``max_tokens`` are intentionally not exposed:
        o-series models reject the former and prefer
        ``max_completion_tokens`` (left to the deployment's configured
        default for now -- task #25 wires per-request knobs once the
        FE surfaces them).
        """
        model = self._resolve_deployment(deployment, kind="reason")
        oai = await self._get_openai_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(messages),
            "stream": True,
        }
        stream = cast(
            AsyncIterator[_StreamEvent],
            await oai.chat.completions.create(**kwargs),
        )
        try:
            async for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None) or ""
                if reasoning:
                    yield OrchestratorEvent(
                        channel=OrchestratorChannel.REASONING, content=reasoning
                    )
                answer = getattr(delta, "content", None) or ""
                if answer:
                    yield OrchestratorEvent(
                        channel=OrchestratorChannel.ANSWER, content=answer
                    )
        except Exception as exc:  # noqa: BLE001 -- surface to SSE error channel
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content=str(exc),
                metadata={"code": "reason_stream_failed"},
            )

    async def aclose(self) -> None:
        # We only own the client when we constructed it ourselves.
        if self._project_client is not None and self._project_client_override is None:
            await self._project_client.close()
            self._project_client = None
        # Drop the cached AsyncOpenAI handle either way -- it's bound to
        # the AIProjectClient lifecycle and stale once that closes.
        self._openai_client = None
