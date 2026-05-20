"""Parsers provider domain (package marker only).

Pillar: Stable Core
Phase: 6

Per Hard Rule #13 / development_plan §2.4: this `__init__.py` is a
package marker only. The `Registry[type[BaseParser]]` instance and
concrete-parser side-effect imports live in `registry.py`. Callers:

    from backend.core.providers.parsers import registry as parsers_registry

    parser = parsers_registry.registry.get("txt")()
"""
