"""Agents-SDK provider domain (package marker only).

Pillar: Stable Core
Phase: 4

Per Hard Rule #13 / development_plan §2.4: this `__init__.py` is a
package marker only. The `Registry[type[BaseAgentsProvider]]` instance
+ eager side-effect imports of concrete providers live in
`registry.py`. Callers:

    from backend.core.providers.agents import registry as agents_registry

    provider = agents_registry.registry.get("foundry")(
        settings=settings, credential=credential
    )
"""
