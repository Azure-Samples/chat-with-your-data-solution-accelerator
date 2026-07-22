"""Shared registry-first search-provider resolution for the Functions
ingestion blueprints (``batch_push``, ``add_url``, and the
``blob_event`` delete path).

Keys ``search_registry`` on ``settings.database.index_store`` (Hard
Rule #4) and, on the ``pgvector`` path, stands up the per-worker
:class:`functions.core.pgvector_pool.PgVectorPool` and wires its
acquired ``asyncpg.Pool`` into the provider factory kwargs.
``"AzureSearch"`` returns a
:class:`backend.core.providers.search.azure_search.AzureSearch`
instance that owns its own SDK client; ``"pgvector"`` returns a
:class:`backend.core.providers.search.pgvector.PgVector` instance
wired to the pool.

Runs ``ensure_schema`` once before returning -- a no-op on AzureSearch
(the index is owned by Bicep) and the once-per-process DDL bootstrap on
pgvector -- so callers can dispatch straight to the ingestion handler
without hitting ``relation "documents" does not exist`` on a fresh
deploy.

Returns both the provider and the optional pool helper in a frozen
:class:`ResolvedSearch` so the **caller** owns teardown: ``aclose`` the
provider, then the pool. If resolution fails before returning -- pool
acquisition, provider construction, or ``ensure_schema`` -- this helper
closes whatever it already opened and re-raises (Hard Rule #14) so no
asyncpg pool / SDK client leaks; the trigger-level decorators
(:func:`functions.core.exception_mapping.log_queue_errors` /
:func:`functions.core.exception_mapping.map_function_exceptions`) own
the observability ladder.
"""

from typing import Any

from azure.core.credentials_async import AsyncTokenCredential
from pydantic import BaseModel, ConfigDict

from backend.core.providers.search import registry as search_registry
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, IndexStore
from functions.core.pgvector_pool import PgVectorPool


class ResolvedSearch(BaseModel):
    """Resolved search provider plus its optional pgvector pool helper.

    ``pool_helper`` is ``None`` on the AzureSearch path. The caller
    owns teardown and closes ``provider`` first, then ``pool_helper``
    when present, so the SDK client is released before the connection
    pool it was layered over.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    provider: BaseSearch
    pool_helper: PgVectorPool | None


async def resolve_search_provider(
    *, settings: AppSettings, credential: AsyncTokenCredential
) -> ResolvedSearch:
    """Resolve the registry-first search provider and bootstrap its schema.

    On the ``pgvector`` path, constructs the per-worker
    :class:`PgVectorPool`, acquires the ``asyncpg.Pool``, and wires it
    into the provider factory kwargs. Runs ``ensure_schema`` once, then
    returns the provider plus the optional pool helper so the caller
    owns teardown. On any failure before the return, closes whatever was
    already opened and re-raises.
    """
    search_key = settings.database.index_store
    pool_helper: PgVectorPool | None = None
    # `Any` is justified here per Hard Rule #11 boundary carve-out: the
    # registry callable accepts heterogeneous kwargs across provider
    # concretes (AzureSearch takes settings+credential; PgVector
    # additionally takes `pool`). Same pattern as backend/app.py:lifespan.
    search_kwargs: dict[str, Any] = {
        "settings": settings,
        "credential": credential,
    }
    provider: BaseSearch | None = None
    resolved = False
    try:
        if search_key == IndexStore.PGVECTOR:
            pool_helper = PgVectorPool(settings=settings, credential=credential)
            search_kwargs["pool"] = await pool_helper.acquire()
        provider = search_registry.registry.get(search_key)(**search_kwargs)
        await provider.ensure_schema()
        resolved = True
        return ResolvedSearch(provider=provider, pool_helper=pool_helper)
    finally:
        # On any early exit (error or cancellation) release what was
        # already opened, provider before pool, so the SDK client is
        # closed over the connection it was layered on; the in-flight
        # exception then propagates to the trigger-level decorators.
        if not resolved:
            if provider is not None:
                await provider.aclose()
            if pool_helper is not None:
                await pool_helper.aclose()
