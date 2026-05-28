"""Pillar: Stable Core / Phase: 3.5 (debt #Q6a) + Phase 5 (#39, #35e) — DI provider tests."""

import base64
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.core.settings import Environment
from backend.core.types import RuntimeConfig
from backend.dependencies import (
    get_agents_provider,
    get_database_client,
    get_runtime_overrides,
    get_search_provider,
    requires_role,
)


def _request_with_state(**state_kwargs: object) -> object:
    """Build a stand-in `Request` exposing `request.app.state.<attr>`."""
    state = SimpleNamespace(**state_kwargs)
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


def test_get_search_provider_returns_none_when_unset() -> None:
    """Lifespan may skip search wiring when no endpoint is configured."""
    request = _request_with_state()
    assert get_search_provider(request) is None  # type: ignore[arg-type]


def test_get_search_provider_returns_state_instance_when_set() -> None:
    """When lifespan stashes a provider on app.state, DI hands it out."""
    sentinel = MagicMock(name="search_provider")
    request = _request_with_state(search_provider=sentinel)
    assert get_search_provider(request) is sentinel  # type: ignore[arg-type]


def test_get_database_client_raises_when_missing() -> None:
    """If lifespan didn't run, DI must surface a clear error."""
    request = _request_with_state()
    with pytest.raises(RuntimeError, match="database_client missing"):
        get_database_client(request)  # type: ignore[arg-type]


def test_get_database_client_returns_state_instance_when_set() -> None:
    """When lifespan stashes a database client on app.state, DI hands it out."""
    sentinel = MagicMock(name="database_client")
    request = _request_with_state(database_client=sentinel)
    assert get_database_client(request) is sentinel  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CU-001c: agents provider DI seam (Phase 4 -- agent_framework wiring)
# ---------------------------------------------------------------------------


def test_get_agents_provider_raises_when_missing() -> None:
    """If lifespan didn't run, DI must surface a clear error so callers
    don't silently get None and fall through to a NoneType.AttributeError
    deep inside the orchestrator."""
    request = _request_with_state()
    with pytest.raises(RuntimeError, match="agents_provider missing"):
        get_agents_provider(request)  # type: ignore[arg-type]


def test_get_agents_provider_returns_state_instance_when_set() -> None:
    """When lifespan stashes the FoundryAgentsProvider on app.state, DI
    hands out the same instance for every request -- one HTTP transport
    per process (parity with credential_provider, llm_provider)."""
    sentinel = MagicMock(name="agents_provider")
    request = _request_with_state(agents_provider=sentinel)
    assert get_agents_provider(request) is sentinel  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# #35e(a): get_runtime_overrides DI seam (live-reload runtime overrides)
#
# Lifespan loads the persisted RuntimeConfig from the DB once at
# startup and stashes the result on `app.state.runtime_overrides`
# (None when nothing is persisted yet). The PATCH /api/admin/config
# route atomically reassigns the same attribute after a successful
# upsert, so reads-after-PATCH within the same process surface the
# new overrides without a container restart. The DI seam below is the
# read side of that channel; T+5 wires `GET /api/admin/config/effective`
# on top of it, and downstream consumers (orchestrators, etc.) follow.
# ---------------------------------------------------------------------------


def test_get_runtime_overrides_returns_none_when_unset() -> None:
    """No persisted RuntimeConfig -> lifespan stashes None and the
    dep hands it back. Callers MUST treat None as 'no overrides yet'
    and fall through to the env-default `AppSettings` snapshot.
    """
    request = _request_with_state(runtime_overrides=None)
    assert get_runtime_overrides(request) is None  # type: ignore[arg-type]


def test_get_runtime_overrides_returns_state_instance_when_set() -> None:
    """When lifespan (or the PATCH route) stashes a RuntimeConfig on
    app.state, DI hands out the same instance until the next reassignment.
    """
    sentinel = RuntimeConfig(openai_temperature=0.7, updated_by="u-1")
    request = _request_with_state(runtime_overrides=sentinel)
    assert get_runtime_overrides(request) is sentinel  # type: ignore[arg-type]


def test_get_runtime_overrides_returns_none_when_attr_missing() -> None:
    """Defensive: if lifespan never ran (e.g. ASGI test transport that
    skips the lifespan protocol) the attribute is missing entirely.
    The dep MUST return None rather than raise -- runtime overrides
    are an optional layer; missing them is a no-op, not a 500.
    """
    request = _request_with_state()
    assert get_runtime_overrides(request) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# #39: requires_role(role) -- Easy Auth role-claim gate
#
# Replaces the old "any authenticated caller" admin gate. The factory
# returns a FastAPI dependency that:
#
# * Reads the `X-MS-CLIENT-PRINCIPAL` header (base64 JSON with full
#   Easy Auth claims), decodes it, and asserts the requested role is
#   present.
# * Returns the caller's user id (Entra object id) on success.
# * Raises 401 when Easy Auth headers are missing/malformed in
#   production -- a misconfigured Easy Auth must fail closed.
# * Raises 403 when the caller is authenticated but lacks the role.
# * In `local` environment, falls back to "local-dev" when no headers
#   are present so the admin panel is exercisable end-to-end during
#   development without forging the base64 claims blob.
#
# Easy Auth role-claim shape: roles can appear with `typ` either equal
# to the literal string `"roles"` (the short form) OR the full URI
# `http://schemas.microsoft.com/ws/2008/06/identity/claims/role`. The
# helper accepts both.
# ---------------------------------------------------------------------------


