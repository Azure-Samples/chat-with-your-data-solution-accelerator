"""Azure AI Search-backed provider.

Pillar: Stable Core
Phase: 3

Wraps `azure.search.documents.aio.SearchClient`. Hybrid retrieval:
free-text query is always sent; an optional `vector` enables
hybrid (text + vector) scoring. Semantic re-ranking is enabled
when `settings.search.use_semantic_search` is set and the index is
configured for it -- a missing semantic config falls back to keyword
scoring (the SDK ignores the flag).

Authentication is `AsyncTokenCredential` only (Hard Rule #2 / ADR 0002
-- no Key Vault, no shared keys). Pinning the index name to
`settings.search.index` keeps the surface tight; multi-index workloads
add another provider key with a different index.

Field mapping: the v1 indexer wrote chunks with these fields, kept
here so an upgrade-in-place doesn't need a reindex:

    id        -> SearchResult.id           (key field)
    content   -> SearchResult.content      (chunk text)
    title     -> SearchResult.title        (source filename)
    url       -> SearchResult.url          (blob SAS / source URI)
    @search.score / @search.reranker_score -> SearchResult.score

Callers needing custom field names can subclass and override
`_to_result()`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from azure.search.documents.aio import SearchClient
from azure.search.documents.models import (
    QueryType,
    VectorizedQuery,
)

from shared.types import SearchResult

from . import registry
from .base import BaseSearch

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


_DEFAULT_SELECT_FIELDS = ("id", "content", "title", "url")


@registry.register("azure_search")
class AzureSearch(BaseSearch):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
        *,
        client: SearchClient | None = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests to inject a fake SearchClient. Production path
        # constructs lazily so no HTTP session opens at import.
        self._client_override = client
        self._client: SearchClient | None = client

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self) -> SearchClient:
        if self._client is not None:
            return self._client
        endpoint = self._settings.search.endpoint
        index = self._settings.search.index
        if not endpoint:
            raise RuntimeError(
                "AZURE_AI_SEARCH_ENDPOINT is not set. AzureSearch requires a "
                "search service endpoint."
            )
        if not index:
            raise RuntimeError(
                "AZURE_AI_SEARCH_INDEX is not set. AzureSearch requires an "
                "index name."
            )
        self._client = SearchClient(
            endpoint=endpoint, index_name=index, credential=self._credential
        )
        return self._client

    def _to_result(self, doc: dict[str, Any]) -> SearchResult:
        # Instance method (not @staticmethod) so subclass overrides can
        # read `self._settings` for custom field names without changing
        # the call site.
        score = doc.get("@search.reranker_score") or doc.get("@search.score")
        return SearchResult(
            id=str(doc.get("id", "")),
            content=str(doc.get("content", "")),
            title=str(doc.get("title", "")),
            url=str(doc.get("url", "")),
            score=float(score) if score is not None else None,
        )

    # ------------------------------------------------------------------
    # BaseSearch implementation
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
    ) -> Sequence[SearchResult]:
        cfg = self._settings.search
        # `top_k if not None` (not `top_k or ...`) so an explicit 0
        # would propagate; today it'd 400 from the SDK, but the call
        # site stays honest.
        effective_top_k = top_k if top_k is not None else cfg.top_k
        kwargs: dict[str, Any] = {
            "search_text": query,
            "top": effective_top_k,
            "select": list(_DEFAULT_SELECT_FIELDS),
        }
        if filter_expression is not None:
            kwargs["filter"] = filter_expression
        if vector is not None:
            # k_nearest_neighbors mirrors `top` so vector and text
            # retrieval return comparable candidate pools before
            # semantic re-ranking merges them.
            kwargs["vector_queries"] = [
                VectorizedQuery(
                    vector=list(vector),
                    k_nearest_neighbors=effective_top_k,
                    fields="content_vector",
                )
            ]
        if cfg.use_semantic_search:
            kwargs["query_type"] = QueryType.SEMANTIC
            kwargs["semantic_configuration_name"] = "default"

        client = self._get_client()
        results: list[SearchResult] = []
        async for doc in await client.search(**kwargs):
            results.append(self._to_result(doc))
        return results

    async def aclose(self) -> None:
        # Only close the client when we constructed it ourselves.
        if self._client is not None and self._client_override is None:
            await self._client.close()
            self._client = None
