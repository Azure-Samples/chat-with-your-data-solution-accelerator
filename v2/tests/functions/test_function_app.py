"""Pillar: Stable Core / Phase: 1 (debt #7) — tests for v2/src/functions/function_app.py."""
from __future__ import annotations

import json

import azure.functions as func
import pytest

from functions.function_app import _health_payload, app, health


def test_app_is_anonymous_function_app() -> None:
    assert isinstance(app, func.FunctionApp)
    assert app.auth_level == func.AuthLevel.ANONYMOUS


def test_health_payload_shape() -> None:
    assert _health_payload() == {"status": "ok"}


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
