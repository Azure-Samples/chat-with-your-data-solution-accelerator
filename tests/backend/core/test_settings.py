"""Tests for `shared.settings`."""

from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

import backend.core.settings as _settings_module
from backend.core import settings as settings_mod
from backend.core.settings import (
    AppSettings,
    ContentSafetySettings,
    DbType,
    DocumentIntelligenceSettings,
    IndexStore,
    IngestionTrigger,
    OrchestratorName,
    OrchestratorSettings,
    SpeechSettings,
    get_settings,
)

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
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-5.1",
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
    assert settings.openai.gpt_deployment == "gpt-5.1"
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


def test_search_knowledge_base_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, COSMOS_ENV)
    settings = AppSettings()
    assert settings.search.knowledge_base_name == "cwyd-kb"
    assert settings.search.knowledge_source_name == "cwyd-index-ks"
    assert settings.search.knowledge_base_api_version == "2025-11-01-preview"
    assert settings.search.connection_name == ""


def test_search_knowledge_base_env_override_beats_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(
        monkeypatch,
        {
            **COSMOS_ENV,
            "AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME": "kb-custom",
            "AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME": "ks-custom",
            "AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION": "2026-04-01",
            "AZURE_AI_SEARCH_CONNECTION_NAME": "search-conn-custom",
        },
    )
    settings = AppSettings()
    assert settings.search.knowledge_base_name == "kb-custom"
    assert settings.search.knowledge_source_name == "ks-custom"
    assert settings.search.knowledge_base_api_version == "2026-04-01"
    assert settings.search.connection_name == "search-conn-custom"


def test_ingestion_trigger_defaults_to_direct_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`StorageSettings.ingestion_trigger` defaults to `DIRECT_ENQUEUE` so
    local dev and any deploy without a storage Event Grid subscription keep
    the backend-side enqueue (no env var set in `COSMOS_ENV`).
    """
    _set(monkeypatch, COSMOS_ENV)
    settings = AppSettings()
    assert settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE


def test_ingestion_trigger_env_override_selects_event_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AZURE_INGESTION_TRIGGER=event_grid` flips the trigger to
    `EVENT_GRID`; the cloud deploy sets this once the `blob_event`
    queue trigger is live so the backend stops double-enqueueing.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_INGESTION_TRIGGER", "event_grid")
    settings = AppSettings()
    assert settings.storage.ingestion_trigger is IngestionTrigger.EVENT_GRID


def test_ingestion_trigger_rejects_unknown_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized `AZURE_INGESTION_TRIGGER` fails closed at load --
    the field is a hard `StrEnum` with no `str` arm (no registry dispatch
    on this value) per Hard Rule #11.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_INGESTION_TRIGGER", "kafka")
    with pytest.raises(ValidationError):
        AppSettings()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_db_type_validation_rejects_first_party_postgresql_without_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting the first-party `postgresql` key without the matching env
    coupling still fails at Pydantic load. Confirms Unit 3 carve-out did
    not silently weaken first-party validation.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_DB_TYPE", "postgresql")
    monkeypatch.setenv("AZURE_INDEX_STORE", "pgvector")
    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.parametrize(
    "third_party_key",
    ["mongodb", "dynamodb", "Cassandra-Custom"],
)
def test_db_type_accepts_third_party_registry_key(
    monkeypatch: pytest.MonkeyPatch,
    third_party_key: str,
) -> None:
    """Hard Rule #11 registry-driven carve-out: `DatabaseSettings.db_type`
    is typed `DbType | str` so a third-party-registered key flows through
    Pydantic validation unmodified. Dispatch-time validation moves to the
    registry boundary (`databases_registry.registry.get(...)`); first-party
    cosmos/postgres env-var coupling does not apply.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_DB_TYPE", third_party_key)
    settings = AppSettings()
    assert settings.database.db_type == third_party_key
    # Pydantic took the `str` arm of the union, not a coerced `DbType` member.
    assert not isinstance(settings.database.db_type, DbType)
    # The first-party mode-consistency check did not fire: cosmos_endpoint
    # is still populated from COSMOS_ENV but no AzureSearch coupling was
    # enforced because the key is third-party.
    assert settings.database.cosmos_endpoint.startswith("https://cosmos-")


