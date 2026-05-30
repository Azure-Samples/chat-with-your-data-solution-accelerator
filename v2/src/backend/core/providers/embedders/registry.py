"""Embedders provider registry (single plug-point).

Pillar: Stable Core
Phase: 6

Holds the `Registry[SupportsEmbedderConstruction]` instance for the
embedders domain. Concrete embedders self-register against this
registry via `@registry.register("<key>")`.

The Protocols below describe the structural contract callers
(ingestion blueprints) rely on: the registered class is callable
with `(*, settings, credential)` and yields an instance with
`embed()` + `aclose()`. This boundary is wider than the
`BaseEmbedder` ABC because the ABC intentionally pins only the
embedding contract -- construction and lifecycle are owned by
each concrete provider (e.g. `AzureOpenAIEmbedder`).

Caller pattern (Hard Rule #13):

    from backend.core.providers.embedders import registry as embedders_registry

    embedder_cls = embedders_registry.registry.get("azure_openai")
    embedder = embedder_cls(settings=settings, credential=credential)
    try:
        await embedder.embed(chunks)
    finally:
        await embedder.aclose()
"""

# pyright: reportUnusedImport=false
# `from . import azure_openai` below is an intentional side-effect
# import that triggers `@registry.register("azure_openai")`; pyright
# cannot see the side-effect and would flag it as unused.

from ._instance import (
    EmbedderInstance as EmbedderInstance,
    SupportsEmbedderConstruction as SupportsEmbedderConstruction,
    registry as registry,
)
from . import azure_openai  # noqa: F401
