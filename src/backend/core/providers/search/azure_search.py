"""Azure AI Search-backed provider.

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
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import (
    QueryType,
    VectorizedQuery,
)

from backend.core.settings import AppSettings
from backend.core.types import SearchDocument, SearchResult

from .registry import registry
from .base import BaseSearch, SourceListing

logger = logging.getLogger(__name__)

# Try/except policy
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

    # Internals

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
            # A present-but-null `url` field makes `.get("url", "")` return
            # `None` (the default only fires when the key is absent), so coerce
            # falsy values to "" rather than stringifying `None` to "None".
            url=str(doc.get("url") or ""),
            score=float(score) if score is not None else None,
        )

    # BaseSearch implementation

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        use_semantic_search: bool | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
    ) -> Sequence[SearchResult]:
        cfg = self._settings.search
        # `top_k if not None` (not `top_k or ...`) so an explicit 0
        # would propagate; today it'd 400 from the SDK, but the call
        # site stays honest.
        effective_top_k = top_k if top_k is not None else cfg.top_k
        # Same None-means-default rule for the semantic flag so an
        # explicit per-call `False` can disable re-ranking even when the
        # settings default is on (and vice versa).
        effective_semantic = (
            use_semantic_search
            if use_semantic_search is not None
            else cfg.use_semantic_search
        )
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
        if effective_semantic:
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
                await client.search(
                    **kwargs
                ),  # pyright: ignore[reportUnknownMemberType]
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

    async def delete_by_source(self, source: str) -> int:
        # `title` is searchable but NOT filterable in the deployed index,
        # so a server-side `$filter` on it is rejected. Page every chunk
        # selecting `id` + `title` and match the source by exact equality
        # client-side -- the same index-schema-robust approach
        # `list_sources` uses for the not-facetable `title`. Matching
        # client-side also keeps the user-supplied filename out of any
        # OData expression, closing the injection seam a server-side
        # filter would open.
        client = self._get_client()
        ids: list[str] = []
        deleted_count = 0
        try:
            paged = cast(
                AsyncIterable[dict[str, Any]],
                await client.search(  # pyright: ignore[reportUnknownMemberType]
                    search_text="*",
                    select=["id", "title"],
                ),
            )
            async for doc in paged:
                if doc.get("title") != source:
                    continue
                doc_id = doc.get("id")
                if doc_id is not None:
                    ids.append(str(doc_id))
            # SDK's delete_documents caps at 1000 docs/batch; chunk to
            # stay under that even when a single source owns more chunks.
            batch_size = 1000
            for batch_start in range(0, len(ids), batch_size):
                batch = ids[batch_start : batch_start + batch_size]
                await client.delete_documents(  # pyright: ignore[reportUnknownMemberType]
                    documents=[{"id": doc_id} for doc_id in batch]
                )
                deleted_count += len(batch)
        except AzureError:
            logger.exception(
                "azure_search delete_by_source failed",
                extra={
                    "operation": "delete_by_source",
                    "provider": "azure_search",
                    "index_name": self._settings.search.index,
                    "source": source,
                    "deleted_count": deleted_count,
                },
            )
            raise
        return deleted_count

    async def list_sources(self) -> list[SourceListing]:
        # Page every chunk selecting only its `title` (the source
        # filename / URL) and aggregate distinct sources client-side.
        # Faceting on `title` is avoided: it fails on index schemas that
        # do not mark `title` as facetable (Code: FieldNotFacetable), so
        # paging keeps this robust to the deployed index schema. Sources
        # are returned sorted alphabetically for a deterministic admin
        # UI ordering.
        client = self._get_client()
        counts: dict[str, int] = {}
        try:
            paged = cast(
                AsyncIterable[dict[str, Any]],
                await client.search(  # pyright: ignore[reportUnknownMemberType]
                    search_text="*",
                    select=["title"],
                ),
            )
            async for doc in paged:
                title = doc.get("title")
                if title:
                    key = str(title)
                    counts[key] = counts.get(key, 0) + 1
        except AzureError:
            logger.exception(
                "azure_search list_sources failed",
                extra={
                    "operation": "list_sources",
                    "provider": "azure_search",
                    "index_name": self._settings.search.index,
                },
            )
            raise
        return [
            SourceListing(source=source, chunk_count=count, last_modified=None)
            for source, count in sorted(counts.items())
        ]

    async def get_document_by_key(self, key: str) -> SearchResult | None:
        client = self._get_client()
        try:
            # SDK boundary: SearchClient.get_document returns the raw
            # document fields as a dict; `_to_result` maps them onto the
            # provider-agnostic SearchResult (Hard Rule #15). A by-key
            # fetch carries no relevance score, so SearchResult.score is
            # None here.
            doc = cast(
                dict[str, Any],
                await client.get_document(  # pyright: ignore[reportUnknownMemberType]
                    key=key,
                    selected_fields=list(_DEFAULT_SELECT_FIELDS),
                ),
            )
        except ResourceNotFoundError:
            # Soft miss: a citation can reference a key that was since
            # re-ingested or deleted. Degrade to the raw id (the caller
            # treats None as "leave the citation unenriched") rather than
            # failing the answer. Narrow catch -- every other AzureError
            # still logs + re-raises below.
            return None
        except AzureError:
            logger.exception(
                "azure_search get_document_by_key failed",
                extra={
                    "operation": "get_document_by_key",
                    "provider": "azure_search",
                    "index_name": self._settings.search.index,
                },
            )
            raise
        return self._to_result(doc)

    async def merge_or_upload_documents(
        self,
        *,
        documents: Sequence[SearchDocument],
    ) -> list[Any]:
        if not documents:
            return []
        # Hard Rule #15: SearchDocument is the source of truth; the
        # `dict[str, Any]` payload below is the SDK boundary shape that
        # `SearchClient.merge_or_upload_documents` accepts.
        payload: list[dict[str, Any]] = [doc.model_dump() for doc in documents]
        client = self._get_client()
        try:
            return cast(
                list[Any],
                await client.merge_or_upload_documents(  # pyright: ignore[reportUnknownMemberType]
                    documents=payload
                ),
            )
        except AzureError:
            logger.exception(
                "azure_search merge_or_upload_documents failed",
                extra={
                    "operation": "merge_or_upload_documents",
                    "provider": "azure_search",
                    "index_name": self._settings.search.index,
                    "document_count": len(payload),
                },
            )
            raise

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
