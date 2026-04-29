"""pgvector-backed search provider.

Pillar: Stable Core
Phase: 4

Reads from a `documents` table populated by the Postgres ingestion
pipeline (Phase 5). Schema (created by the ingestion side, not here):

    CREATE TABLE documents (
        id              TEXT PRIMARY KEY,
        content         TEXT NOT NULL,
        title           TEXT,
        url             TEXT,
        content_vector  vector(1536) NOT NULL
    );
    CREATE INDEX documents_vec_hnsw
        ON documents USING hnsw (content_vector vector_cosine_ops);

Hybrid retrieval is approximated as **cosine similarity over the
embedding** when a `vector` is provided; without one we fall back to
Postgres full-text search via `to_tsvector` / `plainto_tsquery`. The
caller (chat pipeline) is expected to embed the query upstream so
both modes are exercised.

DI: takes an `asyncpg.Pool` directly so a *single* pool/process is
shared with the chat-history database client (task #30 contract).
The lifespan bootstraps the postgres client (`ensure_pool()`) and
then hands its pool to this provider.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from shared.types import SearchResult

from . import registry
from .base import BaseSearch

if TYPE_CHECKING:
    import asyncpg
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


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
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
        *,
        pool: "asyncpg.Pool",
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

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
    ) -> Sequence[SearchResult]:
        cfg = self._settings.search
        effective_top_k = top_k if top_k is not None else cfg.top_k
        # Table name is whitelisted at construction (`self._table`),
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

        rows = await self._pool.fetch(sql, *params)
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

    async def aclose(self) -> None:
        # Pool ownership stays with PostgresClient -- never close it
        # here or we'd kill the chat-history database too.
        return None
