"""
Global pytest fixtures for CWYD v2.

Pillar: Stable Core
Phase: 0
"""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip all AZURE_*, CWYD_*, LOAD_*, ORCHESTRATOR-related env so each test
    starts from a deterministic baseline. Tests opt back in via monkeypatch.setenv."""
    for key in list(os.environ):
        if key.startswith(("AZURE_", "CWYD_", "LOAD_")) or key in {
            "ORCHESTRATOR",
            "DATABASE_TYPE",
            "LOG_LEVEL",
        }:
            monkeypatch.delenv(key, raising=False)
    yield
