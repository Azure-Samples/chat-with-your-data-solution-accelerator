"""pgvector-backed search provider.

Reads from / writes to a ``documents`` table whose schema is
auto-created on first use by :meth:`PgVector.ensure_schema` (called
by the backend lifespan and the Functions ingestion blueprints).
Canonical shape:

    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS documents (
        id              TEXT PRIMARY KEY,
        content         TEXT NOT NULL,
        title           TEXT,
        url             TEXT,
        last_modified   TIMESTAMPTZ NOT NULL DEFAULT now(),
        content_vector  vector(<dims>) NOT NULL
    );
    CREATE INDEX IF NOT EXISTS documents_vec_hnsw
        ON documents USING hnsw (content_vector vector_cosine_ops);

Vector column dimensionality is sourced from
``settings.openai.embedding_dimensions`` so deploys targeting
``text-embedding-3-large`` (3072) or shortened-output variants pick
up the right column width at first bootstrap. Changing the
dimension on an existing deploy requires a manual drop+recreate;
``CREATE TABLE IF NOT EXISTS`` does not alter an existing column.

Hybrid retrieval is approximated as **cosine similarity over the
embedding** when a `vector` is provided; without one we fall back to
Postgres full-text search via `to_tsvector` / `plainto_tsquery`. The
caller (chat pipeline) is expected to embed the query upstream so
both modes are exercised.

DI: takes an `asyncpg.Pool` directly so a *single* pool/process is
shared with the chat-history database client.
The lifespan bootstraps the postgres client (`ensure_pool()`) and
then hands its pool to this provider.
"""

import asyncio
from typing import Any, Mapping, Sequence, cast

import logging

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import SearchDocument, SearchResult

from .registry import registry
from .base import BaseSearch, SourceListing


logger = logging.getLogger(__name__)


def _format_vector_literal(vector: Sequence[float]) -> str:
    """pgvector accepts text literals like '[0.1,0.2,...]'.

    asyncpg has no native vector codec out of the box, so we send the
    literal and cast on the SQL side (`$1::vector`).
    """
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


