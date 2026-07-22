"""Tests for the parsers provider domain."""

import importlib
from unittest.mock import patch

import pytest

from backend.core.providers.parsers import registry as parsers_registry
from backend.core.providers.parsers.base import BaseParser
from backend.core.registry import Registry
from backend.core.types import Chunk


class _FakeParser(BaseParser):
    """Minimal concrete BaseParser used to exercise the registry."""

    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        return [
            Chunk(id=f"{source}__0", content=content.decode(), source=source, index=0)
        ]


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> Registry[type[BaseParser]]:
    """Swap the module-level `parsers_registry.registry` for an empty one.

    Tests register fake parsers without polluting the global registry
    that real provider concretes will populate.
    """
    fresh: Registry[type[BaseParser]] = Registry("parsers")
    monkeypatch.setattr(parsers_registry, "registry", fresh)
    return fresh


def test_registry_is_named_parsers() -> None:
    # Sanity check on the production registry instance.
    assert parsers_registry.registry.domain == "parsers"


def test_register_and_create_returns_instance(
    isolated_registry: Registry[type[BaseParser]],
) -> None:
    isolated_registry.register("txt")(_FakeParser)

    parser = parsers_registry.registry.get("txt")()

    assert isinstance(parser, _FakeParser)
    assert isinstance(parser, BaseParser)


def test_create_is_case_insensitive(
    isolated_registry: Registry[type[BaseParser]],
) -> None:
    isolated_registry.register("PDF")(_FakeParser)

    assert isinstance(parsers_registry.registry.get("pdf")(), _FakeParser)
    assert isinstance(parsers_registry.registry.get("PdF")(), _FakeParser)


def test_create_unknown_key_raises_keyerror_listing_available(
    isolated_registry: Registry[type[BaseParser]],
) -> None:
    isolated_registry.register("txt")(_FakeParser)

    with pytest.raises(KeyError) as exc:
        parsers_registry.registry.get("docx")

    # Registry surfaces the sorted list of available keys.
    assert "txt" in str(exc.value)


def test_duplicate_registration_same_value_is_idempotent(
    isolated_registry: Registry[type[BaseParser]],
) -> None:
    isolated_registry.register("txt")(_FakeParser)
    # Re-registering the same class under the same key must not raise.
    isolated_registry.register("txt")(_FakeParser)

    assert isinstance(parsers_registry.registry.get("txt")(), _FakeParser)


def test_duplicate_registration_different_value_raises(
    isolated_registry: Registry[type[BaseParser]],
) -> None:
    class _OtherParser(BaseParser):
        async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
            return []

    isolated_registry.register("txt")(_FakeParser)

    with pytest.raises(ValueError):
        isolated_registry.register("txt")(_OtherParser)


def test_baseparser_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseParser()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_parser_returns_chunks() -> None:
    parser = _FakeParser()

    chunks = await parser.parse(b"hello", source="greeting.txt")

    assert chunks == [
        Chunk(id="greeting.txt__0", content="hello", source="greeting.txt", index=0)
    ]


# ---------------------------------------------------------------------------
# Entry-point discovery wiring (Hard Rule #11 registry-driven carve-out).
# ---------------------------------------------------------------------------


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.parsers` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.

    Note: this domain has no first-party side-effect imports at backend
    startup (PDF/DOCX/MD/HTML/TXT concretes live under
    `src/functions/core/parsers/` and self-register at Functions
    startup), so there is no `test_first_party_key_registered_at_import`
    companion case.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(parsers_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.parsers")
        finally:
            importlib.reload(parsers_registry)
