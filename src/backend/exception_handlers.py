"""App-level exception handlers (Router policy implementation).

Per [v2/docs/exception_handling_policy.md](../../v2/docs/exception_handling_policy.md)
"Routers" row: domain exceptions surface as **sanitized**
HTTPException-style responses with no SDK stack-trace, no PII, and no
upstream payload echoed back to the client. The handlers below
register on the FastAPI app instance once (via
`install_exception_handlers`, called from `app.create_app()`) and
apply uniformly to every router (conversation / history / admin /
health).

Why app-level (not per-route try/except)?

- Single source of truth: one place to update the sanitized message
  when a new SDK is added; per-route blocks drift.
- Hard Rule #9 (clean, modular): scattering N >= 12 try/except blocks
  across routers reproduces v1's spaghetti pattern.
- FastAPI canonical pattern: `app.add_exception_handler(ExcType, fn)`
  is exactly the surface the framework was designed for.

Dispatch order: FastAPI walks `type(exc).__mro__` against the handler
dict, so the most-specific class wins. `HTTPException` and
`RequestValidationError` keep their default handlers (they live in
their own MRO branches, not under `Exception` in our dict); operators
and tests that already raise `HTTPException(...)` for 401 / 404 / 422
see the unchanged surface.

Status-code rationale:

- `openai.APIError`            -> 502 (upstream model error -- we can't
                                  serve the request, but the client's
                                  *input* was valid).
- `CosmosHttpResponseError`    -> 503 (datastore transient).
- `asyncpg.PostgresError`      -> 503 (datastore transient).
- `AzureError`                 -> 503 (azure-search / AIProjectClient /
                                  blob -- generic dependency).
- `ConfigResolutionError`      -> 409 (the operator-selected effective
                                  config is self-contradictory -- a
                                  conflict only the operator can fix).
- `Exception` (final net)      -> 500 (unknown unhandled bug).
"""

import logging
from typing import Any

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import httpx
import openai
from azure.core.exceptions import AzureError
from azure.cosmos.exceptions import CosmosHttpResponseError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.services.admin import ConfigResolutionError

logger = logging.getLogger(__name__)

_OPENAI_DETAIL = "Upstream model error."
_COSMOS_DETAIL = "Database temporarily unavailable."
_POSTGRES_DETAIL = "Database temporarily unavailable."
_AZURE_DETAIL = "Azure dependency temporarily unavailable."
_HTTPX_FETCH_DETAIL = (
    "Failed to fetch the requested URL (the remote server returned an error)."
)
_INTERNAL_DETAIL = "Internal server error."


def _request_extras(request: Request) -> dict[str, Any]:
    """Build the structured logging extras for a request-scoped error.

    Reads the Easy Auth principal header directly (rather than going
    through the per-router `get_user_id` dependency) because exception
    handlers run *outside* the request's dependency injection scope.
    Empty string when absent so log records have a stable shape.
    """
    return {
        "method": request.method,
        "path": request.url.path,
        "user_id": request.headers.get("x-ms-client-principal-id", ""),
    }


async def _openai_api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Sanitize OpenAI / Foundry IQ failures to a 502 response."""
    logger.exception(
        "openai.APIError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=502, content={"detail": _OPENAI_DETAIL})


async def _cosmos_http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Sanitize Cosmos transport failures to a 503 response."""
    logger.exception(
        "CosmosHttpResponseError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=503, content={"detail": _COSMOS_DETAIL})


async def _postgres_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Sanitize asyncpg failures to a 503 response."""
    logger.exception(
        "asyncpg.PostgresError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=503, content={"detail": _POSTGRES_DETAIL})


async def _azure_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Sanitize generic azure-core failures (Search, AIProjectClient,
    Storage, etc.) to a 503 response. Registered AFTER the more
    specific `CosmosHttpResponseError` handler so MRO dispatch lands
    on the Cosmos-specific one for Cosmos errors and falls through
    here for everything else under `AzureError`.
    """
    logger.exception(
        "AzureError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=503, content={"detail": _AZURE_DETAIL})


async def _config_resolution_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Map an invalid effective configuration to a 409 Conflict (ADR 0022).

    Unlike the SDK-failure handlers above, this is an *expected*
    domain error -- the operator selected a self-contradictory
    effective config (for example an orchestrator that needs an Azure
    AI Search index on a deployment that has none). So it logs at
    ERROR via `logger.error` -- not `logger.exception` -- because the
    `reason` + `context` extras self-describe the conflict and a stack
    trace would be noise; and the response body carries the actionable
    `message` + `reason` (rather than a sanitized generic string) so
    the operator can fix the deployment without reading server logs.

    Starlette's handler contract types `exc` as the base `Exception`;
    the app routes only `ConfigResolutionError` here, so narrow once
    for typed access to `reason` / `context`.
    """
    assert isinstance(exc, ConfigResolutionError)
    logger.error(
        "configuration resolution failed at router boundary",
        extra={
            **_request_extras(request),
            "operation": "resolve_effective_config",
            "reason": exc.reason,
            **exc.context,
        },
    )
    return JSONResponse(
        status_code=409,
        content={"error": str(exc), "reason": exc.reason},
    )


async def _httpx_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map an upstream HTTP fetch failure to a 502 response.

    ``httpx.HTTPError`` covers ``HTTPStatusError`` (4xx/5xx from the remote
    site, e.g. Wikipedia 403), ``ConnectError``, ``TimeoutException``, and
    all other httpx transport failures raised by ``url_fetcher.fetch_url``.
    """
    logger.exception(
        "httpx.HTTPError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=502, content={"detail": _HTTPX_FETCH_DETAIL})


async def _unhandled_exception_handler(  # noqa: BLE001 -- final safety net
    request: Request, exc: Exception
) -> JSONResponse:
    """Final safety net: catch anything not covered by a more specific
    handler. Logs the full exc_info via `logger.exception` so triage
    can reconstruct from App Insights, then returns a generic 500
    body with no SDK detail leaked to the client.

    Note: `HTTPException` and `RequestValidationError` keep their
    framework defaults -- FastAPI's MRO dispatch finds those handlers
    first and never reaches this one for those types.
    """
    logger.exception(
        "unhandled exception at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=500, content={"detail": _INTERNAL_DETAIL})


def install_exception_handlers(app: FastAPI) -> None:
    """Register all router-policy exception handlers on `app` exactly once.

    Idempotent at the FastAPI level: `add_exception_handler` overwrites
    the dict entry for a given class. Called from `create_app()` so
    every TestClient(create_app()) wired in tests gets the same
    sanitized surface.
    """
    app.add_exception_handler(openai.APIError, _openai_api_error_handler)
    app.add_exception_handler(CosmosHttpResponseError, _cosmos_http_error_handler)
    app.add_exception_handler(asyncpg.PostgresError, _postgres_error_handler)
    app.add_exception_handler(AzureError, _azure_error_handler)
    app.add_exception_handler(ConfigResolutionError, _config_resolution_error_handler)
    # httpx errors from URL ingestion: HTTPStatusError (403/5xx from remote),
    # ConnectError, TimeoutException etc. -> 502 instead of 500.
    app.add_exception_handler(httpx.HTTPError, _httpx_error_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
