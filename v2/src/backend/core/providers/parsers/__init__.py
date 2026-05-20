"""Parsers provider domain (registry-keyed).

Pillar: Stable Core
Phase: 6

Single plug-point for turning raw file bytes into a `list[Chunk]`
ready for embedding + indexing. Ingestion pipelines call
`parsers.create(key, ...)` -- never instantiate a parser class
directly. Concrete ingestion-only parsers (PDF/DOCX/MD) live under
`v2/src/functions/core/parsers/` and self-register against this same
registry (decision D1 in development_plan §4.6.1).

Recipe:

    parser = parsers.create("txt")
    chunks = await parser.parse(content_bytes, source="file.txt")
"""

from typing import Any

from backend.core.registry import Registry

from .base import BaseParser

registry: Registry[type[BaseParser]] = Registry("parsers")


def create(key: str, **kwargs: Any) -> BaseParser:
    """Instantiate the parser registered under `key`.

    `key` is case-insensitive (handled by `Registry`). Convention:
    register by file extension without the leading dot (`"txt"`,
    `"pdf"`, `"md"`) so the ingestion handler can dispatch from
    `Path(filename).suffix.lstrip(".")` with no lookup table.
    """
    return registry.get(key)(**kwargs)


__all__ = ["BaseParser", "create", "registry"]
