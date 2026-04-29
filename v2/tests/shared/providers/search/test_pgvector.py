"""Tests for the pgvector search provider (Phase 4 task #30).

Pillar: Stable Core
Phase: 4

Asserts on (a) registry key matches `index_store` Literal lowercase
so dispatch is registry-only (Hard Rule #4), (b) hybrid SQL shape
(parameterized, vector cast, ORDER BY cosine distance), (c) FTS
fallback when no vector is supplied, (d) row -> SearchResult mapping,
(e) the provider does NOT close the injected pool.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.providers import search
from shared.providers.search.pgvector import PgVector, _format_vector_literal
from shared.settings import AppSettings, DatabaseSettings, SearchSettings


def _make_settings(top_k: int = 5) -> AppSettings:
    s = MagicMock(spec=AppSettings)
    s.search = SearchSettings(top_k=top_k, use_semantic_search=False)
    s.database = DatabaseSettings(
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint="postgresql://x:5432/cwyd?sslmode=require",
        postgres_admin_principal_name="id-cwyd001",
    )
    return s


def _make_pool(rows: list[dict[str, Any]] | None = None) -> MagicMock:
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows or [])
    pool.close = AsyncMock()
    return pool


def _row(
    *,
    id: str = "doc-1",
    content: str = "hello",
    title: str = "t",
    url: str = "https://example.com/a",
    score: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": id,
        "content": content,
        "title": title,
        "url": url,
        "score": score,
    }


def test_pgvector_registers_under_index_store_literal_lowercase() -> None:
    # Key must equal `settings.database.index_store.lower()` so
    # search.create() dispatches via registry alone (Hard Rule #4).
    assert "pgvector" in search.registry.keys()
    assert search.registry.get("pgvector") is PgVector


def test_format_vector_literal_emits_pgvector_text_form() -> None:
    assert _format_vector_literal([0.1, -0.5, 1.0]) == "[0.1,-0.5,1.0]"


@pytest.mark.asyncio
async def test_search_with_vector_uses_cosine_distance_and_limits_top_k() -> None:
    pool = _make_pool([_row(score=0.95), _row(id="doc-2", score=0.80)])
    provider = PgVector(
        settings=_make_settings(top_k=5), credential=AsyncMock(), pool=pool
    )

    hits = await provider.search("hi", vector=[0.1, 0.2, 0.3], top_k=2)

    assert len(hits) == 2
    assert hits[0].id == "doc-1"
    assert hits[0].score == pytest.approx(0.95)

    sql, vec_param, top_param = pool.fetch.await_args.args
    assert "<=> $1::vector" in sql
    assert "ORDER BY content_vector <=> $1::vector" in sql
    assert "LIMIT $2" in sql
    assert vec_param == "[0.1,0.2,0.3]"
    assert top_param == 2


@pytest.mark.asyncio
async def test_search_falls_back_to_fts_when_no_vector_supplied() -> None:
    pool = _make_pool([_row(score=0.42)])
    provider = PgVector(
        settings=_make_settings(top_k=3), credential=AsyncMock(), pool=pool
    )

    hits = await provider.search("ping")

    assert len(hits) == 1
    sql, query_param, top_param = pool.fetch.await_args.args
    assert "to_tsvector('english', content)" in sql
    assert "plainto_tsquery('english', $1)" in sql
    assert "ORDER BY score DESC LIMIT $2" in sql
    assert query_param == "ping"
    assert top_param == 3  # default top_k from settings


@pytest.mark.asyncio
async def test_search_appends_filter_expression_in_vector_mode() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )
    await provider.search(
        "q",
        vector=[0.0, 0.0],
        filter_expression="title = 'a'",
    )
    sql = pool.fetch.await_args.args[0]
    assert "WHERE title = 'a'" in sql


@pytest.mark.asyncio
async def test_search_appends_filter_expression_in_fts_mode() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )
    await provider.search("q", filter_expression="title = 'a'")
    sql = pool.fetch.await_args.args[0]
    assert "AND (title = 'a')" in sql


@pytest.mark.asyncio
async def test_search_handles_null_string_fields_gracefully() -> None:
    pool = _make_pool(
        [{"id": "x", "content": None, "title": None, "url": None, "score": None}]
    )
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )
    hits = await provider.search("q", vector=[0.0])
    assert hits[0].content == ""
    assert hits[0].title == ""
    assert hits[0].url == ""
    assert hits[0].score is None


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_pool() -> None:
    # Pool ownership stays with PostgresClient. Closing it here would
    # kill chat-history I/O.
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )
    await provider.aclose()
    pool.close.assert_not_called()


def test_search_create_returns_pgvector_instance_via_registry() -> None:
    pool = _make_pool([])
    provider = search.create(
        "pgvector",
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
    )
    assert isinstance(provider, PgVector)


def test_custom_table_name_is_interpolated() -> None:
    # Whitelisted at construction so SQL injection isn't possible from
    # untrusted input.
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
        table="cwyd_chunks",
    )
    assert provider._table == "cwyd_chunks"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_custom_table_name_appears_in_emitted_sql() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
        table="cwyd_chunks",
    )
    await provider.search("q", vector=[0.0])
    sql = pool.fetch.await_args.args[0]
    assert "FROM cwyd_chunks " in sql