@pytest.mark.parametrize(
    ("db_key", "index_key"),
    [
        ("mongodb", "mongodb_search"),
        ("dynamodb", "opensearch"),
        ("Cassandra-Custom", "Cassandra-Vector"),
    ],
)
def test_index_store_accepts_third_party_registry_key(
    monkeypatch: pytest.MonkeyPatch,
    db_key: str,
    index_key: str,
) -> None:
    """Hard Rule #11 registry-driven carve-out: `DatabaseSettings.index_store`
    is typed `IndexStore | str`. A third-party `index_store` paired with a
    third-party `db_type` flows through Pydantic unmodified; the validator's
    fall-through skips first-party env-var coupling. Dispatch-time validation
    moves to the `search_registry.registry.get(...)` boundary.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_DB_TYPE", db_key)
    monkeypatch.setenv("AZURE_INDEX_STORE", index_key)
    settings = AppSettings()
    assert settings.database.index_store == index_key
    # Pydantic took the `str` arm of the union, not a coerced `IndexStore` member.
    assert not isinstance(settings.database.index_store, IndexStore)


def test_index_store_validation_rejects_third_party_with_first_party_cosmos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A third-party `index_store` paired with first-party `db_type=cosmosdb`
    is rejected: the first-party branch still enforces
    `index_store == AzureSearch`. Third-party index stores only make sense
    when paired with a third-party `db_type` that skips the coupling check.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_INDEX_STORE", "mongodb_search")
    with pytest.raises(ValidationError):
        AppSettings()


def test_orchestrator_default_is_agent_framework(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cloud default orchestrator is `agent_framework` (ADR 0021),
    grounded by a Foundry IQ Knowledge Base over the Azure AI Search
    index. `COSMOS_ENV` is AzureSearch-backed, so the default pairing is
    valid; pgvector deployments must override to `langgraph` (ADR 0022).
    """
    _set(monkeypatch, COSMOS_ENV)
    settings = AppSettings()
    assert settings.orchestrator.name == OrchestratorName.AGENT_FRAMEWORK


def test_orchestrator_name_enum_pins_first_party_keys() -> None:
    """`OrchestratorName` is the StrEnum canonical home for the
    first-party orchestrator registry keys (Hard Rule #11 registry-
    driven carve-out). The field default is the enum member -- not a
    bare string -- so every internal comparison routes through it.
    """
    assert OrchestratorName.LANGGRAPH == "langgraph"
    assert OrchestratorName.AGENT_FRAMEWORK == "agent_framework"
    assert {member.value for member in OrchestratorName} == {
        "langgraph",
        "agent_framework",
    }
    assert (
        OrchestratorSettings.model_fields["name"].default
        is OrchestratorName.AGENT_FRAMEWORK
    )


@pytest.mark.parametrize(
    "third_party_key",
    ["crewai", "semantic-kernel-custom", "my_orchestrator"],
)
def test_orchestrator_accepts_third_party_registry_key(
    monkeypatch: pytest.MonkeyPatch,
    third_party_key: str,
) -> None:
    """Hard Rule #11 registry-driven carve-out: `OrchestratorSettings.name`
    is typed `OrchestratorName | str` so a third-party-registered
    orchestrator key flows through Pydantic unmodified via the `str`
    arm. Settings-time rejection of unknown keys is gone; dispatch-
    time validation moves to the registry boundary
    (`orchestrators_registry.registry.get(name)` raises `KeyError`
    listing every registered key).
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("CWYD_ORCHESTRATOR_NAME", third_party_key)
    settings = AppSettings()
    assert settings.orchestrator.name == third_party_key


def test_orchestrator_can_be_set_to_agent_framework(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting `agent_framework` no longer requires any agent-id env
    var. The `OrchestratorSettings.agent_id` field was removed per
    ADR 0008 -- the orchestrator resolves the Foundry agent lazily on
    first request via the registry-backed `agents` provider.
    Settings-load must succeed cleanly.
    """
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("CWYD_ORCHESTRATOR_NAME", "agent_framework")
    monkeypatch.delenv("AZURE_AI_AGENT_ID", raising=False)
    monkeypatch.delenv("CWYD_ORCHESTRATOR_AGENT_ID", raising=False)
    settings = AppSettings()
    assert settings.orchestrator.name == OrchestratorName.AGENT_FRAMEWORK


