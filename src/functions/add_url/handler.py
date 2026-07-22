"""Pure orchestration handler for the ``add_url`` blueprint.

``add_url_handler`` composes :func:`functions.add_url.url_fetcher.fetch_url`
with the :class:`backend.core.providers.parsers.base.BaseParser`
registry, the :class:`backend.core.providers.embedders.base.BaseEmbedder`
registry, and
:meth:`backend.core.providers.search.base.BaseSearch.merge_or_upload_documents`
into the per-request ingestion step that consumes one
:class:`AddUrlRequest` and writes embedded chunks into the configured
search index.

Mirrors :func:`functions.batch_push.handler.batch_push_handler` so the
two ingestion entry points (queue-triggered blob push vs. HTTP-
triggered URL ingest) share the same parse / embed / push pipeline
shape. The only differences are (a) input source (URL bytes via
httpx vs. blob bytes via Storage SDK) and (b) trigger semantics
(HTTP request vs. queue message).

Design notes:

* Every collaborator is injected (DI). The blueprint dispatches the
  ``search_provider`` via ``search_registry.registry.get(
  settings.database.index_store)`` so the handler stays agnostic of
  whether the write lands in Azure AI Search or in pgvector. Each
  concrete provider owns its own SDK boundary + structured logging
  inside its ``merge_or_upload_documents`` override.
* ``AddUrlRequest`` is defined inline because it is **not** a
  cross-blueprint wire contract -- only the ``add_url`` HTTP
  trigger constructs it and only this handler consumes it.
  Cross-blueprint envelopes (queue messages, event-grid payloads)
  live in :mod:`functions.core.contracts` per the docstring rule
  in that module. Frozen + ``extra="forbid"`` so a malformed HTTP
  body surfaces as a Pydantic ``ValidationError`` at the trigger
  boundary instead of silently dropping fields.
* ``_build_document`` is intentionally duplicated from
  :mod:`functions.batch_push.handler` rather than imported.
  Per-blueprint independence is a Stable Core invariant -- the two
  ingestion paths must be free to evolve their search-document
  shapes independently (e.g., ``add_url`` may later add a
  ``source_url`` field that ``batch_push`` does not need).
* No try/except wrapper here. ``fetch_url``, the embedder, and
  ``search_provider.merge_or_upload_documents`` already wrap their
  SDK boundaries per [v2/docs/exception_handling_policy.md] section
  "Functions blueprints". Adding another layer would double-log.
  Any exception propagates so the HTTP trigger's
  ``@map_function_exceptions("add_url")`` decorator translates it
  into the right ``HttpResponse`` (422 for ``ValidationError``,
  502 for SDK errors, 500 for everything else).
* Empty-chunk inputs (whitespace-only page, parser returns ``[]``)
  short-circuit before any embedder / search call and emit a
  single info log keyed on the URL + ingestion job id so
  operators can correlate zero-chunk URLs across the pipeline.
"""

import logging
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from backend.core.providers.embedders.registry import EmbedderInstance
from backend.core.providers.parsers.base import BaseParser
from backend.core.providers.search.base import BaseSearch
from backend.core.types import Chunk, SearchDocument
from functions.add_url.url_fetcher import fetch_url

logger = logging.getLogger(__name__)


class AddUrlRequest(BaseModel):
    """Typed parameter contract for :func:`add_url_handler`.

    The HTTP trigger builds this from the request JSON body
    so ``url`` validation (non-empty, stripped of whitespace) and
    ``ingestion_job_id`` correlation id assignment both happen at
    a single typed boundary. ``frozen=True`` + ``extra="forbid"``
    mirror the discipline in
    :class:`functions.core.contracts.BatchPushQueueMessage`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1)
    ingestion_job_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)


class AddUrlResponse(BaseModel):
    """Typed response contract for the ``add_url`` HTTP trigger.

    Summarizes a single URL ingestion: the correlation id for the
    request, the URL that was fetched, and how many search documents
    were written to the index. Frozen + ``extra="forbid"`` so the wire
    shape stays a fixed, three-field contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ingestion_job_id: str = Field(
        description="Correlation id for this URL ingestion request."
    )
    url: str = Field(description="The URL that was fetched and ingested.")
    document_count: int = Field(
        description="Number of search documents written to the index for this URL."
    )


def _build_document(chunk: Chunk, vector: list[float]) -> SearchDocument:
    """Map a parsed chunk + its vector into a :class:`SearchDocument`.

    Field names mirror the read-side mapping in
    :class:`backend.core.providers.search.azure_search.AzureSearch` so
    an in-place upgrade does not require a reindex (``id``,
    ``content``, ``title``, ``content_vector``). ``title`` is set to
    the source URL so search-result rendering has a human-readable
    label until an HTML parser with proper ``<title>`` extraction
    ships in a later phase.
    """
    return SearchDocument(
        id=chunk.id,
        content=chunk.content,
        title=chunk.source,
        content_vector=vector,
    )


async def add_url_handler(
    request: AddUrlRequest,
    parser: BaseParser,
    embedder: EmbedderInstance,
    search_provider: BaseSearch,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[SearchDocument]:
    """Fetch -> parse -> embed -> push one ``add_url`` request.

    ``client`` is an optional ``httpx.AsyncClient`` so the HTTP
    trigger can share a single client across requests when
    the Functions host reuses the worker. When omitted, ``fetch_url``
    builds its own per-call client. See :func:`fetch_url` for the
    exact construction semantics.

    Returns the documents handed to
    ``search_provider.merge_or_upload_documents`` (in chunk order) so
    the HTTP trigger can include a count in its response body and
    tests can assert on the wire shape end-to-end.
    """
    content = await fetch_url(request.url, client=client)
    chunks = await parser.parse(content, source=request.url)
    if not chunks:
        logger.info(
            "add_url produced zero chunks",
            extra={
                "operation": "add_url_handler",
                "url": request.url,
                "ingestion_job_id": request.ingestion_job_id,
            },
        )
        return []

    embedding_results = await embedder.embed(chunks)
    vectors = [vector for result in embedding_results for vector in result.vectors]
    if len(vectors) != len(chunks):
        raise RuntimeError(
            "add_url embedder vector count mismatch: expected "
            f"{len(chunks)} vectors for {request.url!r}, got {len(vectors)}."
        )

    documents = [
        _build_document(chunk, vector) for chunk, vector in zip(chunks, vectors)
    ]
    await search_provider.merge_or_upload_documents(documents=documents)
    return documents
