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
    get_content_safety_guard,
    get_database_client,
    get_runtime_overrides,
    get_search_provider,
    get_tenant_id,
    get_user_id,
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
_TENANT_TYP_FULL = "http://schemas.microsoft.com/identity/claims/tenantid"


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


# ---------------------------------------------------------------------------
# #35g unblock: get_tenant_id -- Easy Auth tenant-claim extraction
#
# Per-tenant config isolation needs the caller's Entra tenant id.
# Unlike the user object id (carried in the dedicated
# `x-ms-client-principal-id` header), the tenant id lives ONLY inside
# the base64 `x-ms-client-principal` claims blob, so `get_tenant_id`
# decodes the blob and extracts the `tid` claim. It is tolerant to both
# the short `typ="tid"` and the full URI tenantid claim forms (mirrors
# the role gate accepting both `roles` and the full role URI).
#
# Fail-closed in production (missing/malformed/absent claim -> 401);
# local-dev bypass returns "local-dev-tenant" when the claim is
# unavailable so per-tenant flows are exercisable without forging a
# claims blob -- but a malformed blob still fails closed even in local
# (parity with requires_role).
# ---------------------------------------------------------------------------


def test_get_tenant_id_returns_tid_short_form() -> None:
    """Short ``typ="tid"`` claim -> returned verbatim in production."""
    request = _request({_PRINCIPAL: _claims(("tid", "tenant-abc"))})
    assert get_tenant_id(request, _settings("production")) == "tenant-abc"


def test_get_tenant_id_accepts_full_uri_tenant_claim() -> None:
    """Easy Auth may emit the tenant id with the schema-URI ``typ``."""
    request = _request({_PRINCIPAL: _claims((_TENANT_TYP_FULL, "tenant-xyz"))})
    assert get_tenant_id(request, _settings("production")) == "tenant-xyz"


def test_get_tenant_id_raises_401_when_claims_header_missing_in_production() -> None:
    """No claims blob in production -> fail closed (401)."""
    request = _request({})
    with pytest.raises(HTTPException) as exc:
        get_tenant_id(request, _settings("production"))
    assert exc.value.status_code == 401


def test_get_tenant_id_raises_401_when_tenant_claim_absent_in_production() -> None:
    """Valid claims blob carrying no tenant claim -> 401 in production.

    A blob with only a role claim and no ``tid`` must not silently fold
    the caller into a single shared tenant -- that would defeat the
    per-tenant isolation this dep exists to provide.
    """
    request = _request({_PRINCIPAL: _claims(("roles", "admin"))})
    with pytest.raises(HTTPException) as exc:
        get_tenant_id(request, _settings("production"))
    assert exc.value.status_code == 401


def test_get_tenant_id_raises_401_on_malformed_base64() -> None:
    """Undecodable claims blob -> fail closed (401)."""
    request = _request({_PRINCIPAL: "not!valid!base64==="})
    with pytest.raises(HTTPException) as exc:
        get_tenant_id(request, _settings("production"))
    assert exc.value.status_code == 401


def test_get_tenant_id_raises_401_on_malformed_json() -> None:
    """Valid base64 wrapping non-JSON bytes -> fail closed (401)."""
    bad = base64.b64encode(b"not-json-at-all").decode("ascii")
    request = _request({_PRINCIPAL: bad})
    with pytest.raises(HTTPException) as exc:
        get_tenant_id(request, _settings("production"))
    assert exc.value.status_code == 401


def test_get_tenant_id_falls_back_to_local_dev_tenant_when_no_headers_in_local() -> None:
    """Local-dev bypass: no claims blob + ``environment == 'local'`` ->
    return the synthetic ``'local-dev-tenant'`` so per-tenant flows are
    exercisable end-to-end without forging Easy Auth claims."""
    request = _request({})
    assert get_tenant_id(request, _settings("local")) == "local-dev-tenant"


def test_get_tenant_id_in_local_returns_real_tenant_when_claim_present() -> None:
    """Local environment does NOT blindly synthesize when a real tenant
    claim is present -- the forged blob's ``tid`` wins over the synthetic
    fallback (parity with requires_role honoring forged claims locally)."""
    request = _request({_PRINCIPAL: _claims(("tid", "tenant-local-real"))})
    assert get_tenant_id(request, _settings("local")) == "tenant-local-real"


