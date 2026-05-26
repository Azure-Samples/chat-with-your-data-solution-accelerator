"""Azure OpenAI embedder provider routed through Foundry IQ.

Pillar: Stable Core
Phase: 6

Implements the `BaseEmbedder` contract for ingestion pipelines by
converting `Chunk.content` values into embeddings via the LLM provider
registry (`foundry_iq`).
"""

import logging

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.providers.llm import registry as llm_registry
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.settings import AppSettings
from backend.core.types import Chunk, EmbeddingResult

from .base import BaseEmbedder
from .registry import registry


logger = logging.getLogger(__name__)


@registry.register("azure_openai")
class AzureOpenAIEmbedder(BaseEmbedder):
    """Embeds chunk text using the configured Azure OpenAI deployment."""

    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        llm_provider: BaseLLMProvider | None = None,
    ) -> None:
        self._settings = settings
        self._credential = credential
        self._llm_provider_override = llm_provider
        self._llm_provider = llm_provider

    def _get_llm_provider(self) -> BaseLLMProvider:
        if self._llm_provider is not None:
            return self._llm_provider
        self._llm_provider = llm_registry.registry.get("foundry_iq")(
            settings=self._settings,
            credential=self._credential,
        )
        return self._llm_provider

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        if not chunks:
            return []

        inputs = [chunk.content for chunk in chunks]
        provider = self._get_llm_provider()
        try:
            result = await provider.embed(
                inputs,
                deployment=self._settings.openai.embedding_deployment or None,
            )
        except AzureError:
            logger.exception(
                "azure_openai embed failed",
                extra={
                    "operation": "embed",
                    "provider": "azure_openai",
                    "deployment": self._settings.openai.embedding_deployment,
                },
            )
            raise

        if len(result.vectors) != len(chunks):
            raise RuntimeError(
                "Embedding vector count mismatch: expected "
                f"{len(chunks)} vectors, got {len(result.vectors)}."
            )

        return [result]

    async def aclose(self) -> None:
        if self._llm_provider is not None and self._llm_provider_override is None:
            await self._llm_provider.aclose()
            self._llm_provider = None
