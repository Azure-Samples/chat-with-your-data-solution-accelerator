"""Pillar: Stable Core / Phase: 3.5 (debt #Q6b) — lifespan wires search provider."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import AzureError

from backend.app import _init_content_safety_client, create_app
from backend.core.settings import AppSettings, get_settings
from backend.core.types import RuntimeConfig


COSMOS_ENV: dict[str, str] = {
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
    "AZURE_AI_PROJECT_ENDPOINT": "https://foundry-cwyd001.services.ai.azure.com/api/projects/p1",
    "AZURE_AI_SEARCH_ENDPOINT": "https://srch-cwyd001.search.windows.net",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-5.1",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
}


@pytest.fixture(autouse=True)
def _clean_caches() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _apply_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key in list(COSMOS_ENV.keys()) + [
        "AZURE_POSTGRES_ENDPOINT",
        "AZURE_UAMI_CLIENT_ID",
        "AZURE_CONTENT_SAFETY_ENDPOINT",
        "AZURE_CONTENT_SAFETY_ENABLED",
        "AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _patched_lifespan(monkeypatch: pytest.MonkeyPatch):
    """Stub credentials + llm + databases + agents so lifespan stays offline; let search registry dispatch run."""
    fake_credential = MagicMock(name="credential")
    fake_credential.close = AsyncMock()
    fake_cred_provider = MagicMock()
    fake_cred_provider.get_credential = AsyncMock(return_value=fake_credential)

    fake_llm = MagicMock(name="llm_provider")
    fake_llm.aclose = AsyncMock()

    fake_db = MagicMock(name="database_client")
    fake_db.aclose = AsyncMock()
    # #35e(a): lifespan loads persisted RuntimeConfig overrides into
    # app.state. Stub returns None so the unrelated lifespan tests
    # below see `app.state.runtime_overrides is None` (the cold-start
    # default). Tests that exercise the load path override this stub.
    fake_db.get_runtime_config = AsyncMock(return_value=None)

    fake_agents = MagicMock(name="agents_provider")
    fake_agents.aclose = AsyncMock()

    fake_cred_registry = MagicMock(name="credentials_registry")
    fake_cred_registry.get.return_value = lambda **_kw: fake_cred_provider

    monkeypatch.setattr(
        "backend.app.credentials_registry.select_default", lambda *_a, **_kw: "azure_cli"
    )
    monkeypatch.setattr(
        "backend.app.credentials_registry.registry", fake_cred_registry
    )
    fake_llm_registry = MagicMock(name="llm_registry")
    fake_llm_registry.get.return_value = lambda **_kw: fake_llm
    monkeypatch.setattr(
        "backend.app.llm_registry.registry", fake_llm_registry
    )
    fake_databases_registry = MagicMock(name="databases_registry")
    fake_databases_registry.get.return_value = lambda **_kw: fake_db
    monkeypatch.setattr(
        "backend.app.databases_registry.registry", fake_databases_registry
    )
    fake_agents_registry = MagicMock(name="agents_registry")
    fake_agents_registry.get.return_value = lambda **_kw: fake_agents
    monkeypatch.setattr(
        "backend.app.agents_registry.registry", fake_agents_registry
    )
    return fake_credential


async def test_lifespan_constructs_search_provider_when_endpoint_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Search is configured, lifespan stashes a provider on app.state."""
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)

    fake_search = MagicMock(name="search_provider")
    fake_search.aclose = AsyncMock()
    fake_search.ensure_schema = AsyncMock()
    fake_search_registry = MagicMock(name="search_registry")
    fake_search_registry.get.return_value = lambda **_kw: fake_search
    monkeypatch.setattr(
        "backend.app.search_registry.registry", fake_search_registry
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.search_provider is fake_search

    fake_search.aclose.assert_awaited_once()


async def test_lifespan_skips_search_when_endpoint_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No endpoint => no search provider; orchestrator runs in pass-through mode."""
    env = {**COSMOS_ENV, "AZURE_AI_SEARCH_ENDPOINT": ""}
    _apply_env(monkeypatch, env)
    _patched_lifespan(monkeypatch)

    called = {"count": 0}

    def _fail_get(*_a, **_kw):
        called["count"] += 1
        raise AssertionError("search registry must not be invoked")

    fake_search_registry = MagicMock(name="search_registry")
    fake_search_registry.get.side_effect = _fail_get
    monkeypatch.setattr("backend.app.search_registry.registry", fake_search_registry)

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.search_provider is None

    assert called["count"] == 0


async def test_lifespan_constructs_database_client_and_closes_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan stashes a database client on app.state and aclose()s it on shutdown."""
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)
    _fake_sr = MagicMock(name="search_registry")
    _fake_sr.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr("backend.app.search_registry.registry", _fake_sr)

    captured: dict[str, object] = {}

    def _capture_get(key):
        captured["key"] = key

        def _factory(**kwargs):
            captured["settings"] = kwargs.get("settings")
            captured["credential"] = kwargs.get("credential")
            client = MagicMock(name="database_client")
            client.aclose = AsyncMock()
            client.get_runtime_config = AsyncMock(return_value=None)
            captured["client"] = client
            return client

        return _factory

    fake_databases_registry = MagicMock(name="databases_registry")
    fake_databases_registry.get.side_effect = _capture_get
    monkeypatch.setattr(
        "backend.app.databases_registry.registry", fake_databases_registry
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.database_client is captured["client"]
        # Registry key must equal the settings db_type literal so dispatch
        # is registry-only (Hard Rule #4).
        assert captured["key"] == "cosmosdb"

    captured["client"].aclose.assert_awaited_once()  # type: ignore[attr-defined]


async def test_lifespan_dispatches_postgresql_db_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When db_type=postgresql, lifespan dispatches to the 'postgresql' registry key."""
    env = {
        **COSMOS_ENV,
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_COSMOS_ENDPOINT": "",
        "AZURE_AI_SEARCH_ENDPOINT": "",
        "AZURE_POSTGRES_ENDPOINT": "postgresql://x.postgres.database.azure.com:5432/cwyd?sslmode=require",
        "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME": "id-cwyd001",
    }
    _apply_env(monkeypatch, env)
    _patched_lifespan(monkeypatch)

    captured_key: dict[str, object] = {}

    def _capture_get(key):
        captured_key["key"] = key

        def _factory(**_kw):
            client = MagicMock()
            client.aclose = AsyncMock()
            client.ensure_pool = AsyncMock(return_value=MagicMock(name="pool"))
            client.get_runtime_config = AsyncMock(return_value=None)
            return client

        return _factory

    fake_databases_registry = MagicMock(name="databases_registry")
    fake_databases_registry.get.side_effect = _capture_get
    monkeypatch.setattr(
        "backend.app.databases_registry.registry", fake_databases_registry
    )
    _fake_sr2 = MagicMock(name="search_registry")
    _fake_sr2.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr2
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert captured_key["key"] == "postgresql"


async def test_lifespan_wires_pgvector_with_postgres_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 4 hardening (B1): pgvector dispatch + pool DI from postgres client.

    `index_store=pgvector` must (1) register a search provider on app.state
    via `search_registry.registry.get("pgvector")(...)` -- not be silently skipped -- and
    (2) inject the postgres client's pool as the `pool=` kwarg so the
    search provider and the database client share one pool per process.
    """
    env = {
        **COSMOS_ENV,
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_COSMOS_ENDPOINT": "",
        "AZURE_AI_SEARCH_ENDPOINT": "",
        "AZURE_POSTGRES_ENDPOINT": "postgresql://x.postgres.database.azure.com:5432/cwyd?sslmode=require",
        "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME": "id-cwyd001",
    }
    _apply_env(monkeypatch, env)
    _patched_lifespan(monkeypatch)

    fake_pool = MagicMock(name="postgres_pool")
    fake_db = MagicMock(name="postgres_client")
    fake_db.aclose = AsyncMock()
    fake_db.ensure_pool = AsyncMock(return_value=fake_pool)
    fake_db.get_runtime_config = AsyncMock(return_value=None)
    fake_databases_registry = MagicMock(name="databases_registry")
    fake_databases_registry.get.return_value = lambda **_kw: fake_db
    monkeypatch.setattr(
        "backend.app.databases_registry.registry", fake_databases_registry
    )

    fake_search = MagicMock(name="pgvector_provider")
    fake_search.aclose = AsyncMock()
    fake_search.ensure_schema = AsyncMock()
    captured: dict[str, object] = {}

    def _capture_search_get(key):
        captured["key"] = key

        def _factory(**kwargs):
            captured["kwargs"] = kwargs
            return fake_search

        return _factory

    fake_search_registry = MagicMock(name="search_registry")
    fake_search_registry.get.side_effect = _capture_search_get
    monkeypatch.setattr("backend.app.search_registry.registry", fake_search_registry)

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.search_provider is fake_search

    # Registry key must equal the settings index_store Literal value
    # (Hard Rule #4) -- no name-string translation in dispatch.
    assert captured["key"] == "pgvector"
    # pgvector must receive the postgres pool via DI (single pool/process).
    assert captured["kwargs"]["pool"] is fake_pool
    fake_db.ensure_pool.assert_awaited_once()
    fake_search.aclose.assert_awaited_once()


async def test_lifespan_pgvector_does_not_require_search_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pgvector mode must not be gated on `AZURE_AI_SEARCH_ENDPOINT`.

    The `endpoint`-absent skip applies to `AzureSearch` only; pgvector
    talks to postgres, not Azure AI Search.
    """
    env = {
        **COSMOS_ENV,
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_COSMOS_ENDPOINT": "",
        "AZURE_AI_SEARCH_ENDPOINT": "",  # explicitly absent
        "AZURE_POSTGRES_ENDPOINT": "postgresql://x.postgres.database.azure.com:5432/cwyd?sslmode=require",
        "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME": "id-cwyd001",
    }
    _apply_env(monkeypatch, env)
    _patched_lifespan(monkeypatch)

    fake_db = MagicMock()
    fake_db.aclose = AsyncMock()
    fake_db.ensure_pool = AsyncMock(return_value=MagicMock())
    fake_db.get_runtime_config = AsyncMock(return_value=None)
    fake_databases_registry = MagicMock(name="databases_registry")
    fake_databases_registry.get.return_value = lambda **_kw: fake_db
    monkeypatch.setattr(
        "backend.app.databases_registry.registry", fake_databases_registry
    )

    fake_search = MagicMock()
    fake_search.aclose = AsyncMock()
    fake_search.ensure_schema = AsyncMock()
    fake_search_registry = MagicMock(name="search_registry")
    fake_search_registry.get.return_value = lambda **_kw: fake_search
    monkeypatch.setattr(
        "backend.app.search_registry.registry", fake_search_registry
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.search_provider is fake_search


# ---------------------------------------------------------------------------
# ensure_schema wiring (PGVECTOR-SCHEMA-BOOTSTRAP-DEBT sub-unit 1d)
# ---------------------------------------------------------------------------


async def test_lifespan_calls_ensure_schema_once_before_yield(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`await search_provider.ensure_schema()` must run once during
    startup, before the lifespan yields to the app. Provider-agnostic:
    AzureSearch inherits the no-op default; pgvector runs the DDL.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)

    record: list[str] = []

    async def _record_ensure_schema() -> None:
        record.append("ensure_schema")

    fake_search = MagicMock(name="search_provider")
    fake_search.aclose = AsyncMock()
    fake_search.ensure_schema = AsyncMock(side_effect=_record_ensure_schema)
    fake_search_registry = MagicMock(name="search_registry")
    fake_search_registry.get.return_value = lambda **_kw: fake_search
    monkeypatch.setattr(
        "backend.app.search_registry.registry", fake_search_registry
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        # By the time the app is yielding, ensure_schema must already
        # have run. Subsequent assertions confirm it ran exactly once
        # (not per-request, not in shutdown).
        assert record == ["ensure_schema"]
        fake_search.ensure_schema.assert_awaited_once()

    # No second call during shutdown.
    fake_search.ensure_schema.assert_awaited_once()


async def test_lifespan_propagates_ensure_schema_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ensure_schema` failure must abort startup -- the app refuses to
    boot rather than yielding into a request loop that will crash on
    every first query/ingestion. Consistent with how earlier setup
    failures (credentials, database client) already behave.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)

    fake_search = MagicMock(name="search_provider")
    fake_search.aclose = AsyncMock()
    fake_search.ensure_schema = AsyncMock(
        side_effect=AzureError("ddl rejected")
    )
    fake_search_registry = MagicMock(name="search_registry")
    fake_search_registry.get.return_value = lambda **_kw: fake_search
    monkeypatch.setattr(
        "backend.app.search_registry.registry", fake_search_registry
    )

    app = create_app()
    with pytest.raises(AzureError):
        async with app.router.lifespan_context(app):
            pass  # pragma: no cover -- startup must raise

    fake_search.ensure_schema.assert_awaited_once()


async def test_lifespan_configures_app_insights_from_typed_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan reads the connection string from
    `ObservabilitySettings.app_insights_connection_string`, not directly
    from `os.getenv`.

    The settings field is populated via env var
    `AZURE_APP_INSIGHTS_CONNECTION_STRING` (env_prefix=AZURE_); the
    legacy `APPLICATIONINSIGHTS_CONNECTION_STRING` form is intentionally
    NOT honored at the lifespan layer post-CU-002b -- the operator must
    use the typed name.
    """
    env = {
        **COSMOS_ENV,
        "AZURE_APP_INSIGHTS_CONNECTION_STRING": (
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
            "IngestionEndpoint=https://eastus2.in.applicationinsights.azure.com/"
        ),
    }
    _apply_env(monkeypatch, env)
    _patched_lifespan(monkeypatch)
    _fake_sr3 = MagicMock(name="search_registry")
    _fake_sr3.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr3
    )

    captured: dict[str, str] = {}

    def _fake_configure(*, connection_string: str) -> None:
        captured["connection_string"] = connection_string

    monkeypatch.setattr(
        "backend.app.configure_azure_monitor", _fake_configure
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert captured["connection_string"].startswith("InstrumentationKey=")


async def test_lifespan_skips_app_insights_when_typed_setting_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the typed setting is empty, telemetry must stay disabled
    even if the legacy `APPLICATIONINSIGHTS_CONNECTION_STRING` env var
    is set -- that legacy alias is not read by AppSettings (CU-007).
    """
    env = {
        **COSMOS_ENV,
        # Legacy alias intentionally set; must be ignored by the lifespan.
        "APPLICATIONINSIGHTS_CONNECTION_STRING": (
            "InstrumentationKey=11111111-1111-1111-1111-111111111111"
        ),
    }
    _apply_env(monkeypatch, env)
    monkeypatch.delenv("AZURE_APP_INSIGHTS_CONNECTION_STRING", raising=False)
    _patched_lifespan(monkeypatch)
    _fake_sr4 = MagicMock(name="search_registry")
    _fake_sr4.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr4
    )

    called = {"count": 0}

    def _fake_configure(**_kw) -> None:
        called["count"] += 1

    monkeypatch.setattr(
        "backend.app.configure_azure_monitor", _fake_configure
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert called["count"] == 0


def test_create_app_cors_uses_typed_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`create_app` reads `NetworkSettings.cors_origins` (CU-002a alias
    on `BACKEND_CORS_ORIGINS`) instead of calling `os.getenv`.

    Asserts on the live `CORSMiddleware` config so a regression that
    re-introduces `os.getenv` would fail loudly.
    """
    env = {
        **COSMOS_ENV,
        "BACKEND_CORS_ORIGINS": "http://a.example, https://b.example",
    }
    _apply_env(monkeypatch, env)

    app = create_app()
    cors_layers = [
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    ]
    assert cors_layers, "CORS middleware must be installed"
    cors = cors_layers[0]
    origins = cors.kwargs.get("allow_origins")
    assert origins == ["http://a.example", "https://b.example"]
    # When origins is a non-wildcard list, allow_credentials must be True
    # (otherwise the browser refuses to send cookies / Authorization).
    assert cors.kwargs.get("allow_credentials") is True


def test_create_app_cors_falls_back_to_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `BACKEND_CORS_ORIGINS` -> wildcard origin + credentials disabled
    (CORS spec forbids credentials with `*`).
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    monkeypatch.delenv("BACKEND_CORS_ORIGINS", raising=False)

    app = create_app()
    cors = next(
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    assert cors.kwargs.get("allow_origins") == ["*"]
    assert cors.kwargs.get("allow_credentials") is False


# ---------------------------------------------------------------------------
# CU-001c: lifespan constructs FoundryAgentsProvider via registry
# ---------------------------------------------------------------------------


async def test_lifespan_constructs_agents_provider_via_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan must dispatch through `agents.create("foundry", ...)` and
    stash the provider on `app.state.agents_provider`.

    Asserts the registry key (`"foundry"`) and that `settings` +
    `credential` are forwarded -- mirrors how `llm` / `databases` are
    wired (Hard Rule #4: registry-only dispatch).
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)
    _fake_sr5 = MagicMock(name="search_registry")
    _fake_sr5.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr5
    )

    captured: dict[str, object] = {}
    fake_agents = MagicMock(name="agents_provider")
    fake_agents.aclose = AsyncMock()

    def _capture_get(key):
        captured["key"] = key

        def _factory(**kwargs):
            captured["settings"] = kwargs.get("settings")
            captured["credential"] = kwargs.get("credential")
            return fake_agents

        return _factory

    fake_agents_registry = MagicMock(name="agents_registry")
    fake_agents_registry.get.side_effect = _capture_get
    monkeypatch.setattr("backend.app.agents_registry.registry", fake_agents_registry)

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.agents_provider is fake_agents

    assert captured["key"] == "foundry"
    assert captured["settings"] is not None
    assert captured["credential"] is not None


async def test_lifespan_closes_agents_provider_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reverse-order shutdown: `agents_provider.aclose()` must be awaited
    on lifespan exit so the cached AgentsClient HTTP transport is freed.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)
    _fake_sr6 = MagicMock(name="search_registry")
    _fake_sr6.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr6
    )

    fake_agents = MagicMock(name="agents_provider")
    fake_agents.aclose = AsyncMock()
    fake_agents_registry = MagicMock(name="agents_registry")
    fake_agents_registry.get.return_value = lambda **_kw: fake_agents
    monkeypatch.setattr(
        "backend.app.agents_registry.registry", fake_agents_registry
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    fake_agents.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# #35e(a): live-reload runtime overrides -- lifespan loads persisted
# RuntimeConfig from the database and stashes it on app.state, so reads
# survive container restarts. The PATCH /api/admin/config route handles
# the post-startup reassignment (covered in test_admin.py).
# ---------------------------------------------------------------------------


async def test_lifespan_loads_persisted_runtime_overrides_into_app_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the database returns a persisted `RuntimeConfig`, lifespan
    stashes it on ``app.state.runtime_overrides`` so the dependency
    `get_runtime_overrides` returns it from the very first request --
    no need to wait for a PATCH to repopulate after a restart.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)
    _fake_sr7 = MagicMock(name="search_registry")
    _fake_sr7.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr7
    )

    persisted = RuntimeConfig(
        openai_temperature=0.42,
        updated_at="2026-05-07T12:00:00+00:00",
        updated_by="u-prev",
    )
    fake_db = MagicMock(name="database_client")
    fake_db.aclose = AsyncMock()
    fake_db.get_runtime_config = AsyncMock(return_value=persisted)
    fake_databases_registry = MagicMock(name="databases_registry")
    fake_databases_registry.get.return_value = lambda **_kw: fake_db
    monkeypatch.setattr(
        "backend.app.databases_registry.registry", fake_databases_registry
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.runtime_overrides is persisted

    fake_db.get_runtime_config.assert_awaited_once()


async def test_lifespan_runtime_overrides_none_when_no_persisted_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cold start: nothing in the database -> lifespan stashes None.
    Downstream consumers MUST treat None as 'no overrides yet' and
    fall through to the env-default `AppSettings` snapshot.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)  # default fake_db returns None
    _fake_sr8 = MagicMock(name="search_registry")
    _fake_sr8.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr(
        "backend.app.search_registry.registry", _fake_sr8
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.runtime_overrides is None


# ---------------------------------------------------------------------------
# U-CS-2: Content Safety client lifespan wiring
# ---------------------------------------------------------------------------


_CONTENT_SAFETY_ENABLED_ENV = {
    "AZURE_CONTENT_SAFETY_ENABLED": "true",
    "AZURE_CONTENT_SAFETY_ENDPOINT": (
        "https://cs-cwyd001.cognitiveservices.azure.com/"
    ),
}


def _patch_search_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most lifespan tests stub the search registry with a no-op factory
    so they can focus on whichever subsystem they're asserting on.
    """
    fake_sr = MagicMock(name="search_registry")
    fake_sr.get.return_value = lambda **_kw: MagicMock(
        aclose=AsyncMock(), ensure_schema=AsyncMock()
    )
    monkeypatch.setattr("backend.app.search_registry.registry", fake_sr)


def test_init_content_safety_client_returns_none_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `content_safety.enabled` is False, the helper short-circuits
    without instantiating `ContentSafetyClient` -- callers receive None
    and treat it as 'screening disabled'.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(
        "AZURE_CONTENT_SAFETY_ENDPOINT",
        "https://cs-cwyd001.cognitiveservices.azure.com/",
    )
    # Explicitly opt OUT -- the `enabled` default is now True.
    monkeypatch.setenv("AZURE_CONTENT_SAFETY_ENABLED", "false")
    settings = AppSettings()
    assert settings.content_safety.enabled is False
    assert settings.content_safety.endpoint != ""

    ctor_spy = MagicMock()
    monkeypatch.setattr("backend.app.ContentSafetyClient", ctor_spy)

    result = _init_content_safety_client(settings, MagicMock(name="credential"))

    assert result is None
    ctor_spy.assert_not_called()


def test_init_content_safety_client_returns_none_when_endpoint_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`enabled=True` alone is not enough -- a missing endpoint is a
    misconfiguration that fails open (no guard) rather than crashing
    boot. Helper still short-circuits.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_CONTENT_SAFETY_ENABLED", "true")
    # AZURE_CONTENT_SAFETY_ENDPOINT stays unset
    settings = AppSettings()
    assert settings.content_safety.enabled is True
    assert settings.content_safety.endpoint == ""

    ctor_spy = MagicMock()
    monkeypatch.setattr("backend.app.ContentSafetyClient", ctor_spy)

    result = _init_content_safety_client(settings, MagicMock(name="credential"))

    assert result is None
    ctor_spy.assert_not_called()


def test_init_content_safety_client_builds_with_endpoint_and_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both gates are open the helper constructs ContentSafetyClient
    with `endpoint=` + `credential=` kwargs (matches Azure SDK signature)
    and returns the resulting client unchanged.
    """
    _apply_env(monkeypatch, {**COSMOS_ENV, **_CONTENT_SAFETY_ENABLED_ENV})
    settings = AppSettings()
    assert settings.content_safety.enabled is True
    assert settings.content_safety.endpoint != ""

    fake_client = MagicMock(name="content_safety_client")
    ctor_spy = MagicMock(return_value=fake_client)
    monkeypatch.setattr("backend.app.ContentSafetyClient", ctor_spy)

    fake_credential = MagicMock(name="credential")
    result = _init_content_safety_client(settings, fake_credential)

    assert result is fake_client
    ctor_spy.assert_called_once_with(
        endpoint=settings.content_safety.endpoint,
        credential=fake_credential,
    )


async def test_lifespan_stashes_none_when_content_safety_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Content Safety endpoint configured -> `app.state.content_safety_client`
    is None and the chat pipeline runs unguarded. The `enabled` default is
    True, but the lifespan gate also requires an endpoint, so absent one the
    guard stays off.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)
    _patch_search_registry(monkeypatch)

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.content_safety_client is None