def test_get_tenant_id_falls_back_to_local_dev_tenant_when_claim_absent_in_local() -> None:
    """Local + valid blob but no ``tid`` claim -> synthetic tenant (the
    soft-fallback branch, mirroring requires_role's local fallback when
    the principal id is absent from an otherwise-valid blob)."""
    request = _request({_PRINCIPAL: _claims(("roles", "admin"))})
    assert get_tenant_id(request, _settings("local")) == "local-dev-tenant"


# ---------------------------------------------------------------------------
# U-CS-3: get_content_safety_guard -- builds the per-request guard from
# the lifespan-owned ContentSafetyClient. Returns None when the client
# is absent (content safety disabled) so consumers can treat None as
# "screening off" and pass the user input through unchanged.
# ---------------------------------------------------------------------------


def _settings_with_threshold(threshold: int) -> Any:
    """Build a stand-in ``AppSettings`` exposing only the field the dep reads.

    Keeps the test focused on the guard wiring -- a full ``AppSettings()``
    would force every test to set the full COSMOS_ENV fixture even though
    only ``content_safety.severity_threshold`` is consumed here.
    """
    return SimpleNamespace(
        content_safety=SimpleNamespace(severity_threshold=threshold)
    )


def test_get_content_safety_guard_returns_none_when_attr_missing() -> None:
    """Lifespan never ran -> attribute is absent entirely. Dep MUST
    return None rather than raise -- content safety is an optional
    layer; missing it means 'guard off', not 500.
    """
    request = _request_with_state()
    settings = _settings_with_threshold(4)
    assert get_content_safety_guard(request, settings) is None  # type: ignore[arg-type]


def test_get_content_safety_guard_returns_none_when_client_is_none() -> None:
    """Lifespan ran with content_safety disabled -> attribute is
    explicitly None. Same handling as the missing-attribute case.
    """
    request = _request_with_state(content_safety_client=None)
    settings = _settings_with_threshold(4)
    assert get_content_safety_guard(request, settings) is None  # type: ignore[arg-type]


def test_get_content_safety_guard_builds_with_client_and_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When lifespan stashed a real client, the dep constructs a fresh
    ``ContentSafetyGuard`` per request, threading the configured
    severity_threshold. ContentSafetyGuard itself is cheap (no
    network) so per-request construction is intentional -- it keeps
    the runtime-override channel (U-CS-7) trivial to wire in later.
    """
    fake_client = MagicMock(name="content_safety_client")
    request = _request_with_state(content_safety_client=fake_client)
    settings = _settings_with_threshold(6)

    fake_guard = MagicMock(name="content_safety_guard")
    ctor_spy = MagicMock(return_value=fake_guard)
    monkeypatch.setattr("backend.dependencies.ContentSafetyGuard", ctor_spy)

    result = get_content_safety_guard(request, settings)  # type: ignore[arg-type]

    assert result is fake_guard
    ctor_spy.assert_called_once_with(
        client=fake_client, severity_threshold=6
    )


def test_get_content_safety_guard_threads_default_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Threshold flows from ``settings.content_safety.severity_threshold``
    verbatim -- the dep itself MUST NOT hard-code a default. The
    Pydantic sub-model owns the default-and-validation contract.
    """
    fake_client = MagicMock(name="content_safety_client")
    request = _request_with_state(content_safety_client=fake_client)
    settings = _settings_with_threshold(2)

    ctor_spy = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("backend.dependencies.ContentSafetyGuard", ctor_spy)

    get_content_safety_guard(request, settings)  # type: ignore[arg-type]

    assert ctor_spy.call_args.kwargs["severity_threshold"] == 2


# ---------------------------------------------------------------------------
# U-CS-7: runtime-override cascade. The `RuntimeConfig.content_safety_enabled`
# override layer wins over the env baseline at request time. Rules:
#
#   * override is `None` (the cold default + the post-clear state once an
#     admin has PATCHed `null`) -> defer to the env baseline (client exists
#     iff env enabled at lifespan).
#   * override is `False` (admin explicitly turned the guard off) -> return
#     None even when the lifespan client exists; operator-off ALWAYS wins.
#   * override is `True` (admin explicitly turned the guard on) -> the
#     override cannot synthesize a client out of thin air (no endpoint /
#     credential at request time), so the lifespan client must already
#     exist -- when it does, return the guard; when it doesn't, return
#     None (fail-open, consistent with the "no client" rule above).
# ---------------------------------------------------------------------------


