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

from backend.core.registry import Registry

from .base import BaseEmbedder

registry: Registry[type[BaseEmbedder]] = Registry("embedders")
