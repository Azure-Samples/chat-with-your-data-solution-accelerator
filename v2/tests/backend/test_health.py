"""Tests for the health router (Phase 2 task #13).

Pillar: Stable Core
Phase: 2
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.dependencies import (
    get_credential_provider,
    get_llm_provider,
)
from providers.credentials.base import BaseCredentialProvider
from providers.llm.base import BaseLLMProvider
from shared.settings import AppSettings, get_settings


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


def _set_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    # Wipe known CWYD vars first so test cases are hermetic.
    for key in list(COSMOS_ENV.keys()) + [
        "AZURE_POSTGRES_ENDPOINT",
        "AZURE_UAMI_CLIENT_ID",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _build_app(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Build an app and stub providers without invoking lifespan.

    `dependency_overrides` short-circuits the real provider lookup
    (which would otherwise raise because lifespan never ran). This is
    the FastAPI-canonical way to keep tests synchronous and offline.
    """
    _set_env(monkeypatch, env)
    app = create_app()
    fake_llm = MagicMock(spec=BaseLLMProvider)
    fake_cred = MagicMock(spec=BaseCredentialProvider)
    fake_cred.get_credential = AsyncMock(return_value=MagicMock())
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_credential_provider] = lambda: fake_cred
    return app


# ---------------------------------------------------------------------------
# /api/health -- diagnostic, always 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_200_when_all_checks_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(COSMOS_ENV, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pass"
    assert body["version"] == "v2"
    names = {c["name"]: c["status"] for c in body["checks"]}
    assert names == {"foundry_iq": "pass", "database": "pass", "search": "pass"}


@pytest.mark.asyncio
async def test_health_reports_fail_when_foundry_endpoint_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_AI_PROJECT_ENDPOINT"}
    app = _build_app(env, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
    assert r.status_code == 200  # diagnostic endpoint always 200
    body = r.json()
    assert body["status"] == "fail"
    foundry = next(c for c in body["checks"] if c["name"] == "foundry_iq")
    assert foundry["status"] == "fail"
    assert "AZURE_AI_PROJECT_ENDPOINT" in foundry["detail"]


@pytest.mark.asyncio
async def test_health_reports_fail_when_search_endpoint_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_AI_SEARCH_ENDPOINT"}
    app = _build_app(env, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
    body = r.json()
    assert body["status"] == "fail"
    search = next(c for c in body["checks"] if c["name"] == "search")
    assert search["status"] == "fail"


@pytest.mark.asyncio
async def test_health_skip_does_not_degrade_overall_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pgvector mode legitimately has no separate search service.

    `skip` must be neutral -- the overall status should still be
    `pass` so deployments don't permanently advertise as degraded.
    """
    env = {
        **{
            k: v
            for k, v in COSMOS_ENV.items()
            if k not in {
                "AZURE_DB_TYPE",
                "AZURE_COSMOS_ENDPOINT",
                "AZURE_INDEX_STORE",
                "AZURE_AI_SEARCH_ENDPOINT",
            }
        },
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_POSTGRES_ENDPOINT": "postgresql://pg-cwyd001.postgres.database.azure.com:5432/cwyd?sslmode=require",
    }
    app = _build_app(env, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
    body = r.json()
    assert body["status"] == "pass"
    names = {c["name"]: c["status"] for c in body["checks"]}
    assert names["search"] == "skip"
    assert names["database"] == "pass"
    assert names["foundry_iq"] == "pass"


@pytest.mark.asyncio
async def test_health_response_model_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(COSMOS_ENV, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
    body = r.json()
    assert set(body.keys()) == {"status", "version", "checks"}
    for check in body["checks"]:
        assert set(check.keys()) >= {"name", "status"}


# ---------------------------------------------------------------------------
# /api/health/ready -- readiness probe, 503 on fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ready_returns_200_when_all_checks_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app(COSMOS_ENV, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "pass"


@pytest.mark.asyncio
async def test_ready_returns_503_when_dependency_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_AI_PROJECT_ENDPOINT"}
    app = _build_app(env, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "fail"


# ---------------------------------------------------------------------------
# DI wiring smoke tests (task #14)
# ---------------------------------------------------------------------------


def test_get_app_settings_returns_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.dependencies import get_app_settings

    _set_env(monkeypatch, COSMOS_ENV)
    s = get_app_settings()
    assert isinstance(s, AppSettings)
    assert s.database.db_type == "cosmosdb"


def test_get_credential_provider_raises_when_lifespan_did_not_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DI now reads from app.state -- absence is a hard error."""
    from fastapi import Request

    _set_env(monkeypatch, COSMOS_ENV)
    app = create_app()
    fake_request = MagicMock(spec=Request)
    fake_request.app = app
    # app.state attribute was never populated by lifespan
    with pytest.raises(RuntimeError, match="lifespan did not run"):
        get_credential_provider(fake_request)


def test_get_llm_provider_raises_when_lifespan_did_not_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import Request

    _set_env(monkeypatch, COSMOS_ENV)
    app = create_app()
    fake_request = MagicMock(spec=Request)
    fake_request.app = app
    with pytest.raises(RuntimeError, match="lifespan did not run"):
        get_llm_provider(fake_request)


# ---------------------------------------------------------------------------
# Lifespan wiring (task #14 + D1 lifecycle fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_populates_app_state_and_closes_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end lifespan exercise with a stubbed credential provider.

    Confirms the lifespan in `backend/app.py` builds the credential and
    LLM provider once, stashes them on `app.state`, and calls
    `aclose()` / `close()` on shutdown so aiohttp transports don't
    leak.

    `httpx.ASGITransport` does not run the ASGI lifespan protocol, so
    we drive the lifespan context manager directly. This is also a
    truer unit test of `_lifespan` itself.
    """
    from backend.app import _lifespan

    _set_env(monkeypatch, COSMOS_ENV)

    fake_credential = MagicMock()
    fake_credential.close = AsyncMock()
    fake_cred_provider = MagicMock(spec=BaseCredentialProvider)
    fake_cred_provider.get_credential = AsyncMock(return_value=fake_credential)

    fake_llm_provider = MagicMock(spec=BaseLLMProvider)
    fake_llm_provider.aclose = AsyncMock()

    monkeypatch.setattr(
        "backend.app.credentials.create",
        lambda key, *, settings: fake_cred_provider,
    )
    monkeypatch.setattr(
        "backend.app.llm.create",
        lambda key, *, settings, credential: fake_llm_provider,
    )

    app = create_app()
    async with _lifespan(app):
        assert app.state.credential_provider is fake_cred_provider
        assert app.state.llm_provider is fake_llm_provider
        assert app.state.credential is fake_credential

    fake_llm_provider.aclose.assert_awaited_once()
    fake_credential.close.assert_awaited_once()
