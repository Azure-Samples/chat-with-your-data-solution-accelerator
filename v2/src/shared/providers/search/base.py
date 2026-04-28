'''Search provider ABC.

Pillar: Stable Core
Phase: 3

Every concrete search provider (`azure_search` task #21, `pgvector`
task #30, `integrated_vectorization` future) inherits from `BaseSearch`
and self-registers via `@registry.register("<key>")`.

Constructors take `AppSettings` so providers can read their own
endpoint / index / top_k defaults; data-plane authentication uses an
`AsyncTokenCredential` (managed identity in production, AzureCli in
local dev) -- never an API key (Hard Rule #2: no Key Vault, no shared
secrets).

`search(query, *, top_k=None, vector=None, filter=None)` returns
provider-agnostic `SearchResult` instances. Producers map their native
shape (search documents, pgvector rows) to `SearchResult` so the chat
pipeline (task #22) and citation extractor (task #23) consume one
stable type.
'''
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings
    from shared.types import SearchResult


class BaseSearch(ABC):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
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
    ) -> "Sequence[SearchResult]":
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

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default no-op."""
        return None
