"""DI provider tests."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request

from backend.core.types import RuntimeConfig
from backend.dependencies import (
    get_agents_provider,
    get_content_safety_guard,
    get_database_client,
    get_runtime_overrides,
    get_search_provider,
    get_user_id,
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
# agents provider DI seam (agent_framework wiring)
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
# get_runtime_overrides DI seam (live-reload runtime overrides)
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


_PRINCIPAL_ID = "x-ms-client-principal-id"


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (k.lower().encode("ascii"), v.encode("utf-8"))
        for k, v in (headers or {}).items()
    ]
    scope: dict[str, Any] = {"type": "http", "headers": raw_headers}
    return Request(scope)


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
    return SimpleNamespace(content_safety=SimpleNamespace(severity_threshold=threshold))


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
    ctor_spy.assert_called_once_with(client=fake_client, severity_threshold=6)


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


def test_get_content_safety_guard_returns_none_when_override_false_and_no_client() -> (
    None
):
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
# get_user_id -- principal-id header extraction
#
# Reads `x-ms-client-principal-id` and returns it verbatim when it is a
# valid GUID. A missing, blank, or non-GUID header folds into the
# anonymous default id `00000000-0000-0000-0000-000000000000`. Never
# raises: the id scopes a tenant partition, not a trust boundary.
# ---------------------------------------------------------------------------


def test_get_user_id_returns_principal_id_when_header_present() -> None:
    request = _request({_PRINCIPAL_ID: "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab"})
    assert get_user_id(request) == "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab"


def test_get_user_id_falls_back_to_default_guid_when_header_missing() -> None:
    request = _request({})
    assert get_user_id(request) == "00000000-0000-0000-0000-000000000000"


def test_get_user_id_falls_back_to_default_guid_when_not_a_guid() -> None:
    request = _request({_PRINCIPAL_ID: "user-oid-42"})
    assert get_user_id(request) == "00000000-0000-0000-0000-000000000000"
