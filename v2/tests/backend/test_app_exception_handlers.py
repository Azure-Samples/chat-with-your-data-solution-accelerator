"""App-level exception handlers (Phase C4 -- Router policy implementation).

Pillar: Stable Core
Phase: 5.5 (Phase C -- Try/catch policy + sweep, sub-unit C4)

Per [v2/docs/exception_handling_policy.md](../../docs/exception_handling_policy.md)
"Routers" row: every public route surfaces upstream SDK failures as
**sanitized** HTTP responses with no SDK stack-trace, no PII, and no
upstream payload echoed back. The implementation lives in
`backend/app.py::_install_exception_handlers` and runs once at app
construction; this module verifies (a) the sanitized status codes,
(b) the sanitized response bodies, (c) the structured ERROR log
record carrying `method` / `path` / `user_id` / `exception_class`
extras, and (d) that `HTTPException` and `RequestValidationError`
keep their FastAPI defaults (no shadowing).
"""

import asyncpg
import httpx
import openai
import pytest
from azure.core.exceptions import AzureError, ServiceRequestError
from azure.cosmos.exceptions import CosmosHttpResponseError
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app import _install_exception_handlers


_APP_LOGGER_NAME = "backend.app"


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _build_app_with_failing_route(exc: Exception) -> FastAPI:
    """Build a minimal FastAPI app with the C4 handlers installed and
    a single route that raises `exc`.

    Avoids `create_app()` (which spins up the lifespan + reads env)
    so each test is self-contained, fast, and exercises *only* the
    handler installation contract -- no router wiring side-effects.
    """
    app = FastAPI()
    _install_exception_handlers(app)

    @app.get("/_test/raise")
    async def _raise() -> None:
        raise exc

    return app


def _api_error(message: str = "boom") -> openai.APIError:
    """Construct an `openai.APIError` with the v2 SDK signature.

    `openai>=2.26` requires a positional `httpx.Request` and a
    keyword-only `body`; bare-message construction raises TypeError.
    """
    return openai.APIError(
        message,
        httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        body=None,
    )


# ---------------------------------------------------------------------------
# Sanitized-status tests
# ---------------------------------------------------------------------------


def test_openai_api_error_returns_502_with_sanitized_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = _build_app_with_failing_route(_api_error("upstream model crashed"))
    with caplog.at_level("ERROR", logger=_APP_LOGGER_NAME):
        with TestClient(app) as client:
            response = client.get(
                "/_test/raise",
                headers={"x-ms-client-principal-id": "user-42"},
            )

    assert response.status_code == 502
    assert response.json() == {"detail": "Upstream model error."}
    # Sanitization invariant: SDK message must NOT leak.
    assert "upstream model crashed" not in response.text

    record = _find_error_record(caplog, "exception_class", "APIError")
    assert record.method == "GET"
    assert record.path == "/_test/raise"
    assert record.user_id == "user-42"


def test_cosmos_http_error_returns_503_with_sanitized_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = _build_app_with_failing_route(
        CosmosHttpResponseError(message="429 throttled by gateway")
    )
    with caplog.at_level("ERROR", logger=_APP_LOGGER_NAME):
        with TestClient(app) as client:
            response = client.get("/_test/raise")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable."}
    assert "429 throttled" not in response.text

    record = _find_error_record(caplog, "exception_class", "CosmosHttpResponseError")
    assert record.method == "GET"
    assert record.path == "/_test/raise"
    # Header absent -> stable empty-string user_id, never KeyError on log.
    assert record.user_id == ""


def test_postgres_error_returns_503_with_sanitized_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = _build_app_with_failing_route(
        asyncpg.PostgresError("pg connection lost: SSL handshake")
    )
    with caplog.at_level("ERROR", logger=_APP_LOGGER_NAME):
        with TestClient(app) as client:
            response = client.get("/_test/raise")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable."}
    assert "SSL handshake" not in response.text

    record = _find_error_record(caplog, "exception_class", "PostgresError")
    assert record.method == "GET"
    assert record.path == "/_test/raise"


