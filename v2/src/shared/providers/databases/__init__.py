"""Databases domain (registry-keyed).

Pillar: Stable Core
Phase: 4

Concrete clients (`cosmosdb` task #27, `postgres` task #28) plug in by
self-registering against `BaseDatabaseClient`. Callers always go
through `databases.create(...)`, never new a client class directly
(ADR 0001 + Hard Rule #4).

Recipe (per development_plan.md \u00a73.5):

    client = databases.create(
        settings.database.db_type,        # "cosmosdb" | "postgresql"
        settings=settings,
        credential=credential,
    )
    convs = await client.list_conversations(user_id)

`cosmosdb` lands in task #27; `postgresql` in task #28. Both keys are
the registry keys self-registered by the concrete clients and must
match `DatabaseSettings.db_type` (a `Literal["cosmosdb",
"postgresql"]`). The mapping is regression-guarded by
`tests/shared/test_databases_factory.py`.
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
