"""Databases provider registry (single plug-point).

Pillar: Stable Core
Phase: 4

Holds the `Registry[type[BaseDatabaseClient]]` instance + eager
side-effect imports of `cosmosdb` and `postgres` (which call
`@registry.register(...)` at import time).

Caller pattern (Hard Rule #13):

    from backend.core.providers.databases import registry as databases_registry

    client = databases_registry.registry.get(settings.database.db_type)(
        settings=settings, credential=credential
    )

The registry key must match `settings.database.db_type`
(`Literal["cosmosdb", "postgresql"]`) so dispatch is registry-only
(Hard Rule #4 — no name-string translation in the caller).
"""

# pyright: reportUnusedImport=false
# `from . import <module>` lines below are intentional side-effect
# imports that trigger `@registry.register(...)`; pyright cannot see
# the side-effect and would flag them as unused (Hard Rule #4).

from backend.core.registry import Registry

from .base import BaseDatabaseClient

registry: Registry[type[BaseDatabaseClient]] = Registry("databases")

# Eager side-effect imports: must come AFTER `registry = ...` so the
# decorators have a target to register against.
from . import cosmosdb  # noqa: E402, F401
from . import postgres  # noqa: E402, F401
