"""Tests for src/functions/function_app.py."""

import json

import azure.functions as func
import pytest
from pydantic import ValidationError

from functions.function_app import HealthPayload, _health_payload, app, health


def test_app_is_anonymous_function_app() -> None:
    assert isinstance(app, func.FunctionApp)
    assert app.auth_level == func.AuthLevel.ANONYMOUS


def test_health_payload_shape() -> None:
    assert _health_payload() == HealthPayload()
    assert _health_payload().model_dump() == {"status": "ok"}


def test_health_payload_is_frozen_and_forbids_extras() -> None:
    payload = HealthPayload()
    with pytest.raises(ValidationError):
        payload.status = "degraded"  # type: ignore[misc]  -- frozen model rejects mutation
    with pytest.raises(ValidationError):
        HealthPayload(status="ok", extra="nope")  # type: ignore[call-arg]  -- extra="forbid"


def test_health_route_registered() -> None:
    function_names = {fb._function._name for fb in app._function_builders}
    assert "health" in function_names


@pytest.mark.parametrize("method", ["GET"])
def test_health_returns_200_json(method: str) -> None:
    req = func.HttpRequest(method=method, url="/api/health", body=b"", headers={})
    resp = health(req)
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert json.loads(resp.get_body()) == {"status": "ok"}
