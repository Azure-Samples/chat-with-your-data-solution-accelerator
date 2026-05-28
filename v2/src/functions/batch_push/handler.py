"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline, task #41)

Pure orchestration handler for the ``batch_push`` blueprint.

``batch_push_handler`` composes the previously-landed Phase 6 units --
:func:`functions.batch_push.blob_fetcher.download_blob`, the
:class:`backend.core.providers.parsers.base.BaseParser` registry, the
:class:`backend.core.providers.embedders.base.BaseEmbedder` registry,
and :func:`backend.core.providers.search.writer.push_documents` -- into
the per-message ingestion step that consumes one
:class:`BatchPushQueueMessage` and writes embedded chunks into the
configured search index.

Design notes:

* Every collaborator is injected (DI). Credentials wiring, container /
  search-client construction, and the queue-trigger binding live in
  the next units (function_app.py blueprint registration). Client
  injection keeps the handler directly unit-testable without spinning
  up Azurite / a real Search service.
* No try/except wrapper here. ``download_blob``, the embedder, and
  :func:`push_documents` already wrap their SDK boundaries per
  [v2/docs/exception_handling_policy.md] section "Functions
  blueprints". Adding another layer would double-log. Any exception
  propagates so the Functions runtime applies its retry / poison-queue
  policy.
* Empty-chunk inputs (whitespace-only file, parser returns ``[]``)
  short-circuit before any embedder / search call. The Functions log
  emits a single info entry so operators can spot zero-chunk files
  without having to correlate parser + search records by job id.
"""

import logging

from azure.storage.blob.aio import ContainerClient

from backend.core.providers.embedders.base import BaseEmbedder
from backend.core.providers.parsers.base import BaseParser
from backend.core.providers.search.writer import (
    SupportsMergeOrUploadDocuments,
    push_documents,
)
from backend.core.types import Chunk, SearchDocument
from functions.batch_push.blob_fetcher import download_blob
from functions.core.contracts import BatchPushQueueMessage

logger = logging.getLogger(__name__)


def _build_document(chunk: Chunk, vector: list[float]) -> SearchDocument:
    """Map a parsed chunk + its vector into a :class:`SearchDocument`.

    Field names mirror the read-side mapping in
    :class:`backend.core.providers.search.azure_search.AzureSearch` so an
    in-place upgrade doesn't require a reindex (``id``, ``content``,
    ``title``, ``content_vector``). ``url`` is intentionally omitted --
    blob SAS / source URLs are an ``add_url`` (#42) concern.
    """
    return SearchDocument(
        id=chunk.id,
        content=chunk.content,
        title=chunk.source,
        content_vector=vector,
    )


async def batch_push_handler(
    message: BatchPushQueueMessage,
    container_client: ContainerClient,
    parser: BaseParser,
    embedder: BaseEmbedder,
    search_writer: SupportsMergeOrUploadDocuments,
) -> list[SearchDocument]:
    """Download → parse → embed → push one ``batch_push`` message.

    Returns the documents handed to :func:`push_documents` (in chunk
    order) so the future HTTP / queue-trigger wrapper can include a
    count in traces and tests can assert on the wire shape end-to-end.
    """
    content = await download_blob(container_client, message.filename)
    chunks = await parser.parse(content, source=message.filename)
    if not chunks:
        logger.info(
            "batch_push produced zero chunks",
            extra={
                "operation": "batch_push_handler",
                "container": message.container_name,
                "blob_filename": message.filename,
                "ingestion_job_id": message.ingestion_job_id,
            },
        )
        return []

    embedding_results = await embedder.embed(chunks)
    vectors = [vector for result in embedding_results for vector in result.vectors]
    if len(vectors) != len(chunks):
        raise RuntimeError(
            "batch_push embedder vector count mismatch: expected "
            f"{len(chunks)} vectors for {message.filename!r}, got {len(vectors)}."
        )

    documents = [
        _build_document(chunk, vector) for chunk, vector in zip(chunks, vectors)
    ]
    await push_documents(search_writer, documents)
    return documents
