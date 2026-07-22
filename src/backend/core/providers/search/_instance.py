"""Registry instance for the search provider domain.

Holds the `Registry[type[BaseSearch]]` instance in a leaf module so
`registry.py` can be top-imports-only per Hard Rule #17. The public
surface (eager concrete imports of `azure_search` + `pgvector`) stays
in `registry.py`.
"""

from backend.core.registry import Registry

from .base import BaseSearch

registry: Registry[type[BaseSearch]] = Registry("search")
