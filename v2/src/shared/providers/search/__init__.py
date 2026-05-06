"""Search domain (registry-keyed).

Pillar: Stable Core
Phase: 3

Concrete providers (`azure_search` task #21, `pgvector` task #30) plug
in by self-registering against `BaseSearch`. Callers always go through
`search.create(...)`, never new a provider class directly (ADR 0001 +
Hard Rule #4).

Recipe (per development_plan.md \u00a73.5):

    handler = search.create(
        settings.database.index_store,
        settings=settings,
        credential=credential,
    )
    hits = await handler.search("ping")

The registry key MUST equal the `settings.database.index_store` Literal
value (`AzureSearch` / `pgvector`) so dispatch never goes through a
name-string translation (Hard Rule #4).
"""
# pyright: reportUnusedImport=false
# `from . import <module>` lines below are intentional side-effect
# imports that trigger `@registry.register(...)`; pyright cannot see
# the side-effect and would flag them as unused (Hard Rule #4).

from typing import Any
from shared.registry import Registry

from .base import BaseSearch

registry: Registry[type[BaseSearch]] = Registry("search")

# Side-effect imports (eager, one line per concrete provider).
from . import azure_search  # noqa: E402, F401
from . import pgvector  # noqa: E402, F401


def create(key: str, **kwargs: Any) -> BaseSearch:
    """Instantiate the search provider registered under `key`."""
    return registry.get(key)(**kwargs)


__all__ = ["BaseSearch", "create", "registry"]
