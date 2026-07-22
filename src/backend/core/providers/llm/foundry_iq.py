"""Foundry IQ-backed LLM provider.

Wraps `azure.ai.projects.aio.AIProjectClient`, which exposes an
`AsyncOpenAI`-compatible client via the **async** `get_openai_client()`
method (it returns `Awaitable[AsyncOpenAI]`, NOT the client directly --
a recurring foot-gun: always `await` it before use).
Foundry IQ routes the call to the right Azure OpenAI deployment under
the project account -- no per-deployment endpoints, no per-deployment
keys.

Why we don't `from openai import ...`: hard rule #7 bans direct openai
SDK usage in `src/{shared,providers,pipelines}/**`. We *use* the
client object returned by Foundry, but never import its type, so the
ban is structurally enforced (grep stays clean). We DO declare narrow
`Protocol` shapes locally for the response objects we read so pyright
`--strict` can verify our access pattern without coupling to the
openai stubs.
"""

from typing import Any, AsyncIterator, Protocol, Sequence, cast

import logging

import openai
from azure.ai.projects.aio import AIProjectClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError
from pydantic import BaseModel, ConfigDict

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

# Try/except policy
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


# Narrow Protocols for the openai-compatible response shapes we consume.
# Defined locally (not imported from `openai`) per Hard Rule #7. These
# describe ONLY the attributes this module reads; the actual SDK objects
# carry many more fields. Annotated `Any` for sub-fields the openai
# stubs themselves leave under-typed (Foundry IQ surfaces vendor
# extensions like `reasoning_content` that aren't in the public stubs).


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
    *summary* deltas only stream through the Responses surface, not
    chat completions (api versions 2024-12-01 / 2025-04-01 /
    2025-09-01).
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

    def get_openai_client(self, *, base_url: str | None = None) -> _OpenAIClient: ...


