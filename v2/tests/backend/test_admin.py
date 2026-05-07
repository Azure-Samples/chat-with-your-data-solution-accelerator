"""Pillar: Stable Core / Phase: 5 (tasks #35a, #35b, #35c, #39) -- admin router tests.

Covers the read-only ``GET /api/admin/status`` endpoint, the
``GET /api/admin/config`` runtime-toggle subset (#35b), the
``PATCH /api/admin/config`` merge-patch endpoint (#35c), and the
#39 RBAC-narrowed ``_REQUIRE_ADMIN_USER`` auth gate (replaces the
former ``admin_user_id`` placeholder; the role-claim contract itself
is unit-tested in ``test_dependencies.py::test_requires_role_*``).
"""

from types import SimpleNamespace as NS
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from backend.dependencies import get_app_settings, get_database_client
from backend.routers.admin import _REQUIRE_ADMIN_USER, router as admin_router


# ---------------------------------------------------------------------------
# Settings stub: nested SimpleNamespace mirrors AppSettings shape.
# Sensitive values carry a 'DO-NOT-LEAK' marker so the leak-guard test
# can assert they never reach the wire.
# ---------------------------------------------------------------------------


def _settings(
    *,
    environment: str = "local",
    orchestrator_name: str = "langgraph",
    db_type: str = "cosmosdb",
    index_store: str = "AzureSearch",
    project_endpoint: str = "https://my-foundry.cognitiveservices.azure.com/projects/proj1",
    gpt_deployment: str = "gpt-4o",
    embedding_deployment: str = "text-embedding-3-large",
    reasoning_deployment: str = "",
    search_endpoint: str = "https://srch.search.windows.net",
    app_insights_conn: str = "",
    cors_origins: list[str] | None = None,
    # Runtime-toggle fields (surfaced by GET /api/admin/config in #35b).
    openai_temperature: float = 0.0,
    openai_max_tokens: int = 1000,
    search_use_semantic_search: bool = True,
    search_top_k: int = 5,
    log_level: str = "INFO",
    # Sensitive: must NEVER appear in the status / config response.
    tenant_id: str = "tenant-secret-DO-NOT-LEAK",
    uami_client_id: str = "uami-secret-DO-NOT-LEAK",
    cosmos_endpoint: str = "https://cosmos-secret-DO-NOT-LEAK.documents.azure.com:443/",
    postgres_endpoint: str = "",
    api_version: str = "api-version-secret-DO-NOT-LEAK",
) -> Any:
    return NS(
        environment=environment,
        orchestrator=NS(name=orchestrator_name),
        database=NS(
            db_type=db_type,
            index_store=index_store,
            cosmos_endpoint=cosmos_endpoint,
            postgres_endpoint=postgres_endpoint,
        ),
        foundry=NS(project_endpoint=project_endpoint),
        openai=NS(
            gpt_deployment=gpt_deployment,
            embedding_deployment=embedding_deployment,
            reasoning_deployment=reasoning_deployment,
            api_version=api_version,
            temperature=openai_temperature,
            max_tokens=openai_max_tokens,
        ),
        search=NS(
            endpoint=search_endpoint,
            use_semantic_search=search_use_semantic_search,
            top_k=search_top_k,
        ),
        observability=NS(
            app_insights_connection_string=app_insights_conn,
            log_level=log_level,
        ),
        identity=NS(tenant_id=tenant_id, uami_client_id=uami_client_id),
        network=NS(cors_origins=cors_origins or []),
    )


@pytest.fixture
def admin_app_factory():
    """Build a minimal FastAPI app exposing only the admin router.

    The app is intentionally NOT the full ``backend.app.create_app()``
    -- task #35e wires ``app.include_router(admin.router)`` and re-runs
    the green-gate. Until then the admin router boots in isolation so
    tests do not depend on lifespan-built providers.
    """

    def _make(settings: Any, db: Any = None) -> FastAPI:
        app = FastAPI()
        app.include_router(admin_router)
        app.dependency_overrides[get_app_settings] = lambda: settings
        # Pin the #39 admin-role gate so route tests that don't probe
        # auth gating can run without forging the Easy Auth headers.
        app.dependency_overrides[_REQUIRE_ADMIN_USER] = lambda: "u-1"
        if db is not None:
            app.dependency_overrides[get_database_client] = lambda: db
        return app

    return _make


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# ---------------------------------------------------------------------------
# admin auth gate (#39 -- RBAC-narrowed to the "admin" role claim).
#
# The role-claim parsing contract is exhaustively unit-tested in
# tests/backend/test_dependencies.py::test_requires_role_*. The smoke
# tests below are the ROUTE-level wiring checks: do the admin routes
# actually consume the gate, and does a missing principal in production
# surface as 401 end-to-end through the router?
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /api/admin/status -- payload shape and value mapping
# ---------------------------------------------------------------------------


