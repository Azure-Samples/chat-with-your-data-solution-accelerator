"""Embedders provider domain (package marker only).

Pillar: Stable Core
Phase: 6

Per Hard Rule #13 / development_plan §2.4: this `__init__.py` is a
package marker only. The `Registry[type[BaseEmbedder]]` instance and
concrete-embedder side-effect imports live in `registry.py`. Callers:

    from backend.core.providers.embedders import registry as embedders_registry

    embedder = embedders_registry.registry.get("azure_openai")(...)
"""