def test_azure_error_returns_503_with_sanitized_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Generic azure-core errors (Search, AIProjectClient, Storage)
    that are NOT Cosmos-specific land on the AzureError handler.
    """
    app = _build_app_with_failing_route(
        ServiceRequestError(message="DNS resolution failed for srch.windows.net")
    )
    with caplog.at_level("ERROR", logger=_APP_LOGGER_NAME):
        with TestClient(app) as client:
            response = client.get("/_test/raise")

    assert response.status_code == 503
    assert response.json() == {"detail": "Azure dependency temporarily unavailable."}
    assert "DNS resolution failed" not in response.text

    record = _find_error_record(caplog, "exception_class", "ServiceRequestError")
    assert record.path == "/_test/raise"


def test_unhandled_exception_returns_500_with_sanitized_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Final safety net: anything not covered by a more specific
    handler lands on the generic Exception handler with a 500.
    """
    app = _build_app_with_failing_route(RuntimeError("internal bug detail"))
    with caplog.at_level("ERROR", logger=_APP_LOGGER_NAME):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/raise")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "internal bug detail" not in response.text

    record = _find_error_record(caplog, "exception_class", "RuntimeError")
    assert record.method == "GET"
    assert record.path == "/_test/raise"


# ---------------------------------------------------------------------------
# Pass-through invariants (HTTPException + 422 must NOT be shadowed)
# ---------------------------------------------------------------------------


def test_httpexception_pass_through_is_not_shadowed_by_exception_handler() -> None:
    """`HTTPException(404, ...)` must surface as a real 404 with the
    operator-supplied detail -- the generic Exception handler
    registered in C4 must NOT intercept it. FastAPI's MRO dispatch
    finds the framework's HTTPException handler first.
    """
    app = _build_app_with_failing_route(
        HTTPException(status_code=404, detail="missing-thing")
    )
    with TestClient(app) as client:
        response = client.get("/_test/raise")

    assert response.status_code == 404
    # Operator-controlled detail flows through verbatim (the policy
    # forbids leaking *upstream SDK* payloads; route-level
    # HTTPException details ARE the sanitized surface and must pass).
    assert response.json() == {"detail": "missing-thing"}


def test_request_validation_error_pass_through_returns_422() -> None:
    """422 from Pydantic body validation must stay untouched -- the
    generic Exception handler must NOT swallow it into a 500.
    Demonstrates the framework default still wins for
    `RequestValidationError`.
    """
    from pydantic import BaseModel

    class _Body(BaseModel):
        name: str

    app = FastAPI()
    _install_exception_handlers(app)

    @app.post("/_test/echo")
    async def _echo(body: _Body) -> dict[str, str]:
        return {"name": body.name}

    with TestClient(app) as client:
        # Missing required `name` field forces a 422.
        response = client.post("/_test/echo", json={})

    assert response.status_code == 422
    payload = response.json()
    # FastAPI default 422 shape carries `detail` as a list of error
    # objects -- not the sanitized string from the C4 Exception
    # handler. Locks in that the framework handler still wins.
    assert isinstance(payload["detail"], list)


# ---------------------------------------------------------------------------
# MRO dispatch invariant -- Cosmos-specific handler beats generic AzureError
# ---------------------------------------------------------------------------


def test_cosmos_specific_handler_wins_over_generic_azure_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`CosmosHttpResponseError` extends `HttpResponseError` (azure-
    core) which extends `AzureError`. Verifies FastAPI's MRO dispatch
    lands on the Cosmos handler (503 + 'Database temporarily
    unavailable.') NOT the generic AzureError handler (503 + 'Azure
    dependency temporarily unavailable.'). Both return 503; the
    distinct `detail` strings are how we know which handler ran.
    """
    app = _build_app_with_failing_route(
        CosmosHttpResponseError(message="cosmos transient")
    )
    with caplog.at_level("ERROR", logger=_APP_LOGGER_NAME):
        with TestClient(app) as client:
            response = client.get("/_test/raise")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable."}
    # Negative assertion: the generic AzureError detail string
    # must not appear -- proves dispatch landed on the specific one.
    assert "Azure dependency" not in response.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_error_record(
    caplog: pytest.LogCaptureFixture,
    attr: str,
    value: str,
):
    """Return the single ERROR record whose `attr` extra equals `value`.

    Asserts exactly-one match so a regression that double-fires the
    handler (or mis-tags the extras) shows up loudly.
    """
    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR" and getattr(r, attr, None) == value
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 ERROR record with {attr}={value!r}, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    return matches[0]