_EXPECTED_STATUS_KEYS = {
    "orchestrator_name",
    "db_type",
    "index_store",
    "environment",
    "foundry_project_endpoint_host",
    "gpt_deployment",
    "embedding_deployment",
    "reasoning_deployment",
    "search_enabled",
    "app_insights_enabled",
    "cors_origins",
    "version",
}


@pytest.mark.asyncio
async def test_status_returns_expected_field_set(admin_app_factory) -> None:
    app = admin_app_factory(_settings())
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _EXPECTED_STATUS_KEYS


@pytest.mark.asyncio
async def test_status_extracts_foundry_host_only_not_path(
    admin_app_factory,
) -> None:
    app = admin_app_factory(
        _settings(
            project_endpoint="https://my-foundry.cognitiveservices.azure.com/projects/proj1"
        )
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    body = resp.json()
    assert body["foundry_project_endpoint_host"] == (
        "my-foundry.cognitiveservices.azure.com"
    )


@pytest.mark.asyncio
async def test_status_returns_empty_host_when_endpoint_unset(
    admin_app_factory,
) -> None:
    app = admin_app_factory(_settings(project_endpoint=""))
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert resp.json()["foundry_project_endpoint_host"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint, expected",
    [("", False), ("https://srch.search.windows.net", True)],
)
async def test_status_search_enabled_flag(
    admin_app_factory, endpoint: str, expected: bool
) -> None:
    app = admin_app_factory(_settings(search_endpoint=endpoint))
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert resp.json()["search_enabled"] is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conn, expected",
    [
        ("", False),
        ("InstrumentationKey=00000000-0000-0000-0000-000000000000", True),
    ],
)
async def test_status_app_insights_enabled_flag(
    admin_app_factory, conn: str, expected: bool
) -> None:
    app = admin_app_factory(_settings(app_insights_conn=conn))
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert resp.json()["app_insights_enabled"] is expected


@pytest.mark.asyncio
async def test_status_maps_orchestrator_db_index_environment(
    admin_app_factory,
) -> None:
    app = admin_app_factory(
        _settings(
            orchestrator_name="agent_framework",
            db_type="postgresql",
            index_store="pgvector",
            environment="production",
            postgres_endpoint=(
                "postgresql://my-pg.postgres.database.azure.com:5432/cwyd?sslmode=require"
            ),
            cosmos_endpoint="",
        )
    )
    # production mode -> route requires header; forge it via the
    # already-pinned _REQUIRE_ADMIN_USER override (the fixture pinned
    # "u-1"), so the request still succeeds.
    # "u-1"), so the request still succeeds.
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    body = resp.json()
    assert body["orchestrator_name"] == "agent_framework"
    assert body["db_type"] == "postgresql"
    assert body["index_store"] == "pgvector"
    assert body["environment"] == "production"


@pytest.mark.asyncio
async def test_status_returns_cors_and_deployments(admin_app_factory) -> None:
    app = admin_app_factory(
        _settings(
            gpt_deployment="gpt-4o",
            embedding_deployment="text-embedding-3-large",
            reasoning_deployment="o3-mini",
            cors_origins=["http://localhost:3000", "https://prod.example.com"],
        )
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    body = resp.json()
    assert body["gpt_deployment"] == "gpt-4o"
    assert body["embedding_deployment"] == "text-embedding-3-large"
    assert body["reasoning_deployment"] == "o3-mini"
    assert body["cors_origins"] == [
        "http://localhost:3000",
        "https://prod.example.com",
    ]


# ---------------------------------------------------------------------------
# Sensitive-field leak guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "marker",
    [
        "tenant-secret-DO-NOT-LEAK",
        "uami-secret-DO-NOT-LEAK",
        "cosmos-secret-DO-NOT-LEAK",
        "api-version-secret-DO-NOT-LEAK",
    ],
)
async def test_status_does_not_leak_sensitive_settings(
    admin_app_factory, marker: str
) -> None:
    """Each sensitive AppSettings field carries a 'DO-NOT-LEAK' marker
    in the test stub. The status response body MUST NOT contain any of
    them -- catches accidental ``settings.model_dump()`` regressions
    and any future field additions that bypass the explicit allow-list.
    """
    app = admin_app_factory(_settings())
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert marker not in resp.text


