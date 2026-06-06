"""Import-time wiring tests for the databases registry.

Pillar: Stable Core
Phase: 4
"""

import importlib
from unittest.mock import patch

from backend.core.providers.databases import registry as databases_registry
from backend.core.settings import DbType


def test_first_party_keys_registered_at_import() -> None:
    """First-party side-effect imports (`cosmosdb`, `postgres`) trigger
    `@registry.register(...)` and populate the registry with every
    `DbType` enum value.
    """
    enum_values = {member.value for member in DbType}
    registered = set(databases_registry.registry.keys())
    assert enum_values.issubset(registered), (
        f"first-party registry keys drifted: enum={enum_values!r} "
        f"registered={registered!r}"
    )


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.<domain>` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(databases_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.databases")
        finally:
            importlib.reload(databases_registry)
