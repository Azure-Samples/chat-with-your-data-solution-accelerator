"""Tests for the pgvector search provider (Phase 4 task #30).

Pillar: Stable Core
Phase: 4

Asserts on (a) registry key matches `index_store` Literal lowercase
so dispatch is registry-only (Hard Rule #4), (b) hybrid SQL shape
(parameterized, vector cast, ORDER BY cosine distance), (c) FTS
fallback when no vector is supplied, (d) row -> SearchResult mapping,
(e) the provider does NOT close the injected pool.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncio
import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import pytest

from backend.core.providers.search import registry as search_registry
from backend.core.providers.search.base import SourceListing
from backend.core.providers.search.pgvector import PgVector, _format_vector_literal
from backend.core.settings import (
    AppSettings,
    DatabaseSettings,
    OpenAISettings,
    SearchSettings,
)
from backend.core.types import SearchDocument

_PGVECTOR_LOGGER_NAME = "backend.core.providers.search.pgvector"


def _make_settings(top_k: int = 5, dimensions: int = 1536) -> AppSettings:
    s = MagicMock(spec=AppSettings)
    s.search = SearchSettings(top_k=top_k, use_semantic_search=False)
    s.database = DatabaseSettings(
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint="postgresql://x:5432/cwyd?sslmode=require",
        postgres_admin_principal_name="id-cwyd001",
    )
    s.openai = OpenAISettings(embedding_dimensions=dimensions)
    return s


def _make_pool(rows: list[dict[str, Any]] | None = None) -> MagicMock:
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows or [])
    pool.execute = AsyncMock(return_value="CREATE")
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
    # search registry dispatches via Hard Rule #4 (no name-mapping).
    assert "pgvector" in search_registry.registry.keys()
    assert search_registry.registry.get("pgvector") is PgVector


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
async def test_search_accepts_and_ignores_use_semantic_search() -> None:
    # pgvector has no semantic re-ranking mode; the flag exists only for
    # BaseSearch-seam parity. Passing it must not alter the emitted SQL
    # or raise -- the query runs exactly as if it were omitted.
    pool = _make_pool([_row(score=0.42)])
    provider = PgVector(
        settings=_make_settings(top_k=3), credential=AsyncMock(), pool=pool
    )

    hits = await provider.search("ping", use_semantic_search=True)

    assert len(hits) == 1
    sql, query_param, top_param = pool.fetch.await_args.args
    assert "to_tsvector('english', content)" in sql
    assert query_param == "ping"
    assert top_param == 3


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
    provider = search_registry.registry.get("pgvector")(
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


@pytest.mark.asyncio
async def test_search_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SDK-level failure on `pool.fetch` must surface via the boundary
    wrap with canonical extras + re-raise so the router layer can map
    to a sanitized HTTPException. Mirrors the `azure_search` contract.
    """
    pool = MagicMock()
    pool.fetch = AsyncMock(
        side_effect=asyncpg.PostgresError("connection terminated")
    )
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    with caplog.at_level("ERROR", logger=_PGVECTOR_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await provider.search("hello", vector=[0.1])

    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR"
        and getattr(r, "operation", None) == "search"
        and getattr(r, "provider", None) == "pgvector"
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record with operation=search/provider=pgvector, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    pool.fetch.assert_awaited_once()


# ---------------------------------------------------------------------------
# delete_by_source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_source_emits_parameterized_delete_with_title_filter() -> None:
    pool = _make_pool([{"id": "chunk-1"}, {"id": "chunk-2"}])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    deleted = await provider.delete_by_source("sample.pdf")

    assert deleted == 2
    sql, source_param = pool.fetch.await_args.args
    assert "DELETE FROM documents" in sql
    assert "WHERE title = $1" in sql
    assert "RETURNING id" in sql
    assert source_param == "sample.pdf"


@pytest.mark.asyncio
async def test_delete_by_source_returns_zero_when_no_rows_match() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    deleted = await provider.delete_by_source("nope.pdf")

    assert deleted == 0


@pytest.mark.asyncio
async def test_delete_by_source_interpolates_custom_table_name_in_sql() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
        table="cwyd_chunks",
    )

    await provider.delete_by_source("any.pdf")

    sql = pool.fetch.await_args.args[0]
    assert "DELETE FROM cwyd_chunks WHERE title = $1" in sql


