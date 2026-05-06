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
    `agents` provider in `v2/src/shared/agents/` (CU-010a) -- not env.
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
_BACKEND_REQUIRED_ENVS = (
    "AZURE_DB_TYPE",
    "AZURE_INDEX_STORE",
    "AZURE_COSMOS_ENDPOINT",
    "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_POSTGRES_ENDPOINT",
    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME",
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
# the same routing flags + the active-mode endpoint(s). It does NOT need
# `AZURE_COSMOS_ENDPOINT` (no chat-history writes from the function host).
_FUNCTION_REQUIRED_ENVS = (
    "AZURE_DB_TYPE",
    "AZURE_INDEX_STORE",
    "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_POSTGRES_ENDPOINT",
    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME",
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
