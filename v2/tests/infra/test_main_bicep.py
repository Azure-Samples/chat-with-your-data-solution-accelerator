"""Pillar: Stable Core / Phase: Cleanup audit batch 2 (CU-009a) — Bicep regression tests.

The full Bicep contract is validated by `az bicep build` (run as the
last step of CU-009a); these grep-style guards catch *symbol-level*
regressions fast (no Bicep CLI required) so a stray rename, copy-paste
revert, or AI-generated "helpful" re-add can't silently re-introduce
the env-only agent-id path.

CU-009a (2026-05-05) reversed CU-001e: per ADR 0008
(lazy-foundry-agent-bootstrap), the Foundry agent id is no longer an
operator-supplied env value. Agent identity is resolved lazily on
first request and persisted in the chat-history DB. Both the
`azureAiAgentId` Bicep parameter and the `AZURE_AI_AGENT_ID`
container-app env binding **must remain absent**; restoring either
re-creates the dead-config drift CU-008..CU-012 was opened to remove.
"""

from pathlib import Path

import pytest


_BICEP = (
    Path(__file__).resolve().parents[2] / "infra" / "main.bicep"
)


@pytest.fixture(scope="module")
def bicep_text() -> str:
    return _BICEP.read_text(encoding="utf-8")


def test_bicep_does_not_declare_azure_ai_agent_id_param(bicep_text: str) -> None:
    """`azureAiAgentId` must NOT be declared as a Bicep parameter.

    Per ADR 0008 (lazy-foundry-agent-bootstrap), agent identity is
    resolved lazily on first request and persisted in the chat-history
    DB. Re-adding this parameter would re-introduce the dead-config
    path CU-009a was opened to remove. If you genuinely need to pin a
    specific agent post-deployment, use the registry-backed
    `agents` provider in `v2/src/backend/core/agents/` (CU-010a) -- not env.
    """
    assert "azureAiAgentId" not in bicep_text, (
        "azureAiAgentId Bicep param must remain absent (CU-009a reversal of "
        "CU-001e). Agent identity is now DB-backed; see ADR 0008. To pin a "
        "specific agent, use the registry-backed agents provider, not env."
    )


def test_backend_container_env_does_not_expose_agent_id(bicep_text: str) -> None:
    """The backend Container App must NOT expose `AZURE_AI_AGENT_ID`.

    CU-009a (2026-05-05) removed this env binding. The runtime resolves
    CWYD + RAI agent ids lazily on first request and caches them in the
    chat-history DB. A literal `AZURE_AI_AGENT_ID` in the container-app
    env collection would let operators set a value that the runtime
    silently ignores -- exactly the dead-config drift this CU removes.
    """
    assert "'AZURE_AI_AGENT_ID'" not in bicep_text, (
        "AZURE_AI_AGENT_ID env binding must remain absent (CU-009a reversal "
        "of CU-001e). Agent identity is now DB-backed; see ADR 0008."
    )
    assert "AZURE_AI_AGENT_ID" not in bicep_text, (
        "AZURE_AI_AGENT_ID must not appear anywhere in main.bicep -- not as "
        "an env var, not in a comment that suggests operators should set it. "
        "Use the registry-backed agents provider instead (CU-010a)."
    )


# ---------------------------------------------------------------------------
# Phase 4 hardening (#32d): backend ACA + Function App env-binding drift guard.
#
# The Phase 4 outputs (`AZURE_COSMOS_ENDPOINT`, `AZURE_POSTGRES_ENDPOINT`,
# `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_INDEX_STORE`,
# `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME`) are emitted at the module-output
# layer (lines ~1606-1661) but were NEVER bound onto the running container
# `env:` arrays. Without these bindings the backend lifespan crashes at
# `databases.create("cosmosdb", ...)` because `cfg.cosmos_endpoint` stays
# empty (`DatabaseSettings._enforce_mode_consistency` raises). Hard Rule #8:
# `azd up` must succeed at the end of every phase. This guard pins both
# bindings so a future copy-paste revert can't silently re-introduce the gap.
# ---------------------------------------------------------------------------


