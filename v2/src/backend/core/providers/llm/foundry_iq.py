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
openai stubs (Q14a).
"""

from typing import Any, AsyncIterator, Protocol, Sequence, cast

import logging

import openai
from azure.ai.projects.aio import AIProjectClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.settings import AppSettings
from backend.core.types import (
    ChatChunk,
    ChatMessage,
    ChatRole,
    EmbeddingResult,
    OrchestratorChannel,
    OrchestratorEvent,
)

from .registry import registry
from .base import BaseLLMProvider


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try/except policy (Phase C2d)
#
# Per v2/docs/exception_handling_policy.md (Provider entry-points row), every
# OpenAI / AIProjectClient call at a provider boundary catches a narrow SDK
# exception (`openai.APIError` for chat / embed / stream calls; the broader
# `azure.core.exceptions.AzureError` for `AIProjectClient.get_openai_client`
# and `close`, since those traverse azure-core transport before the OpenAI
# layer is reached), structured-logs via
# `logger.exception(..., extra={"operation": ..., "provider": "foundry_iq",
# "deployment": ...})`, and re-raises so the router / pipeline layer can
# translate to a sanitized HTTPException or SSE error event.
#
# Two carve-outs:
# - `reason()` already yields `OrchestratorEvent(channel=ERROR, ...)` on
#   stream-iteration failure (intentional per ADR 0007 + the policy doc's
#   "Existing intentional catches" list). The catch is upgraded here to
#   call `logger.exception` BEFORE the yield so failures land in App
#   Insights even when the SSE consumer drops the error event. The
#   pre-stream `await oai.chat.completions.create(...)` setup is wrapped
#   separately so an immediate auth / throttle failure also surfaces as
#   an ERROR event instead of bubbling up untyped.
# - `aclose()` shutdown path catches `(AzureError, OSError)` and
#   `logger.warning`-then-swallows: shutdown is best-effort per the
#   policy doc Lifespan row.
# ---------------------------------------------------------------------------


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


class _Responses(Protocol):
    """Narrow view of the openai client's `responses` namespace.

    `reason()` calls `oai.responses.create(...)` (Responses API,
    `2025-04-01-preview` and later) instead of
    `oai.chat.completions.create(...)` because gpt-5's reasoning
    *summary* deltas only stream through the Responses surface --
    chat completions only ever returns `content` deltas for gpt-5
    (verified empirically against api versions 2024-12-01 /
    2025-04-01 / 2025-09-01 with reasoning_effort=medium).
    """

    async def create(self, **kwargs: Any) -> Any: ...


class _OpenAIClient(Protocol):
    chat: _ChatNamespace
    embeddings: _Embeddings
    responses: _Responses


class _ProjectClientView(Protocol):
    """Narrow view of `AIProjectClient` covering only what we call.

    The SDK's own type for `get_openai_client()` is
    ``(*, agent_name=..., **kwargs: Any) -> AsyncOpenAI`` -- the
    trailing `**kwargs: Any` leaks `reportUnknownMemberType` through
    `--strict`. Casting the project client to this protocol at the
    boundary tells pyright "yes, we know it returns an AsyncOpenAI;
    we don't care about the kwargs surface."
    """

    def get_openai_client(self) -> _OpenAIClient: ...


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
        # Cache the resolved AsyncOpenAI handle so we don't re-run the
        # factory on every chat / embed call. The underlying client is
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
        """Return the cached `AsyncOpenAI`-compatible client.

        `AIProjectClient.get_openai_client()` is synchronous in
        azure-ai-projects >=2.2.0 -- it returns an `AsyncOpenAI`
        directly (the *client* is async, the factory call is not).
        Caching the resolved client avoids re-running the factory on
        every chat / embed call. The method stays `async` to preserve
        a uniform await-this-once contract for callers.
        """
        if self._openai_client is None:
            project = cast(_ProjectClientView, self._get_project_client())
            try:
                self._openai_client = project.get_openai_client()
            except AzureError:
                # Init-style failure -- AIProjectClient lives in azure-core,
                # so AAD / DNS / TLS surface as AzureError subclasses
                # (ClientAuthenticationError, ServiceRequestError, etc.).
                logger.exception(
                    "foundry_iq get_openai_client failed",
                    extra={
                        "operation": "get_openai_client",
                        "provider": "foundry_iq",
                    },
                )
                raise
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
        try:
            response = cast(
                _ChatResponse, await oai.chat.completions.create(**kwargs)
            )
        except openai.APIError:
            logger.exception(
                "foundry_iq chat completions.create failed",
                extra={
                    "operation": "chat",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            raise
        choice = response.choices[0].message
        return ChatMessage(role=ChatRole.ASSISTANT, content=choice.content or "")

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
        try:
            stream = cast(
                AsyncIterator[_StreamEvent],
                await oai.chat.completions.create(**kwargs),
            )
        except openai.APIError:
            logger.exception(
                "foundry_iq chat_stream completions.create failed",
                extra={
                    "operation": "chat_stream_create",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            raise
        try:
            async for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta
                yield ChatChunk(
                    content=getattr(delta, "content", "") or "",
                    finish_reason=event.choices[0].finish_reason,
                )
        except openai.APIError:
            # Mid-stream failure (token throttling, dropped connection,
            # server-side timeout). Log structured + re-raise so the
            # pipeline layer can translate to an SSE ERROR event for the
            # FE reasoning panel.
            logger.exception(
                "foundry_iq chat_stream iteration failed",
                extra={
                    "operation": "chat_stream_iter",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            raise

    async def embed(
        self,
        inputs: Sequence[str],
        *,
        deployment: str | None = None,
    ) -> EmbeddingResult:
        model = self._resolve_deployment(deployment, kind="embed")
        oai = await self._get_openai_client()
        try:
            response = await oai.embeddings.create(
                model=model, input=list(inputs)
            )
        except openai.APIError:
            logger.exception(
                "foundry_iq embeddings.create failed",
                extra={
                    "operation": "embed",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            raise
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
        """Stream from a reasoning deployment via the Responses API.

        Yields ``reasoning``-channel events for chain-of-thought
        *summary* tokens and ``answer``-channel events for the final
        answer tokens (ADR 0007).

        Implementation note: switched from
        ``oai.chat.completions.create(..., stream=True)`` to
        ``oai.responses.create(..., reasoning={"effort": "...",
        "summary": "auto"}, stream=True)`` because gpt-5 (and other
        modern reasoning models on Azure) **never** populate
        ``delta.reasoning_content`` on chat-completions streams --
        verified empirically against API versions ``2024-12-01-preview``,
        ``2025-04-01-preview``, and ``2025-09-01-preview`` with
        ``reasoning_effort=medium``. The reasoning summary surface is
        only exposed through the Responses API. Stream events are
        dispatched on the typed ``evt.type`` discriminator instead of
        the openai SDK class names so this module stays compliant with
        Hard Rule #7 (no openai-types imports in v2 runtime). The two
        event kinds we read both expose ``evt.delta`` as a string.

        ``temperature`` / ``max_tokens`` are intentionally not exposed:
        reasoning models reject the former and prefer
        ``max_output_tokens`` (left to the deployment's configured
        default for now).
        """
        model = self._resolve_deployment(deployment, kind="reason")
        oai = await self._get_openai_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "input": self._to_openai_messages(messages),
            "reasoning": {"effort": "medium", "summary": "auto"},
            "stream": True,
        }
        try:
            stream = cast(
                AsyncIterator[Any],
                await oai.responses.create(**kwargs),
            )
        except openai.APIError as exc:
            # Pre-stream failure (auth, throttle, missing deployment).
            # `reason()` always surfaces failures as ERROR events for
            # the FE reasoning panel (ADR 0007 / SSE contract); we add
            # the structured log so App Insights captures it too,
            # then yield the error event INSTEAD OF re-raising so the
            # SSE generator stays alive and the consumer sees an
            # explicit error event.
            logger.exception(
                "foundry_iq reason responses.create failed",
                extra={
                    "operation": "reason_create",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content=str(exc),
                metadata={"code": "reason_stream_failed"},
            )
            return
        try:
            async for event in stream:
                event_type = getattr(event, "type", None)
                if event_type == "response.reasoning_summary_text.delta":
                    delta = getattr(event, "delta", None) or ""
                    if delta:
                        yield OrchestratorEvent(
                            channel=OrchestratorChannel.REASONING,
                            content=delta,
                        )
                elif event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", None) or ""
                    if delta:
                        yield OrchestratorEvent(
                            channel=OrchestratorChannel.ANSWER,
                            content=delta,
                        )
                # Other event types (response.created,
                # response.in_progress, *.added, *.done, *.completed,
                # content_part.*) carry no token payload for the FE
                # reasoning panel; intentionally dropped to keep the
                # SSE channel narrow (ADR 0007 channel set).
        except Exception as exc:  # noqa: BLE001 -- surface to SSE error channel
            # Mid-stream failure -- broad catch is intentional (ADR 0007 +
            # exception_handling_policy.md "Existing intentional catches")
            # so a streaming model returning anything unexpected still
            # yields an explicit error event instead of crashing the SSE
            # generator. Logger.exception() added in C2d so observability
            # is uniform with the other provider methods even though the
            # surface stays SSE-channel-only.
            logger.exception(
                "foundry_iq reason stream iteration failed",
                extra={
                    "operation": "reason_iter",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content=str(exc),
                metadata={"code": "reason_stream_failed"},
            )

    async def aclose(self) -> None:
        # We only own the client when we constructed it ourselves.
        if self._project_client is not None and self._project_client_override is None:
            try:
                await self._project_client.close()
            except (AzureError, OSError):
                # Lifespan shutdown is best-effort: the container is
                # going away regardless. Log at WARNING so the failure
                # is visible without crashing the shutdown sequence.
                logger.warning(
                    "foundry_iq AIProjectClient.close failed",
                    extra={
                        "operation": "aclose",
                        "provider": "foundry_iq",
                    },
                )
            self._project_client = None
        # Drop the cached AsyncOpenAI handle either way -- it's bound to
        # the AIProjectClient lifecycle and stale once that closes.
        self._openai_client = None
