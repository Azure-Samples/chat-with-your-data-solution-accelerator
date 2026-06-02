'''Search provider ABC.

Pillar: Stable Core
Phase: 3

Every concrete search provider (`azure_search`, `pgvector`,
`integrated_vectorization` future) inherits from `BaseSearch`
and self-registers via `@registry.register("<key>")`.

Constructors take `AppSettings` so providers can read their own
endpoint / index / top_k defaults; data-plane authentication uses an
`AsyncTokenCredential` (managed identity in production, AzureCli in
local dev) -- never an API key (Hard Rule #2: no Key Vault, no shared
secrets).

`search(query, *, top_k=None, vector=None, filter=None)` returns
provider-agnostic `SearchResult` instances. Producers map their native
shape (search documents, pgvector rows) to `SearchResult` so the chat
pipeline and citation extractor consume one
stable type.

`merge_or_upload_documents(*, documents)` is the symmetric write
surface used by ingestion blueprints. Concrete providers override
with their native upsert (Azure Search SDK call / Postgres ON
CONFLICT UPDATE / etc.); the default body raises
`NotImplementedError` so a provider that forgets to implement fails
loudly at the ingestion call site rather than silently no-oping.
'''

from abc import ABC, abstractmethod
from typing import Any, Sequence

from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import SearchDocument, SearchResult


class BaseSearch(ABC):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
    ) -> None:
        self._settings = settings
        self._credential = credential

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
    ) -> Sequence[SearchResult]:
        """Return search hits for the given query.

        - `query`: free-text query. Required even for pure-vector
          searches (used for hybrid scoring + semantic re-ranking).
        - `top_k`: max hits to return. None = provider default
          (`settings.search.top_k`).
        - `vector`: optional dense embedding for hybrid / pure-vector
          retrieval. Providers that don't support vectors ignore it.
        - `filter_expression`: provider-specific filter (OData for
          azure_search, SQL fragment for pgvector). Pass-through; no
          parsing here. Named `filter_expression` to avoid shadowing
          the `filter()` builtin.
        """

    @abstractmethod
    async def delete_by_source(self, source: str) -> int:
        """Delete every indexed chunk whose source matches `source`.

        - `source`: the filename or URL ingestion stored on each chunk
          (mapped to the `title` field in both Azure Search and the
          pgvector schema).
        - Returns the count of chunks deleted. A return of 0 means no
          matching documents existed; the admin route maps that to a
          404 response.
        """

    async def merge_or_upload_documents(
        self,
        *,
        documents: Sequence[SearchDocument],
    ) -> list[Any]:
        """Upsert ingestion documents into the provider's index.

        Symmetric write counterpart to :meth:`search` /
        :meth:`delete_by_source`. Concrete providers override with
        their native upsert path (Azure Search SDK
        ``merge_or_upload_documents`` / Postgres
        ``ON CONFLICT (id) DO UPDATE`` / etc.); each implementation
        owns the ``SearchDocument`` -> wire-shape translation at its
        own SDK boundary (Hard Rule #15: the ingestion model is the
        source of truth; the dict/row passed to the SDK is a
        transport detail).

        Keyword-only ``documents`` matches the
        ``SupportsMergeOrUploadDocuments`` Protocol in
        :mod:`backend.core.providers.search.writer` so adapter sites
        and provider sites share one signature.

        Returns provider-specific result objects (Azure SDK
        ``IndexingResult``, asyncpg ``Record``, etc.) typed
        ``list[Any]`` per Hard Rule #11(a) boundary carve-out --
        callers that need a uniform success/failure shape build it on
        top of the raw return rather than forcing every backend into
        a synthetic envelope.

        Default implementation raises ``NotImplementedError`` so a
        provider class that forgets to override the method fails at
        the ingestion call site rather than silently dropping data.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement merge_or_upload_documents; "
            "override on the concrete provider class."
        )

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default no-op."""
        return None
