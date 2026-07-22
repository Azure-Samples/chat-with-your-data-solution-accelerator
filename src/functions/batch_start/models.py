"""Request payload model for the ``batch_start`` blueprint.

The ``batch_start`` HTTP route kicks off (or re-kicks) ingestion for a
blob-storage prefix by fanning work out onto a queue consumed by the
``batch_push`` blueprint. This module owns the inbound request DTO and
the outbound response DTO.

Field-name fidelity: v1 ``code/backend/batch/batch_start_processing.py``
takes no body and reads the container name from environment via
``env_helper.AZURE_BLOB_CONTAINER_NAME``. v2 moves to a body-first
contract so the same Functions app can drive multiple containers /
prefixes without redeploying. The ``container_name`` field name
matches v1's snake_case usage in
``code/backend/batch/utilities/helpers/azure_blob_storage_client.py``.
"""

from pydantic import BaseModel, ConfigDict, Field


class BatchStartRequest(BaseModel):
    """Inbound HTTP payload for the ``batch_start`` blueprint.

    Validates a caller's request to start (or re-start) ingestion for a
    blob-storage prefix. The DTO is storage-shape agnostic: the route
    handler is responsible for translating it into queue messages for
    ``batch_push``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    container_name: str = Field(min_length=1)
    prefix: str | None = None
    force_reindex: bool = False


class BatchStartResponse(BaseModel):
    """Outbound HTTP payload for the ``batch_start`` blueprint.

    Summarizes the ingestion work fanned out to the ``batch_push`` queue
    for a caller's request: the correlation id shared by every enqueued
    message, how many messages were enqueued, and the blob filenames
    they cover.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ingestion_job_id: str | None = Field(
        description=(
            "Correlation id shared by every message enqueued for this "
            "request, or null when the prefix matched no blobs and nothing "
            "was enqueued."
        )
    )
    enqueued_count: int = Field(
        description="Number of blob messages enqueued for batch_push to process."
    )
    filenames: list[str] = Field(
        description="Blob filenames enqueued for ingestion, in enqueue order."
    )
