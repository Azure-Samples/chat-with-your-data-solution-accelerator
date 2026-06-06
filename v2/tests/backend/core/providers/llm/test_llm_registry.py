"""Import-time wiring tests for the LLM provider domain.

Pillar: Stable Core
Phase: 2
"""

import importlib
from unittest.mock import patch

from backend.core.providers.llm import registry as llm_registry


def test_first_party_key_registered_at_import() -> None:
    """The eager `from . import foundry_iq` side-effect import must
    populate the `foundry_iq` key against the LLM registry by the time
    the module finishes loading.
    """
    assert "foundry_iq" in llm_registry.registry.keys()


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.llm` group string. Patches the discovery
    module then reloads the registry so the freshly bound name
    resolves to the mock; restores the real binding in `finally` to
    keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(llm_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.llm")
        finally:
            importlib.reload(llm_registry)
