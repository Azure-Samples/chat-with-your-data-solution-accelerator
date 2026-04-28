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
    """Stub credentials + llm so lifespan stays offline; let `search.create` run."""
    fake_credential = MagicMock(name="credential")
    fake_credential.close = AsyncMock()
    fake_cred_provider = MagicMock()
    fake_cred_provider.get_credential = AsyncMock(return_value=fake_credential)

    fake_llm = MagicMock(name="llm_provider")
    fake_llm.aclose = AsyncMock()

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
