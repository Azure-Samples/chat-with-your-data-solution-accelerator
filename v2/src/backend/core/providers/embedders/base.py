"""Embedder provider ABC.

Pillar: Stable Core
Phase: 6
"""

from abc import ABC, abstractmethod

from backend.core.types import Chunk, EmbeddingResult


class BaseEmbedder(ABC):
    """Turns parsed `Chunk`s into embedding vectors.

    Implementations live under `v2/src/backend/core/providers/embedders/`
    and self-register via `@registry.register("<key>")` where `key`
    is the runtime selector used by ingestion handlers.

    The contract accepts chunks (not raw strings) so embedders can
    preserve source/id metadata alignment with downstream search writes.
    """

    @abstractmethod
    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        """Return one or more embedding batches for the provided chunks."""
