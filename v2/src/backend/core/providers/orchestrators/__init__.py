"""Orchestrator provider domain (package marker only).

Pillar: Stable Core
Phase: 3

Hard Rule #13: this file is a package marker only. The registry instance,
the eager side-effect imports of concretes (``agent_framework``,
``langgraph``), and any genuine domain helpers live in the sibling
``registry`` module. Callers import the submodule explicitly::

    from backend.core.providers.orchestrators import registry as orchestrators_registry

    orchestrator = orchestrators_registry.registry.get(
        settings.orchestrator.name
    )(settings=settings, llm=llm, ...)

There is no ``create()`` helper -- ``Registry.get(key)(**kwargs)`` does
the same work in one expression (see development_plan.md §2.4).
"""
