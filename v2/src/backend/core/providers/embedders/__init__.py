"""Embedders provider domain (package marker only).

Pillar: Stable Core
Phase: 6

Per Hard Rule #13: this `__init__.py` is a package marker only. The
`Registry[SupportsEmbedderConstruction]` instance, the structural
Protocols (`EmbedderInstance`, `SupportsEmbedderConstruction`), and
the concrete-embedder side-effect imports live in `registry.py`.
Callers:

    from backend.core.providers.embedders import registry as embedders_registry

    embedder_cls = embedders_registry.registry.get("azure_openai")
    embedder = embedder_cls(settings=settings, credential=credential)
"""
