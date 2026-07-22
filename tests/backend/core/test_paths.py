"""Unit tests for :func:`backend.core.paths.parser_key_for_path`."""

import pytest

from backend.core.paths import parser_key_for_path


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("report.PDF", "pdf"),
        ("a/b/file.txt", "txt"),
        ("article", ""),
        ("name.", ""),
        ("archive.tar.gz", "gz"),
    ],
)
def test_parser_key_for_path(name: str, expected: str) -> None:
    assert parser_key_for_path(name) == expected