# ---------------------------------------------------------------------------
# agent_id removal
# ---------------------------------------------------------------------------


def test_orchestrator_settings_no_agent_id_field() -> None:
    """`OrchestratorSettings` must NOT declare an `agent_id` field.

    The field was reversed per ADR 0008
    (lazy-foundry-agent-bootstrap). Restoring it here would
    re-introduce the dead-config drift ADR 0008 removed. Pin
    specific Foundry agents through the registry-backed `agents`
    provider, not via settings.
    """
    assert "agent_id" not in OrchestratorSettings.model_fields, (
        "OrchestratorSettings.agent_id must remain absent. Foundry agent "
        "identity is now DB-backed via the agents "
        "provider; see ADR 0008."
    )


def test_agent_framework_loads_without_any_agent_id_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings-load under `agent_framework` must succeed even when both
    legacy env aliases are explicitly cleared. The previous
    cross-field validator (`_require_agent_id_for_agent_framework`)
    is gone; the runtime resolver in
    `agents.get_or_create_agent` replaces it.
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
    for model in (
        AppSettings,
        *AppSettings.model_fields["identity"].annotation.__mro__,
    ):
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
# OpenAISettings
# ---------------------------------------------------------------------------


def test_openai_embedding_dimensions_defaults_to_1536(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.delenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", raising=False)
    settings = AppSettings()
    # 1536 matches text-embedding-ada-002 / text-embedding-3-small and
    # the pgvector(N) literal hard-coded in the schema docstring.
    assert settings.openai.embedding_dimensions == 1536


def test_openai_embedding_dimensions_reads_env_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "3072")
    settings = AppSettings()
    assert settings.openai.embedding_dimensions == 3072


# ---------------------------------------------------------------------------
# SpeechSettings
# ---------------------------------------------------------------------------