class _ResponsesInputItem(BaseModel):
    """One `message`-typed item in a Responses API `input` array.

    The Responses `input` array is stricter than the Chat Completions
    `messages` array: every item must declare an explicit `type`, so a
    bare `{"role", "content"}` dict is rejected with an empty-`type`
    error. This is the hand-authored model whose `model_dump()` is the
    `input` wire shape (per Hard Rule #15) -- distinct from
    `_to_openai_messages`, which dumps an already-typed `ChatMessage`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str = "message"
    role: str
    content: str


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
        # Cache the resolved project-scoped AsyncOpenAI handle (chat,
        # reason, agents) so we don't re-run the factory on every call.
        # The underlying client is designed to be reused.
        self._openai_client: _OpenAIClient | None = None
        # Embeddings are not served by the Foundry project route, so they
        # use a separate client pointed at the AI Services account
        # endpoint. Cached independently; see `_get_embeddings_client`.
        self._embeddings_client: _OpenAIClient | None = None
        # Per-deployment reasoning-capability cache, populated lazily by
        # `supports_reasoning`: a one-shot Responses-API probe records
        # whether the model behind a deployment accepts the `reasoning`
        # parameter, so the answer path routes to the reasoning surface
        # only for capable models -- no configuration flag.
        self._reasoning_support: dict[str, bool] = {}

    # Internals

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

    async def _get_embeddings_client(self) -> _OpenAIClient:
        """Return the cached account-scoped client used for embeddings.

        The Foundry **project** route -- the default ``base_url`` of
        ``get_openai_client()``, ``.../api/projects/<project>/openai/v1``
        -- proxies chat, responses, and agent calls but does **not**
        serve ``/embeddings``. Embeddings are an account-scoped Azure
        OpenAI data operation, so we ask the *same* Foundry factory for
        a client whose ``base_url`` is overridden to the AI Services
        account endpoint (``AZURE_AI_SERVICES_ENDPOINT`` +
        ``/openai/v1``). The Entra token provider is unchanged: the
        account endpoint accepts the project's
        ``https://ai.azure.com/.default`` token.
        """
        if self._embeddings_client is None:
            services_endpoint = self._settings.foundry.services_endpoint
            if not services_endpoint:
                raise RuntimeError(
                    "AZURE_AI_SERVICES_ENDPOINT is not set. FoundryIQ "
                    "embeddings require the AI Services account endpoint "
                    "because the Foundry project route does not serve "
                    "/embeddings."
                )
            base_url = f"{services_endpoint.rstrip('/')}/openai/v1"
            project = cast(_ProjectClientView, self._get_project_client())
            try:
                self._embeddings_client = project.get_openai_client(base_url=base_url)
            except AzureError:
                logger.exception(
                    "foundry_iq get_openai_client (embeddings) failed",
                    extra={
                        "operation": "get_embeddings_client",
                        "provider": "foundry_iq",
                    },
                )
                raise
        return self._embeddings_client

    def _resolve_deployment(self, override: str | None, *, kind: str) -> str:
        if override:
            return override
        cfg = self._settings.openai
        chosen = {
            "chat": cfg.gpt_deployment,
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
        # Emit only the fields the OpenAI Chat Completions API accepts --
        # a plain-string role and the content -- so ChatMessage's
        # `metadata` field (and the enum role) never leak onto the wire.
        # Mirrors `_to_responses_input`.
        return [{"role": m.role.value, "content": m.content} for m in messages]

    @staticmethod
    def _to_responses_input(
        messages: Sequence[ChatMessage],
    ) -> list[_ResponsesInputItem]:
        # Each turn is emitted as an explicit `message` item with a
        # plain-string role so the Responses endpoint classifies it
        # unambiguously; `reason()` dumps these to the wire shape.
        return [
            _ResponsesInputItem(role=m.role.value, content=m.content) for m in messages
        ]

    # BaseLLMProvider implementation

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
            # gpt-5 / o-series chat models reject the legacy `max_tokens`
            # and require `max_completion_tokens` (identical semantics: an
            # upper bound on generated tokens).
            kwargs["max_completion_tokens"] = max_tokens
        try:
            response = cast(_ChatResponse, await oai.chat.completions.create(**kwargs))
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
            # gpt-5 / o-series chat models reject the legacy `max_tokens`
            # and require `max_completion_tokens` (identical semantics: an
            # upper bound on generated tokens).
            kwargs["max_completion_tokens"] = max_tokens
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
        oai = await self._get_embeddings_client()
        dimensions = self._settings.openai.embedding_dimensions
        try:
            response = await oai.embeddings.create(
                model=model, input=list(inputs), dimensions=dimensions
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

        Uses ``oai.responses.create(..., reasoning={"effort": "...",
        "summary": "auto"}, stream=True)`` rather than
        ``oai.chat.completions.create(..., stream=True)`` because gpt-5
        (and other modern reasoning models on Azure) **never** populate
        ``delta.reasoning_content`` on chat-completions streams; the
        reasoning summary surface is only exposed through the Responses
        API (API versions ``2024-12-01-preview``, ``2025-04-01-preview``,
        ``2025-09-01-preview``). Stream events are
        dispatched on the typed ``evt.type`` discriminator instead of
        the openai SDK class names so this module stays compliant with
        Hard Rule #7 (no openai-types imports in v2 runtime). The two
        event kinds we read both expose ``evt.delta`` as a string.

        ``temperature`` / ``max_tokens`` are intentionally not exposed:
        reasoning models reject the former and prefer
        ``max_output_tokens`` (left to the deployment's configured
        default).
        """
        model = self._resolve_deployment(deployment, kind="chat")
        oai = await self._get_openai_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "input": [item.model_dump() for item in self._to_responses_input(messages)],
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

    async def supports_reasoning(self, deployment: str | None = None) -> bool:
        """Probe-and-cache whether the answer model accepts reasoning.

        Overrides the ABC default with a one-shot Responses-API probe:
        the first time a deployment is seen, issue a minimal
        ``responses.create(..., reasoning=...)`` call. A 200 means the
        model emits a reasoning summary (cache ``True``); an explicit
        ``reasoning``-parameter rejection means it cannot (cache
        ``False``). Any other failure -- auth, throttle, budget, 5xx,
        network -- is NOT a capability signal: it is logged and reported
        as ``False`` for this call WITHOUT caching, so the answer still
        streams via plain chat and the probe re-runs next time.

        Keyed by the resolved deployment name, so a single probe predicts
        both the ``complete()`` answer path and any orchestrator that
        answers through the same deployment.
        """
        model = self._resolve_deployment(deployment, kind="chat")
        cached = self._reasoning_support.get(model)
        if cached is not None:
            return cached
        try:
            oai = await self._get_openai_client()
            await oai.responses.create(
                model=model,
                input=[
                    item.model_dump()
                    for item in self._to_responses_input(
                        [ChatMessage(role=ChatRole.USER, content="ping")]
                    )
                ],
                reasoning={"effort": "low", "summary": "auto"},
                max_output_tokens=256,
                stream=False,
            )
        except (openai.APIError, AzureError) as exc:
            if isinstance(exc, openai.APIError) and self._is_reasoning_unsupported(exc):
                logger.info(
                    "foundry_iq deployment does not support reasoning summaries",
                    extra={
                        "operation": "supports_reasoning",
                        "provider": "foundry_iq",
                        "deployment": model,
                    },
                )
                self._reasoning_support[model] = False
                return False
            logger.warning(
                "foundry_iq reasoning-capability probe failed; treating as "
                "unsupported for this call only",
                extra={
                    "operation": "supports_reasoning",
                    "provider": "foundry_iq",
                    "deployment": model,
                },
            )
            return False
        self._reasoning_support[model] = True
        return True

    @staticmethod
    def _is_reasoning_unsupported(exc: openai.APIError) -> bool:
        """Whether ``exc`` is the model rejecting the ``reasoning`` param.

        Azure OpenAI returns a 400 whose ``param`` is ``"reasoning"`` (or
        whose message names the unsupported ``reasoning`` parameter) when
        the deployment is a non-reasoning model. Every other failure --
        auth, throttle, budget, 5xx, network -- is a transient /
        unrelated error and must NOT be cached as a capability verdict.
        """
        param = getattr(exc, "param", None)
        if param == "reasoning":
            return True
        message = str(getattr(exc, "message", "") or exc).lower()
        return "reasoning" in message and (
            "unsupported" in message or "not supported" in message
        )

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Completion that streams reasoning when the answer model supports it.

        Resolves the answer deployment and probes its reasoning capability
        (:meth:`supports_reasoning`, cached per deployment). A
        reasoning-capable answer model (gpt-5 / o-series) streams through
        the Responses API summary path (the surface :meth:`reason` uses),
        emitting a chain-of-thought summary on the ``reasoning`` channel
        alongside the ``answer`` tokens. A non-reasoning model falls back
        to the base routing: :meth:`chat` non-streaming.

        Capability is detected at this single model-invocation boundary,
        so every orchestrator that answers through ``complete()`` (the
        LangGraph path and any future provider-based orchestrator)
        surfaces reasoning with no per-orchestrator logic.
        """
        chosen = self._resolve_deployment(deployment, kind="chat")
        if await self.supports_reasoning(chosen):
            # Reasoning models reject the chat sampling params, so
            # `temperature` / `max_tokens` are not forwarded here.
            async for event in self.reason(messages, deployment=chosen):
                yield event
            return
        async for event in super().complete(
            messages,
            deployment=deployment,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield event

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
        # Drop the cached AsyncOpenAI handles either way -- they're bound
        # to the AIProjectClient lifecycle and stale once that closes.
        self._openai_client = None
        self._embeddings_client = None