_PRINCIPAL_ID = "x-ms-client-principal-id"
_PRINCIPAL = "x-ms-client-principal"
_ROLE_TYP_FULL = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"


def _claims(*role_pairs: tuple[str, str]) -> str:
    """Build a base64-encoded Easy Auth claims payload.

    Each ``role_pairs`` entry is ``(typ, val)`` -- pass either
    ``("roles", "admin")`` (short form) or
    ``(_ROLE_TYP_FULL, "admin")`` (full URI form).
    """
    payload = {
        "auth_typ": "aad",
        "claims": [{"typ": typ, "val": val} for typ, val in role_pairs],
    }
    raw = json.dumps(payload).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _settings(environment: Environment | str = Environment.PRODUCTION) -> Any:
    # Accept either an `Environment` member (preferred) or a raw
    # string (legacy callsites in this module) so the helper stays
    # stable as new tests are added. Strings are coerced to the
    # enum so `is Environment.LOCAL` dispatch in `requires_role`
    # works regardless of how the caller spelled the value.
    coerced = (
        environment
        if isinstance(environment, Environment)
        else Environment(environment)
    )
    return SimpleNamespace(environment=coerced)


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (k.lower().encode("ascii"), v.encode("utf-8"))
        for k, v in (headers or {}).items()
    ]
    scope: dict[str, Any] = {"type": "http", "headers": raw_headers}
    return Request(scope)


def test_requires_role_returns_user_id_when_role_present() -> None:
    dep = requires_role("admin")
    request = _request(
        {
            _PRINCIPAL_ID: "user-oid-123",
            _PRINCIPAL: _claims(("roles", "admin")),
        }
    )
    assert dep(request, _settings("production")) == "user-oid-123"


def test_requires_role_accepts_full_uri_role_claim() -> None:
    """Easy Auth may emit role claims with the schema-URI ``typ``."""
    dep = requires_role("admin")
    request = _request(
        {
            _PRINCIPAL_ID: "user-oid-456",
            _PRINCIPAL: _claims((_ROLE_TYP_FULL, "admin")),
        }
    )
    assert dep(request, _settings("production")) == "user-oid-456"


def test_requires_role_raises_403_when_role_absent() -> None:
    """Authenticated caller without the role -> 403 (not 401)."""
    dep = requires_role("admin")
    request = _request(
        {
            _PRINCIPAL_ID: "user-oid-789",
            _PRINCIPAL: _claims(("roles", "reader")),
        }
    )
    with pytest.raises(HTTPException) as exc:
        dep(request, _settings("production"))
    assert exc.value.status_code == 403


def test_requires_role_raises_401_when_principal_id_missing_in_production() -> None:
    """Production must fail closed when Easy Auth is broken/disabled."""
    dep = requires_role("admin")
    request = _request({})
    with pytest.raises(HTTPException) as exc:
        dep(request, _settings("production"))
    assert exc.value.status_code == 401


def test_requires_role_raises_401_when_claims_header_missing_in_production() -> None:
    """Principal id alone is not enough to evaluate role membership."""
    dep = requires_role("admin")
    request = _request({_PRINCIPAL_ID: "user-oid-abc"})
    with pytest.raises(HTTPException) as exc:
        dep(request, _settings("production"))
    assert exc.value.status_code == 401


def test_requires_role_raises_401_on_malformed_base64() -> None:
    dep = requires_role("admin")
    request = _request(
        {_PRINCIPAL_ID: "user-oid-def", _PRINCIPAL: "not!valid!base64==="}
    )
    with pytest.raises(HTTPException) as exc:
        dep(request, _settings("production"))
    assert exc.value.status_code == 401


def test_requires_role_raises_401_on_malformed_json() -> None:
    """Valid base64 wrapping non-JSON bytes must fail closed."""
    dep = requires_role("admin")
    bad = base64.b64encode(b"not-json-at-all").decode("ascii")
    request = _request({_PRINCIPAL_ID: "user-oid-ghi", _PRINCIPAL: bad})
    with pytest.raises(HTTPException) as exc:
        dep(request, _settings("production"))
    assert exc.value.status_code == 401


def test_requires_role_falls_back_to_local_dev_when_no_headers_in_local() -> None:
    """Local-dev bypass: no headers + ``environment == 'local'`` ->
    return ``'local-dev'`` so the admin panel is exercisable end-to-end
    during development without forging Easy Auth claims."""
    dep = requires_role("admin")
    request = _request({})
    assert dep(request, _settings("local")) == "local-dev"


def test_requires_role_in_local_still_validates_when_headers_present() -> None:
    """Local environment does NOT skip role checking when the caller
    explicitly sends Easy Auth headers -- devs can exercise the
    real role gate locally by forging the claims blob."""
    dep = requires_role("admin")
    request = _request(
        {
            _PRINCIPAL_ID: "user-oid-jkl",
            _PRINCIPAL: _claims(("roles", "reader")),
        }
    )
    with pytest.raises(HTTPException) as exc:
        dep(request, _settings("local"))
    assert exc.value.status_code == 403


def test_requires_role_factory_returns_distinct_callable_per_call() -> None:
    """Each ``requires_role(role)`` invocation must return a NEW
    callable so FastAPI's `app.dependency_overrides` keying stays
    deterministic. Modules that need a stable key MUST cache the
    returned dep at module import time (see admin.py for the pattern).
    """
    dep_a = requires_role("admin")
    dep_b = requires_role("admin")
    assert dep_a is not dep_b