# ---------------------------------------------------------------------------
# Auth gate via the full route (production mode, missing header -> 401)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_endpoint_requires_easy_auth_in_production() -> None:
    """End-to-end #39 RBAC check: the route must reject anonymous
    callers in production. Builds the app WITHOUT the
    ``_REQUIRE_ADMIN_USER`` override so the real role-claim gate runs.
    """
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_endpoint_returns_403_when_caller_lacks_admin_role() -> None:
    """End-to-end #39 RBAC check: an authenticated caller WITHOUT the
    ``admin`` role claim must be rejected with 403, not 200. Builds the
    app WITHOUT the ``_REQUIRE_ADMIN_USER`` override so the real gate
    parses the forged claims blob.
    """
    import base64
    import json

    payload = {
        "auth_typ": "aad",
        "claims": [{"typ": "roles", "val": "reader"}],
    }
    claims_blob = base64.b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    async with _client(app) as ac:
        resp = await ac.get(
            "/api/admin/status",
            headers={
                "x-ms-client-principal-id": "user-oid-789",
                "x-ms-client-principal": claims_blob,
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_status_endpoint_returns_200_when_caller_has_admin_role(
    admin_app_factory,
) -> None:
    """End-to-end #39 RBAC check: an authenticated caller WITH the
    ``admin`` role claim reaches the route handler. Builds the app
    WITHOUT the ``_REQUIRE_ADMIN_USER`` override so the real gate
    parses the forged claims blob and resolves the user id.
    """
    import base64
    import json

    payload = {
        "auth_typ": "aad",
        "claims": [{"typ": "roles", "val": "admin"}],
    }
    claims_blob = base64.b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    async with _client(app) as ac:
        resp = await ac.get(
            "/api/admin/status",
            headers={
                "x-ms-client-principal-id": "user-oid-admin",
                "x-ms-client-principal": claims_blob,
            },
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pillar declaration (Hard Rule #3)
# ---------------------------------------------------------------------------


def test_admin_router_module_declares_pillar_and_phase() -> None:
    """Hard Rule #3: every new module under v2/src/** opens with a
    Pillar / Phase docstring header so reviewers and future agents
    can map the file to the development plan.
    """
    import backend.routers.admin as mod

    doc = (mod.__doc__ or "").lower()
    assert "pillar:" in doc
    assert "phase: 5" in doc


# ---------------------------------------------------------------------------
# GET /api/admin/config -- runtime-toggle subset (#35b)
#
# Read-only typed view of the AppSettings fields that #35c will allow
# admins to mutate at runtime. Field allow-list is intentionally
# limited to settings that are NOT infra-pinned (the v2 OrchestratorSettings
# docstring on `name` and the OpenAI / Search / Observability tunables
# already shipped in Phase 2). No new AppSettings fields are introduced
# by #35b -- adding e.g. content-safety / RAI flags would trigger
# Hard Rule #10 + #12 and is deferred to a separate task.
# ---------------------------------------------------------------------------


_EXPECTED_CONFIG_KEYS = {
    "orchestrator_name",
    "openai_temperature",
    "openai_max_tokens",
    "search_use_semantic_search",
    "search_top_k",
    "log_level",
}


@pytest.mark.asyncio
async def test_config_returns_expected_field_set(admin_app_factory) -> None:
    app = admin_app_factory(_settings())
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _EXPECTED_CONFIG_KEYS


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["langgraph", "agent_framework"])
async def test_config_maps_orchestrator_name(
    admin_app_factory, name: str
) -> None:
    app = admin_app_factory(_settings(orchestrator_name=name))
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    assert resp.json()["orchestrator_name"] == name


@pytest.mark.asyncio
async def test_config_maps_openai_runtime_toggles(admin_app_factory) -> None:
    app = admin_app_factory(
        _settings(openai_temperature=0.7, openai_max_tokens=2048)
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    body = resp.json()
    assert body["openai_temperature"] == 0.7
    assert body["openai_max_tokens"] == 2048


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "use_semantic, top_k", [(True, 5), (False, 10)]
)
async def test_config_maps_search_runtime_toggles(
    admin_app_factory, use_semantic: bool, top_k: int
) -> None:
    app = admin_app_factory(
        _settings(
            search_use_semantic_search=use_semantic, search_top_k=top_k
        )
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    body = resp.json()
    assert body["search_use_semantic_search"] is use_semantic
    assert body["search_top_k"] == top_k


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["INFO", "DEBUG", "WARNING"])
async def test_config_maps_log_level(admin_app_factory, level: str) -> None:
    app = admin_app_factory(_settings(log_level=level))
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    assert resp.json()["log_level"] == level


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "marker",
    [
        "tenant-secret-DO-NOT-LEAK",
        "uami-secret-DO-NOT-LEAK",
        "cosmos-secret-DO-NOT-LEAK",
        "api-version-secret-DO-NOT-LEAK",
    ],
)
async def test_config_does_not_leak_sensitive_settings(
    admin_app_factory, marker: str
) -> None:
    """Same DO-NOT-LEAK contract as the status endpoint -- a future
    refactor that swaps the explicit allow-list for a generic
    ``settings.model_dump()`` would fail this test.
    """
    app = admin_app_factory(_settings())
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    assert marker not in resp.text


@pytest.mark.asyncio
async def test_config_endpoint_requires_easy_auth_in_production() -> None:
    """#39 RBAC: anonymous callers must be rejected in production.

    Builds the app WITHOUT the ``_REQUIRE_ADMIN_USER`` override so the
    real dependency runs and the missing Easy Auth header trips the 401.
    """
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/admin/config -- runtime overrides (#35c-4)
#
# RFC 7396 JSON Merge Patch over the same 6-field surface as GET:
#   * absent JSON key  -> override unchanged
#   * explicit `null`  -> override cleared (falls through to env default
#                          on next live-reload; live-reload itself is
#                          deferred -- see dev_plan #35c "Excluded")
#   * explicit value   -> override set
#   * unknown JSON key -> 422 (field allow-list lock-in -- catches a
#                          future settings drift where someone adds a
#                          new RuntimeConfig field but forgets to wire
#                          its validator)
#   * wrong-type value -> 422 (Pydantic validation on the merged shape)
#
# The route MUST persist via `db.upsert_runtime_config(merged)` so the
# override survives container restarts; effective-config GET (which
# would overlay this on env defaults) is deferred to a separate row.
# ---------------------------------------------------------------------------


def _fake_db(
    *, current: Any = None, upsert: Any = None
) -> Any:
    """Build a minimal fake `BaseDatabaseClient` exposing only the two
    runtime-config methods the PATCH route consumes (#35c-2 +
    #35c-3). `current` is the value `get_runtime_config` returns;
    `upsert` lets a test pin a custom AsyncMock to capture the
    write argument for assertion."""
    from unittest.mock import AsyncMock

    db = NS()
    db.get_runtime_config = AsyncMock(return_value=current)
    db.upsert_runtime_config = upsert or AsyncMock(return_value=None)
    return db


@pytest.mark.asyncio
async def test_patch_config_persists_single_field_override(
    admin_app_factory,
) -> None:
    """Happy path: a single-field PATCH must (a) call
    `db.upsert_runtime_config` exactly once with that field set on a
    `RuntimeConfig`, and (b) return 200 with the merged config in the
    response body. Locks the storage call -- without it, the override
    would be ack'd to the operator but lost on container restart."""
    from backend.core.types import RuntimeConfig

    db = _fake_db(current=None)
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"openai_temperature": 0.7}
        )
    assert resp.status_code == 200
    db.upsert_runtime_config.assert_awaited_once()
    persisted = db.upsert_runtime_config.await_args.args[0]
    assert isinstance(persisted, RuntimeConfig)
    assert persisted.openai_temperature == 0.7
    body = resp.json()
    assert body["openai_temperature"] == 0.7


@pytest.mark.asyncio
async def test_patch_config_rejects_unknown_field_with_422(
    admin_app_factory,
) -> None:
    """Unknown JSON keys must 422 (not silently ignored). Locks the
    field allow-list at the route boundary so a future settings drift
    (someone adds `RuntimeConfig.new_toggle` but forgets to wire its
    validator) cannot accept stale-shape PATCH bodies that the GET
    side has no contract for."""
    db = _fake_db()
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"bogus_field": "x"}
        )
    assert resp.status_code == 422
    db.upsert_runtime_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_config_rejects_wrong_type_with_422(
    admin_app_factory,
) -> None:
    """Type mismatch must 422 -- Pydantic validation on the merged
    `RuntimeConfig`. Without this guard a string-shaped temperature
    would round-trip through Cosmos JSON / Postgres JSONB cleanly
    and only crash the LLM call hours later when the wrong type
    reached `openai_chat.create(temperature=...)`."""
    db = _fake_db()
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config",
            json={"openai_temperature": "not-a-float"},
        )
    assert resp.status_code == 422
    db.upsert_runtime_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_config_explicit_null_clears_override(
    admin_app_factory,
) -> None:
    """RFC 7396 explicit `null` semantics: the field is *cleared* (set
    to `None` on the persisted RuntimeConfig). The next live-reload
    of `app.state.settings` will then fall through to the env default
    for that field. This is the operator UX for 'undo my override'
    without restarting the container or deleting the row."""
    from backend.core.types import RuntimeConfig

    db = _fake_db(current=RuntimeConfig(openai_temperature=0.5))
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"openai_temperature": None}
        )
    assert resp.status_code == 200
    persisted = db.upsert_runtime_config.await_args.args[0]
    assert persisted.openai_temperature is None
    body = resp.json()
    assert body["openai_temperature"] is None


