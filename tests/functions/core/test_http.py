"""Tests for functions/core/http.py."""

import json
from http import HTTPStatus

import azure.functions as func
import pytest
from pydantic import ValidationError

from functions.core.http import ErrorEnvelope, ErrorType, json_response


def test_error_type_members_are_wire_strings() -> None:
    # StrEnum members must equal their wire-string values so JSON
    # round-trips (Enum -> json.dumps -> json.loads -> str compare) work.
    assert ErrorType.VALIDATION_ERROR == "validation_error"
    assert ErrorType.UPSTREAM_STORAGE_ERROR == "upstream_storage_error"
    assert ErrorType.INTERNAL_SERVER_ERROR == "internal_server_error"
    assert set(ErrorType) == {
        ErrorType.VALIDATION_ERROR,
        ErrorType.UPSTREAM_STORAGE_ERROR,
        ErrorType.INTERNAL_SERVER_ERROR,
    }


def test_error_type_json_serializes_as_bare_string() -> None:
    # The exception-mapping decorator will write ErrorType members
    # straight into {"error": ...}; ensure that doesn't blow up.
    payload = {"error": ErrorType.VALIDATION_ERROR}
    assert json.dumps(payload) == '{"error": "validation_error"}'


def test_json_response_returns_http_response_with_correct_status() -> None:
    resp = json_response({"ok": True}, HTTPStatus.OK)
    assert isinstance(resp, func.HttpResponse)
    assert resp.status_code == 200


def test_json_response_sets_application_json_mimetype() -> None:
    resp = json_response({"ok": True}, HTTPStatus.OK)
    # azure.functions.HttpResponse normalizes mimetype -> Content-Type header.
    assert resp.mimetype == "application/json"


def test_json_response_body_round_trips_through_json() -> None:
    payload: dict[str, object] = {
        "ingestion_job_id": "job-abc-123",
        "enqueued_count": 3,
        "filenames": ["a.pdf", "b.pdf", "c.pdf"],
    }
    resp = json_response(payload, HTTPStatus.OK)
    assert resp.get_body() is not None
    assert json.loads(resp.get_body()) == payload


def test_json_response_accepts_error_enum_in_payload() -> None:
    # Verifies the expected wire shape: {"error": ErrorType.X} -> bare string.
    resp = json_response(
        {"error": ErrorType.UPSTREAM_STORAGE_ERROR}, HTTPStatus.BAD_GATEWAY
    )
    assert resp.status_code == 502
    assert json.loads(resp.get_body()) == {"error": "upstream_storage_error"}


def test_json_response_handles_each_blueprint_status_code() -> None:
    # Sanity: the four statuses the exception ladder emits all round-trip cleanly.
    for status in (
        HTTPStatus.OK,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
    ):
        resp = json_response({"ok": True}, status)
        assert resp.status_code == int(status)


def test_error_envelope_upstream_storage_omits_details() -> None:
    # No details supplied -> exclude_none drops the key entirely, matching
    # the {"error": "upstream_storage_error"} wire body.
    envelope = ErrorEnvelope(error=ErrorType.UPSTREAM_STORAGE_ERROR)
    assert envelope.model_dump(exclude_none=True) == {"error": "upstream_storage_error"}


def test_error_envelope_internal_server_omits_details() -> None:
    envelope = ErrorEnvelope(error=ErrorType.INTERNAL_SERVER_ERROR)
    assert envelope.model_dump(exclude_none=True) == {"error": "internal_server_error"}


def test_error_envelope_validation_error_carries_details() -> None:
    envelope = ErrorEnvelope(
        error=ErrorType.VALIDATION_ERROR,
        details=[{"loc": ["name"], "msg": "field required", "type": "missing"}],
    )
    assert envelope.model_dump(exclude_none=True) == {
        "error": "validation_error",
        "details": [{"loc": ["name"], "msg": "field required", "type": "missing"}],
    }


def test_error_envelope_details_defaults_to_none() -> None:
    envelope = ErrorEnvelope(error=ErrorType.VALIDATION_ERROR)
    assert envelope.details is None


def test_error_envelope_is_frozen() -> None:
    envelope = ErrorEnvelope(error=ErrorType.VALIDATION_ERROR)
    with pytest.raises(ValidationError):
        envelope.error = ErrorType.INTERNAL_SERVER_ERROR


def test_error_envelope_forbids_extras() -> None:
    with pytest.raises(ValidationError):
        ErrorEnvelope(error=ErrorType.VALIDATION_ERROR, extra="x")
