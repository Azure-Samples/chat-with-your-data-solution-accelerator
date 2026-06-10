"""Plain-text parser (`*.txt`).

Pillar: Stable Core
Phase: 6

First concrete `BaseParser` to land in v2.
Self-registers under key `"txt"` per the registration convention in
`base.py` (lowercase file extension, no leading dot). Eager-imported
from `functions/core/parsers/registry.py` so the registration fires at process
start (Option SE-1 in development_plan §2.4.5).

Chunking strategy — paragraph-based, blank-line separated. v2
removed the chunker primitive (decision D2 in §4.6.1): parsers are
expected to chunk in whatever way is appropriate for the format.
For plain text, paragraphs are the natural semantic unit -- they
match the v1 default, surface cleanly in downstream embedders, and
keep chunk boundaries deterministic so re-ingesting the same file
produces stable, Search-safe document keys via
`BaseParser.make_chunk_id(source, index)`.

Whitespace-only or empty inputs return `[]` so the downstream
embedder + indexer never see zero-content chunks.

Bytes are decoded as UTF-8 with `errors="strict"` -- malformed bytes
propagate as `UnicodeDecodeError` so the Functions runtime retry +
poison-queue path engages (preferred over silent fall-back to
`errors="replace"` which would mask real producer-side corruption).
"""

import re

from backend.core.types import Chunk
from backend.core.providers.parsers.base import BaseParser
from .registry import registry

_PARAGRAPH_SEPARATOR = re.compile(r"(?:\r?\n[ \t]*){2,}")

@registry.register("txt")
class TextParser(BaseParser):
    """Parse a UTF-8 plain-text file into one `Chunk` per paragraph."""

    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        text = content.decode("utf-8")
        paragraphs = [p.strip() for p in _PARAGRAPH_SEPARATOR.split(text)]
        return [
            Chunk(
                id=self.make_chunk_id(source, index),
                content=para,
                source=source,
                index=index,
            )
            for index, para in enumerate(p for p in paragraphs if p)
        ]