@pytest.mark.asyncio
async def test_patch_config_sparse_update_preserves_other_overrides(
    admin_app_factory,
) -> None:
    """RFC 7396 sparse semantics: an absent JSON key leaves the
    existing override untouched. Validates the merge reads
    `db.get_runtime_config()` first -- without this an operator
    flipping `openai_temperature` would silently wipe their previous
    `openai_max_tokens` override (because the persisted shape is the
    full RuntimeConfig, not a per-field key)."""
    from backend.core.types import RuntimeConfig

    db = _fake_db(
        current=RuntimeConfig(
            openai_temperature=0.5, openai_max_tokens=2048
        )
    )
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"openai_temperature": 0.9}
        )
    assert resp.status_code == 200
    persisted = db.upsert_runtime_config.await_args.args[0]
    assert persisted.openai_temperature == 0.9
    # Untouched override survives.
    assert persisted.openai_max_tokens == 2048


@pytest.mark.asyncio
async def test_patch_config_records_caller_id_and_timestamp(
    admin_app_factory,
) -> None:
    """Audit trail: every persisted RuntimeConfig must carry the
    admin caller's user id (from `_REQUIRE_ADMIN_USER`, pinned to "u-1"
    in this fixture) and an ISO-8601 `updated_at` so a future query
    can answer 'who flipped temperature to 0.9 and when?'. Without
    these, the override row is anonymous and undateable."""
    db = _fake_db()
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"openai_temperature": 0.7}
        )
    assert resp.status_code == 200
    persisted = db.upsert_runtime_config.await_args.args[0]
    assert persisted.updated_by == "u-1"
    # ISO-8601 with timezone -- not just "now()" formatted weirdly.
    assert persisted.updated_at
    from datetime import datetime

    parsed = datetime.fromisoformat(persisted.updated_at)
    assert parsed.tzinfo is not None


