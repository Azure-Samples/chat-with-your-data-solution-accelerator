"""Unit tests for :func:`functions.core.search_resolution.resolve_search_provider`.

Covers both registry-keyed paths plus the failure-cleanup contract:

* **AzureSearch path** -- no pool helper is constructed, ``ensure_schema``
  runs once, and the factory is called without a ``pool`` kwarg.
* **pgvector path** -- the :class:`PgVectorPool` is built, ``acquire`` is
  awaited, the acquired pool is wired into the factory kwargs, and the
  returned ``pool_helper`` is the constructed helper.
* **ensure_schema failure** -- the provider (and, on the pgvector path,
  the pool) are closed and the exception propagates, so a fresh-deploy
  DDL rejection cannot leak the asyncpg pool / SDK client.

Stubs subclass the real :class:`BaseSearch` / :class:`PgVectorPool`
because :class:`ResolvedSearch` is a Pydantic model with
``arbitrary_types_allowed`` -- the field types are validated by
``isinstance``, so a loose double would be rejected at construction.
"""

from collections.abc import Sequence
from unittest.mock import MagicMock

import pytest
from azure.core.exceptions import AzureError

from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, IndexStore
from backend.core.types import SearchResult
from functions.core import search_resolution
from functions.core.pgvector_pool import PgVectorPool

_SENTINEL_POOL = object()


def _make_settings(index_store: IndexStore) -> AppSettings:
    """An ``AppSettings`` double whose ``database.index_store`` is fixed.

    The pgvector path constructs ``PgVectorPool`` and the factory with
    this object, so a ``MagicMock`` spec'd to ``AppSettings`` is enough --
    the real pool/provider are stubbed and never read its fields.
    """
    settings = MagicMock(spec=AppSettings)
    database = MagicMock()
    database.index_store = index_store
    settings.database = database
    return settings


class _RecordingSearch(BaseSearch):
    """A ``BaseSearch`` double that records its lifecycle calls.

    Implements the two abstract methods (``search`` / ``delete_by_source``)
    so it is instantiable, and overrides ``ensure_schema`` / ``aclose`` to
    append to a shared call-order trail.
    """

    def __init__(self, *, record: list[str], fail_ensure: bool = False) -> None:
        self._record = record
        self._fail_ensure = fail_ensure

    async def search(self, query: str, **_kwargs: object) -> Sequence[SearchResult]:
        return []

    async def delete_by_source(self, source: str) -> int:
        return 0

    async def ensure_schema(self) -> None:
        self._record.append("ensure_schema")
        if self._fail_ensure:
            raise AzureError("ddl rejected")

    async def aclose(self) -> None:
        self._record.append("aclose")


class _FakePool(PgVectorPool):
    """A ``PgVectorPool`` double that hands out a sentinel pool.

    Matches the real constructor signature (so the override is
    LSP-compatible) but skips ``super().__init__`` to avoid touching real
    config; ``acquire`` returns the sentinel and ``aclose`` records.
    """

    def __init__(
        self,
        settings: object,
        credential: object,
        *,
        pool: object | None = None,
        record: list[str] | None = None,
    ) -> None:
        self.captured_settings = settings
        self.captured_credential = credential
        self._record = record if record is not None else []

    async def acquire(self) -> object:
        return _SENTINEL_POOL

    async def aclose(self) -> None:
        self._record.append("pool_aclose")


def _patch_registry(
    monkeypatch: pytest.MonkeyPatch,
    provider: BaseSearch,
    captured_kwargs: dict[str, object],
) -> None:
    """Patch the shared search registry so ``get`` returns a capturing factory."""

    def _factory(**kwargs: object) -> BaseSearch:
        captured_kwargs.update(kwargs)
        return provider

    monkeypatch.setattr(
        search_resolution.search_registry.registry, "get", lambda _key: _factory
    )


@pytest.mark.asyncio
async def test_azure_search_path_skips_pool_and_runs_ensure_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []
    provider = _RecordingSearch(record=record)
    captured_kwargs: dict[str, object] = {}
    _patch_registry(monkeypatch, provider, captured_kwargs)
    credential = MagicMock()

    resolved = await search_resolution.resolve_search_provider(
        settings=_make_settings(IndexStore.AZURE_SEARCH), credential=credential
    )

    # No pgvector pool on the AzureSearch path; the factory is called
    # without a `pool` kwarg and ensure_schema bootstraps once.
    assert resolved.provider is provider
    assert resolved.pool_helper is None
    assert "pool" not in captured_kwargs
    assert record == ["ensure_schema"]


@pytest.mark.asyncio
async def test_pgvector_path_builds_pool_and_wires_pool_kwarg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []
    provider = _RecordingSearch(record=record)
    captured_kwargs: dict[str, object] = {}
    _patch_registry(monkeypatch, provider, captured_kwargs)
    monkeypatch.setattr(search_resolution, "PgVectorPool", _FakePool)
    credential = MagicMock()

    resolved = await search_resolution.resolve_search_provider(
        settings=_make_settings(IndexStore.PGVECTOR), credential=credential
    )

    # The pgvector path constructs the pool helper, acquires it, and
    # wires the acquired asyncpg pool into the provider factory kwargs.
    assert isinstance(resolved.pool_helper, _FakePool)
    assert resolved.pool_helper.captured_credential is credential
    assert captured_kwargs["pool"] is _SENTINEL_POOL
    assert resolved.provider is provider
    assert record == ["ensure_schema"]


@pytest.mark.asyncio
async def test_ensure_schema_failure_closes_provider_and_pool_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []
    provider = _RecordingSearch(record=record, fail_ensure=True)
    captured_kwargs: dict[str, object] = {}
    _patch_registry(monkeypatch, provider, captured_kwargs)

    closed: list[str] = []

    class _ClosingPool(_FakePool):
        async def aclose(self) -> None:
            closed.append("pool_aclose")

    monkeypatch.setattr(search_resolution, "PgVectorPool", _ClosingPool)

    with pytest.raises(AzureError):
        await search_resolution.resolve_search_provider(
            settings=_make_settings(IndexStore.PGVECTOR), credential=MagicMock()
        )

    # Provider is closed before the pool so the SDK client is released
    # over the connection it was layered on; both fire and the error
    # propagates so the trigger decorator owns retry/poison.
    assert record == ["ensure_schema", "aclose"]
    assert closed == ["pool_aclose"]


@pytest.mark.asyncio
async def test_ensure_schema_failure_on_azure_search_closes_provider_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []
    provider = _RecordingSearch(record=record, fail_ensure=True)
    captured_kwargs: dict[str, object] = {}
    _patch_registry(monkeypatch, provider, captured_kwargs)

    with pytest.raises(AzureError):
        await search_resolution.resolve_search_provider(
            settings=_make_settings(IndexStore.AZURE_SEARCH), credential=MagicMock()
        )

    # No pool was opened, so only the provider is closed; the failure
    # still propagates.
    assert record == ["ensure_schema", "aclose"]
