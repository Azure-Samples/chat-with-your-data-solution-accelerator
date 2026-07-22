"""Tests for the search domain."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)

from backend.core.providers.search import registry as search_registry
from backend.core.providers.search.azure_search import AzureSearch
from backend.core.providers.search.base import BaseSearch, SourceListing
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchDocument, SearchResult

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
async def test_search_semantic_override_true_wins_over_settings_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.use_semantic_search = False
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping", use_semantic_search=True)
    kwargs = client.search.await_args.kwargs
    assert kwargs.get("query_type") is not None
    assert kwargs.get("semantic_configuration_name") == "default"


@pytest.mark.asyncio
async def test_search_semantic_override_false_wins_over_settings_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.use_semantic_search = True
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping", use_semantic_search=False)
    kwargs = client.search.await_args.kwargs
    assert "query_type" not in kwargs
    assert "semantic_configuration_name" not in kwargs


@pytest.mark.asyncio
async def test_search_semantic_none_falls_back_to_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    settings.search.use_semantic_search = True
    client = _make_client()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    await handler.search("ping", use_semantic_search=None)
    kwargs = client.search.await_args.kwargs
    assert kwargs.get("query_type") is not None
    assert kwargs.get("semantic_configuration_name") == "default"


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
    client.search = AsyncMock(side_effect=HttpResponseError(message="429 throttled"))
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

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


# ---------------------------------------------------------------------------
# delete_by_source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_source_collects_ids_then_deletes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.search = AsyncMock(
        return_value=_FakeAsyncIter(
            [
                {"id": "chunk-1", "title": "sample.pdf"},
                {"id": "chunk-2", "title": "sample.pdf"},
                {"id": "chunk-3", "title": "sample.pdf"},
            ]
        )
    )
    client.delete_documents = AsyncMock(return_value=[])
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    deleted = await handler.delete_by_source("sample.pdf")

    assert deleted == 3
    search_kwargs = client.search.await_args.kwargs
    # `title` is searchable but NOT filterable in the deployed index, so
    # the scan must not send a server-side $filter; it pages every chunk
    # selecting id + title and matches the source client-side (mirrors
    # list_sources).
    assert "filter" not in search_kwargs
    assert search_kwargs["select"] == ["id", "title"]
    assert search_kwargs["search_text"] == "*"
    delete_kwargs = client.delete_documents.await_args.kwargs
    assert delete_kwargs["documents"] == [
        {"id": "chunk-1"},
        {"id": "chunk-2"},
        {"id": "chunk-3"},
    ]


@pytest.mark.asyncio
async def test_delete_by_source_returns_zero_when_no_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    # The scan yields chunks, but none whose title matches the source,
    # so nothing is deleted.
    client.search = AsyncMock(
        return_value=_FakeAsyncIter(
            [
                {"id": "chunk-1", "title": "other.pdf"},
                {"id": "chunk-2", "title": "another.pdf"},
            ]
        )
    )
    client.delete_documents = AsyncMock()
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    deleted = await handler.delete_by_source("nope.pdf")

    assert deleted == 0
    client.delete_documents.assert_not_called()


@pytest.mark.asyncio
async def test_delete_by_source_matches_title_client_side_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The scan returns chunks from several sources; only the chunks
    # whose title exactly equals the requested source are deleted.
    # Matching client-side (rather than via a server-side OData $filter
    # on the user-supplied filename) also removes the OData-injection
    # seam a quote-bearing filename would otherwise open.
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.search = AsyncMock(
        return_value=_FakeAsyncIter(
            [
                {"id": "chunk-1", "title": "o'reilly.pdf"},
                {"id": "chunk-2", "title": "other.pdf"},
                {"id": "chunk-3", "title": "o'reilly.pdf"},
            ]
        )
    )
    client.delete_documents = AsyncMock(return_value=[])
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    deleted = await handler.delete_by_source("o'reilly.pdf")

    assert deleted == 2
    assert "filter" not in client.search.await_args.kwargs
    delete_kwargs = client.delete_documents.await_args.kwargs
    assert delete_kwargs["documents"] == [
        {"id": "chunk-1"},
        {"id": "chunk-3"},
    ]


@pytest.mark.asyncio
async def test_delete_by_source_logs_and_reraises_on_azure_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.search = AsyncMock(side_effect=HttpResponseError(message="500 server error"))
    client.delete_documents = AsyncMock()
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    with caplog.at_level("ERROR", logger=_AZURE_SEARCH_LOGGER_NAME):
        with pytest.raises(AzureError):
            await handler.delete_by_source("sample.pdf")

    record = _find_record(caplog, "delete_by_source")
    assert record.provider == "azure_search"
    assert record.index_name == "cwyd-index"
    assert record.source == "sample.pdf"
    assert record.deleted_count == 0
    client.delete_documents.assert_not_called()


# ---------------------------------------------------------------------------
# merge_or_upload_documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_or_upload_documents_calls_sdk_with_keyword_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock(
        return_value=[{"key": "a", "succeeded": True}]
    )
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    docs = [
        SearchDocument(id="a", content="hello", content_vector=[0.1, 0.2]),
        SearchDocument(id="b", content="world", content_vector=[0.3, 0.4]),
    ]

    result = await handler.merge_or_upload_documents(documents=docs)

    client.merge_or_upload_documents.assert_awaited_once_with(
        documents=[d.model_dump() for d in docs]
    )
    assert result == [{"key": "a", "succeeded": True}]


@pytest.mark.asyncio
async def test_merge_or_upload_documents_returns_empty_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock()
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    result = await handler.merge_or_upload_documents(documents=[])

    assert result == []
    client.merge_or_upload_documents.assert_not_called()


@pytest.mark.asyncio
async def test_merge_or_upload_documents_logs_and_reraises_on_azure_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock(
        side_effect=ServiceRequestError(message="search unavailable")
    )
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    docs = [SearchDocument(id="a", content="hello")]

    with caplog.at_level("ERROR", logger=_AZURE_SEARCH_LOGGER_NAME):
        with pytest.raises(AzureError):
            await handler.merge_or_upload_documents(documents=docs)

    record = _find_record(caplog, "merge_or_upload_documents")
    assert record.provider == "azure_search"
    assert record.index_name == "cwyd-index"
    assert record.document_count == 1
    client.merge_or_upload_documents.assert_awaited_once()


# ---------------------------------------------------------------------------
# list_sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sources_aggregates_distinct_sources_from_paged_titles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    # Interleaved chunks across two sources: 3 x alpha, 7 x beta.
    docs = (
        [{"title": "beta.pdf"}] * 4
        + [{"title": "alpha.pdf"}] * 3
        + [{"title": "beta.pdf"}] * 3
    )
    client = _make_client(docs)
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    listings = await handler.list_sources()

    # Sorted alphabetically by source; chunk_count is the per-source tally.
    assert listings == [
        SourceListing(source="alpha.pdf", chunk_count=3, last_modified=None),
        SourceListing(source="beta.pdf", chunk_count=7, last_modified=None),
    ]


@pytest.mark.asyncio
async def test_list_sources_pages_titles_without_faceting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = _make_client([])
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    await handler.list_sources()

    search_kwargs = client.search.await_args.kwargs
    assert search_kwargs["search_text"] == "*"
    assert search_kwargs["select"] == ["title"]
    # No faceting -- the index schema may not mark `title` as facetable.
    assert "facets" not in search_kwargs


@pytest.mark.asyncio
async def test_list_sources_skips_blank_titles_and_returns_empty_when_no_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    # Empty index -> no sources.
    client = _make_client([])
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    assert await handler.list_sources() == []

    # Docs with missing / blank titles are skipped; only real sources count.
    client = _make_client(
        [{"title": ""}, {}, {"title": "gamma.pdf"}, {"title": "gamma.pdf"}]
    )
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)
    assert await handler.list_sources() == [
        SourceListing(source="gamma.pdf", chunk_count=2, last_modified=None),
    ]


@pytest.mark.asyncio
async def test_list_sources_logs_and_reraises_on_azure_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.search = AsyncMock(side_effect=HttpResponseError(message="500 server error"))
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    with caplog.at_level("ERROR", logger=_AZURE_SEARCH_LOGGER_NAME):
        with pytest.raises(AzureError):
            await handler.list_sources()

    record = _find_record(caplog, "list_sources")
    assert record.provider == "azure_search"
    assert record.index_name == "cwyd-index"


# ---------------------------------------------------------------------------
# get_document_by_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_by_key_maps_document_to_search_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.get_document = AsyncMock(
        return_value={
            "id": "chunk-9",
            "content": "Welcome to Contoso Electronics.",
            "title": "Benefit_Options.pdf",
            "url": "https://blob/benefit_options.pdf",
        }
    )
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    result = await handler.get_document_by_key("chunk-9")

    assert isinstance(result, SearchResult)
    assert result.id == "chunk-9"
    assert result.content == "Welcome to Contoso Electronics."
    assert result.title == "Benefit_Options.pdf"
    assert result.url == "https://blob/benefit_options.pdf"
    # A by-key fetch carries no relevance score.
    assert result.score is None


@pytest.mark.asyncio
async def test_get_document_by_key_maps_null_url_to_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A null ``url`` field maps to ``""`` -- never the string ``"None"``.

    A Search document can carry an explicit ``url: null``; ``dict.get("url",
    "")`` returns that ``None`` (the key is present, so the default never
    fires), so the mapper must coerce it to an empty string rather than
    stringifying it to ``"None"``. The enrichment path backfills this ``url``
    onto a KB citation, so a stray ``"None"`` would render as a broken link.
    """
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.get_document = AsyncMock(
        return_value={
            "id": "chunk-9",
            "content": "Welcome to Contoso Electronics.",
            "title": "Benefit_Options.pdf",
            "url": None,
        }
    )
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    result = await handler.get_document_by_key("chunk-9")

    assert result is not None
    assert result.url == ""


