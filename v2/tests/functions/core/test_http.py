"""Pillar: Stable Core / Phase: 6 — tests for functions/core/http.py."""

import json
from http import HTTPStatus

import azure.functions as func

from functions.core.http import ErrorType, json_response


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
    # The exception-mapping decorator (U7f) will write ErrorType members
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
    # Verifies U7f's expected wire shape: {"error": ErrorType.X} -> bare string.
    resp = json_response({"error": ErrorType.UPSTREAM_STORAGE_ERROR}, HTTPStatus.BAD_GATEWAY)
    assert resp.status_code == 502
    assert json.loads(resp.get_body()) == {"error": "upstream_storage_error"}


def test_json_response_handles_each_blueprint_status_code() -> None:
    # Sanity: the four statuses U7f's ladder will emit all round-trip cleanly.
    for status in (
        HTTPStatus.OK,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
    ):
        resp = json_response({"ok": True}, status)
        assert resp.status_code == int(status)
