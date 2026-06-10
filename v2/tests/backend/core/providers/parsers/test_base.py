"""Tests for `BaseParser` shared helpers.

Pillar: Stable Core
Phase: 6
"""

import hashlib
import re

from backend.core.providers.parsers.base import BaseParser

# Azure AI Search document-key charset: letters, digits, `_`, `-`, `=`.
_SEARCH_KEY_SAFE = re.compile(r"[A-Za-z0-9_\-=]+")


def _is_search_key_safe(key: str) -> bool:
    return _SEARCH_KEY_SAFE.fullmatch(key) is not None


def test_make_chunk_id_is_deterministic() -> None:
    assert BaseParser.make_chunk_id("doc.pdf", 0) == BaseParser.make_chunk_id(
        "doc.pdf", 0
    )


def test_make_chunk_id_is_search_key_safe_for_dotted_source() -> None:
    # The raw `Benefit_Options.pdf__0` form is rejected by Azure Search
    # because of the extension dot; the hashed key must be accepted.
    assert _is_search_key_safe(BaseParser.make_chunk_id("Benefit_Options.pdf", 0))


def test_make_chunk_id_is_search_key_safe_for_pathological_sources() -> None:
    for source in ("a b/c.pdf", "resume (final).docx", "x.y.z", "weird:name*?.txt"):
        assert _is_search_key_safe(BaseParser.make_chunk_id(source, 3)), source


def test_make_chunk_id_distinguishes_source_and_index() -> None:
    a0 = BaseParser.make_chunk_id("doc.pdf", 0)
    a1 = BaseParser.make_chunk_id("doc.pdf", 1)
    b0 = BaseParser.make_chunk_id("other.pdf", 0)
    assert len({a0, a1, b0}) == 3


def test_make_chunk_id_is_sha256_of_readable_key() -> None:
    expected = hashlib.sha256(b"doc.pdf__7").hexdigest()
    assert BaseParser.make_chunk_id("doc.pdf", 7) == expected