@pytest.mark.asyncio
async def test_patch_config_response_body_matches_persisted_runtime_config(
    admin_app_factory,
) -> None:
    """The response body MUST be the just-persisted RuntimeConfig so
    the operator UI can render the new override-state without a
    follow-up GET. Asserts shape symmetry: every key on the persisted
    RuntimeConfig appears in the response, nothing extra (no leaked
    settings, no internal fields)."""
    from backend.core.types import RuntimeConfig

    db = _fake_db()
    app = admin_app_factory(_settings(), db=db)
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"search_top_k": 10}
        )
    assert resp.status_code == 200
    persisted = db.upsert_runtime_config.await_args.args[0]
    assert set(resp.json().keys()) == set(
        RuntimeConfig.model_fields.keys()
    )
    assert resp.json()["search_top_k"] == persisted.search_top_k


@pytest.mark.asyncio
async def test_patch_config_requires_easy_auth_in_production() -> None:
    """H1 hardening parity with GET: anonymous callers must be
    rejected in production. Without this, an unauthenticated PATCH
    could mutate the persisted runtime config indefinitely."""
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    db = _fake_db()
    app.dependency_overrides[get_database_client] = lambda: db
    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"openai_temperature": 0.7}
        )
    assert resp.status_code == 401
    db.upsert_runtime_config.assert_not_awaited()


