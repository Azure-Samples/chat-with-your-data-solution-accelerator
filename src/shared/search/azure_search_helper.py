"""Search layer: factory + Azure AI Search handler (hybrid & semantic)."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import tiktoken
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery, VectorizedQuery

from shared.common.answer import SourceDocument

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings
    from shared.llm.llm_helper import LLMHelper

logger = logging.getLogger(__name__)

_ENCODER_NAME = "cl100k_base"
_VECTOR_FIELD = "content_vector"
_IMAGE_VECTOR_FIELD = "image_vector"


# ── Shared helpers ───────────────────────────────────────────────


def _build_search_client(settings: EnvSettings) -> SearchClient:
    """Build a SearchClient with the correct credential type."""
    search = settings.search
    if settings.auth.azure_auth_type == "keys":
        credential = AzureKeyCredential(search.key)
    else:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
    return SearchClient(
        endpoint=f"https://{search.service}.search.windows.net",
        index_name=search.index,
        credential=credential,
    )


# ── Abstract base ─────────────────────────────────────────────────


class SearchHandlerBase(ABC):
    @abstractmethod
    def query_search(self, question: str) -> list[SourceDocument]:
        ...


# ── Azure AI Search handler (push / hybrid / semantic) ───────────


class AzureSearchHandler(SearchHandlerBase):
    """Hybrid + semantic search against an Azure AI Search index.

    Generates client-side embeddings via the raw OpenAI API, using
    tokenized input (as the old CWYD did).
    """

    def __init__(self, settings: EnvSettings, llm_helper: LLMHelper) -> None:
        self.settings = settings
        self.llm_helper = llm_helper
        self.search_client = _build_search_client(settings)
        self._encoder = tiktoken.get_encoding(_ENCODER_NAME)

    def query_search(self, question: str) -> list[SourceDocument]:
        tokenised = self._encoder.encode(question)
        embedding = self.llm_helper.generate_embeddings(tokenised)
        search = self.settings.search

        if search.use_semantic_search:
            # Semantic: filter only on the search request, not on the vector query
            vector_query = VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=search.top_k,
                fields=_VECTOR_FIELD,
            )
            results = self.search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                filter=search.filter or None,
                query_type="semantic",
                semantic_configuration_name=search.semantic_search_config,
                query_caption="extractive",
                query_answer="extractive",
                top=search.top_k,
            )
        else:
            # Hybrid: filter on vector query too (matches old behaviour)
            vector_query = VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=search.top_k,
                fields=_VECTOR_FIELD,
                filter=search.filter or None,
            )
            results = self.search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                query_type="simple",
                filter=search.filter or None,
                top=search.top_k,
            )

        return self._convert(results)

    @staticmethod
    def _convert(results) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        for r in results:
            docs.append(
                SourceDocument(
                    id=r.get("id", ""),
                    content=r.get("content", ""),
                    title=r.get("title", ""),
                    source=r.get("source", ""),
                    chunk=r.get("chunk"),
                    offset=r.get("offset"),
                    page_number=r.get("page_number"),
                    chunk_id=r.get("chunk_id"),
                )
            )
        return docs


# ── Integrated Vectorization handler (server-side embeddings) ────


class IntegratedVectorizationSearchHandler(SearchHandlerBase):
    """Uses VectorizableTextQuery — the search service generates embeddings."""

    def __init__(self, settings: EnvSettings) -> None:
        self.settings = settings
        self.search_client = _build_search_client(settings)

    def query_search(self, question: str) -> list[SourceDocument]:
        search = self.settings.search

        vector_query = VectorizableTextQuery(
            text=question,
            k_nearest_neighbors=search.top_k,
            fields=_VECTOR_FIELD,
            exhaustive=True,
        )

        if search.use_semantic_search:
            results = self.search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                filter=search.filter or None,
                query_type="semantic",
                semantic_configuration_name=search.semantic_search_config,
                query_caption="extractive",
                query_answer="extractive",
                top=search.top_k,
            )
        else:
            results = self.search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                top=search.top_k,
            )

        return self._convert(results)

    @staticmethod
    def _extract_source_url(original_source: str) -> str:
        """Handle double-URL sources from integrated vectorization."""
        if not original_source:
            return ""
        matches = list(re.finditer(r"https?://", original_source))
        if len(matches) > 1:
            return original_source[matches[1].start() :]
        return original_source + "_SAS_TOKEN_PLACEHOLDER_"

    @staticmethod
    def _convert(results) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        for r in results:
            docs.append(
                SourceDocument(
                    id=r.get("id", ""),
                    content=r.get("content", ""),
                    title=r.get("title", ""),
                    source=IntegratedVectorizationSearchHandler._extract_source_url(
                        r.get("source", "")
                    ),
                    chunk_id=r.get("chunk_id"),
                )
            )
        return docs


# ── Factory ──────────────────────────────────────────────────────


class SearchFactory:
    """Creates the appropriate search handler based on settings."""

    @staticmethod
    def get_handler(settings: EnvSettings, llm_helper: LLMHelper) -> SearchHandlerBase:
        if settings.database.database_type.lower() == "postgresql":
            from shared.search._postgres_handler import PostgresSearchHandler

            return PostgresSearchHandler(settings, llm_helper)

        if settings.search.use_integrated_vectorization:
            return IntegratedVectorizationSearchHandler(settings)

        return AzureSearchHandler(settings, llm_helper)

    @staticmethod
    def get_source_documents(
        handler: SearchHandlerBase, question: str
    ) -> list[SourceDocument]:
        return handler.query_search(question)
