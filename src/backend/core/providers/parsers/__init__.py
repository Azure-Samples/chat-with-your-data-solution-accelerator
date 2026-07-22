"""Parsers provider domain (package marker only).

Per Hard Rule #13: this `__init__.py` is a
package marker only. The `Registry[type[BaseParser]]` instance and
concrete-parser side-effect imports live in `registry.py`. Callers:

    from backend.core.providers.parsers import registry as parsers_registry

    parser = parsers_registry.registry.get("txt")()
"""