# ---------------------------------------------------------------------------
# #35e(a): live-reload runtime overrides -- PATCH writes through to
# `app.state.runtime_overrides` so the next request's
# `get_runtime_overrides` dependency surfaces the new override without
# a container restart. Lifespan-side seed loading is covered in
# tests/backend/test_app_lifespan.py::test_lifespan_loads_persisted_*.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_config_writes_back_to_app_state_runtime_overrides(
    admin_app_factory,
) -> None:
    """After a successful PATCH, the live process MUST observe the new
    override via `app.state.runtime_overrides` (the read side of the
    live-reload channel that downstream consumers read through the
    `get_runtime_overrides` dependency). Without this, every PATCH
    would still require a container restart to take effect, which is
    exactly the gap #35e(a) closes.
    """
    db = _fake_db()
    app = admin_app_factory(_settings(), db=db)
    # Seed `app.state` with a stale override to prove the PATCH
    # actually replaces it (not merely "appends if absent").
    from backend.core.types import RuntimeConfig

    app.state.runtime_overrides = RuntimeConfig(openai_temperature=0.1)

    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"openai_temperature": 0.9}
        )
    assert resp.status_code == 200

    # Persisted shape and in-memory shape must be the SAME instance --
    # the route must reuse the merged RuntimeConfig it just upserted,
    # not re-fetch from the DB (which would mask a write/read drift).
    persisted = db.upsert_runtime_config.await_args.args[0]
    assert app.state.runtime_overrides is persisted
    assert app.state.runtime_overrides.openai_temperature == 0.9


@pytest.mark.asyncio
async def test_patch_config_does_not_touch_app_state_on_validation_failure(
    admin_app_factory,
) -> None:
    """If the PATCH bails out with 422 (unknown key, wrong type, etc.)
    the in-memory `app.state.runtime_overrides` MUST stay untouched --
    the operator's previous override remains active. Without this
    invariant, a typo in the PATCH body could silently wipe the live
    config to whatever half-merged shape the route reached before
    raising.
    """
    from backend.core.types import RuntimeConfig

    seeded = RuntimeConfig(openai_temperature=0.5, updated_by="u-prev")
    db = _fake_db()
    app = admin_app_factory(_settings(), db=db)
    app.state.runtime_overrides = seeded

    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/admin/config", json={"bogus_field": "x"}
        )
    assert resp.status_code == 422
    db.upsert_runtime_config.assert_not_awaited()
    assert app.state.runtime_overrides is seeded


# ---------------------------------------------------------------------------
# #35e(b): GET /api/admin/config/effective -- merged view of env defaults
# overlaid with persisted DB overrides, with per-field provenance hints
# so the admin UI can render "this value comes from env / from override".
# Reads the override side through the live-reload channel
# (`get_runtime_overrides` -> `request.app.state.runtime_overrides`)
# established in #35e(a), so this endpoint reflects PATCHes immediately
# without a database round-trip.
# ---------------------------------------------------------------------------


_EXPECTED_EFFECTIVE_KEYS = {"values", "sources", "updated_at", "updated_by"}


@pytest.mark.asyncio
async def test_config_effective_returns_env_defaults_when_no_overrides(
    admin_app_factory,
) -> None:
    """No persisted overrides -> every field's source is "env",
    every value matches the `AppSettings` env default, and the audit
    fields (`updated_at`, `updated_by`) are null. This is the
    cold-start shape every freshly-deployed environment will report
    until the first admin PATCH lands.
    """
    app = admin_app_factory(
        _settings(
            orchestrator_name="langgraph",
            openai_temperature=0.0,
            openai_max_tokens=1000,
            search_use_semantic_search=True,
            search_top_k=5,
            log_level="INFO",
        )
    )
    # No `app.state.runtime_overrides` set -- the dep tolerates the
    # missing attr and returns None, exercising the cold-start path.

    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config/effective")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _EXPECTED_EFFECTIVE_KEYS

    assert body["values"] == {
        "orchestrator_name": "langgraph",
        "openai_temperature": 0.0,
        "openai_max_tokens": 1000,
        "search_use_semantic_search": True,
        "search_top_k": 5,
        "log_level": "INFO",
    }
    assert body["sources"] == {
        "orchestrator_name": "env",
        "openai_temperature": "env",
        "openai_max_tokens": "env",
        "search_use_semantic_search": "env",
        "search_top_k": "env",
        "log_level": "env",
    }
    assert body["updated_at"] is None
    assert body["updated_by"] is None


