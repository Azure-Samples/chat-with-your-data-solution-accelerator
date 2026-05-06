"""Pillar: Stable Core / Phase: 5 (task #35a) -- admin router tests.

Covers the read-only ``GET /api/admin/status`` endpoint and the
``admin_user_id`` auth-gating dependency that mirrors
``backend.routers.history.get_user_id``. RBAC narrowing
(admin-role-only) is deferred to task #39 with explicit ``# TODO(#39):``
markers in the router; for now any authenticated caller is accepted.
"""

from types import SimpleNamespace as NS
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from backend.dependencies import get_app_settings
from backend.routers.admin import admin_user_id, router as admin_router


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

    def _make(settings: Any) -> FastAPI:
        app = FastAPI()
        app.include_router(admin_router)
        app.dependency_overrides[get_app_settings] = lambda: settings
        # Pin admin_user_id so route tests that don't probe auth gating
        # can run without forging the Easy Auth header.
        app.dependency_overrides[admin_user_id] = lambda: "u-1"
        return app

    return _make


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# ---------------------------------------------------------------------------
# admin_user_id (auth gate, mirrors history.get_user_id H1 hardening)
# ---------------------------------------------------------------------------


def test_admin_user_id_reads_easy_auth_header() -> None:
    from starlette.requests import Request

    scope: dict[str, Any] = {
        "type": "http",
        "headers": [
            (b"x-ms-client-principal-id", b"00000000-0000-0000-0000-000000000abc")
        ],
    }
    settings = _settings(environment="production")
    assert (
        admin_user_id(Request(scope), settings)
        == "00000000-0000-0000-0000-000000000abc"
    )


def test_admin_user_id_falls_back_to_local_dev_when_header_missing_in_local() -> None:
    from starlette.requests import Request

    scope: dict[str, Any] = {"type": "http", "headers": []}
    settings = _settings(environment="local")
    assert admin_user_id(Request(scope), settings) == "local-dev"


def test_admin_user_id_raises_401_in_production_when_header_missing() -> None:
    """Production must fail closed -- mirrors history H1 hardening (#32b)."""
    from fastapi import HTTPException
    from starlette.requests import Request

    scope: dict[str, Any] = {"type": "http", "headers": []}
    settings = _settings(environment="production")
    with pytest.raises(HTTPException) as exc:
        admin_user_id(Request(scope), settings)
    assert exc.value.status_code == 401


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
    # already-pinned admin_user_id override (the fixture pinned
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
    """End-to-end H1 hardening check: the route must reject anonymous
    callers in production. Builds the app WITHOUT the ``admin_user_id``
    override so the real dependency runs.
    """
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/status")
    assert resp.status_code == 401


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
    """H1 hardening: anonymous callers must be rejected in production.

    Builds the app WITHOUT the ``admin_user_id`` override so the real
    dependency runs and the missing Easy Auth header trips the 401.
    """
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_app_settings] = lambda: _settings(
        environment="production"
    )
    async with _client(app) as ac:
        resp = await ac.get("/api/admin/config")
    assert resp.status_code == 401
