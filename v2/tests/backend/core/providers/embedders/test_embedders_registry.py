"""Tests for the embedders provider domain (Phase 6 task #41, U8e).

Pillar: Stable Core
Phase: 6
"""

import importlib
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from azure.core.credentials_async import AsyncTokenCredential

from backend.core.providers.embedders import registry as embedders_registry
from backend.core.providers.embedders.azure_openai import AzureOpenAIEmbedder
from backend.core.providers.embedders.base import BaseEmbedder
from backend.core.providers.embedders.registry import (
    EmbedderInstance,
    SupportsEmbedderConstruction,
)
from backend.core.registry import Registry
from backend.core.settings import AppSettings
from backend.core.types import Chunk, EmbeddingResult


class _FakeEmbedder(BaseEmbedder):
    """Minimal concrete BaseEmbedder used to exercise the registry.

    Constructor matches the `SupportsEmbedderConstruction` Protocol
    shape so the class can be registered against the widened registry
    generic without `pyright: ignore` escape valves.
    """

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        credential: AsyncTokenCredential | None = None,
    ) -> None:
        self._settings = settings
        self._credential = credential
        self.aclose_calls = 0

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        vector_count = len(chunks)
        vectors = [[0.1, 0.2] for _ in range(vector_count)]
        return [EmbeddingResult(vectors=vectors, model="fake")]

    async def aclose(self) -> None:
        self.aclose_calls += 1


@pytest.fixture
def isolated_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> Registry[SupportsEmbedderConstruction]:
    """Swap the module-level `embedders_registry.registry` for an empty one.

    Tests register fake embedders without polluting the global registry
    that real provider concretes populate at import time.
    """
    fresh: Registry[SupportsEmbedderConstruction] = Registry("embedders")
    monkeypatch.setattr(embedders_registry, "registry", fresh)
    return fresh


@pytest.fixture
def fake_settings() -> AppSettings:
    return cast(AppSettings, MagicMock(spec=AppSettings))


@pytest.fixture
def fake_credential() -> AsyncTokenCredential:
    return cast(AsyncTokenCredential, MagicMock(spec=AsyncTokenCredential))


def test_registry_is_named_embedders() -> None:
    assert embedders_registry.registry.domain == "embedders"


