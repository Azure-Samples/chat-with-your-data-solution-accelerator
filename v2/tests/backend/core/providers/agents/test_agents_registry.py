"""Import-time wiring tests for the agents provider domain.

Pillar: Stable Core
Phase: 4
"""

import importlib
from unittest.mock import patch

from backend.core.providers.agents import registry as agents_registry


def test_first_party_key_registered_at_import() -> None:
    """The eager `from . import foundry` side-effect import must populate
    the `foundry` key against the agents registry by the time the
    module finishes loading.
    """
    registered = set(agents_registry.registry.keys())
    assert "foundry" in registered, (
        f"first-party `foundry` key missing from agents registry: "
        f"registered={registered!r}"
    )


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.agents` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(agents_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.agents")
        finally:
            importlib.reload(agents_registry)
