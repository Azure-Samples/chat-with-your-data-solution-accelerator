"""Pillar: Stable Core / Phase: 3.5 (debt #Q6b) — lifespan wires search provider."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app import create_app
from shared.settings import get_settings


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
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-4o",
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
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _patched_lifespan(monkeypatch: pytest.MonkeyPatch):
    """Stub credentials + llm + databases + agents so lifespan stays offline; let `search.create` run."""
    fake_credential = MagicMock(name="credential")
    fake_credential.close = AsyncMock()
    fake_cred_provider = MagicMock()
    fake_cred_provider.get_credential = AsyncMock(return_value=fake_credential)

    fake_llm = MagicMock(name="llm_provider")
    fake_llm.aclose = AsyncMock()

    fake_db = MagicMock(name="database_client")
    fake_db.aclose = AsyncMock()

    fake_agents = MagicMock(name="agents_provider")
    fake_agents.aclose = AsyncMock()

    monkeypatch.setattr(
        "backend.app.credentials.select_default", lambda *_a, **_kw: "azure_cli"
    )
    monkeypatch.setattr(
        "backend.app.credentials.create",
        lambda *_a, **_kw: fake_cred_provider,
    )
    monkeypatch.setattr(
        "backend.app.llm.create", lambda *_a, **_kw: fake_llm
    )
    monkeypatch.setattr(
        "backend.app.databases.create", lambda *_a, **_kw: fake_db
    )
    monkeypatch.setattr(
        "backend.app.agents.create", lambda *_a, **_kw: fake_agents
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
    monkeypatch.setattr(
        "backend.app.search.create",
        lambda *_a, **_kw: fake_search,
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

    def _fail_create(*_a, **_kw):
        called["count"] += 1
        raise AssertionError("search.create must not be invoked")

    monkeypatch.setattr("backend.app.search.create", _fail_create)

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
    monkeypatch.setattr(
        "backend.app.search.create", lambda *_a, **_kw: MagicMock(aclose=AsyncMock())
    )

    captured: dict[str, object] = {}

    def _capture_create(key, **kwargs):
        captured["key"] = key
        captured["settings"] = kwargs.get("settings")
        captured["credential"] = kwargs.get("credential")
        client = MagicMock(name="database_client")
        client.aclose = AsyncMock()
        captured["client"] = client
        return client

    monkeypatch.setattr("backend.app.databases.create", _capture_create)

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
    """When db_type=postgresql, lifespan calls databases.create('postgresql', ...)."""
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

    def _capture(key, **_kw):
        captured_key["key"] = key
        client = MagicMock()
        client.aclose = AsyncMock()
        client.ensure_pool = AsyncMock(return_value=MagicMock(name="pool"))
        return client

    monkeypatch.setattr("backend.app.databases.create", _capture)
    monkeypatch.setattr(
        "backend.app.search.create",
        lambda *_a, **_kw: MagicMock(aclose=AsyncMock()),
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
    via `search.create("pgvector", ...)` -- not be silently skipped -- and
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
    monkeypatch.setattr(
        "backend.app.databases.create", lambda *_a, **_kw: fake_db
    )

    fake_search = MagicMock(name="pgvector_provider")
    fake_search.aclose = AsyncMock()
    captured: dict[str, object] = {}

    def _capture_search(key, **kwargs):
        captured["key"] = key
        captured["kwargs"] = kwargs
        return fake_search

    monkeypatch.setattr("backend.app.search.create", _capture_search)

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
    monkeypatch.setattr(
        "backend.app.databases.create", lambda *_a, **_kw: fake_db
    )

    fake_search = MagicMock()
    fake_search.aclose = AsyncMock()
    monkeypatch.setattr(
        "backend.app.search.create", lambda *_a, **_kw: fake_search
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.search_provider is fake_search


# ---------------------------------------------------------------------------
# CU-002b: typed Application Insights + CORS wiring
# ---------------------------------------------------------------------------


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
    monkeypatch.setattr(
        "backend.app.search.create",
        lambda *_a, **_kw: MagicMock(aclose=AsyncMock()),
    )

    captured: dict[str, str] = {}

    def _fake_configure(*, connection_string: str) -> None:
        captured["connection_string"] = connection_string

    # `azure.monitor.opentelemetry` is imported lazily inside the
    # lifespan; patch the module that the lifespan resolves to.
    monkeypatch.setitem(
        __import__("sys").modules,
        "azure.monitor.opentelemetry",
        MagicMock(configure_azure_monitor=_fake_configure),
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
    monkeypatch.setattr(
        "backend.app.search.create",
        lambda *_a, **_kw: MagicMock(aclose=AsyncMock()),
    )

    called = {"count": 0}

    def _fake_configure(**_kw) -> None:
        called["count"] += 1

    monkeypatch.setitem(
        __import__("sys").modules,
        "azure.monitor.opentelemetry",
        MagicMock(configure_azure_monitor=_fake_configure),
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
    monkeypatch.setattr(
        "backend.app.search.create",
        lambda *_a, **_kw: MagicMock(aclose=AsyncMock()),
    )

    captured: dict[str, object] = {}
    fake_agents = MagicMock(name="agents_provider")
    fake_agents.aclose = AsyncMock()

    def _capture(key, **kwargs):
        captured["key"] = key
        captured["settings"] = kwargs.get("settings")
        captured["credential"] = kwargs.get("credential")
        return fake_agents

    monkeypatch.setattr("backend.app.agents.create", _capture)

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
    monkeypatch.setattr(
        "backend.app.search.create",
        lambda *_a, **_kw: MagicMock(aclose=AsyncMock()),
    )

    fake_agents = MagicMock(name="agents_provider")
    fake_agents.aclose = AsyncMock()
    monkeypatch.setattr(
        "backend.app.agents.create", lambda *_a, **_kw: fake_agents
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    fake_agents.aclose.assert_awaited_once()
