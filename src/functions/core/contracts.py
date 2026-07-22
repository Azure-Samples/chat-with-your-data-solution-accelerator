"""Cross-blueprint Functions wire contracts.

This module owns the DTOs that travel **between** Functions blueprints
on the storage queue / event grid wire. A blueprint that produces a
message (e.g. ``batch_start`` enqueuing onto the push queue) and the
blueprint that consumes it (e.g. ``batch_push`` reading the same
queue) both import the envelope from this module so the wire format
has exactly one source of truth.

Why this lives under ``functions/core/`` and not ``backend/core/``:
the backend chat container never produces or consumes these
envelopes. They are Functions-runtime contracts only -- pure
ingestion-pipeline plumbing -- so they belong with the rest of the
Functions-only shared layer per
[.github/instructions/v2-functions-core.instructions.md] "Functions-
runtime helper" rule.
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

    Field-name fidelity: v1's ``batch_start_processing.py`` sent
    ``json.dumps({"filename": x})`` -- container was implicit via
    ``AZURE_BLOB_CONTAINER_NAME``. v2 makes container explicit so a
    single Functions app can drive multiple containers, and adds
    ``ingestion_job_id`` so all chunks emitted from one
    ``batch_start`` call share a correlation id in traces /
    search-index documents.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    container_name: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    ingestion_job_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    force_reindex: bool = False
