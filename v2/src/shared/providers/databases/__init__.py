"""Databases domain (registry-keyed).

Pillar: Stable Core
Phase: 4

Concrete clients (`cosmosdb` task #27, `postgres` task #28) plug in by
self-registering against `BaseDatabaseClient`. Callers always go
through `databases.create(...)`, never new a client class directly
(ADR 0001 + Hard Rule #4).

Recipe (per development_plan.md \u00a73.5):

    client = databases.create(
        settings.database.db_type,        # "cosmosdb" | "postgres"
        settings=settings,
        credential=credential,
    )
    convs = await client.list_conversations(user_id)

`cosmosdb` lands later in task #27; `postgres` in task #28. The eager
side-effect imports below stay commented until those units land --
this module currently exposes only the ABC + registry primitive.
"""
from __future__ import annotations

from shared.registry import Registry

from .base import BaseDatabaseClient

registry: Registry[type[BaseDatabaseClient]] = Registry("databases")

# Side-effect imports (eager, one line per concrete client). Added as
# each client lands:
from . import cosmosdb  # noqa: E402, F401
from . import postgres  # noqa: E402, F401


def create(key: str, **kwargs: object) -> BaseDatabaseClient:
    """Instantiate the database client registered under `key`."""
    return registry.get(key)(**kwargs)


__all__ = ["BaseDatabaseClient", "create", "registry"]
