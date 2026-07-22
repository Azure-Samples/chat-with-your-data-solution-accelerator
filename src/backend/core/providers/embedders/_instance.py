"""Registry instance + structural Protocols for the embedders provider domain.

Holds the `Registry[SupportsEmbedderConstruction]` instance and the
two `runtime_checkable` Protocols that describe its generic parameter
(`EmbedderInstance` + `SupportsEmbedderConstruction`). Lives in a leaf
module so `registry.py` can be top-imports-only per Hard Rule #17.
"""

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