async def test_lifespan_stashes_client_when_content_safety_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When enabled + endpoint set, lifespan stashes the constructed
    client on `app.state.content_safety_client` so the DI layer
    (U-CS-3) can inject it into the chat pipeline.
    """
    _apply_env(monkeypatch, {**COSMOS_ENV, **_CONTENT_SAFETY_ENABLED_ENV})
    _patched_lifespan(monkeypatch)
    _patch_search_registry(monkeypatch)

    fake_client = MagicMock(name="content_safety_client")
    fake_client.close = AsyncMock()
    ctor_spy = MagicMock(return_value=fake_client)
    monkeypatch.setattr("backend.app.ContentSafetyClient", ctor_spy)

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.content_safety_client is fake_client

    ctor_spy.assert_called_once()


async def test_lifespan_closes_content_safety_client_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The aiohttp transport owned by ContentSafetyClient MUST be closed
    on shutdown -- forgetting this leaks sockets in long-running test
    suites and dev reloads.
    """
    _apply_env(monkeypatch, {**COSMOS_ENV, **_CONTENT_SAFETY_ENABLED_ENV})
    _patched_lifespan(monkeypatch)
    _patch_search_registry(monkeypatch)

    fake_client = MagicMock(name="content_safety_client")
    fake_client.close = AsyncMock()
    monkeypatch.setattr(
        "backend.app.ContentSafetyClient", MagicMock(return_value=fake_client)
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    fake_client.close.assert_awaited_once()


async def test_lifespan_shutdown_tolerates_missing_content_safety_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the client was never built (default env), shutdown must not
    raise -- the close path is a no-op, not an AttributeError.
    """
    _apply_env(monkeypatch, COSMOS_ENV)
    _patched_lifespan(monkeypatch)
    _patch_search_registry(monkeypatch)

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.content_safety_client is None
    # Reaching here proves shutdown didn't blow up trying to close None.
