"""Tests for `backend.services.health` (health-probe diagnostic helpers).

Pillar: Stable Core
Phase: 7 (router cleanup -- health-probe diagnostic helpers)
"""

from types import SimpleNamespace
from typing import cast

import pytest

from backend.core.settings import AppSettings, get_settings
from backend.models.health import CheckStatus, DependencyCheck, HealthResponse, OverallStatus
from backend.services.health import _aggregate, _check_database, _check_foundry, _check_search, run_health_checks


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
def _clean_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key in list(COSMOS_ENV.keys()) + ["AZURE_POSTGRES_ENDPOINT", "AZURE_UAMI_CLIENT_ID"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> AppSettings:
    _set_env(monkeypatch, env)
    return AppSettings()


# ---------------------------------------------------------------------------
# _check_foundry
# ---------------------------------------------------------------------------


def test_check_foundry_passes_when_endpoints_set(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, COSMOS_ENV)
    result = _check_foundry(settings)
    assert result.name == "foundry_iq"
    assert result.status is CheckStatus.PASS


def test_check_foundry_fails_when_project_endpoint_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_AI_PROJECT_ENDPOINT"}
    settings = _settings(monkeypatch, env)
    result = _check_foundry(settings)
    assert result.status is CheckStatus.FAIL
    assert "AZURE_AI_PROJECT_ENDPOINT" in result.detail


def test_check_foundry_fails_when_gpt_deployment_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_OPENAI_GPT_DEPLOYMENT"}
    settings = _settings(monkeypatch, env)
    result = _check_foundry(settings)
    assert result.status is CheckStatus.FAIL
    assert "AZURE_OPENAI_GPT_DEPLOYMENT" in result.detail


# ---------------------------------------------------------------------------
# _check_database
# ---------------------------------------------------------------------------


def test_check_database_passes_for_cosmosdb(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, COSMOS_ENV)
    result = _check_database(settings)
    assert result.name == "database"
    assert result.status is CheckStatus.PASS
    assert "cosmosdb" in result.detail


def test_check_database_passes_for_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        **{k: v for k, v in COSMOS_ENV.items() if k not in {"AZURE_DB_TYPE", "AZURE_COSMOS_ENDPOINT", "AZURE_INDEX_STORE"}},
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_POSTGRES_ENDPOINT": "postgresql://pg-cwyd001.postgres.database.azure.com:5432/cwyd?sslmode=require",
    }
    settings = _settings(monkeypatch, env)
    result = _check_database(settings)
    assert result.status is CheckStatus.PASS
    assert "postgresql" in result.detail


def test_check_database_fails_when_endpoint_missing() -> None:
    """Defensive branch: `_check_database` returns FAIL when neither endpoint is configured.

    `AppSettings` validates that cosmos/postgres endpoints are present at
    construction time, so this branch can't be reached through real settings.
    Use a lightweight stub to exercise the helper's own logic.
    """
    stub = SimpleNamespace(
        database=SimpleNamespace(db_type="cosmosdb", cosmos_endpoint="", postgres_endpoint=""),
    )
    result = _check_database(cast(AppSettings, stub))
    assert result.status is CheckStatus.FAIL
    assert "cosmosdb" in result.detail


# ---------------------------------------------------------------------------
# _check_search
# ---------------------------------------------------------------------------


def test_check_search_passes_for_azure_search(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, COSMOS_ENV)
    result = _check_search(settings)
    assert result.name == "search"
    assert result.status is CheckStatus.PASS
    assert result.detail == "AzureSearch"


def test_check_search_fails_when_endpoint_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_AI_SEARCH_ENDPOINT"}
    settings = _settings(monkeypatch, env)
    result = _check_search(settings)
    assert result.status is CheckStatus.FAIL
    assert "AZURE_AI_SEARCH_ENDPOINT" in result.detail


def test_check_search_skips_for_pgvector(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        **{k: v for k, v in COSMOS_ENV.items() if k not in {"AZURE_DB_TYPE", "AZURE_COSMOS_ENDPOINT", "AZURE_INDEX_STORE", "AZURE_AI_SEARCH_ENDPOINT"}},
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_POSTGRES_ENDPOINT": "postgresql://pg-cwyd001.postgres.database.azure.com:5432/cwyd?sslmode=require",
    }
    settings = _settings(monkeypatch, env)
    result = _check_search(settings)
    assert result.status is CheckStatus.SKIP
    assert "pgvector" in result.detail


# ---------------------------------------------------------------------------
# _aggregate (re-tested in this module's home; tests/backend/test_health.py
# also covers it via its existing import.)
# ---------------------------------------------------------------------------


def test_aggregate_all_pass_returns_pass() -> None:
    checks = [
        DependencyCheck(name="a", status=CheckStatus.PASS),
        DependencyCheck(name="b", status=CheckStatus.PASS),
    ]
    assert _aggregate(checks) is OverallStatus.PASS


def test_aggregate_skip_is_neutral() -> None:
    checks = [
        DependencyCheck(name="a", status=CheckStatus.PASS),
        DependencyCheck(name="b", status=CheckStatus.SKIP),
    ]
    assert _aggregate(checks) is OverallStatus.PASS


def test_aggregate_any_fail_returns_fail() -> None:
    checks = [
        DependencyCheck(name="a", status=CheckStatus.PASS),
        DependencyCheck(name="b", status=CheckStatus.FAIL),
        DependencyCheck(name="c", status=CheckStatus.SKIP),
    ]
    assert _aggregate(checks) is OverallStatus.FAIL


# ---------------------------------------------------------------------------
# run_health_checks -- public surface, orchestrates the 4 privates
# ---------------------------------------------------------------------------


def test_run_health_checks_returns_health_response_with_all_three_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, COSMOS_ENV)
    result = run_health_checks(settings)
    assert isinstance(result, HealthResponse)
    assert result.status is OverallStatus.PASS
    names = {c.name for c in result.checks}
    assert names == {"foundry_iq", "database", "search"}


def test_run_health_checks_overall_fails_when_any_dependency_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {k: v for k, v in COSMOS_ENV.items() if k != "AZURE_AI_PROJECT_ENDPOINT"}
    settings = _settings(monkeypatch, env)
    result = run_health_checks(settings)
    assert result.status is OverallStatus.FAIL
    foundry = next(c for c in result.checks if c.name == "foundry_iq")
    assert foundry.status is CheckStatus.FAIL


def test_run_health_checks_overall_passes_when_search_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        **{k: v for k, v in COSMOS_ENV.items() if k not in {"AZURE_DB_TYPE", "AZURE_COSMOS_ENDPOINT", "AZURE_INDEX_STORE", "AZURE_AI_SEARCH_ENDPOINT"}},
        "AZURE_DB_TYPE": "postgresql",
        "AZURE_INDEX_STORE": "pgvector",
        "AZURE_POSTGRES_ENDPOINT": "postgresql://pg-cwyd001.postgres.database.azure.com:5432/cwyd?sslmode=require",
    }
    settings = _settings(monkeypatch, env)
    result = run_health_checks(settings)
    assert result.status is OverallStatus.PASS
    search = next(c for c in result.checks if c.name == "search")
    assert search.status is CheckStatus.SKIP
