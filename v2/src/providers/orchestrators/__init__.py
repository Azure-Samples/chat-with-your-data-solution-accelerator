"""Orchestrator domain (registry-keyed).

Pillar: Stable Core
Phase: 3

Concrete orchestrators (`langgraph` task #18, `agent_framework` task
#19) plug in by self-registering against `OrchestratorBase`. Callers
always go through `orchestrators.create(...)`, never new an
orchestrator class directly (ADR 0001 + Hard Rule #4).

Recipe (per development_plan.md ยง3.5):

    orchestrator = orchestrators.create(
        settings.orchestrator.kind,
        settings=settings,
        llm=llm,
    )
    async for event in orchestrator.run(messages):
        ...

Until task #18 lands the registry is intentionally empty -- the eager
import section below is reserved for the future
`from . import langgraph, agent_framework` lines. Until then,
`orchestrators.create("anything")` raises a clear KeyError naming the
empty registry.
"""
from __future__ import annotations

from shared.registry import Registry

from .base import OrchestratorBase

registry: Registry[type[OrchestratorBase]] = Registry("orchestrators")

# Side-effect imports (eager, one line per concrete provider).
from . import agent_framework  # noqa: E402, F401
from . import langgraph  # noqa: E402, F401


def create(key: str, **kwargs: object) -> OrchestratorBase:
    """Instantiate the orchestrator registered under `key`."""
    return registry.get(key)(**kwargs)


__all__ = ["OrchestratorBase", "create", "registry"]
