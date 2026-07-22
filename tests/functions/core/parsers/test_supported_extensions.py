"""v1 supported-file-type parity guard.

v1 (`docs/supported_file_types.md`) shipped these out of the box:
PDF, JPEG, JPG, PNG, TXT, HTML, MD, DOCX, JSON. This test asserts the
v2 ingestion parser registry resolves every one of those extensions so
the admin upload (415 gate) and URL ingest cover the same set v1 did.
"""

import pytest

from backend.core.providers.parsers.base import ParserKey
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


def test_registry_resolves_by_parser_key_member() -> None:
    # Registration used ParserKey members; a member lookup resolves the
    # same class a plain-string (blob-extension) lookup does.
    assert ingestion_parsers_registry.registry.get(
        ParserKey.PDF
    ) is ingestion_parsers_registry.registry.get("pdf")


# Extensions whose parser routes through Azure AI Services (Document
# Intelligence) and therefore needs AZURE_AI_SERVICES_ENDPOINT.
_DI_ROUTED_EXTENSIONS = ("pdf", "docx", "jpeg", "jpg", "png")
# Extensions parsed locally (pure-CPU), needing no AI Services endpoint.
_LOCAL_EXTENSIONS = ("txt", "md", "json", "html")


@pytest.mark.parametrize("extension", _DI_ROUTED_EXTENSIONS)
def test_di_routed_extension_requires_ai_services(extension: str) -> None:
    parser_cls = ingestion_parsers_registry.registry.get(extension)
    assert parser_cls.requires_ai_services is True


@pytest.mark.parametrize("extension", _LOCAL_EXTENSIONS)
def test_local_extension_does_not_require_ai_services(extension: str) -> None:
    parser_cls = ingestion_parsers_registry.registry.get(extension)
    assert parser_cls.requires_ai_services is False
