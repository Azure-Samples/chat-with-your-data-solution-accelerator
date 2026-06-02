"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Queue-trigger blueprint that consumes ``batch_push`` messages and runs
:func:`functions.batch_push.handler.batch_push_handler` once per
message.

Wire shape:

* **Trigger** -- ``azure.functions.QueueMessage`` binding against the
  queue named by the ``AZURE_DOC_PROCESSING_QUEUE`` app-setting
  (expanded by the Functions host via the ``%...%`` env-ref
  convention). Connection is the standard ``AzureWebJobsStorage``
  identity-based binding (``AzureWebJobsStorage__queueServiceUri``
  + ``AzureWebJobsStorage__credential=managedidentity``
  + ``AzureWebJobsStorage__clientId=<UAMI client id>`` wired by Bicep).
* **Producer** -- :mod:`functions.batch_start.queue_writer` enqueues
  :class:`BatchPushQueueMessage` envelopes via ``model_dump_json()``.
* **Failure mode** -- :func:`functions.core.exception_mapping.log_queue_errors`
  logs a structured trail (warning on validation drift, exception on
  AzureError / generic) and **re-raises** so the runtime applies its
  retry policy and ultimately moves the message to the poison queue.

Thin composition over the ``functions/core/`` helpers:

* :func:`functions.batch_push.queue_reader.parse_push_message` --
  decode + Pydantic-validate the envelope.
* :func:`functions.core.storage_endpoints.resolve_storage_endpoints` --
  derive the blob endpoint (queue endpoint is owned by the trigger
  binding, not this body).
* :func:`functions.core.exception_mapping.log_queue_errors` -- owns
  the observability ladder.
* :func:`functions.batch_push.handler.batch_push_handler` -- pure
  orchestration (download -> parse -> embed -> push).

Registry-first collaborator wiring (Hard Rule #4):

* Credentials provider via ``credentials_registry``.
* Parser via ``ingestion_parsers_registry`` (key resolved from the
  blob filename extension; see :func:`_parser_key_for_filename`).
* Embedder via ``embedders_registry`` -- the post-Phase-6 default key
  is ``"azure_openai"`` (single concrete embedder today; an alternate
  concrete would land in §4.6.1 and the lookup key would be lifted
  to settings then).
* Search write target via ``search_registry`` keyed on
  ``settings.database.index_store`` -- ``"AzureSearch"`` returns an
  :class:`backend.core.providers.search.azure_search.AzureSearch`
  instance that owns its own SDK client; ``"pgvector"`` returns a
  :class:`backend.core.providers.search.pgvector.PgVector` instance
  that needs the asyncpg pool wired via
  :class:`functions.core.pgvector_pool.PgVectorPool`. Both concretes
  satisfy ``BaseSearch.merge_or_upload_documents`` so the handler
  stays provider-agnostic.

The private :func:`_execute` helper remains the single seam that
unit tests monkeypatch so they do not need Azurite, a real
credential, or a real Search service.
"""

from pathlib import PurePosixPath
from typing import Any

import azure.functions as func
from azure.storage.blob.aio import ContainerClient

from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.embedders import registry as embedders_registry
from backend.core.providers.search import registry as search_registry
from backend.core.settings import AppSettings, IndexStore, get_settings
from backend.core.types import SearchDocument
from functions.batch_push.handler import batch_push_handler
from functions.batch_push.queue_reader import parse_push_message
from functions.core.contracts import BatchPushQueueMessage
from functions.core.exception_mapping import log_queue_errors
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.pgvector_pool import PgVectorPool
from functions.core.storage_endpoints import resolve_storage_endpoints

bp = func.Blueprint()


def _parser_key_for_filename(filename: str) -> str:
    """Return the lowercase extension (no dot) for parser-registry lookup.

    ``PurePosixPath`` (not ``Path``) keeps separator handling stable
    across Windows dev hosts and Linux Functions runtimes -- the
    filename comes from a blob path, which is POSIX-style on every
    platform Azure Storage exposes.
    """
    return PurePosixPath(filename).suffix.lstrip(".").lower()


async def _execute(
    message: BatchPushQueueMessage, settings: AppSettings
) -> list[SearchDocument]:
    """Resolve all collaborators and dispatch to ``batch_push_handler``.

    Extracted from :func:`batch_push` so route-level tests can
    monkeypatch this single seam instead of spinning up Azurite +
    Foundry IQ + a real Search service. Returns the documents pushed
    to Search (in chunk order) so callers can assert on the wire
    shape end-to-end.
    """
    blob_endpoint, _queue_endpoint = resolve_storage_endpoints(settings.storage)
    cred_provider = credentials_registry.registry.get(
        credentials_registry.select_default(settings.identity.uami_client_id)
    )(settings=settings)
    parser_cls = ingestion_parsers_registry.registry.get(
        _parser_key_for_filename(message.filename)
    )
    search_key = settings.database.index_store
    async with await cred_provider.get_credential() as credential:
        parser = parser_cls(settings=settings, credential=credential)
        embedder_cls = embedders_registry.registry.get("azure_openai")
        embedder = embedder_cls(settings=settings, credential=credential)
        # PgVectorPool is constructed only on the pgvector path so the
        # AzureSearch path stays free of any postgres SDK touch. The
        # helper's `acquire()` is single-flight + idempotent; the pool
        # is closed in the `finally` so the credential context fully
        # owns the connection lifecycle (no dangling sockets after
        # token expiry).
        pool_helper: PgVectorPool | None = None
        try:
            # `Any` is justified here per Hard Rule #11 boundary carve-out:
            # the registry callable accepts heterogeneous kwargs across
            # provider concretes (AzureSearch takes settings+credential;
            # PgVector additionally takes `pool`). Same pattern as
            # backend/app.py:lifespan.
            search_kwargs: dict[str, Any] = {
                "settings": settings,
                "credential": credential,
            }
            if search_key == IndexStore.PGVECTOR:
                pool_helper = PgVectorPool(
                    settings=settings, credential=credential
                )
                search_kwargs["pool"] = await pool_helper.acquire()
            search_provider = search_registry.registry.get(search_key)(
                **search_kwargs
            )
            try:
                # ensure_schema is a no-op on AzureSearch (index owned
                # by Bicep) and runs the pgvector DDL once-per-process
                # under an asyncio.Lock + readiness flag. Unconditional
                # call keeps the wiring provider-agnostic; raising here
                # still triggers `finally: aclose` below.
                await search_provider.ensure_schema()
                async with ContainerClient(
                    account_url=blob_endpoint,
                    container_name=message.container_name,
                    credential=credential,
                ) as container_client:
                    return await batch_push_handler(
                        message=message,
                        container_client=container_client,
                        parser=parser,
                        embedder=embedder,
                        search_provider=search_provider,
                    )
            finally:
                await search_provider.aclose()
        finally:
            if pool_helper is not None:
                await pool_helper.aclose()
            await embedder.aclose()


@bp.queue_trigger(
    arg_name="msg",
    queue_name="%AZURE_DOC_PROCESSING_QUEUE%",
    connection="AzureWebJobsStorage",
)
@log_queue_errors("batch_push")
async def batch_push(msg: func.QueueMessage) -> None:
    """Queue trigger -- per-message ingestion step.

    Parses the envelope, then dispatches to :func:`_execute` which
    resolves collaborators via the registries and runs
    :func:`batch_push_handler`. Failures bubble to
    :func:`log_queue_errors` which logs and re-raises so the Functions
    runtime engages retry -> poison.
    """
    message = parse_push_message(msg)
    await _execute(message, get_settings())
