"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline, task #40)

Queue-message envelope emitted by ``batch_start`` and consumed by
``batch_push``.

Each blob that ``batch_start`` fans out becomes one queue message of
this shape. The envelope is the only contract between the two
blueprints: ``batch_push`` MUST be able to reconstruct everything it
needs (container, blob, force-reindex semantics, correlation id) from
the message body without re-reading environment variables.

Field-name fidelity: v1's `batch_start_processing.py` sent
`json.dumps({"filename": x})` -- container was implicit via
``AZURE_BLOB_CONTAINER_NAME``. v2 makes container explicit so a single
Functions app can drive multiple containers, and adds
``ingestion_job_id`` so all chunks emitted from one ``batch_start``
call share a correlation id in traces / search-index documents.

Co-location note (FUNC-SHARED-PKG, [v2/docs/development_plan.md] §0.1):
This DTO lives under ``batch_start/`` until ``batch_push`` also
references it (Phase 6 unit #7). At that point we ask the user before
promoting it to ``v2/src/functions/_shared/contracts.py`` per Hard
Rule #10.
"""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class BatchPushQueueMessage(BaseModel):
    """Queue envelope produced by ``batch_start`` for ``batch_push``.

    Frozen + ``extra="forbid"`` so a malformed / drifted producer
    surfaces as a Pydantic ``ValidationError`` on the consumer side
    rather than silently dropping fields. JSON round-trip
    (``model_dump_json`` -> Storage Queue body -> ``model_validate_json``)
    is the on-wire contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    container_name: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    ingestion_job_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    force_reindex: bool = False
