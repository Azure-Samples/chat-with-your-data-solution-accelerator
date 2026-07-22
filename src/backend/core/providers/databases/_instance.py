"""Registry instance for the databases provider domain.

Holds the `Registry[type[BaseDatabaseClient]]` instance in a leaf
module so `registry.py` can be top-imports-only per Hard Rule #17. The
public surface (eager concrete imports of `cosmosdb` + `postgres`)
stays in `registry.py`.
"""

from backend.core.registry import Registry

from .base import BaseDatabaseClient

registry: Registry[type[BaseDatabaseClient]] = Registry("databases")