@pytest.mark.asyncio
async def test_config_effective_overlays_partial_overrides(
    admin_app_factory,
) -> None:
    """A `RuntimeConfig` with only some fields set MUST overlay just
    those fields and leave the rest reporting `"env"` provenance.
    Mirrors the RFC 7396 storage shape (`T | None = None` per field
    where None means 'not overridden').
    """
    from backend.core.types import RuntimeConfig

    app = admin_app_factory(
        _settings(
            orchestrator_name="langgraph",
            openai_temperature=0.0,
            openai_max_tokens=1000,
            search_use_semantic_search=True,
            search_top_k=5,
            log_level="INFO",
        )
    )
    app.state.runtime_overrides = RuntimeConfig(
        openai_temperature=0.9,
        log_level="DEBUG",
        updated_at="2026-05-07T12:00:00+00:00",
        updated_by="u-admin",
    )

    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config/effective")
    assert resp.status_code == 200
    body = resp.json()

    # Overridden fields surface override values.
    assert body["values"]["openai_temperature"] == 0.9
    assert body["values"]["log_level"] == "DEBUG"
    # Non-overridden fields surface env defaults.
    assert body["values"]["orchestrator_name"] == "langgraph"
    assert body["values"]["openai_max_tokens"] == 1000
    assert body["values"]["search_use_semantic_search"] is True
    assert body["values"]["search_top_k"] == 5
    # Provenance reflects the per-field origin.
    assert body["sources"] == {
        "orchestrator_name": "env",
        "openai_temperature": "override",
        "openai_max_tokens": "env",
        "search_use_semantic_search": "env",
        "search_top_k": "env",
        "log_level": "override",
    }
    # Audit fields surfaced from the override row.
    assert body["updated_at"] == "2026-05-07T12:00:00+00:00"
    assert body["updated_by"] == "u-admin"


@pytest.mark.asyncio
async def test_config_effective_treats_explicit_none_field_as_env(
    admin_app_factory,
) -> None:
    """A persisted `RuntimeConfig` whose field is explicitly None
    (operator cleared the override via PATCH `null`) MUST report
    `"env"` provenance for that field -- None means 'fall through to
    env default', not 'override the value to null'.
    """
    from backend.core.types import RuntimeConfig

    app = admin_app_factory(
        _settings(openai_temperature=0.3, log_level="WARNING")
    )
    # Override row exists but every mutable field is None -- equivalent
    # to "operator cleared all overrides via successive PATCH null".
    app.state.runtime_overrides = RuntimeConfig(
        updated_at="2026-05-07T13:00:00+00:00",
        updated_by="u-admin",
    )

    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config/effective")
    body = resp.json()

    assert body["values"]["openai_temperature"] == 0.3
    assert body["values"]["log_level"] == "WARNING"
    assert all(src == "env" for src in body["sources"].values())
    # Audit fields still surface even when no field is overridden --
    # the row exists, the operator just cleared every field.
    assert body["updated_at"] == "2026-05-07T13:00:00+00:00"
    assert body["updated_by"] == "u-admin"


@pytest.mark.asyncio
async def test_config_effective_overlays_all_fields_when_fully_overridden(
    admin_app_factory,
) -> None:
    """Every field overridden -> every source is "override", every
    value comes from the override row. Sanity check on the merge loop.
    """
    from backend.core.types import RuntimeConfig

    app = admin_app_factory(_settings())
    app.state.runtime_overrides = RuntimeConfig(
        orchestrator_name="agent_framework",
        openai_temperature=0.7,
        openai_max_tokens=2000,
        search_use_semantic_search=False,
        search_top_k=10,
        log_level="DEBUG",
        updated_at="2026-05-07T14:00:00+00:00",
        updated_by="u-admin",
    )

    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config/effective")
    body = resp.json()

    assert body["values"] == {
        "orchestrator_name": "agent_framework",
        "openai_temperature": 0.7,
        "openai_max_tokens": 2000,
        "search_use_semantic_search": False,
        "search_top_k": 10,
        "log_level": "DEBUG",
    }
    assert all(src == "override" for src in body["sources"].values())
