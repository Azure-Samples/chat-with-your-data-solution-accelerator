"""Databases provider domain (package marker only).

Pillar: Stable Core
Phase: 4

Per Hard Rule #13 / development_plan §2.4: this `__init__.py` is a
package marker only. The `Registry[type[BaseDatabaseClient]]` instance
+ eager side-effect imports of concrete clients live in `registry.py`.
Callers:

    from backend.core.providers.databases import registry as databases_registry

    client = databases_registry.registry.get(settings.database.db_type)(
        settings=settings, credential=credential
    )
"""