def test_get_content_safety_guard_returns_guard_when_override_enabled_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override = True + lifespan client present -> guard returned.

    Covers the 'admin explicitly turned screening on AND lifespan was
    able to build the client' path -- the override doesn't add new
    behavior beyond the env baseline here, but the test locks in that
    the cascade doesn't accidentally drop the guard.
    """
    fake_client = MagicMock(name="content_safety_client")
    overrides = RuntimeConfig(content_safety_enabled=True)
    request = _request_with_state(
        content_safety_client=fake_client,
        runtime_overrides=overrides,
    )
    settings = _settings_with_threshold(4)

    fake_guard = MagicMock(name="content_safety_guard")
    ctor_spy = MagicMock(return_value=fake_guard)
    monkeypatch.setattr("backend.dependencies.ContentSafetyGuard", ctor_spy)

    result = get_content_safety_guard(request, settings)  # type: ignore[arg-type]

    assert result is fake_guard


def test_get_content_safety_guard_returns_none_when_override_enabled_false() -> None:
    """Override = False + lifespan client present -> guard MUST be None.

    The load-bearing override case (mirrors U-CS-5's distinguish-False-
    from-None semantic). Operator-off always wins; the lifespan client
    stays built (cheap, no network), but no guard is handed to the
    request, so screening is effectively disabled until the operator
    PATCHes the override back to True or null.
    """
    fake_client = MagicMock(name="content_safety_client")
    overrides = RuntimeConfig(content_safety_enabled=False)
    request = _request_with_state(
        content_safety_client=fake_client,
        runtime_overrides=overrides,
    )
    settings = _settings_with_threshold(4)

    assert get_content_safety_guard(request, settings) is None  # type: ignore[arg-type]


def test_get_content_safety_guard_returns_guard_when_override_enabled_none_and_client_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override = None (the cold default + post-clear state) -> defer
    to env baseline. With a lifespan client present, that means the
    guard is returned -- proves the cascade doesn't treat None as
    'disabled' (which would be a regression on the U-CS-3 contract).
    """
    fake_client = MagicMock(name="content_safety_client")
    overrides = RuntimeConfig(content_safety_enabled=None)
    request = _request_with_state(
        content_safety_client=fake_client,
        runtime_overrides=overrides,
    )
    settings = _settings_with_threshold(4)

    fake_guard = MagicMock(name="content_safety_guard")
    ctor_spy = MagicMock(return_value=fake_guard)
    monkeypatch.setattr("backend.dependencies.ContentSafetyGuard", ctor_spy)

    result = get_content_safety_guard(request, settings)  # type: ignore[arg-type]

    assert result is fake_guard


def test_get_content_safety_guard_returns_none_when_override_false_and_no_client() -> None:
    """Override = False + no lifespan client -> None (vacuously).

    Belt-and-braces: the 'no client' rule already wins on its own, but
    the test pins the override = False path to 'always None' regardless
    of whether the client is present. Prevents a future refactor from
    accidentally short-circuiting the override check above the client
    check and synthesizing a guard from nothing.
    """
    overrides = RuntimeConfig(content_safety_enabled=False)
    request = _request_with_state(
        content_safety_client=None,
        runtime_overrides=overrides,
    )
    settings = _settings_with_threshold(4)

    assert get_content_safety_guard(request, settings) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# get_user_id -- Easy Auth principal extraction (no role gate)
#
# Sibling of `requires_role`: reads `x-ms-client-principal-id` and
# returns the caller's Entra object id. Falls back to "local-dev"
# only when `settings.environment is Environment.LOCAL` so chat
# history is exercisable in dev without forging Easy Auth headers;
# production raises 401 on a missing header (fail-closed).
# ---------------------------------------------------------------------------


def test_get_user_id_returns_principal_id_when_header_present() -> None:
    request = _request({_PRINCIPAL_ID: "user-oid-42"})
    assert get_user_id(request, _settings("production")) == "user-oid-42"


def test_get_user_id_falls_back_to_local_dev_when_local_and_header_missing() -> None:
    request = _request({})
    assert get_user_id(request, _settings(Environment.LOCAL)) == "local-dev"


def test_get_user_id_raises_401_when_production_and_header_missing() -> None:
    request = _request({})
    with pytest.raises(HTTPException) as exc_info:
        get_user_id(request, _settings(Environment.PRODUCTION))
    assert exc_info.value.status_code == 401
    assert "Missing client principal" in exc_info.value.detail