def test_register_and_create_returns_instance(
    isolated_registry: Registry[SupportsEmbedderConstruction],
    fake_settings: AppSettings,
    fake_credential: AsyncTokenCredential,
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    embedder = embedders_registry.registry.get("azure_openai")(
        settings=fake_settings, credential=fake_credential
    )

    assert isinstance(embedder, _FakeEmbedder)
    assert isinstance(embedder, BaseEmbedder)


def test_create_is_case_insensitive(
    isolated_registry: Registry[SupportsEmbedderConstruction],
    fake_settings: AppSettings,
    fake_credential: AsyncTokenCredential,
) -> None:
    isolated_registry.register("Azure_OpenAI")(_FakeEmbedder)

    assert isinstance(
        embedders_registry.registry.get("azure_openai")(
            settings=fake_settings, credential=fake_credential
        ),
        _FakeEmbedder,
    )
    assert isinstance(
        embedders_registry.registry.get("AZURE_OPENAI")(
            settings=fake_settings, credential=fake_credential
        ),
        _FakeEmbedder,
    )


def test_create_unknown_key_raises_keyerror_listing_available(
    isolated_registry: Registry[SupportsEmbedderConstruction],
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    with pytest.raises(KeyError) as exc:
        embedders_registry.registry.get("missing")

    assert "azure_openai" in str(exc.value)


def test_duplicate_registration_same_value_is_idempotent(
    isolated_registry: Registry[SupportsEmbedderConstruction],
    fake_settings: AppSettings,
    fake_credential: AsyncTokenCredential,
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    assert isinstance(
        embedders_registry.registry.get("azure_openai")(
            settings=fake_settings, credential=fake_credential
        ),
        _FakeEmbedder,
    )


def test_duplicate_registration_different_value_raises(
    isolated_registry: Registry[SupportsEmbedderConstruction],
) -> None:
    class _OtherEmbedder(BaseEmbedder):
        def __init__(
            self,
            *,
            settings: AppSettings | None = None,
            credential: AsyncTokenCredential | None = None,
        ) -> None:
            self._settings = settings
            self._credential = credential

        async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
            return [EmbeddingResult(vectors=[], model="other")]

        async def aclose(self) -> None:
            return

    isolated_registry.register("azure_openai")(_FakeEmbedder)

    with pytest.raises(ValueError):
        isolated_registry.register("azure_openai")(_OtherEmbedder)


def test_baseembedder_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseEmbedder()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_embedder_returns_embedding_results() -> None:
    embedder = _FakeEmbedder()

    results = await embedder.embed(
        [
            Chunk(id="a__0", content="hello", source="a", index=0),
            Chunk(id="a__1", content="world", source="a", index=1),
        ]
    )

    assert results == [EmbeddingResult(vectors=[[0.1, 0.2], [0.1, 0.2]], model="fake")]


# ---------------------------------------------------------------------------
# Protocol-satisfaction tests (SupportsEmbedderConstruction widening).
# ---------------------------------------------------------------------------


def test_fake_embedder_instance_satisfies_embedder_instance_protocol(
    fake_settings: AppSettings, fake_credential: AsyncTokenCredential
) -> None:
    embedder = _FakeEmbedder(settings=fake_settings, credential=fake_credential)
    assert isinstance(embedder, EmbedderInstance)


def test_azure_openai_embedder_class_satisfies_construction_protocol() -> None:
    assert isinstance(AzureOpenAIEmbedder, SupportsEmbedderConstruction)


@pytest.mark.asyncio
async def test_registry_accepts_class_not_inheriting_from_base_embedder(
    isolated_registry: Registry[SupportsEmbedderConstruction],
    fake_settings: AppSettings,
    fake_credential: AsyncTokenCredential,
) -> None:
    """Widening the generic from `type[BaseEmbedder]` to
    `SupportsEmbedderConstruction` lets the registry accept any class
    matching the structural shape -- including classes that do not
    inherit from the `BaseEmbedder` ABC.
    """

    class _StructuralEmbedder:
        def __init__(
            self,
            *,
            settings: AppSettings,
            credential: AsyncTokenCredential,
        ) -> None:
            self._settings = settings
            self._credential = credential

        async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
            return [EmbeddingResult(vectors=[], model="structural")]

        async def aclose(self) -> None:
            return

    isolated_registry.register("structural")(_StructuralEmbedder)

    embedder = embedders_registry.registry.get("structural")(
        settings=fake_settings, credential=fake_credential
    )

    assert isinstance(embedder, _StructuralEmbedder)
    assert not isinstance(embedder, BaseEmbedder)
    assert isinstance(embedder, EmbedderInstance)


@pytest.mark.asyncio
async def test_registered_embedder_aclose_lifecycle(
    isolated_registry: Registry[SupportsEmbedderConstruction],
    fake_settings: AppSettings,
    fake_credential: AsyncTokenCredential,
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    embedder = embedders_registry.registry.get("azure_openai")(
        settings=fake_settings, credential=fake_credential
    )
    assert isinstance(embedder, _FakeEmbedder)
    assert embedder.aclose_calls == 0

    await embedder.aclose()

    assert embedder.aclose_calls == 1


# ---------------------------------------------------------------------------
# Entry-point discovery wiring (Hard Rule #11 registry-driven carve-out).
# ---------------------------------------------------------------------------


def test_first_party_key_registered_at_import() -> None:
    """First-party side-effect import (`azure_openai`) triggers
    `@registry.register("azure_openai")` at module-load time.
    """
    registered = set(embedders_registry.registry.keys())
    assert "azure_openai" in registered, (
        f"first-party `azure_openai` key missing from embedders registry: "
        f"registered={registered!r}"
    )


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.embedders` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(embedders_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.embedders")
        finally:
            importlib.reload(embedders_registry)
