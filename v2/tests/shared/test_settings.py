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
    """Selecting `agent_framework` no longer requires any agent-id env
    var. CU-009b (2026-05-05) removed the `OrchestratorSettings.agent_id`
    field per ADR 0008 -- the orchestrator resolves the Foundry agent
    lazily on first request via the registry-backed `agents` provider.
    Settings-load must succeed cleanly.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("CWYD_ORCHESTRATOR_NAME", "agent_framework")
    monkeypatch.delenv("AZURE_AI_AGENT_ID", raising=False)
    monkeypatch.delenv("CWYD_ORCHESTRATOR_AGENT_ID", raising=False)
    settings = AppSettings()
    assert settings.orchestrator.name == "agent_framework"


# ---------------------------------------------------------------------------
# CU-009b: agent_id removal (reversal of CU-001a)
# ---------------------------------------------------------------------------


def test_orchestrator_settings_no_agent_id_field() -> None:
    """`OrchestratorSettings` must NOT declare an `agent_id` field.

    CU-009b (2026-05-05) reversed CU-001a per ADR 0008
    (lazy-foundry-agent-bootstrap). Restoring the field here would
    re-introduce the dead-config drift the cleanup audit batch was
    opened to remove. Pin specific Foundry agents through the
    registry-backed `agents` provider (CU-010a), not via settings.
    """
    from shared.settings import OrchestratorSettings

    assert "agent_id" not in OrchestratorSettings.model_fields, (
        "OrchestratorSettings.agent_id must remain absent (CU-009b reversal "
        "of CU-001a). Foundry agent identity is now DB-backed via the agents "
        "provider; see ADR 0008."
    )


def test_agent_framework_loads_without_any_agent_id_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings-load under `agent_framework` must succeed even when both
    legacy env aliases are explicitly cleared. The previous
    cross-field validator (`_require_agent_id_for_agent_framework`,
    CU-001a) is gone; the runtime resolver in
    `agents.get_or_create_agent` (CU-010c) replaces it.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("CWYD_ORCHESTRATOR_NAME", "agent_framework")
    monkeypatch.delenv("AZURE_AI_AGENT_ID", raising=False)
    monkeypatch.delenv("CWYD_ORCHESTRATOR_AGENT_ID", raising=False)
    # No ValidationError expected.
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


# ---------------------------------------------------------------------------
# NetworkSettings.cors_origins (CU-002a)
# ---------------------------------------------------------------------------


def test_cors_origins_default_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.delenv("BACKEND_CORS_ORIGINS", raising=False)
    settings = AppSettings()
    assert settings.network.cors_origins == []


def test_cors_origins_parses_comma_separated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173, https://app.example.com ,http://127.0.0.1:5173",
    )
    settings = AppSettings()
    assert settings.network.cors_origins == [
        "http://localhost:5173",
        "https://app.example.com",
        "http://127.0.0.1:5173",
    ]


def test_cors_origins_parses_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(
        "BACKEND_CORS_ORIGINS",
        '["http://localhost:5173","https://app.example.com"]',
    )
    settings = AppSettings()
    assert settings.network.cors_origins == [
        "http://localhost:5173",
        "https://app.example.com",
    ]


def test_cors_origins_empty_string_yields_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "")
    settings = AppSettings()
    assert settings.network.cors_origins == []


# ---------------------------------------------------------------------------
# .env.sample consistency (CU-007 -> CU-008a relocation)
# ---------------------------------------------------------------------------


def _expected_env_var_names() -> set[str]:
    """Set of every env var consumed by AppSettings or its sub-models.

    Walks each `BaseSettings` sub-model in the AppSettings tree, takes
    its declared `env_prefix`, and prefixes every field name. Mirrors
    pydantic-settings' own resolution so the test can't drift from
    runtime behavior.
    """
    expected: set[str] = set()
    # Root AppSettings reads its own scalar fields under env_prefix=AZURE_
    root_prefix = AppSettings.model_config.get("env_prefix", "")
    for field_name, field_info in AppSettings.model_fields.items():
        # Skip composed sub-settings -- handled below.
        annotation = field_info.annotation
        if annotation is not None and hasattr(annotation, "model_config"):
            sub_prefix = annotation.model_config.get("env_prefix", "")
            for sub_field in annotation.model_fields:
                expected.add(f"{sub_prefix}{sub_field}".upper())
            continue
        expected.add(f"{root_prefix}{field_name}".upper())
    return expected


# Variables the example file is allowed to expose even though AppSettings
# does not consume them as typed fields today. Each entry must have a
# documented reason -- bare aliases are not allowed.
#
# Post-CU-002b + CU-001a, the only legitimate exemptions are:
#   - frontend-only env vars (Vite reads them, AppSettings does not);
#   - alias-only fields whose primary env var name does not derive from
#     `<env_prefix><field_name>` (the round-trip helper only walks the
#     prefix+field convention, so `validation_alias` paths must be
#     listed here explicitly).
_ENV_EXAMPLE_EXEMPTIONS: dict[str, str] = {
    # Frontend build-time variable read by Vite, not by AppSettings.
    "VITE_BACKEND_URL": "frontend (vite)",
    # Consumed by NetworkSettings.cors_origins via validation_alias
    # (CU-002a). The round-trip helper only walks env_prefix+field_name
    # so alias-based fields stay listed here as documented exemptions.
    "BACKEND_CORS_ORIGINS": (
        "NetworkSettings.cors_origins via validation_alias (CU-002a)"
    ),
    # CU-009b (2026-05-05) removed the previous AZURE_AI_AGENT_ID
    # exemption: the OrchestratorSettings.agent_id field that consumed
    # it via validation_alias was deleted per ADR 0008. Do not re-add
    # an exemption for an env var no settings field reads -- that's
    # exactly the dead-config drift this test guards against.
}


def test_env_sample_keys_round_trip_through_appsettings() -> None:
    """Every non-comment key in v2/.env.sample must be consumed by
    AppSettings (or be an explicitly documented exemption).

    Guards against the v1->v2 alias drift that CU-007 cleaned up. New
    keys added to the sample without a matching AppSettings field will
    fail this test loudly so the operator's `v2/.env` does not silently
    do nothing. Path moved from v2/docker/.env.dev.example to v2/.env.sample
    in CU-008a (single source of truth at v2/ root).
    """
    from pathlib import Path

    example = (
        Path(__file__).resolve().parents[2]
        / ".env.sample"
    )
    assert example.exists(), f"missing sample file: {example}"

    declared: set[str] = set()
    for raw_line in example.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            declared.add(key)

    expected = _expected_env_var_names()
    unknown: set[str] = set()
    for key in declared:
        if key in expected:
            continue
        if key in _ENV_EXAMPLE_EXEMPTIONS:
            continue
        unknown.add(key)

    assert not unknown, (
        "v2/.env.sample contains keys that AppSettings does not consume "
        "and that are not in the documented exemption list: "
        f"{sorted(unknown)}. Either add the field to shared/settings.py "
        "or document the exemption in _ENV_EXAMPLE_EXEMPTIONS with a "
        "reason."
    )
