"""Import-time wiring tests for the search registry."""

import importlib
from unittest.mock import patch

from backend.core.providers.search import registry as search_registry
from backend.core.settings import IndexStore


def test_first_party_keys_registered_at_import() -> None:
    """First-party side-effect imports (`azure_search`, `pgvector`)
    trigger `@registry.register(...)` and populate the registry with
    every `IndexStore` enum value. Comparison is case-insensitive
    because `Registry` lower-cases keys on register/get.
    """
    enum_values = {member.value.lower() for member in IndexStore}
    registered = set(search_registry.registry.keys())
    assert enum_values.issubset(registered), (
        f"first-party registry keys drifted: enum={enum_values!r} "
        f"registered={registered!r}"
    )


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.search` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(search_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.search")
        finally:
            importlib.reload(search_registry)
