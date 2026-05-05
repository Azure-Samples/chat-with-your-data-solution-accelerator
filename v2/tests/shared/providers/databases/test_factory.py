"""Regression guards for the `databases` provider factory contract.

Pillar: Stable Core
Phase: 4

CU-006 (cleanup_audit) freezes two invariants:

1. The registry keys self-registered by concrete clients
   (`cosmosdb`, `postgresql`) MUST equal the values of
   `DatabaseSettings.db_type` (a `Literal[...]`). Otherwise a config
   that passes pydantic validation could still raise `KeyError` at
   `databases.create(...)` dispatch time.
2. `databases.create(<key>, ...)` returns an instance of
   `BaseDatabaseClient` (Hard Rule #4: registry-only dispatch, no
   `if/elif` provider branching elsewhere in the codebase).
"""
from __future__ import annotations

from typing import get_args
from unittest.mock import MagicMock

import pytest

from shared.providers import databases
from shared.providers.databases.base import BaseDatabaseClient
from shared.settings import DatabaseSettings


def test_registry_keys_match_db_type_literal() -> None:
    """The set of registered keys must equal the `db_type` Literal set.

    A mismatch means either (a) a new backend was registered without
    extending the Literal -- the operator can't select it via env var
    -- or (b) the Literal was extended without a registered client --
    the lifespan blows up at `databases.create(...)`.
    """
    literal_values = set(
        get_args(DatabaseSettings.model_fields["db_type"].annotation)
    )
    registered_keys = set(databases.registry.keys())
    assert registered_keys == literal_values, (
        "DatabaseSettings.db_type Literal and databases registry keys "
        f"have drifted. Literal={literal_values!r} "
        f"registered={registered_keys!r}"
    )


@pytest.mark.parametrize(
    "key",
    sorted(get_args(DatabaseSettings.model_fields["db_type"].annotation)),
)
def test_create_returns_base_client_subclass(key: str) -> None:
    """Every registered client must satisfy the `BaseDatabaseClient`
    contract -- otherwise the lifespan's `await client.aclose()` and
    chat-history calls will fail at runtime, not at import.
    """
    settings = MagicMock(name="AppSettings")
    credential = MagicMock(name="AsyncTokenCredential")
    client = databases.create(key, settings=settings, credential=credential)
    assert isinstance(client, BaseDatabaseClient)