def test_speech_settings_defaults_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    for key in (
        "AZURE_SPEECH_SERVICE_NAME",
        "AZURE_SPEECH_SERVICE_REGION",
        "AZURE_SPEECH_ACCOUNT_RESOURCE_ID",
        "AZURE_SPEECH_RECOGNIZER_LANGUAGES",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = AppSettings()
    assert settings.speech.service_name == ""
    assert settings.speech.service_region == ""
    assert settings.speech.account_resource_id == ""
    # v1 parity default -- documented in plan/business-cases.md (M5).
    assert settings.speech.recognizer_languages == "en-US,fr-FR,de-DE,it-IT"


def test_speech_settings_reads_env_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_SPEECH_SERVICE_NAME", "spch-cwyd001")
    monkeypatch.setenv("AZURE_SPEECH_SERVICE_REGION", "eastus2")
    monkeypatch.setenv(
        "AZURE_SPEECH_ACCOUNT_RESOURCE_ID",
        "/subscriptions/x/resourceGroups/y/providers/Microsoft.CognitiveServices/accounts/spch-cwyd001",
    )
    monkeypatch.setenv("AZURE_SPEECH_RECOGNIZER_LANGUAGES", "en-US,es-ES")
    settings = AppSettings()
    assert settings.speech.service_name == "spch-cwyd001"
    assert settings.speech.service_region == "eastus2"
    assert settings.speech.account_resource_id.endswith("/spch-cwyd001")
    assert settings.speech.recognizer_languages == "en-US,es-ES"


def test_speech_settings_no_subscription_key_field() -> None:
    """Hard Rule #2: Speech credentials come from UAMI/AAD, never from
    a stored subscription key. Guard against accidental re-introduction
    of the v1 `AZURE_SPEECH_KEY` pattern.
    """
    forbidden = ("key", "secret", "password")
    for field_name in SpeechSettings.model_fields:
        lowered = field_name.lower()
        for token in forbidden:
            assert token not in lowered, (
                f"SpeechSettings.{field_name} looks secret-bearing "
                f"(matched '{token}'); Speech tokens must be minted via "
                "AAD bearer through the credentials provider."
            )


# ---------------------------------------------------------------------------
# ContentSafetySettings
# ---------------------------------------------------------------------------


class _ContentSafetyEnvVar(StrEnum):
    """Sibling env-var names for `ContentSafetySettings` (Hard Rule #11).

    StrEnum -- members compare equal to their string values, so they
    drop straight into `monkeypatch.setenv` / `delenv` without `.value`.
    """

    ENDPOINT = "AZURE_CONTENT_SAFETY_ENDPOINT"
    ENABLED = "AZURE_CONTENT_SAFETY_ENABLED"
    SEVERITY_THRESHOLD = "AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD"


def test_content_safety_settings_defaults_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    for key in _ContentSafetyEnvVar:
        monkeypatch.delenv(key, raising=False)
    settings = AppSettings()
    assert settings.content_safety.endpoint == ""
    # Secure-by-default: the guard opts IN by default. With no endpoint
    # configured the lifespan still builds no client (the gate needs
    # both), so this default is inert until an endpoint is set.
    assert settings.content_safety.enabled is True
    # Azure Content Safety severity is 0/2/4/6; default trips on
    # `medium` (4) -- matches `ContentSafetyGuard.DEFAULT_SEVERITY_THRESHOLD`.
    assert settings.content_safety.severity_threshold == 4


def test_content_safety_settings_reads_env_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(
        _ContentSafetyEnvVar.ENDPOINT,
        "https://cs-cwyd001.cognitiveservices.azure.com/",
    )
    monkeypatch.setenv(_ContentSafetyEnvVar.ENABLED, "true")
    monkeypatch.setenv(_ContentSafetyEnvVar.SEVERITY_THRESHOLD, "6")
    settings = AppSettings()
    parsed = urlparse(settings.content_safety.endpoint)
    assert parsed.scheme == "https"
    assert parsed.hostname is not None
    assert parsed.hostname == "cognitiveservices.azure.com" or parsed.hostname.endswith(
        ".cognitiveservices.azure.com"
    )
    assert settings.content_safety.enabled is True
    assert settings.content_safety.severity_threshold == 6


@pytest.mark.parametrize("threshold", [0, 2, 4, 6, 7])
def test_content_safety_settings_accepts_in_range_threshold(
    monkeypatch: pytest.MonkeyPatch, threshold: int
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(_ContentSafetyEnvVar.SEVERITY_THRESHOLD, str(threshold))
    settings = AppSettings()
    assert settings.content_safety.severity_threshold == threshold


@pytest.mark.parametrize("threshold", [-1, 8, 999])
def test_content_safety_settings_rejects_out_of_range_threshold(
    monkeypatch: pytest.MonkeyPatch, threshold: int
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(_ContentSafetyEnvVar.SEVERITY_THRESHOLD, str(threshold))
    with pytest.raises(ValidationError):
        AppSettings()


def test_content_safety_settings_no_subscription_key_field() -> None:
    """Hard Rule #7 (no Key Vault for app secrets) + Hard Rule #4 (UAMI
    via credentials provider). Content Safety credentials come from
    AAD/UAMI bearer, never a stored subscription key.
    """
    forbidden = ("key", "secret", "password")
    for field_name in ContentSafetySettings.model_fields:
        lowered = field_name.lower()
        for token in forbidden:
            assert token not in lowered, (
                f"ContentSafetySettings.{field_name} looks secret-bearing "
                f"(matched '{token}'); Content Safety credentials must be "
                "minted via AAD bearer through the credentials provider."
            )


def test_content_safety_settings_in_app_settings_exports() -> None:
    """`ContentSafetySettings` must be re-exported alongside the other
    per-subsystem settings models so dependent modules can type-import it
    directly from `backend.core.settings`.
    """
    assert "ContentSafetySettings" in settings_mod.__all__
    assert settings_mod.ContentSafetySettings is not None


# ---------------------------------------------------------------------------
# DocumentIntelligenceSettings
# ---------------------------------------------------------------------------


class _DocIntelEnvVar(StrEnum):
    """Sibling env-var names for `DocumentIntelligenceSettings` (Hard Rule #11)."""

    API_VERSION = "AZURE_DOCUMENT_INTELLIGENCE_API_VERSION"
    MODEL_ID = "AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID"


def test_document_intelligence_settings_defaults_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    for key in _DocIntelEnvVar:
        monkeypatch.delenv(key, raising=False)
    settings = AppSettings()
    assert settings.document_intelligence.api_version == "2024-11-30"
    assert settings.document_intelligence.model_id == "prebuilt-layout"


def test_document_intelligence_settings_reads_env_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv(_DocIntelEnvVar.API_VERSION, "2024-07-31-preview")
    monkeypatch.setenv(_DocIntelEnvVar.MODEL_ID, "prebuilt-read")
    settings = AppSettings()
    assert settings.document_intelligence.api_version == "2024-07-31-preview"
    assert settings.document_intelligence.model_id == "prebuilt-read"


def test_document_intelligence_settings_no_endpoint_field() -> None:
    """Endpoint is intentionally derived from `FoundrySettings.services_endpoint`
    (unified AI Services account per `infra/main.bicep`) rather than a
    standalone env var. Guard against accidental re-introduction of an
    `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` field.
    """
    forbidden = ("endpoint", "url", "host")
    for field_name in DocumentIntelligenceSettings.model_fields:
        lowered = field_name.lower()
        for token in forbidden:
            assert token not in lowered, (
                f"DocumentIntelligenceSettings.{field_name} looks like a "
                f"standalone endpoint field; endpoint MUST derive from "
                f"FoundrySettings.services_endpoint per the unified AI "
                f"Services account in infra/main.bicep."
            )


def test_document_intelligence_settings_no_subscription_key_field() -> None:
    """Hard Rule #2 (UAMI via credentials provider) + Hard Rule #7 (no Key
    Vault for app secrets). Document Intelligence credentials must come
    from AAD/UAMI bearer, never a stored subscription key.
    """
    forbidden = ("key", "secret", "password")
    for field_name in DocumentIntelligenceSettings.model_fields:
        lowered = field_name.lower()
        for token in forbidden:
            assert token not in lowered, (
                f"DocumentIntelligenceSettings.{field_name} looks "
                f"secret-bearing (matched '{token}'); DI tokens must be "
                f"acquired via AAD bearer through the credentials provider."
            )


def test_document_intelligence_settings_in_app_settings_exports() -> None:
    """`DocumentIntelligenceSettings` must be re-exported alongside the
    other per-subsystem settings models so dependent modules can
    type-import it directly from `backend.core.settings`.
    """
    assert "DocumentIntelligenceSettings" in settings_mod.__all__
    assert settings_mod.DocumentIntelligenceSettings is not None


# ---------------------------------------------------------------------------
# NetworkSettings.cors_origins
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
# .env.sample consistency
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
# The only legitimate exemptions are:
#   - frontend-only env vars (Vite reads them, AppSettings does not);
#   - alias-only fields whose primary env var name does not derive from
#     `<env_prefix><field_name>` (the round-trip helper only walks the
#     prefix+field convention, so `validation_alias` paths must be
#     listed here explicitly).
_ENV_EXAMPLE_EXEMPTIONS: dict[str, str] = {
    # Frontend build-time variable read by Vite, not by AppSettings.
    "VITE_BACKEND_URL": "frontend (vite)",
    # Consumed by NetworkSettings.cors_origins via validation_alias.
    # The round-trip helper only walks env_prefix+field_name
    # so alias-based fields stay listed here as documented exemptions.
    "BACKEND_CORS_ORIGINS": ("NetworkSettings.cors_origins via validation_alias"),
    # The previous AZURE_AI_AGENT_ID
    # exemption was removed: the OrchestratorSettings.agent_id field that
    # consumed it via validation_alias was deleted per ADR 0008. Do not re-add
    # an exemption for an env var no settings field reads -- that's
    # exactly the dead-config drift this test guards against.
}


def test_env_sample_keys_round_trip_through_appsettings() -> None:
    """Every non-comment key in .env.sample must be consumed by
    AppSettings (or be an explicitly documented exemption).

    Guards against the v1->v2 alias drift. New keys added to the
    sample without a matching AppSettings field will fail this test
    loudly so the operator's `.env` does not silently do nothing.
    `.env.sample` is the single source of truth at the v2/ root,
    resolved via `parents[3]`.
    """
    example = Path(__file__).resolve().parents[3] / ".env.sample"
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
        ".env.sample contains keys that AppSettings does not consume "
        "and that are not in the documented exemption list: "
        f"{sorted(unknown)}. Either add the field to backend/core/settings.py "
        "or document the exemption in _ENV_EXAMPLE_EXEMPTIONS with a "
        "reason."
    )


# ---------------------------------------------------------------------------
# Environment StrEnum (Hard Rule #11 -- closed-set runtime-dispatch discriminator)
# ---------------------------------------------------------------------------
#
# `AppSettings.environment` is a closed two-value set ("local" / "production")
# that drives runtime branches in `backend.dependencies` (Easy Auth bypass)
# and `backend.routers.history` (user-id fallback). Per Hard Rule #11 the
# field type MUST be a `StrEnum` subclass so dispatch sites compare against
# enum members via `is`-identity rather than free-form string literals.


def test_environment_enum_is_strenum_subclass() -> None:
    """`Environment` is a StrEnum subclass so wire JSON shape is unchanged."""
    assert issubclass(_settings_module.Environment, StrEnum)
    assert issubclass(_settings_module.Environment, str)


@pytest.mark.parametrize(
    "member_name, expected_value",
    [
        ("LOCAL", "local"),
        ("PRODUCTION", "production"),
    ],
)
def test_environment_enum_member_values(member_name: str, expected_value: str) -> None:
    """Each member carries the lowercase string value used on the wire."""
    member = getattr(_settings_module.Environment, member_name)
    assert member.value == expected_value
    assert str(member) == expected_value


def test_environment_enum_has_exactly_two_members() -> None:
    """Frozen 2-member set -- adding a third value is a Hard Rule #11 change."""
    members = {m.name for m in _settings_module.Environment}
    assert members == {"LOCAL", "PRODUCTION"}


def test_environment_field_default_is_local_enum_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default flips from the Literal string `"local"` to `Environment.LOCAL`."""
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.delenv("AZURE_ENVIRONMENT", raising=False)
    settings = AppSettings()
    assert settings.environment is _settings_module.Environment.LOCAL


@pytest.mark.parametrize(
    "raw_value, expected_member",
    [
        ("local", "LOCAL"),
        ("production", "PRODUCTION"),
    ],
)
def test_environment_field_coerces_string_to_enum(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected_member: str,
) -> None:
    """Pydantic coerces wire string values into the StrEnum member."""
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_ENVIRONMENT", raw_value)

    settings = AppSettings()

    expected = getattr(_settings_module.Environment, expected_member)
    assert settings.environment is expected


def test_environment_field_rejects_unknown_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown environment string raises ValidationError (closed-set guard)."""
    _set(monkeypatch, COSMOS_ENV)
    monkeypatch.setenv("AZURE_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        AppSettings()


def test_environment_enum_is_exported_in_all() -> None:
    """`Environment` is part of the public surface of `backend.core.settings`."""
    assert "Environment" in _settings_module.__all__


def test_environment_members_distinct_by_identity() -> None:
    """LOCAL and PRODUCTION are distinct members -- `is`-dispatch is safe."""
    env = _settings_module.Environment
    assert env.LOCAL is not env.PRODUCTION
    # And both compare equal to their string value (StrEnum invariant)
    assert env.LOCAL == "local"
    assert env.PRODUCTION == "production"
