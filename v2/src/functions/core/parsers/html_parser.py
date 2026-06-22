"""HTML parser (`*.html`).

Pillar: Stable Core
Phase: 6

Self-registers under key `"html"` per the registration convention in
`base.py` (lowercase file extension, no leading dot). Eager-imported
from `functions/core/parsers/registry.py` so the registration fires at
process start.

Chunking strategy -- the page's visible text is extracted with
BeautifulSoup (dropping `script` / `style` / `noscript` so the index
isn't polluted with markup), then split into paragraphs on blank
lines, the same semantic unit `TextParser` uses. Mirrors v1's
`download_url_and_upload_to_blob` admin path, which ran the fetched
page through BeautifulSoup `.get_text()` before indexing.

`html.parser` (Python's built-in) is used so no extra native parser
(lxml) is required. Whitespace-only or empty inputs return `[]` so the
downstream embedder + indexer never see zero-content chunks.
"""

import re

from bs4 import BeautifulSoup

from backend.core.providers.parsers.base import BaseParser, ParserKey
from backend.core.types import Chunk

from .registry import registry

_PARAGRAPH_SEPARATOR = re.compile(r"(?:\r?\n[ \t]*){2,}")

_NON_CONTENT_TAGS = ("script", "style", "noscript")


@registry.register(ParserKey.HTML)
class HtmlParser(BaseParser):
    """Parse an HTML page into one `Chunk` per paragraph of extracted text."""

    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        soup = BeautifulSoup(content, "html.parser")
        for element in soup(_NON_CONTENT_TAGS):
            element.decompose()
        text = soup.get_text(separator="\n")
        paragraphs = [paragraph.strip() for paragraph in _PARAGRAPH_SEPARATOR.split(text)]
        return [
            Chunk(
                id=self.make_chunk_id(source, index),
                content=paragraph,
                source=source,
                index=index,
            )
            for index, paragraph in enumerate(p for p in paragraphs if p)
        ]