@registry.register("pgvector")
class PgVector(BaseSearch):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        pool: asyncpg.Pool,
        table: str = "documents",
    ) -> None:
        super().__init__(settings, credential)
        # Pool is REQUIRED -- there is no lazy-construct fallback.
        # Callers (lifespan + tests) MUST hand in a pool created by
        # `PostgresClient.ensure_pool()` so we share a single pool
        # per process (Hard Rule: single SDK client / connection
        # per concern).
        self._pool = pool
        self._table = table
        # Single-flight schema bootstrap. The lock serializes the
        # first N concurrent `ensure_schema()` callers so only one
        # executes the DDL; the flag short-circuits every subsequent
        # call. Mirrors `PostgresClient._ensure_pool` precedent.
        self._schema_ready: bool = False
        self._schema_init_lock: asyncio.Lock = asyncio.Lock()

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        use_semantic_search: bool | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
    ) -> Sequence[SearchResult]:
        # pgvector has no semantic re-ranking mode: retrieval is dense
        # cosine (`vector` provided) or Postgres FTS (text fallback), so
        # `use_semantic_search` is accepted for BaseSearch-seam parity
        # and intentionally has no effect here.
        _ = use_semantic_search
        cfg = self._settings.search
        effective_top_k = top_k if top_k is not None else cfg.top_k
        # Table name is allow-listed at construction (`self._table`),
        # never user-supplied -- safe to interpolate. All values are
        # parameterized.
        if vector is not None:
            sql = (
                f"SELECT id, content, title, url, "
                f"1 - (content_vector <=> $1::vector) AS score "
                f"FROM {self._table} "
            )
            params: list[Any] = [_format_vector_literal(vector)]
            if filter_expression:
                sql += f"WHERE {filter_expression} "
            sql += "ORDER BY content_vector <=> $1::vector LIMIT $2"
            params.append(effective_top_k)
        else:
            # Text-only fallback: Postgres FTS. ts_rank gives a
            # comparable [0..1] score so callers can blend with
            # vector hits if they ever query both modes.
            sql = (
                f"SELECT id, content, title, url, "
                f"ts_rank(to_tsvector('english', content), "
                f"plainto_tsquery('english', $1)) AS score "
                f"FROM {self._table} "
                f"WHERE to_tsvector('english', content) @@ "
                f"plainto_tsquery('english', $1) "
            )
            params = [query]
            if filter_expression:
                sql += f"AND ({filter_expression}) "
            sql += "ORDER BY score DESC LIMIT $2"
            params.append(effective_top_k)

        try:
            rows = cast(
                "list[Mapping[str, Any]]",
                await self._pool.fetch(
                    sql, *params
                ),  # pyright: ignore[reportUnknownMemberType]
            )
        except asyncpg.PostgresError:
            # SDK boundary per Hard Rule #14: structured-log with the
            # canonical extras and re-raise so the router layer can map
            # to a sanitized HTTPException. Mirrors `azure_search.py`.
            logger.exception(
                "pgvector search failed",
                extra={"operation": "search", "provider": "pgvector"},
            )
            raise
        return [
            SearchResult(
                id=str(r["id"]),
                content=str(r["content"] or ""),
                title=str(r["title"] or ""),
                url=str(r["url"] or ""),
                score=float(r["score"]) if r["score"] is not None else None,
            )
            for r in rows
        ]

    async def delete_by_source(self, source: str) -> int:
        # Same `title` field as Azure Search (ingestion writes source
        # filename / URL there for every chunk). RETURNING id lets us
        # report the deletion count without a separate SELECT.
        sql = f"DELETE FROM {self._table} WHERE title = $1 RETURNING id"
        try:
            rows = cast(
                "list[Mapping[str, Any]]",
                await self._pool.fetch(
                    sql, source
                ),  # pyright: ignore[reportUnknownMemberType]
            )
        except asyncpg.PostgresError:
            logger.exception(
                "pgvector delete_by_source failed",
                extra={
                    "operation": "delete_by_source",
                    "provider": "pgvector",
                    "source": source,
                },
            )
            raise
        return len(rows)

    async def list_sources(self) -> list[SourceListing]:
        # `last_modified` is the most recent chunk timestamp per source
        # (MAX over the per-row `last_modified` column written at ingest
        # / re-ingest). NULL titles are excluded so the admin grid never
        # shows a blank-name row (a chunk with no source can't be deleted
        # by the matching `delete_by_source` route anyway).
        sql = (
            f"SELECT title AS source, COUNT(*) AS chunk_count, "
            f"MAX(last_modified) AS last_modified "
            f"FROM {self._table} "
            f"WHERE title IS NOT NULL "
            f"GROUP BY title "
            f"ORDER BY title"
        )
        try:
            rows = cast(
                "list[Mapping[str, Any]]",
                await self._pool.fetch(sql),  # pyright: ignore[reportUnknownMemberType]
            )
        except asyncpg.PostgresError:
            logger.exception(
                "pgvector list_sources failed",
                extra={
                    "operation": "list_sources",
                    "provider": "pgvector",
                },
            )
            raise
        return [
            SourceListing(
                source=str(row["source"]),
                chunk_count=int(row["chunk_count"]),
                last_modified=(
                    row["last_modified"].isoformat()
                    if row["last_modified"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    async def merge_or_upload_documents(
        self,
        *,
        documents: Sequence[SearchDocument],
    ) -> list[Any]:
        if not documents:
            return []
        # Single-statement upsert: one VALUES list keeps the batch to
        # one round-trip. Each row contributes 4 positional params,
        # well under Postgres's 65 535-param ceiling for typical
        # ingestion batches. `$N::vector` casts each text literal
        # (built by `_format_vector_literal`) to pgvector inline
        # because asyncpg has no native vector codec.
        placeholders: list[str] = []
        params: list[Any] = []
        for index, doc in enumerate(documents):
            base = index * 4
            placeholders.append(
                f"(${base + 1}, ${base + 2}, ${base + 3}, ${base + 4}::vector)"
            )
            params.extend(
                (
                    doc.id,
                    doc.content,
                    doc.title,
                    _format_vector_literal(doc.content_vector),
                )
            )
        sql = (
            f"INSERT INTO {self._table} (id, content, title, content_vector) "
            f"VALUES {', '.join(placeholders)} "
            f"ON CONFLICT (id) DO UPDATE SET "
            f"content = EXCLUDED.content, "
            f"title = EXCLUDED.title, "
            f"content_vector = EXCLUDED.content_vector, "
            f"last_modified = now() "
            f"RETURNING id"
        )
        try:
            rows = cast(
                "list[Mapping[str, Any]]",
                await self._pool.fetch(
                    sql, *params
                ),  # pyright: ignore[reportUnknownMemberType]
            )
        except asyncpg.PostgresError:
            logger.exception(
                "pgvector merge_or_upload_documents failed",
                extra={
                    "operation": "merge_or_upload_documents",
                    "provider": "pgvector",
                    "document_count": len(documents),
                },
            )
            raise
        return list(rows)

    async def aclose(self) -> None:
        # Pool ownership stays with PostgresClient -- never close it
        # here or we'd kill the chat-history database too.
        return None

    async def ensure_schema(self) -> None:
        # Fast path: already bootstrapped this process.
        if self._schema_ready:
            return
        async with self._schema_init_lock:
            # Double-check inside the lock -- a concurrent caller may
            # have completed the bootstrap while we waited to acquire.
            if self._schema_ready:
                return
            dimensions = self._settings.openai.embedding_dimensions
            # Table name + dimensions are allow-listed at
            # construction / settings load (never user-supplied) so
            # interpolation is safe; the DDL itself has no
            # parameters that asyncpg could parameterize.
            sql = (
                "CREATE EXTENSION IF NOT EXISTS vector;\n"
                f"CREATE TABLE IF NOT EXISTS {self._table} (\n"
                "    id              TEXT PRIMARY KEY,\n"
                "    content         TEXT NOT NULL,\n"
                "    title           TEXT,\n"
                "    url             TEXT,\n"
                "    last_modified   TIMESTAMPTZ NOT NULL DEFAULT now(),\n"
                f"    content_vector  vector({dimensions}) NOT NULL\n"
                ");\n"
                # Backfill the timestamp column on deploys whose table
                # predates it -- CREATE TABLE IF NOT EXISTS never alters
                # an existing table, so an explicit idempotent ADD COLUMN
                # carries the migration. Existing rows take now() at
                # migration time until they are re-ingested.
                f"ALTER TABLE {self._table} ADD COLUMN IF NOT EXISTS "
                "last_modified TIMESTAMPTZ NOT NULL DEFAULT now();\n"
                f"CREATE INDEX IF NOT EXISTS {self._table}_vec_hnsw "
                f"ON {self._table} USING hnsw "
                "(content_vector vector_cosine_ops);"
            )
            try:
                await self._pool.execute(
                    sql
                )  # pyright: ignore[reportUnknownMemberType]
            except asyncpg.PostgresError:
                logger.exception(
                    "pgvector ensure_schema failed",
                    extra={
                        "operation": "ensure_schema",
                        "provider": "pgvector",
                        "table": self._table,
                        "dimensions": dimensions,
                    },
                )
                raise
            self._schema_ready = True
