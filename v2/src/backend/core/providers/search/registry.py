"""Search provider registry (single plug-point).

Pillar: Stable Core
Phase: 3

Holds the `Registry[type[BaseSearch]]` instance + eager side-effect
imports of `azure_search` and `pgvector` (which call
`@registry.register(...)` at import time).

Caller pattern (Hard Rule #13):

    from backend.core.providers.search import registry as search_registry

    handler = search_registry.registry.get(settings.database.index_store)(
        settings=settings, credential=credential
    )

The registry key MUST equal the `settings.database.index_store` Literal
value (`AzureSearch` / `pgvector`) so dispatch never goes through a
name-string translation (Hard Rule #4). Lookups are case-insensitive
(`Registry` lower-cases on get/set).
"""

# pyright: reportUnusedImport=false
# `from . import <module>` lines below are intentional side-effect
# imports that trigger `@registry.register(...)`; pyright cannot see
# the side-effect and would flag them as unused (Hard Rule #4).

from backend.core.discovery import load_entry_points

from ._instance import registry as registry
from . import azure_search  # noqa: F401
from . import pgvector  # noqa: F401

# Third-party plugins self-register via the `cwyd.providers.search`
# entry-point group per Hard Rule #11 registry-driven carve-out. See
# backend.core.discovery.load_entry_points for the loading contract.
load_entry_points("cwyd.providers.search")