def _slice_module(text: str, start_marker: str, end_marker: str) -> str:
    """Return the substring between `start_marker` and `end_marker`.

    Both markers must appear exactly once after the slice start; the
    slice is half-open (`start..end`) so the caller can search inside
    a single Bicep `module ... { ... }` declaration without false
    positives from sibling modules.
    """
    start = text.find(start_marker)
    assert start != -1, f"start marker {start_marker!r} not found in main.bicep"
    end = text.find(end_marker, start + len(start_marker))
    assert end != -1, (
        f"end marker {end_marker!r} not found after {start_marker!r} -- "
        "the bicep layout has changed; update the slice markers."
    )
    return text[start:end]


@pytest.fixture(scope="module")
def backend_aca_slice(bicep_text: str) -> str:
    """Bicep source between `module backendContainerApp` and the next module."""
    return _slice_module(
        bicep_text,
        "module backendContainerApp ",
        "module appServicePlan ",
    )


@pytest.fixture(scope="module")
def function_app_slice(bicep_text: str) -> str:
    """Bicep source between `module functionApp` and the trailing role-assignment block."""
    return _slice_module(
        bicep_text,
        "module functionApp ",
        # Sentinel comment immediately after the module's closing brace.
        "// Function App needs Storage Blob",
    )


# Backend reads chat history (cosmos OR postgres) AND search (AzureSearch
# OR pgvector). Both endpoint vars per database mode are bound
# unconditionally so a single image can target either deployment without
# rebuild; the Bicep outputs return empty strings in the inactive mode.
# AZURE_UAMI_CLIENT_ID is bound alongside AZURE_CLIENT_ID so the
# credentials provider's select_default() resolves managed_identity (not
# cli) at lifespan startup; without it the AAD chain falls back to az-cli
# inside the container and crashes with CLI_NOT_FOUND.
_BACKEND_REQUIRED_ENVS = (
    "AZURE_DB_TYPE",
    "AZURE_INDEX_STORE",
    "AZURE_COSMOS_ENDPOINT",
    "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_POSTGRES_ENDPOINT",
    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME",
    "AZURE_UAMI_CLIENT_ID",
)


@pytest.mark.parametrize("env_name", _BACKEND_REQUIRED_ENVS)
def test_backend_aca_env_block_binds_required_phase4_settings(
    backend_aca_slice: str, env_name: str
) -> None:
    """Backend ACA `env:` array must bind every Phase 4 setting `AppSettings` reads.

    Without these bindings, `DatabaseSettings._enforce_mode_consistency`
    raises at lifespan startup. Hard Rule #8 (every phase ends green --
    `azd up` must succeed) is the binding constraint. The output values
    themselves already exist (Phase 4 task #34); this guard pins the
    container-app side of the wire so the two halves of the contract
    can't drift.
    """
    assert f"'{env_name}'" in backend_aca_slice, (
        f"{env_name} missing from backend Container App env block. "
        "Add it to the backend ACA `env: union([...])` array in main.bicep "
        "so AppSettings can populate it at runtime. The Phase 4 output of "
        "the same name already exists (lines ~1606-1661); only the "
        "container-app binding is missing."
    )


# Function app runs the indexing pipeline (Phase 6). It writes vectors to
# AzureSearch (cosmosdb mode) OR pgvector (postgresql mode), so it needs
# the same routing flags + the active-mode endpoint(s). `AZURE_COSMOS_ENDPOINT`
# is also bound because `DatabaseSettings._enforce_mode_consistency`
# cross-validates `AZURE_DB_TYPE=cosmosdb` against a non-empty endpoint at
# `AppSettings()` construction time -- the function worker fails to start
# (Pydantic `ValidationError` during settings load) otherwise, even though
# the function host performs no chat-history writes.
_FUNCTION_REQUIRED_ENVS = (
    "AZURE_DB_TYPE",
    "AZURE_INDEX_STORE",
    "AZURE_COSMOS_ENDPOINT",
    "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_POSTGRES_ENDPOINT",
    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME",
    "AZURE_UAMI_CLIENT_ID",
)


@pytest.mark.parametrize("env_name", _FUNCTION_REQUIRED_ENVS)
def test_function_app_settings_bind_required_phase4_settings(
    function_app_slice: str, env_name: str
) -> None:
    """Function App `appSettings` must bind every Phase 4 setting the indexing pipeline reads.

    Same rationale as the backend test -- the function host writes
    vectors to AzureSearch (cosmosdb mode) or pgvector (postgresql
    mode), so both endpoint vars need binding even though only one
    carries a non-empty value at deploy time.
    """
    assert f"'{env_name}'" in function_app_slice, (
        f"{env_name} missing from Function App appSettings block. "
        "Add it to the function `appSettings: union([...])` array in "
        "main.bicep so the indexing pipeline can populate it at runtime."
    )


