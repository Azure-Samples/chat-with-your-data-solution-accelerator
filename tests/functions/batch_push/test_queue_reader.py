"""Tests for src/functions/batch_push/queue_reader.py."""

from typing import cast

import azure.functions as func
import pytest
from pydantic import ValidationError

from functions.batch_push.queue_reader import parse_push_message
from functions.core.contracts import BatchPushQueueMessage


class _FakeQueueMessage:
    """Minimal stand-in for ``azure.functions.QueueMessage``.

    Only ``get_body()`` is exercised by ``parse_push_message``.
    """

    def __init__(self, body: bytes) -> None:
        self._body = body

    def get_body(self) -> bytes:
        return self._body


def _as_queue_message(fake: _FakeQueueMessage) -> func.QueueMessage:
    return cast(func.QueueMessage, fake)


def test_parses_canonical_envelope_round_trip() -> None:
    original = BatchPushQueueMessage(
        container_name="documents",
        filename="2026/contract.pdf",
        ingestion_job_id="job-abc",
        force_reindex=True,
    )
    msg = _as_queue_message(
        _FakeQueueMessage(original.model_dump_json().encode("utf-8"))
    )
    assert parse_push_message(msg) == original


def test_accepts_bytes_body_without_intermediate_decode() -> None:
    raw = b'{"container_name":"c","filename":"f.pdf"}'
    parsed = parse_push_message(_as_queue_message(_FakeQueueMessage(raw)))
    assert parsed.container_name == "c"
    assert parsed.filename == "f.pdf"
    # Defaults applied for omitted optional fields.
    assert parsed.force_reindex is False
    assert parsed.ingestion_job_id  # UUID default


def test_malformed_json_raises_validation_error() -> None:
    msg = _as_queue_message(_FakeQueueMessage(b"not-json"))
    with pytest.raises(ValidationError):
        parse_push_message(msg)


def test_extra_fields_rejected_per_frozen_envelope() -> None:
    # BatchPushQueueMessage is extra="forbid"; a drifted producer
    # adding an unknown field must surface as ValidationError, not
    # silently dropped.
    raw = b'{"container_name":"c","filename":"f.pdf","unknown":"x"}'
    with pytest.raises(ValidationError):
        parse_push_message(_as_queue_message(_FakeQueueMessage(raw)))


def test_missing_required_field_raises_validation_error() -> None:
    raw = b'{"container_name":"c"}'  # filename missing
    with pytest.raises(ValidationError):
        parse_push_message(_as_queue_message(_FakeQueueMessage(raw)))


def test_empty_string_required_field_raises_validation_error() -> None:
    raw = b'{"container_name":"","filename":"f.pdf"}'
    with pytest.raises(ValidationError):
        parse_push_message(_as_queue_message(_FakeQueueMessage(raw)))
