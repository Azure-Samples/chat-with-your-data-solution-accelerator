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

from typing import Protocol, runtime_checkable

from azure.core.credentials_async import AsyncTokenCredential

from backend.core.registry import Registry
from backend.core.settings import AppSettings
from backend.core.types import Chunk, EmbeddingResult


@runtime_checkable
class EmbedderInstance(Protocol):
    """Structural contract for an instantiated embedder.

    Wider than `BaseEmbedder` because callers also need the
    `aclose()` lifecycle hook concrete providers expose.
    """

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]: ...

    async def aclose(self) -> None: ...


@runtime_checkable
class SupportsEmbedderConstruction(Protocol):
    """Structural contract for an embedder class.

    A class satisfies this Protocol when it is callable with
    `(*, settings, credential)` and yields an `EmbedderInstance`.
    Used as the generic parameter of the embedders registry so
    callers can construct an embedder without `pyright: ignore`
    escape valves.
    """

    def __call__(
        self,
        *,
        settings: AppSettings,
        credential: AsyncTokenCredential,
    ) -> EmbedderInstance: ...


registry: Registry[SupportsEmbedderConstruction] = Registry("embedders")

# Eager side-effect import: must come AFTER `registry = ...` so the
# decorator has a target to register against.
from . import azure_openai  # noqa: E402, F401
