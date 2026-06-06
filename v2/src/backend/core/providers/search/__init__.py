"""Search provider domain (package marker only).

Pillar: Stable Core
Phase: 3

Per Hard Rule #13 / development_plan §2.4: this `__init__.py` is a
package marker only. The `Registry[type[BaseSearch]]` instance + eager
side-effect imports of concrete providers live in `registry.py`.
Callers:

    from backend.core.providers.search import registry as search_registry

    handler = search_registry.registry.get(settings.database.index_store)(
        settings=settings, credential=credential
    )
"""
