"""Regression guards for the `databases` provider factory contract.

The factory contract freezes two invariants:

1. The registry keys self-registered by concrete clients
   (`cosmosdb`, `postgresql`) MUST equal the values of
   `DatabaseSettings.db_type` (a `DbType` `StrEnum`). Otherwise a
   config that passes pydantic validation could still raise `KeyError`
   at `databases.create(...)` dispatch time.
2. `databases.create(<key>, ...)` returns an instance of
   `BaseDatabaseClient` (Hard Rule #4: registry-only dispatch, no
   `if/elif` provider branching elsewhere in the codebase).
"""

from unittest.mock import MagicMock

import pytest

from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.settings import DbType


def test_registry_keys_match_db_type_literal() -> None:
    """The set of registered keys must equal the `DbType` enum set.

    A mismatch means either (a) a new backend was registered without
    extending `DbType` -- the operator can't select it via env var --
    or (b) `DbType` was extended without a registered client -- the
    lifespan blows up at `databases_registry.registry.get(...)`.
    """
    enum_values = {member.value for member in DbType}
    registered_keys = set(databases_registry.registry.keys())
    assert registered_keys == enum_values, (
        "DbType members and databases registry keys have drifted. "
        f"enum={enum_values!r} registered={registered_keys!r}"
    )


@pytest.mark.parametrize(
    "key",
    sorted(member.value for member in DbType),
)
def test_create_returns_base_client_subclass(key: str) -> None:
    """Every registered client must satisfy the `BaseDatabaseClient`
    contract -- otherwise the lifespan's `await client.aclose()` and
    chat-history calls will fail at runtime, not at import.
    """
    settings = MagicMock(name="AppSettings")
    credential = MagicMock(name="AsyncTokenCredential")
    client = databases_registry.registry.get(key)(
        settings=settings, credential=credential
    )
    assert isinstance(client, BaseDatabaseClient)
