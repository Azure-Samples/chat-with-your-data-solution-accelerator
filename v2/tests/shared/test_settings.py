"""Tests for `shared.settings` (Phase 2 task #10).

Pillar: Stable Core
Phase: 2
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.settings import AppSettings, get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


COSMOS_ENV: dict[str, str] = {
    # root
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_AI_SERVICE_LOCATION": "eastus2",
    # identity
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_UAMI_CLIENT_ID": "00000000-0000-0000-0000-000000000002",
    "AZURE_UAMI_PRINCIPAL_ID": "00000000-0000-0000-0000-000000000003",
    "AZURE_UAMI_RESOURCE_ID": "/subscriptions/x/resourceGroups/y/providers/.../id-cwyd001",
    # foundry
    "AZURE_AI_SERVICES_ENDPOINT": "https://ai-cwyd001.services.ai.azure.com/",
    "AZURE_AI_PROJECT_ENDPOINT": "https://ai-cwyd001.services.ai.azure.com/api/projects/proj",
    "AZURE_AI_AGENT_API_VERSION": "2025-05-01",
    # openai
    "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-4.1",
    "AZURE_OPENAI_REASONING_DEPLOYMENT": "o4-mini",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
    # database -- cosmosdb mode
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
    "AZURE_COSMOS_ACCOUNT_NAME": "cosmos-cwyd001",
    # search
    "AZURE_AI_SEARCH_ENDPOINT": "https://srch-cwyd001.search.windows.net",
    "AZURE_AI_SEARCH_NAME": "srch-cwyd001",
    # storage
    "AZURE_STORAGE_ACCOUNT_NAME": "stcwyd001",
    "AZURE_STORAGE_BLOB_ENDPOINT": "https://stcwyd001.blob.core.windows.net/",
    "AZURE_DOCUMENTS_CONTAINER": "documents",
    "AZURE_DOC_PROCESSING_QUEUE": "doc-processing",
    # network (always-on outputs)
    "AZURE_BACKEND_URL": "https://ca-back-cwyd001.example.azurecontainerapps.io",
    "AZURE_FRONTEND_URL": "https://app-front-cwyd001.azurewebsites.net",
    "AZURE_FUNCTION_APP_URL": "https://func-cwyd001.azurewebsites.net",
    "AZURE_FUNCTION_APP_NAME": "func-cwyd001",
}

POSTGRES_OVERRIDES: dict[str, str] = {
    "AZURE_DB_TYPE": "postgresql",
    "AZURE_INDEX_STORE": "pgvector",
    "AZURE_COSMOS_ENDPOINT": "",
    "AZURE_COSMOS_ACCOUNT_NAME": "",
    "AZURE_AI_SEARCH_ENDPOINT": "",
    "AZURE_AI_SEARCH_NAME": "",
    "AZURE_POSTGRES_ENDPOINT": "postgresql://psql-cwyd001.postgres.database.azure.com:5432/cwyd?sslmode=require",
    "AZURE_POSTGRES_HOST": "psql-cwyd001.postgres.database.azure.com",
    "AZURE_POSTGRES_NAME": "psql-cwyd001",
    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME": "alice@example.com",
}


def _set(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_loads_from_env_cosmosdb_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    settings = AppSettings()
    assert settings.solution_suffix == "cwyd001"
    assert settings.location == "eastus2"
    assert settings.identity.uami_client_id.endswith("000002")
    assert settings.foundry.project_endpoint.endswith("/projects/proj")
    assert settings.openai.gpt_deployment == "gpt-4.1"
    assert settings.database.db_type == "cosmosdb"
    assert settings.database.index_store == "AzureSearch"
    assert settings.database.cosmos_endpoint.startswith("https://cosmos-")
    assert settings.database.postgres_endpoint == ""
    assert settings.search.endpoint.startswith("https://srch-")
    assert settings.storage.documents_container == "documents"
    assert settings.network.backend_url.startswith("https://ca-back-")


def test_loads_from_env_postgresql_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, {**COSMOS_ENV, **POSTGRES_OVERRIDES})
    settings = AppSettings()
    assert settings.database.db_type == "postgresql"
    assert settings.database.index_store == "pgvector"
    assert settings.database.postgres_endpoint.startswith("postgresql://")
    assert settings.database.postgres_admin_principal_name == "alice@example.com"
    assert settings.database.cosmos_endpoint == ""
    assert settings.search.endpoint == ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_db_type_validation_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_DB_TYPE", "mongodb")
    with pytest.raises(ValidationError):
        AppSettings()


def test_orchestrator_default_is_langgraph(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    settings = AppSettings()
    assert settings.orchestrator.name == "langgraph"


def test_orchestrator_validation_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("CWYD_ORCHESTRATOR_NAME", "crewai")
    with pytest.raises(ValidationError):
        AppSettings()


def test_orchestrator_can_be_set_to_agent_framework(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("CWYD_ORCHESTRATOR_NAME", "agent_framework")
    settings = AppSettings()
    assert settings.orchestrator.name == "agent_framework"


def test_model_validator_cosmosdb_requires_cosmos_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_COSMOS_ENDPOINT", "")
    with pytest.raises(ValidationError, match="AZURE_COSMOS_ENDPOINT"):
        AppSettings()


def test_model_validator_postgresql_requires_postgres_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, {**COSMOS_ENV, **POSTGRES_OVERRIDES})
    monkeypatch.setenv("AZURE_POSTGRES_ENDPOINT", "")
    with pytest.raises(ValidationError, match="AZURE_POSTGRES_ENDPOINT"):
        AppSettings()


def test_model_validator_rejects_index_store_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_INDEX_STORE", "pgvector")
    with pytest.raises(ValidationError, match="AzureSearch"):
        AppSettings()


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    first = get_settings()
    second = get_settings()
    assert first is second


def test_get_settings_cache_clear_picks_up_new_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    first = get_settings()
    assert first.database.db_type == "cosmosdb"

    _set(monkeypatch, {**COSMOS_ENV, **POSTGRES_OVERRIDES})
    get_settings.cache_clear()
    second = get_settings()
    assert second.database.db_type == "postgresql"
    assert second is not first


# ---------------------------------------------------------------------------
# No Key Vault / no secrets
# ---------------------------------------------------------------------------


def test_no_secret_fields_anywhere() -> None:
    """No setting field name may suggest a secret/credential is stored."""
    forbidden_substrings = ("key_vault", "secret", "password", "api_key")
    for model in (AppSettings, *AppSettings.model_fields["identity"].annotation.__mro__):
        if not hasattr(model, "model_fields"):
            continue
        for field_name in model.model_fields:
            lowered = field_name.lower()
            for token in forbidden_substrings:
                assert token not in lowered, (
                    f"{model.__name__}.{field_name} looks secret-bearing "
                    f"(matched '{token}'); credentials must come from "
                    f"providers/credentials/, not settings."
                )


def test_observability_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)  # no AZURE_APP_INSIGHTS_CONNECTION_STRING
    settings = AppSettings()
    assert settings.observability.app_insights_connection_string == ""
    assert settings.observability.log_level == "INFO"
