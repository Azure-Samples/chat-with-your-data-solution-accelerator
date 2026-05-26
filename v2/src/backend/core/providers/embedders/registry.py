"""Embedders provider registry (single plug-point).

Pillar: Stable Core
Phase: 6

Holds the `Registry[type[BaseEmbedder]]` instance for the embedders
domain. Concrete embedders self-register against this registry via
`@registry.register("<key>")` (decision D1 in development_plan §4.6.1).

Caller pattern (Hard Rule #13):

    from backend.core.providers.embedders import registry as embedders_registry

    embedder = embedders_registry.registry.get("azure_openai")(...)
"""

# pyright: reportUnusedImport=false
# `from . import azure_openai` below is an intentional side-effect
# import that triggers `@registry.register("azure_openai")`; pyright
# cannot see the side-effect and would flag it as unused.

from backend.core.registry import Registry

from .base import BaseEmbedder

registry: Registry[type[BaseEmbedder]] = Registry("embedders")

# Eager side-effect import: must come AFTER `registry = ...` so the
# decorator has a target to register against.
from . import azure_openai  # noqa: E402, F401
