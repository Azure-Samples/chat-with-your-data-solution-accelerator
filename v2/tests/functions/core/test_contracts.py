"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/core/contracts.py."""

import json

import pytest
from pydantic import ValidationError

from functions.core.contracts import BatchPushQueueMessage


def test_happy_path_builds_with_all_fields() -> None:
    msg = BatchPushQueueMessage(
        container_name="documents",
        filename="2026/contract.pdf",
        ingestion_job_id="job-abc-123",
        force_reindex=True,
    )
    assert msg.container_name == "documents"
    assert msg.filename == "2026/contract.pdf"
    assert msg.ingestion_job_id == "job-abc-123"
    assert msg.force_reindex is True


def test_defaults_populate_job_id_and_force_reindex() -> None:
    msg = BatchPushQueueMessage(container_name="documents", filename="x.pdf")
    assert msg.force_reindex is False
    # default_factory uses uuid4 -> 36-char string
    assert len(msg.ingestion_job_id) == 36
    assert msg.ingestion_job_id.count("-") == 4


def test_each_default_job_id_is_unique() -> None:
    a = BatchPushQueueMessage(container_name="c", filename="f.pdf")
    b = BatchPushQueueMessage(container_name="c", filename="f.pdf")
    assert a.ingestion_job_id != b.ingestion_job_id


def test_empty_container_name_rejected() -> None:
    with pytest.raises(ValidationError):
        BatchPushQueueMessage(container_name="", filename="x.pdf")


def test_empty_filename_rejected() -> None:
    with pytest.raises(ValidationError):
        BatchPushQueueMessage(container_name="documents", filename="")


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        BatchPushQueueMessage(  # type: ignore[call-arg]
            container_name="documents",
            filename="x.pdf",
            unknown="nope",
        )


def test_model_is_frozen() -> None:
    msg = BatchPushQueueMessage(container_name="documents", filename="x.pdf")
    with pytest.raises(ValidationError):
        msg.filename = "other.pdf"  # type: ignore[misc]


def test_json_round_trip_preserves_all_fields() -> None:
    """On-wire contract: model_dump_json -> queue body -> model_validate_json."""
    original = BatchPushQueueMessage(
        container_name="documents",
        filename="2026/contract.pdf",
        ingestion_job_id="job-abc-123",
        force_reindex=True,
    )
    wire = original.model_dump_json()
    # Round-trip through bytes (Storage Queue encodes message body as bytes).
    decoded = json.loads(wire.encode("utf-8").decode("utf-8"))
    rebuilt = BatchPushQueueMessage.model_validate(decoded)
    assert rebuilt == original


def test_json_round_trip_via_model_validate_json() -> None:
    original = BatchPushQueueMessage(container_name="c", filename="f.pdf")
    rebuilt = BatchPushQueueMessage.model_validate_json(original.model_dump_json())
    assert rebuilt == original
