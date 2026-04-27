"""Foundry IQ-backed LLM provider.

Pillar: Stable Core
Phase: 2

Wraps `azure.ai.projects.aio.AIProjectClient`, which exposes an
`AsyncOpenAI`-compatible client via `get_openai_client()`. Foundry IQ
routes the call to the right Azure OpenAI deployment under the project
account -- no per-deployment endpoints, no per-deployment keys.

Why we don't `from openai import ...`: hard rule #7 bans direct openai
SDK usage in `v2/src/{shared,providers,pipelines}/**`. We *use* the
client object returned by Foundry, but never import its type, so the
ban is structurally enforced (grep stays clean).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence

from azure.ai.projects.aio import AIProjectClient

from shared.types import ChatChunk, ChatMessage, EmbeddingResult

from . import registry
from .base import BaseLLMProvider

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


@registry.register("foundry_iq")
class FoundryIQ(BaseLLMProvider):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
        *,
        project_client: AIProjectClient | None = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests to inject a fake AIProjectClient. Production path
        # constructs lazily so we don't open an HTTP session at import.
        self._project_client_override = project_client
        self._project_client: AIProjectClient | None = project_client

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
        oai = self._get_project_client().get_openai_client()
        kwargs: dict[str, Any] = {
            "model": self._resolve_deployment(deployment, kind="chat"),
            "messages": self._to_openai_messages(messages),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = await oai.chat.completions.create(**kwargs)
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
        oai = self._get_project_client().get_openai_client()
        kwargs: dict[str, Any] = {
            "model": self._resolve_deployment(deployment, kind="chat"),
            "messages": self._to_openai_messages(messages),
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        stream = await oai.chat.completions.create(**kwargs)
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
        oai = self._get_project_client().get_openai_client()
        model = self._resolve_deployment(deployment, kind="embed")
        response = await oai.embeddings.create(model=model, input=list(inputs))
        return EmbeddingResult(
            vectors=[item.embedding for item in response.data],
            model=model,
        )

    async def reason(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
    ) -> ChatMessage:
        # Reasoning-model integration (o-series) is task #25 in
        # v2/docs/development_plan.md and ships in Phase 7. Until then
        # the contract is declared but unimplemented so callers fail
        # loudly instead of silently routing to a chat deployment.
        raise NotImplementedError(
            "FoundryIQ.reason() is reserved for task #25 (Phase 7 -- "
            "o-series reasoning model routing)."
        )

    async def aclose(self) -> None:
        # We only own the client when we constructed it ourselves.
        if self._project_client is not None and self._project_client_override is None:
            await self._project_client.close()
            self._project_client = None