@pytest.mark.asyncio
async def test_delete_by_source_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = MagicMock()
    pool.fetch = AsyncMock(
        side_effect=asyncpg.PostgresError("connection terminated")
    )
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    with caplog.at_level("ERROR", logger=_PGVECTOR_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await provider.delete_by_source("sample.pdf")

    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR"
        and getattr(r, "operation", None) == "delete_by_source"
        and getattr(r, "provider", None) == "pgvector"
        and getattr(r, "source", None) == "sample.pdf"
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record with operation=delete_by_source/provider=pgvector, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    pool.fetch.assert_awaited_once()


# ---------------------------------------------------------------------------
# list_sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sources_emits_group_by_title_with_count_aggregate() -> None:
    ts_alpha = datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)
    ts_beta = datetime(2026, 6, 21, 12, 30, tzinfo=timezone.utc)
    pool = _make_pool(
        [
            {"source": "alpha.pdf", "chunk_count": 3, "last_modified": ts_alpha},
            {"source": "beta.pdf", "chunk_count": 7, "last_modified": ts_beta},
            # Defensive: a NULL aggregate maps to None (can't occur with
            # the NOT NULL column, but the mapper handles it).
            {"source": "gamma.pdf", "chunk_count": 1, "last_modified": None},
        ]
    )
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    listings = await provider.list_sources()

    sql = pool.fetch.await_args.args[0]
    assert "FROM documents" in sql
    assert "GROUP BY title" in sql
    assert "COUNT(*) AS chunk_count" in sql
    assert "MAX(last_modified) AS last_modified" in sql
    assert "ORDER BY title" in sql
    assert "WHERE title IS NOT NULL" in sql
    # Single positional arg -- no params.
    assert len(pool.fetch.await_args.args) == 1
    assert listings == [
        SourceListing(
            source="alpha.pdf", chunk_count=3, last_modified=ts_alpha.isoformat()
        ),
        SourceListing(
            source="beta.pdf", chunk_count=7, last_modified=ts_beta.isoformat()
        ),
        SourceListing(source="gamma.pdf", chunk_count=1, last_modified=None),
    ]


@pytest.mark.asyncio
async def test_list_sources_returns_empty_when_no_rows() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    assert await provider.list_sources() == []


@pytest.mark.asyncio
async def test_list_sources_interpolates_custom_table_name_in_sql() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
        table="cwyd_chunks",
    )

    await provider.list_sources()

    sql = pool.fetch.await_args.args[0]
    assert "FROM cwyd_chunks" in sql


@pytest.mark.asyncio
async def test_list_sources_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = MagicMock()
    pool.fetch = AsyncMock(
        side_effect=asyncpg.PostgresError("connection terminated")
    )
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    with caplog.at_level("ERROR", logger=_PGVECTOR_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await provider.list_sources()

    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR"
        and getattr(r, "operation", None) == "list_sources"
        and getattr(r, "provider", None) == "pgvector"
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record with operation=list_sources/provider=pgvector, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    pool.fetch.assert_awaited_once()


# ---------------------------------------------------------------------------
# merge_or_upload_documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_or_upload_documents_returns_empty_without_pool_call() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    result = await provider.merge_or_upload_documents(documents=[])

    assert result == []
    pool.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_merge_or_upload_documents_emits_upsert_with_returning_id() -> None:
    # Use literal Records (just dicts here since the provider only
    # forwards them) so the test verifies the RETURNING shape is
    # preserved through the boundary.
    pool = _make_pool([{"id": "a"}, {"id": "b"}])
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )
    docs = [
        SearchDocument(id="a", content="hello", title="t1", content_vector=[0.1, 0.2]),
        SearchDocument(id="b", content="world", title="t2", content_vector=[0.3, 0.4]),
    ]

    result = await provider.merge_or_upload_documents(documents=docs)

    assert result == [{"id": "a"}, {"id": "b"}]
    sql, *params = pool.fetch.await_args.args
    assert "INSERT INTO documents (id, content, title, content_vector)" in sql
    # Two-row VALUES list: $1..$4 then $5..$8.
    assert "($1, $2, $3, $4::vector)" in sql
    assert "($5, $6, $7, $8::vector)" in sql
    assert "ON CONFLICT (id) DO UPDATE SET" in sql
    assert "content = EXCLUDED.content" in sql
    assert "title = EXCLUDED.title" in sql
    assert "content_vector = EXCLUDED.content_vector" in sql
    assert "last_modified = now()" in sql
    assert "RETURNING id" in sql
    assert params == [
        "a", "hello", "t1", "[0.1,0.2]",
        "b", "world", "t2", "[0.3,0.4]",
    ]


@pytest.mark.asyncio
async def test_merge_or_upload_documents_interpolates_custom_table_name() -> None:
    pool = _make_pool([])
    provider = PgVector(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
        table="cwyd_chunks",
    )
    docs = [SearchDocument(id="a", content="hello", content_vector=[0.0])]

    await provider.merge_or_upload_documents(documents=docs)

    sql = pool.fetch.await_args.args[0]
    assert "INSERT INTO cwyd_chunks (id, content, title, content_vector)" in sql


