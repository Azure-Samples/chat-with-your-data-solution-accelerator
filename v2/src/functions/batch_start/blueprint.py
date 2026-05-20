"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline, task #39)

HTTP blueprint that exposes the ``batch_start`` orchestrator from
:mod:`functions.batch_start.handler` as
``POST /api/batch_start``.

Responsibilities owned by this module (and nowhere else):

* Construct the per-request ``ContainerClient`` + ``QueueClient`` from
  the registry-backed credential provider so the handler in
  ``handler.py`` stays client-injected / unit-testable.
* Parse and validate the inbound HTTP body into
  :class:`BatchStartRequest`.
* Map exceptions to sanitized HTTP responses per
  [v2/docs/exception_handling_policy.md] sections "Functions
  blueprints" + "Routers": narrow specific catches first
  (``ValidationError`` -> 422, ``AzureError`` -> 502), final
  ``# noqa: BLE001`` safety net -> 500. Every branch uses
  ``logger.exception`` with structured extras; the response body never
  leaks SDK payloads.

Registry-first credentials wiring (Hard Rule #4): we go through
``backend.core.providers.credentials.create(...)``, never
``DefaultAzureCredential()`` directly, so a test fake or
``AzureCliCredential`` shim is a one-config swap. The private
``_execute`` helper is the exact extraction point the test suite
monkeypatches so route-level tests do not need Azurite.
"""

import json
import logging

import azure.functions as func
from azure.core.exceptions import AzureError
from azure.storage.blob.aio import ContainerClient
from azure.storage.queue.aio import QueueClient
from pydantic import ValidationError

from backend.core.providers import credentials
from backend.core.settings import AppSettings, get_settings
from functions.batch_start.handler import batch_start_handler
from functions.batch_start.models import BatchStartRequest
from functions.core.contracts import BatchPushQueueMessage

logger = logging.getLogger(__name__)

bp = func.Blueprint()


def _resolve_endpoints(settings: AppSettings) -> tuple[str, str]:
    """Return ``(blob_endpoint, queue_endpoint)`` URLs for the storage account.

    Prefers the explicit ``AZURE_STORAGE_BLOB_ENDPOINT`` when set
    (sovereign-cloud safe); otherwise derives the public-cloud URL
    from ``AZURE_STORAGE_ACCOUNT_NAME``. Queue endpoint is derived
    from blob endpoint by swapping the service segment so both
    services share one DNS suffix in any cloud.
    """
    blob_endpoint = (
        settings.storage.storage_blob_endpoint
        or f"https://{settings.storage.storage_account_name}.blob.core.windows.net"
    )
    queue_endpoint = blob_endpoint.replace(".blob.", ".queue.", 1)
    return blob_endpoint, queue_endpoint


async def _execute(
    request: BatchStartRequest, settings: AppSettings
) -> list[BatchPushQueueMessage]:
    """Build SDK clients with a registry credential and run the handler.

    Extracted from :func:`batch_start_route` so tests can monkeypatch
    this single seam instead of spinning up Azurite. Mirrors the
    ``_health_payload`` extraction pattern used in
    ``functions/function_app.py``.
    """
    blob_endpoint, queue_endpoint = _resolve_endpoints(settings)
    cred_provider = credentials.create(
        credentials.select_default(settings.identity.uami_client_id),
        settings=settings,
    )
    async with await cred_provider.get_credential() as credential:
        async with (
            ContainerClient(
                account_url=blob_endpoint,
                container_name=request.container_name,
                credential=credential,
            ) as container_client,
            QueueClient(
                account_url=queue_endpoint,
                queue_name=settings.storage.doc_processing_queue,
                credential=credential,
            ) as queue_client,
        ):
            return await batch_start_handler(request, container_client, queue_client)


def _json_response(payload: dict[str, object], status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload),
        status_code=status_code,
        mimetype="application/json",
    )


@bp.route(route="batch_start", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def batch_start(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/batch_start -- fan blobs under a prefix out to the push queue.

    Request body (JSON): :class:`BatchStartRequest`.
    Responses:
      * 200 -- ``{"ingestion_job_id": str|None, "enqueued_count": int,
        "filenames": list[str]}``.
      * 422 -- body failed Pydantic validation (missing/extra field,
        bad JSON, empty body).
      * 502 -- upstream Azure Storage error.
      * 500 -- unexpected handler failure (final safety net).
    """
    try:
        request = BatchStartRequest.model_validate_json(req.get_body() or b"{}")
    except ValidationError as exc:
        logger.warning(
            "batch_start request validation failed",
            extra={
                "operation": "batch_start",
                "trigger": "http",
                "status_code": 422,
            },
        )
        return _json_response(
            {"error": "validation_error", "details": exc.errors(include_input=False)},
            422,
        )

    try:
        messages = await _execute(request, get_settings())
    except AzureError:
        logger.exception(
            "batch_start storage call failed",
            extra={
                "operation": "batch_start",
                "trigger": "http",
                "container": request.container_name,
                "status_code": 502,
            },
        )
        return _json_response({"error": "upstream_storage_error"}, 502)
    except Exception:  # noqa: BLE001 -- final safety net for batch_start route
        logger.exception(
            "batch_start handler failed",
            extra={
                "operation": "batch_start",
                "trigger": "http",
                "container": request.container_name,
                "status_code": 500,
            },
        )
        return _json_response({"error": "internal_server_error"}, 500)

    job_id = messages[0].ingestion_job_id if messages else None
    return _json_response(
        {
            "ingestion_job_id": job_id,
            "enqueued_count": len(messages),
            "filenames": [m.filename for m in messages],
        },
        200,
    )
