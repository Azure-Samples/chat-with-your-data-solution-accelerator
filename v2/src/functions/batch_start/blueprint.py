"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

HTTP blueprint that exposes the ``batch_start`` orchestrator from
:mod:`functions.batch_start.handler` as ``POST /api/batch_start``.

Thin composition over the ``functions/core/`` helpers:

* :func:`functions.core.storage_endpoints.resolve_storage_endpoints`
  -- derive ``(blob_endpoint, queue_endpoint)``.
* :func:`functions.core.storage_clients.storage_clients` -- open the
  ``(ContainerClient, QueueClient)`` pair via a single ``async with``.
* :func:`functions.core.http.json_response` + :class:`HTTPStatus` --
  one place that builds the wire response.
* :func:`functions.core.exception_mapping.map_function_exceptions` --
  owns the 422/502/500 ladder (``ValidationError`` -> 422,
  ``AzureError`` -> 502, ``BLE001`` -> 500) with structured logging.

The route body itself is just parse -> dispatch -> respond. The
private ``_execute`` helper remains the seam route-level tests
monkeypatch so unit tests do not need Azurite or a real credential.

Registry-first credentials wiring (Hard Rule #4): credential
construction still goes through the
``backend.core.providers.credentials`` registry, never
``DefaultAzureCredential()`` directly.
"""

from http import HTTPStatus

import azure.functions as func

from backend.core.providers.credentials import registry as credentials_registry
from backend.core.settings import AppSettings, get_settings
from functions.batch_start.handler import batch_start_handler
from functions.batch_start.models import BatchStartRequest
from functions.core.contracts import BatchPushQueueMessage
from functions.core.exception_mapping import map_function_exceptions
from functions.core.http import json_response
from functions.core.storage_clients import storage_clients
from functions.core.storage_endpoints import resolve_storage_endpoints

bp = func.Blueprint()


async def _execute(
    request: BatchStartRequest, settings: AppSettings
) -> list[BatchPushQueueMessage]:
    """Build SDK clients with a registry credential and run the handler.

    Extracted from :func:`batch_start` so tests can monkeypatch this
    single seam instead of spinning up Azurite. Composes
    ``resolve_storage_endpoints`` + ``storage_clients`` so the route
    body stays parse-and-respond only.
    """
    blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
    cred_provider = credentials_registry.registry.get(
        credentials_registry.select_default(settings.identity.uami_client_id)
    )(settings=settings)
    async with await cred_provider.get_credential() as credential:
        async with storage_clients(
            credential=credential,
            blob_endpoint=blob_endpoint,
            queue_endpoint=queue_endpoint,
            container_name=request.container_name,
            queue_name=settings.storage.doc_processing_queue,
        ) as (container_client, queue_client):
            return await batch_start_handler(request, container_client, queue_client)


@bp.route(route="batch_start", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@map_function_exceptions("batch_start")
async def batch_start(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/batch_start -- fan blobs under a prefix out to the push queue.

    Request body (JSON): :class:`BatchStartRequest`.
    Responses:
      * 200 -- ``{"ingestion_job_id": str|None, "enqueued_count": int,
        "filenames": list[str]}``.
      * 422 -- body failed Pydantic validation (owned by
        :func:`map_function_exceptions`).
      * 502 -- upstream Azure Storage error (owned by
        :func:`map_function_exceptions`).
      * 500 -- unexpected handler failure, final safety net (owned by
        :func:`map_function_exceptions`).
    """
    request = BatchStartRequest.model_validate_json(req.get_body() or b"{}")
    messages = await _execute(request, get_settings())
    job_id = messages[0].ingestion_job_id if messages else None
    return json_response(
        {
            "ingestion_job_id": job_id,
            "enqueued_count": len(messages),
            "filenames": [m.filename for m in messages],
        },
        HTTPStatus.OK,
    )
