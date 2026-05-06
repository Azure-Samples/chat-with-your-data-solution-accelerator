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

from typing import Any, AsyncIterable, Sequence, cast

import logging

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import (
    QueryType,
    VectorizedQuery,
)

from backend.core.settings import AppSettings
from backend.core.types import SearchResult

from . import registry
from .base import BaseSearch


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try/except policy (Phase C2d)
#
# Per v2/docs/exception_handling_policy.md (Provider entry-points + Lifespan
# rows): every `azure.search.documents.aio.SearchClient` call at the
# provider boundary catches `azure.core.exceptions.AzureError` (the
# umbrella for all azure-core SDK transport / service errors --
# `HttpResponseError`, `ServiceRequestError`, `ServiceResponseError`,
# `ClientAuthenticationError`, etc.), structured-logs via
# `logger.exception(..., extra={"operation": ..., "provider":
# "azure_search", "index_name": ...})`, and re-raises so the router /
# pipeline layer can translate to a sanitized HTTPException.
#
# `aclose()` widens the catch to `(AzureError, OSError)` and downgrades
# to `logger.warning` + swallow: shutdown is best-effort per the policy
# doc Lifespan row.
# ---------------------------------------------------------------------------


_DEFAULT_SELECT_FIELDS = ("id", "content", "title", "url")


@registry.register("AzureSearch")
class AzureSearch(BaseSearch):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
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
        # `client.search(...)` is typed `Awaitable[AsyncSearchItemPaged[Dict[Unknown, Unknown]]]`
        # in the azure-search-documents stubs; the leaked Unknowns force
        # a member-type suppression at the access plus a result cast so
        # `_to_result` (which expects `dict[str, Any]`) sees a typed dict.
        try:
            paged = cast(
                AsyncIterable[dict[str, Any]],
                await client.search(**kwargs),  # pyright: ignore[reportUnknownMemberType]
            )
            async for doc in paged:
                results.append(self._to_result(doc))
        except AzureError:
            # The single try wraps both the initial paged-iterator setup
            # AND the `async for doc in paged` iteration -- both are
            # azure-core transport calls under the covers, and either
            # can raise `HttpResponseError` (4xx/5xx) or
            # `ServiceRequestError` (transport-level). Any partially-
            # filled `results` are dropped: the caller treats the
            # search as failed, not as a degraded partial response.
            logger.exception(
                "azure_search client.search failed",
                extra={
                    "operation": "search",
                    "provider": "azure_search",
                    "index_name": self._settings.search.index,
                },
            )
            raise
        return results

    async def aclose(self) -> None:
        # Only close the client when we constructed it ourselves.
        if self._client is not None and self._client_override is None:
            try:
                await self._client.close()
            except (AzureError, OSError):
                # Lifespan shutdown is best-effort: the container is
                # going away regardless. Log at WARNING so the failure
                # is visible without crashing the shutdown sequence.
                logger.warning(
                    "azure_search SearchClient.close failed",
                    extra={
                        "operation": "aclose",
                        "provider": "azure_search",
                        "index_name": self._settings.search.index,
                    },
                )
            self._client = None
