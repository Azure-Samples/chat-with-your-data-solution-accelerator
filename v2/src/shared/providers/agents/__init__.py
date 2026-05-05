"""Agents-SDK provider domain (registry-keyed).

Pillar: Stable Core
Phase: 4

Swap-in point for `azure.ai.agents.aio.AgentsClient` (consumed by the
`agent_framework` orchestrator). Concrete providers self-register
against `BaseAgentsProvider` and callers always go through
`agents.create(...)`, never new the client class directly
(ADR 0001 + Hard Rule #4).

Why a separate domain (vs folding into `llm/`): the Foundry Agents
SDK has its own lifecycle (per-thread runs, run-step polling, agent
metadata) distinct from chat completion. Future swap-ins (e.g. an
in-memory `mock` for tests, an on-prem Agents SDK, langgraph-native
agents) plug in here without touching the `llm/` domain.

Recipe (per development_plan.md ยง3.5):

    provider = agents.create(
        "foundry",
        settings=settings,
        credential=credential,
    )
    client = provider.get_client()  # azure.ai.agents.aio.AgentsClient
"""
from __future__ import annotations

from shared.registry import Registry

from .base import BaseAgentsProvider

registry: Registry[type[BaseAgentsProvider]] = Registry("agents")

# Side-effect import: triggers @registry.register("foundry").
from . import foundry  # noqa: E402, F401


def create(key: str, **kwargs: object) -> BaseAgentsProvider:
    """Instantiate the agents provider registered under `key`."""
    return registry.get(key)(**kwargs)


__all__ = ["BaseAgentsProvider", "create", "registry"]
