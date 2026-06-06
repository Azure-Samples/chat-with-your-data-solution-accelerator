"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Request payload model for the ``batch_start`` blueprint.

The ``batch_start`` HTTP route kicks off (or re-kicks) ingestion for a
blob-storage prefix by fanning work out onto a queue consumed by the
``batch_push`` blueprint. This module owns only the inbound request
DTO.

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
