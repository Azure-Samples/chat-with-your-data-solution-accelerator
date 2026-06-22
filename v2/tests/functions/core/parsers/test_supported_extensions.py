"""v1 supported-file-type parity guard.

Pillar: Stable Core
Phase: 6

v1 (`docs/supported_file_types.md`) shipped these out of the box:
PDF, JPEG, JPG, PNG, TXT, HTML, MD, DOCX, JSON. This test asserts the
v2 ingestion parser registry resolves every one of those extensions so
the admin upload (415 gate) and URL ingest cover the same set v1 did.
"""

import pytest

from functions.core.parsers import registry as ingestion_parsers_registry

# The full v1 out-of-the-box supported set (lowercase, no leading dot).
V1_SUPPORTED_EXTENSIONS = (
    "pdf",
    "jpeg",
    "jpg",
    "png",
    "txt",
    "html",
    "md",
    "docx",
    "json",
)


@pytest.mark.parametrize("extension", V1_SUPPORTED_EXTENSIONS)
def test_v1_extension_is_registered_in_v2(extension: str) -> None:
    # `get` raises KeyError (listing available keys) if a v1 format is
    # missing from v2 -- a regression in supported-file-type parity.
    assert ingestion_parsers_registry.registry.get(extension) is not None
