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
* Search write target via
  :func:`functions.core.search_resolution.resolve_search_provider`,
  which keys ``search_registry`` on ``settings.database.index_store``
  (``"AzureSearch"`` -> an SDK-client-owning
  :class:`backend.core.providers.search.azure_search.AzureSearch`;
  ``"pgvector"`` -> a
  :class:`backend.core.providers.search.pgvector.PgVector` wired to the
  asyncpg pool), runs ``ensure_schema`` once, and returns the provider
  plus its optional :class:`functions.core.pgvector_pool.PgVectorPool`
  helper. ``_execute`` owns teardown -- closing the provider, then the
  pool. Both concretes satisfy ``BaseSearch.merge_or_upload_documents``
  so the handler stays provider-agnostic.

The private :func:`_execute` helper remains the single seam that
unit tests monkeypatch so they do not need Azurite, a real
credential, or a real Search service.
"""

import azure.functions as func
from azure.storage.blob.aio import ContainerClient

from backend.core.paths import parser_key_for_path
from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.embedders import registry as embedders_registry
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchDocument
from functions.batch_push.handler import batch_push_handler
from functions.batch_push.queue_reader import parse_push_message
from functions.core.contracts import BatchPushQueueMessage
from functions.core.exception_mapping import log_queue_errors
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.search_resolution import resolve_search_provider
from functions.core.storage_endpoints import resolve_storage_endpoints

bp = func.Blueprint()


def _parser_key_for_filename(filename: str) -> str:
    """Return the lowercase extension (no dot) for parser-registry lookup.

    Delegates to :func:`backend.core.paths.parser_key_for_path`; the
    filename comes from a blob path, which is POSIX-style on every
    platform Azure Storage exposes.
    """
    return parser_key_for_path(filename)


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
    async with await cred_provider.get_credential() as credential:
        parser = parser_cls(settings=settings, credential=credential)
        embedder_cls = embedders_registry.registry.get("azure_openai")
        embedder = embedder_cls(settings=settings, credential=credential)
        try:
            # Registry-first search provider (+ pgvector pool on the
            # pgvector path); the helper runs ensure_schema and hands
            # back teardown ownership for the provider and pool.
            resolved = await resolve_search_provider(
                settings=settings, credential=credential
            )
            try:
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
                        search_provider=resolved.provider,
                    )
            finally:
                await resolved.provider.aclose()
                if resolved.pool_helper is not None:
                    await resolved.pool_helper.aclose()
        finally:
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
