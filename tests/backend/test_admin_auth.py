"""Admin authentication-gate tests.

Exercise :func:`backend.dependencies.require_authenticated_user`, the
router-level trust boundary mounted on ``/api/admin``. The security
report (anonymous callers reaching the admin surface) is closed by this
gate: when ``AZURE_REQUIRE_ADMIN_AUTH`` is enabled a request without a
valid platform-injected ``x-ms-client-principal-id`` header is rejected
with 401 before any handler runs.

These tests mount the real dependency on a minimal guarded route so the
assertions are about the gate alone, independent of the heavier settings
surface the concrete admin routes resolve.
"""

from types import SimpleNamespace as NS
from typing import Any

import httpx
import pytest
from fastapi import Depends, FastAPI

from backend.dependencies import (
    get_app_settings,
    require_authenticated_user,
)

# A well-formed principal id, as Container Apps EasyAuth would inject
# after validating the caller's token.
_VALID_PRINCIPAL = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_PRINCIPAL_HEADER = "x-ms-client-principal-id"
_ANON_DEFAULT = "00000000-0000-0000-0000-000000000000"


def _settings(*, require_admin_auth: bool) -> Any:
    """Minimal settings stub exposing only the field the gate reads."""
    return NS(auth=NS(require_admin_auth=require_admin_auth))


def _guarded_app(settings: Any) -> FastAPI:
    """Mount the real auth gate on a single echo route."""
    app = FastAPI()
    app.dependency_overrides[get_app_settings] = lambda: settings

    @app.get("/api/admin/_probe")
    async def _probe(user: str = Depends(require_authenticated_user)) -> dict[str, str]:
        return {"user": user}

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_missing_principal_rejected_when_auth_required() -> None:
    """No principal header + auth required -> 401 (fail closed).

    This is the exact anonymous-caller case from the vulnerability
    report: the admin surface must refuse the request.
    """
    app = _guarded_app(_settings(require_admin_auth=True))
    async with _client(app) as client:
        resp = await client.get("/api/admin/_probe")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_principal_rejected_when_auth_required() -> None:
    """A malformed (non-GUID) principal header -> 401."""
    app = _guarded_app(_settings(require_admin_auth=True))
    async with _client(app) as client:
        resp = await client.get(
            "/api/admin/_probe", headers={_PRINCIPAL_HEADER: "not-a-guid"}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_principal_authenticated_when_auth_required() -> None:
    """A valid principal header -> 200 and the id flows to the handler.

    The id is what the PATCH-config handler persists as the audit actor,
    so authenticating here is also what makes ``updated_by`` trustworthy.
    """
    app = _guarded_app(_settings(require_admin_auth=True))
    async with _client(app) as client:
        resp = await client.get(
            "/api/admin/_probe", headers={_PRINCIPAL_HEADER: _VALID_PRINCIPAL}
        )
    assert resp.status_code == 200
    assert resp.json() == {"user": _VALID_PRINCIPAL}


@pytest.mark.asyncio
async def test_anonymous_allowed_when_auth_not_required() -> None:
    """auth disabled (local dev) + no header -> anonymous default id.

    Preserves the loopback dev ergonomics when
    ``AZURE_REQUIRE_ADMIN_AUTH=false``.
    """
    app = _guarded_app(_settings(require_admin_auth=False))
    async with _client(app) as client:
        resp = await client.get("/api/admin/_probe")
    assert resp.status_code == 200
    assert resp.json() == {"user": _ANON_DEFAULT}
