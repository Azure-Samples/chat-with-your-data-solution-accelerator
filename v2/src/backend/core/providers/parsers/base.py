"""Parser provider ABC.

Pillar: Stable Core
Phase: 6
"""

from abc import ABC, abstractmethod

from backend.core.types import Chunk


class BaseParser(ABC):
    """Turns raw file bytes into a list of `Chunk`s.

    Implementations live under `v2/src/backend/core/providers/parsers/`
    (Stable Core defaults) or `v2/src/functions/core/parsers/`
    (ingestion-only formats like PDF/DOCX). All implementations
    self-register via `@registry.register("<extension>")` where the
    key is the lowercase file extension without the leading dot
    (`"txt"`, `"pdf"`, `"md"`).

    `parse` is async because production implementations may call out
    to Document Intelligence or other network parsers; pure-CPU
    parsers (text, markdown) can implement it as `async def` that
    returns immediately.
    """

    @abstractmethod
    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        """Parse `content` into one or more `Chunk`s.

        `source` is the originating filename or URL -- propagated into
        each returned `Chunk.source` so downstream embedders +
        search-writers retain provenance without an extra parameter
        threading through the pipeline. Returned chunks must carry
        deterministic `id`s (typically `f"{source}__{index}"`) so
        re-ingesting the same source produces stable Search document
        keys.
        """
