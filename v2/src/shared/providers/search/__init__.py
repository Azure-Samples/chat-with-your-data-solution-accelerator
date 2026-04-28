"""Search domain (registry-keyed).

Pillar: Stable Core
Phase: 3

Concrete providers (`azure_search` task #21, `pgvector` task #30) plug
in by self-registering against `BaseSearch`. Callers always go through
`search.create(...)`, never new a provider class directly (ADR 0001 +
Hard Rule #4).

Recipe (per development_plan.md \u00a73.5):

    handler = search.create(
        settings.database.index_store.lower(),
        settings=settings,
        credential=credential,
    )
    hits = await handler.search("ping")

`pgvector` lands in Phase 4 (task #30); the eager-import line is
reserved below until then.
"""
from __future__ import annotations

from shared.registry import Registry

from .base import BaseSearch

registry: Registry[type[BaseSearch]] = Registry("search")

# Side-effect imports (eager, one line per concrete provider).
from . import azure_search  # noqa: E402, F401
# Future: from . import pgvector  # noqa: E402, F401


def create(key: str, **kwargs: object) -> BaseSearch:
    """Instantiate the search provider registered under `key`."""
    return registry.get(key)(**kwargs)


__all__ = ["BaseSearch", "create", "registry"]
