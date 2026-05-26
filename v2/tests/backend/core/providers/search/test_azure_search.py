"""Tests for the search domain (Phase 3 task #21).

Pillar: Stable Core
Phase: 3
"""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ServiceRequestError,
)

from backend.core.providers.search import registry as search_registry
from backend.core.providers.search.azure_search import AzureSearch
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchResult


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeAsyncIter:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> "_FakeAsyncIter":
        return self

    async def __anext__(self) -> Any:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _make_client(docs: list[dict[str, Any]] | None = None) -> MagicMock:
    client = MagicMock()
    client.search = AsyncMock(return_value=_FakeAsyncIter(docs or []))
    client.close = AsyncMock()
    return client


def _settings_for_search(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    """Build a real AppSettings populated for cosmosdb + AzureSearch."""
    env = {
        "AZURE_DB_TYPE": "cosmosdb",
        "AZURE_INDEX_STORE": "AzureSearch",
        "AZURE_COSMOS_ENDPOINT": "https://example.documents.azure.com:443/",
        "AZURE_AI_SEARCH_ENDPOINT": "https://search.example.search.windows.net",
        "AZURE_AI_SEARCH_INDEX": "cwyd-index",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()
    return settings


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_azure_search_is_registered() -> None:
    # Registry is case-insensitive; the registration key is the
    # `settings.database.index_store` Literal value "AzureSearch"
    # (Hard Rule #4 -- registry key matches settings Literal).
    assert "azuresearch" in search_registry.registry.keys()
    assert search_registry.registry.get("AzureSearch") is AzureSearch


def test_search_create_returns_azure_search_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    handler = search_registry.registry.get("AzureSearch")(
        settings=settings,
        credential=MagicMock(),
        client=_make_client(),
    )
    assert isinstance(handler, AzureSearch)
    assert isinstance(handler, BaseSearch)


# ---------------------------------------------------------------------------
# Lazy client construction
# ---------------------------------------------------------------------------


def test_lazy_client_raises_when_endpoint_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    # Mutate the resolved settings to simulate a missing endpoint.
    settings.search.endpoint = ""
    handler = AzureSearch(settings=settings, credential=MagicMock())
    with pytest.raises(RuntimeError, match="ENDPOINT"):
        handler._get_client()


def test_lazy_client_raises_when_index_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.index = ""
    handler = AzureSearch(settings=settings, credential=MagicMock())
    with pytest.raises(RuntimeError, match="INDEX"):
        handler._get_client()


# ---------------------------------------------------------------------------
# search() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_passes_query_top_and_select(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.top_k = 3
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping")
    kwargs = client.search.await_args.kwargs
    assert kwargs["search_text"] == "ping"
    assert kwargs["top"] == 3
    assert set(kwargs["select"]) == {"id", "content", "title", "url"}


@pytest.mark.asyncio
async def test_search_top_k_override_wins_over_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.top_k = 5
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping", top_k=10)
    assert client.search.await_args.kwargs["top"] == 10


@pytest.mark.asyncio
async def test_search_includes_vector_query_when_vector_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping", vector=[0.1, 0.2, 0.3])
    vqs = client.search.await_args.kwargs["vector_queries"]
    assert len(vqs) == 1
    assert vqs[0].vector == [0.1, 0.2, 0.3]
    assert vqs[0].fields == "content_vector"


@pytest.mark.asyncio
async def test_search_omits_vector_query_when_no_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping")
    assert "vector_queries" not in client.search.await_args.kwargs


@pytest.mark.asyncio
async def test_search_passes_filter_pass_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping", filter_expression="category eq 'docs'")
    assert client.search.await_args.kwargs["filter"] == "category eq 'docs'"


@pytest.mark.asyncio
async def test_search_enables_semantic_when_setting_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.use_semantic_search = True
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping")
    kwargs = client.search.await_args.kwargs
    assert kwargs.get("query_type") is not None
    assert kwargs.get("semantic_configuration_name") == "default"


@pytest.mark.asyncio
async def test_search_skips_semantic_when_setting_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.use_semantic_search = False
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping")
    kwargs = client.search.await_args.kwargs
    assert "query_type" not in kwargs
    assert "semantic_configuration_name" not in kwargs


@pytest.mark.asyncio
async def test_search_maps_documents_to_search_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = _make_client(
        docs=[
            {
                "id": "doc-1",
                "content": "hello world",
                "title": "greeting.md",
                "url": "https://example/greeting.md",
                "@search.score": 0.87,
            },
            {
                "id": "doc-2",
                "content": "more content",
                "title": "second.md",
                "url": "https://example/second.md",
                "@search.reranker_score": 1.42,
                "@search.score": 0.5,  # reranker takes priority
            },
        ]
    )
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    results = list(await handler.search("ping"))
    assert len(results) == 2
    assert isinstance(results[0], SearchResult)
    assert results[0].id == "doc-1"
    assert results[0].content == "hello world"
    assert results[0].score == pytest.approx(0.87)
    # Reranker score wins.
    assert results[1].score == pytest.approx(1.42)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.aclose()
    client.close.assert_not_called()


# ---------------------------------------------------------------------------
# Failure-path coverage (Phase C2d -- provider try/except sweep)
# ---------------------------------------------------------------------------
#
# Per v2/docs/exception_handling_policy.md (Provider entry-points + Lifespan
# rows): every `azure.search.documents.aio.SearchClient` call at the
# provider boundary catches `azure.core.exceptions.AzureError` (the
# umbrella for `HttpResponseError`, `ServiceRequestError`, etc.),
# structured-logs via `logger.exception` (`logger.warning` for shutdown),
# and re-raises (or swallows on shutdown best-effort).

_AZURE_SEARCH_LOGGER_NAME = "backend.core.providers.search.azure_search"


def _find_record(
    caplog: pytest.LogCaptureFixture,
    operation: str,
    *,
    level: str = "ERROR",
) -> Any:
    matches = [
        r
        for r in caplog.records
        if r.levelname == level and getattr(r, "operation", None) == operation
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 {level} record for operation={operation!r}, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    return matches[0]


@pytest.mark.asyncio
async def test_search_logs_and_reraises_on_azure_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SDK-level failure (4xx/5xx, transport timeout) on `client.search`
    must surface via the new try wrap with the canonical extras + the
    index name in the log payload, then re-raise so the router layer
    can map to a sanitized HTTPException.
    """
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.search = AsyncMock(
        side_effect=HttpResponseError(message="429 throttled")
    )
    client.close = AsyncMock()
    handler = AzureSearch(
        settings=settings, credential=MagicMock(), client=client
    )

    with caplog.at_level("ERROR", logger=_AZURE_SEARCH_LOGGER_NAME):
        with pytest.raises(AzureError):
            await handler.search("hello")

    record = _find_record(caplog, "search")
    assert record.provider == "azure_search"
    assert record.index_name == "cwyd-index"
    client.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_swallows_and_warns_on_close_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shutdown is best-effort: `SearchClient.close()` failure must NOT
    raise (the container is going away anyway), but a WARNING log must
    fire so the failure is visible in App Insights, and the cached
    client handle must be cleared either way.
    """
    settings = _settings_for_search(monkeypatch)
    # Build a client we OWN (no override) so aclose() takes the close path.
    client = MagicMock()
    client.search = AsyncMock(return_value=_FakeAsyncIter([]))
    client.close = AsyncMock(
        side_effect=ServiceRequestError(message="socket already closed")
    )
    handler = AzureSearch(settings=settings, credential=MagicMock())
    handler._client = client  # type: ignore[attr-defined]
    handler._client_override = None  # type: ignore[attr-defined]

    with caplog.at_level("WARNING", logger=_AZURE_SEARCH_LOGGER_NAME):
        await handler.aclose()  # MUST NOT raise

    record = _find_record(caplog, "aclose", level="WARNING")
    assert record.provider == "azure_search"
    assert record.index_name == "cwyd-index"
    client.close.assert_awaited_once()
    # Cached client handle cleared even though close() failed.
    assert handler._client is None  # type: ignore[attr-defined]