# ---------------------------------------------------------------------------
# ADR-0018: Monitoring Metrics Publisher RBAC for UAMI on AppI.
#
# The `applicationInsights` AVM module is created with
# `disableLocalAuth: true`, so ingestion authenticates via Entra. Without
# `Monitoring Metrics Publisher` granted to the UAMI, every telemetry
# write from the backend container app + function app silently 401s and
# telemetry vanishes from AppI -- exactly the observability gap
# ADR-0018 closes.
#
# The role assignment lives inline on the AVM module's `roleAssignments`
# param (mirrors the aiServices pattern at ~line 552) so it inherits the
# same `if (enableMonitoring)` gate as the AppI module itself; a sibling
# top-level resource would either always deploy or need a duplicated gate.
# ---------------------------------------------------------------------------

_MONITORING_METRICS_PUBLISHER_ROLE_NAME = "Monitoring Metrics Publisher"


@pytest.fixture(scope="module")
def application_insights_slice(bicep_text: str) -> str:
    """Bicep source between `module applicationInsights` and the next section."""
    return _slice_module(
        bicep_text,
        "module applicationInsights ",
        "// Virtual network ",
    )


def test_application_insights_grants_metrics_publisher_to_uami(
    application_insights_slice: str,
) -> None:
    """The AppI module must grant `Monitoring Metrics Publisher` to the UAMI (ADR-0018)."""
    assert "roleAssignments:" in application_insights_slice, (
        "applicationInsights AVM module must declare a `roleAssignments` "
        "param granting the UAMI ingestion permission. AppI is created "
        "with disableLocalAuth=true, so without this role telemetry "
        "silently 401s -- the observability gap ADR-0018 closes."
    )
    assert _MONITORING_METRICS_PUBLISHER_ROLE_NAME in application_insights_slice, (
        "applicationInsights roleAssignments must reference "
        f"'{_MONITORING_METRICS_PUBLISHER_ROLE_NAME}' (AVM resolves the "
        "built-in role name) per ADR-0018."
    )
    assert (
        "userAssignedIdentity.outputs.principalId" in application_insights_slice
    ), (
        "applicationInsights roleAssignments must use "
        "`userAssignedIdentity.outputs.principalId` so the workload UAMI "
        "(not the system MI, not a fixed principal) is the grantee."
    )


# ADR-0018 drift-guard pair: backend + function env blocks must wire
# `APPLICATIONINSIGHTS_CONNECTION_STRING` from the AppI module output, so
# the OpenTelemetry exporter inside each workload knows where to send
# telemetry. The env entry lives inside an `enableMonitoring ? [...] : []`
# ternary so it stays absent in non-monitoring builds (no SDK auto-init
# against an empty string); the drift-guard fires on the static Bicep
# source text and so is flag-agnostic.
@pytest.mark.parametrize(
    "slice_fixture",
    ["backend_aca_slice", "function_app_slice"],
)
def test_appinsights_connection_string_bound_to_workload(
    slice_fixture: str, request: pytest.FixtureRequest
) -> None:
    """Backend + function env blocks must wire APPLICATIONINSIGHTS_CONNECTION_STRING (ADR-0018)."""
    module_slice: str = request.getfixturevalue(slice_fixture)
    assert "'APPLICATIONINSIGHTS_CONNECTION_STRING'" in module_slice, (
        f"APPLICATIONINSIGHTS_CONNECTION_STRING missing from {slice_fixture}. "
        "Wire it inside an `enableMonitoring ? [...] : []` ternary sourced "
        "from `applicationInsights!.outputs.connectionString` so the "
        "workload OpenTelemetry exporter knows where to ingest telemetry "
        "(ADR-0018)."
    )
    assert "applicationInsights!.outputs.connectionString" in module_slice, (
        f"{slice_fixture} must source the AppI connection string from "
        "`applicationInsights!.outputs.connectionString` (Bicep output), "
        "not a hand-set secret or runtime `az config appsettings set` "
        "patch (Hard Rule #7 + ADR-0018)."
    )
