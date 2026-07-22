"""Registry instance for the ingestion-only parsers provider domain.

Holds the `Registry[type[BaseParser]]` instance in a leaf module so
`registry.py` can be top-imports-only per Hard Rule #17. The public
surface (eager concrete imports of ingestion parsers) stays in
`registry.py`.
"""

from backend.core.providers.parsers.base import BaseParser
from backend.core.registry import Registry

registry: Registry[type[BaseParser]] = Registry("ingestion_parsers")