@pytest.mark.asyncio
async def test_get_document_by_key_passes_key_and_selected_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.get_document = AsyncMock(return_value={"id": "k1", "content": ""})
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    await handler.get_document_by_key("k1")

    call_kwargs = client.get_document.await_args.kwargs
    assert call_kwargs["key"] == "k1"
    assert call_kwargs["selected_fields"] == ["id", "content", "title", "url"]


@pytest.mark.asyncio
async def test_get_document_by_key_returns_none_when_not_found(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing key is a soft miss: return None, do not log or raise."""
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.get_document = AsyncMock(
        side_effect=ResourceNotFoundError(message="404 not found")
    )
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    with caplog.at_level("ERROR", logger=_AZURE_SEARCH_LOGGER_NAME):
        result = await handler.get_document_by_key("gone")

    assert result is None
    # Not-found is expected control flow, not an error -- nothing logged.
    assert not [
        r
        for r in caplog.records
        if getattr(r, "operation", None) == "get_document_by_key"
    ]


@pytest.mark.asyncio
async def test_get_document_by_key_logs_and_reraises_on_azure_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Any non-not-found SDK failure logs the canonical extras + re-raises."""
    settings = _settings_for_search(monkeypatch)
    client = MagicMock()
    client.get_document = AsyncMock(
        side_effect=HttpResponseError(message="500 server error")
    )
    client.close = AsyncMock()
    handler = AzureSearch(settings=settings, credential=MagicMock(), client=client)

    with caplog.at_level("ERROR", logger=_AZURE_SEARCH_LOGGER_NAME):
        with pytest.raises(AzureError):
            await handler.get_document_by_key("boom")

    record = _find_record(caplog, "get_document_by_key")
    assert record.provider == "azure_search"
    assert record.index_name == "cwyd-index"
