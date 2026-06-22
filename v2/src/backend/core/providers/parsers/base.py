"""Parser provider ABC.

Pillar: Stable Core
Phase: 6
"""

import hashlib
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import ClassVar

from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import Chunk


class ParserKey(StrEnum):
    """Registry keys for the ingestion parser provider domain.

    The closed set of lowercase file extensions (no leading dot) the
    pipeline can parse -- the key every :class:`BaseParser` self-registers
    under (``@registry.register(ParserKey.PDF)``) and the key callers
    resolve a parser by. ``StrEnum`` so a value computed from a blob path
    (a plain ``str``) still matches a member-keyed registry entry, and
    JSON / error-detail serialization stays the bare extension.
    """

    TXT = "txt"
    MD = "md"
    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    JPEG = "jpeg"
    JPG = "jpg"
    PNG = "png"


class BaseParser(ABC):
    """Turns raw file bytes into a list of `Chunk`s.

    Implementations live under `v2/src/backend/core/providers/parsers/`
    (Stable Core defaults) or `v2/src/functions/core/parsers/`
    (ingestion-only formats like PDF/DOCX). All implementations
    self-register via `@registry.register(ParserKey.<EXT>)` where the
    key is the lowercase file extension without the leading dot
    (`ParserKey.TXT`, `ParserKey.PDF`, `ParserKey.MD`).

    `parse` is async because production implementations may call out
    to Document Intelligence or other network parsers; pure-CPU
    parsers (text, markdown) can implement it as `async def` that
    returns immediately.
    """

    # True when the parser routes to Azure AI Services (Document
    # Intelligence) and therefore needs AZURE_AI_SERVICES_ENDPOINT
    # configured to parse. The admin upload boundary reads this to refuse
    # a file whose parse step would otherwise poison every queued message,
    # without hard-coding which extensions are DI-routed. Pure-CPU parsers
    # (text / markdown / html) leave it False.
    requires_ai_services: ClassVar[bool] = False

    def __init__(
        self,
        settings: AppSettings | None = None,
        credential: AsyncTokenCredential | None = None,
    ) -> None:
        """Accept uniform construction kwargs across all parser implementations.

        Pure-CPU parsers (text, markdown) ignore both arguments via
        the default `None`s; network parsers (PDF via Document
        Intelligence, future Content Understanding) consume them.
        Mirrors the `BaseEmbedder` contract so blueprints can wire
        every provider with the same
        `cls(settings=settings, credential=credential)` line.
        """
        self._settings = settings
        self._credential = credential

    @abstractmethod
    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        """Parse `content` into one or more `Chunk`s.

        `source` is the originating filename or URL -- propagated into
        each returned `Chunk.source` so downstream embedders +
        search-writers retain provenance without an extra parameter
        threading through the pipeline. Returned chunks must carry
        deterministic `id`s built via `make_chunk_id(source, index)`
        so re-ingesting the same source produces stable, Search-safe
        document keys.
        """

    @staticmethod
    def make_chunk_id(source: str, index: int) -> str:
        """Build a deterministic, Azure-Search-safe document key.

        Azure AI Search document keys may contain only letters,
        digits, `_`, `-`, and `=`, so a raw `f"{source}__{index}"` is
        rejected with ``InvalidDocumentKey`` whenever `source` carries
        a filename-extension dot or any other disallowed character.
        Hashing the readable `f"{source}__{index}"` with SHA-256
        yields a hex digest that is always key-safe, collision-free,
        and deterministic -- re-ingesting the same `source` + `index`
        merges onto the same Search document. The readable filename
        survives on `Chunk.source` and the Search `title` field, and
        the read-side mapping treats `id` as an opaque string, so the
        hashed key costs nothing downstream.
        """
        raw = f"{source}__{index}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