@pytest.mark.asyncio
async def test_merge_or_upload_documents_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = MagicMock()
    pool.fetch = AsyncMock(
        side_effect=asyncpg.PostgresError("connection terminated")
    )
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )
    docs = [SearchDocument(id="a", content="hello", content_vector=[0.1])]

    with caplog.at_level("ERROR", logger=_PGVECTOR_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await provider.merge_or_upload_documents(documents=docs)

    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR"
        and getattr(r, "operation", None) == "merge_or_upload_documents"
        and getattr(r, "provider", None) == "pgvector"
        and getattr(r, "document_count", None) == 1
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record with operation=merge_or_upload_documents/provider=pgvector/document_count=1, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    pool.fetch.assert_awaited_once()


# ---------------------------------------------------------------------------
# ensure_schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_schema_runs_extension_table_and_index_ddl_in_one_call() -> None:
    pool = _make_pool()
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    await provider.ensure_schema()

    pool.execute.assert_awaited_once()
    sql = pool.execute.await_args.args[0]
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE TABLE IF NOT EXISTS documents" in sql
    assert "last_modified   TIMESTAMPTZ NOT NULL DEFAULT now()" in sql
    assert "content_vector  vector(1536) NOT NULL" in sql
    # Idempotent backfill so deploys whose table predates the column
    # pick it up (CREATE TABLE IF NOT EXISTS won't alter an existing one).
    assert (
        "ADD COLUMN IF NOT EXISTS last_modified TIMESTAMPTZ NOT NULL DEFAULT now()"
        in sql
    )
    assert "CREATE INDEX IF NOT EXISTS documents_vec_hnsw" in sql
    assert "USING hnsw (content_vector vector_cosine_ops)" in sql


@pytest.mark.asyncio
async def test_ensure_schema_uses_configured_embedding_dimensions() -> None:
    pool = _make_pool()
    provider = PgVector(
        settings=_make_settings(dimensions=3072),
        credential=AsyncMock(),
        pool=pool,
    )

    await provider.ensure_schema()

    sql = pool.execute.await_args.args[0]
    assert "content_vector  vector(3072) NOT NULL" in sql
    assert "vector(1536)" not in sql


@pytest.mark.asyncio
async def test_ensure_schema_interpolates_custom_table_name() -> None:
    pool = _make_pool()
    provider = PgVector(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=pool,
        table="cwyd_chunks",
    )

    await provider.ensure_schema()

    sql = pool.execute.await_args.args[0]
    assert "CREATE TABLE IF NOT EXISTS cwyd_chunks" in sql
    assert "CREATE INDEX IF NOT EXISTS cwyd_chunks_vec_hnsw" in sql
    assert "ON cwyd_chunks USING hnsw" in sql


@pytest.mark.asyncio
async def test_ensure_schema_is_idempotent_across_repeat_calls() -> None:
    pool = _make_pool()
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    await provider.ensure_schema()
    await provider.ensure_schema()
    await provider.ensure_schema()

    # Single-flight: DDL runs exactly once across N calls in the
    # same process. The `_schema_ready` flag short-circuits repeats.
    assert pool.execute.await_count == 1


@pytest.mark.asyncio
async def test_ensure_schema_concurrent_callers_run_ddl_once() -> None:
    pool = _make_pool()
    provider = PgVector(
        settings=_make_settings(), credential=AsyncMock(), pool=pool
    )

    # Three concurrent first-use callers. The asyncio.Lock + the
    # double-checked `_schema_ready` flag must ensure only one of
    # them actually executes the DDL; the other two find the flag
    # set inside the lock and short-circuit.
    await asyncio.gather(
        provider.ensure_schema(),
        provider.ensure_schema(),
        provider.ensure_schema(),
    )

    assert pool.execute.await_count == 1


@pytest.mark.asyncio
async def test_ensure_schema_logs_and_reraises_on_postgres_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = MagicMock()
    pool.execute = AsyncMock(
        side_effect=asyncpg.PostgresError("permission denied for schema public")
    )
    provider = PgVector(
        settings=_make_settings(dimensions=1536),
        credential=AsyncMock(),
        pool=pool,
    )

    with caplog.at_level("ERROR", logger=_PGVECTOR_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await provider.ensure_schema()

    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR"
        and getattr(r, "operation", None) == "ensure_schema"
        and getattr(r, "provider", None) == "pgvector"
        and getattr(r, "table", None) == "documents"
        and getattr(r, "dimensions", None) == 1536
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record with operation=ensure_schema/provider=pgvector/table=documents/dimensions=1536, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    pool.execute.assert_awaited_once()
    # Failure must NOT flip the readiness flag -- a retry should
    # re-attempt the DDL rather than silently no-op.
    assert provider._schema_ready is False  # type: ignore[attr-defined]
