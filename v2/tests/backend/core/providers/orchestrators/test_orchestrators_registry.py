"""Import-time wiring tests for the orchestrators provider domain.

Pillar: Stable Core
Phase: 3
"""

import importlib
from unittest.mock import patch

from backend.core.providers.orchestrators import registry as orchestrators_registry


def test_first_party_keys_registered_at_import() -> None:
    """The eager `from . import langgraph` + `from . import agent_framework`
    side-effect imports must populate both first-party keys against the
    orchestrators registry by the time the module finishes loading.
    """
    registered = set(orchestrators_registry.registry.keys())
    assert {"langgraph", "agent_framework"}.issubset(registered), (
        f"first-party orchestrator keys missing from registry: "
        f"registered={registered!r}"
    )


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.orchestrators` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(orchestrators_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.orchestrators")
        finally:
            importlib.reload(orchestrators_registry)
