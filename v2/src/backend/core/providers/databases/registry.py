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

from backend.core.discovery import load_entry_points

from ._instance import registry as registry
from . import cosmosdb  # noqa: F401
from . import postgres  # noqa: F401

# Third-party plugins self-register via the `cwyd.providers.databases`
# entry-point group per Hard Rule #11 registry-driven carve-out. See
# backend.core.discovery.load_entry_points for the loading contract.
load_entry_points("cwyd.providers.databases")
