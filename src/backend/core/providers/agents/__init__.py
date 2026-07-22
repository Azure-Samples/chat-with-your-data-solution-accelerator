"""Agents-SDK provider domain (package marker only).

Per Hard Rule #13: this `__init__.py` is a
package marker only. The `Registry[type[BaseAgentsProvider]]` instance
+ eager side-effect imports of concrete providers live in
`registry.py`. Callers:

    from backend.core.providers.agents import registry as agents_registry

    provider = agents_registry.registry.get("foundry")(
        settings=settings, credential=credential
    )
"""
