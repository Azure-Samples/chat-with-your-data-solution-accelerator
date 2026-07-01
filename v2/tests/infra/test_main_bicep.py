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
    """Bicep source between `module backendContainerApp` and the frontend Container App module."""
    return _slice_module(
        bicep_text,
        "module backendContainerApp ",
        # The frontend App Service + appServicePlan were replaced by the
        # frontend Container App (Phase 1), which is the next module after
        # the backend Container App.
        "module frontendContainerApp ",
    )


@pytest.fixture(scope="module")
def function_app_slice(bicep_text: str) -> str:
    """Bicep source spanning the raw `functionContainerApp` resource.

    The Flex Consumption `functionApp`/`functionPlan` AVM modules were
    replaced (Phase 2) by a raw
    `Microsoft.App/containerApps@... kind: 'functionapp'` resource
    (`functionContainerApp`). The slice runs from that resource to the
    next resource declaration (`storageAccountExisting`), so it covers
    the function's `env:` + `scale:` blocks without spilling into sibling
    resources.
    """
    return _slice_module(
        bicep_text,
        "resource functionContainerApp ",
        "resource storageAccountExisting ",
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


def test_function_container_app_stays_warm_for_queue_consumers(
    function_app_slice: str,
) -> None:
    """The function Container App must keep `minReplicas: 1` (warm).

    The Flex Consumption plan (with its `alwaysReady` set) was replaced
    (Phase 2) by a raw `functionContainerApp` (`kind: 'functionapp'`) on
    the shared Container Apps Environment. The queue consumers --
    `batch_push` on `doc-processing` and `blob_event` on `blob-events` --
    carry the same scale-from-zero loss BUG-0053 fixed: the first
    BlobCreated event after the app idles to zero would be dropped before
    a host instance spins up to drain the queue. `minReplicas: 1` on the
    container app `scale` block is the Container Apps equivalent of the
    former Flex always-ready instance, so it must stay pinned to 1 (never
    `enableScalability ? 1 : 0`).
    """
    assert "minReplicas: 1" in function_app_slice, (
        "minReplicas: 1 missing from the functionContainerApp `scale` block "
        "in main.bicep. The function hosts the batch_push + blob_event queue "
        "consumers; without a warm instance the first queue message after "
        "idle-to-zero is dropped (BUG-0053). Keep `minReplicas: 1` (not "
        "`enableScalability ? 1 : 0`) so the queue triggers stay warm."
    )


def test_bicep_uses_container_apps_not_flex_or_appservice(bicep_text: str) -> None:
    """The frontend App Service + Flex Function App were replaced by Container Apps.

    Phase 1 replaced the frontend App Service (+ `appServicePlan`) with the
    `frontendContainerApp` module; Phase 2 replaced the Flex Consumption
    `functionApp`/`functionPlan` with the raw `functionContainerApp`
    (`kind: 'functionapp'`). Re-adding either removed module would revert to
    a hosting model that cannot run the ACR-built container images.
    """
    # Removed hosting resources must stay gone.
    assert "module appServicePlan " not in bicep_text, (
        "module appServicePlan re-introduced in main.bicep. The frontend "
        "App Service was replaced by the frontendContainerApp Container App "
        "(Phase 1); an App Service plan cannot host the ACR-built frontend "
        "image."
    )
    assert "module functionApp " not in bicep_text, (
        "module functionApp re-introduced in main.bicep. The Flex Consumption "
        "Function App was replaced by the raw functionContainerApp "
        "(kind: 'functionapp') on the shared Container Apps Environment "
        "(Phase 2)."
    )
    # New container-hosted resources must exist.
    assert "module frontendContainerApp " in bicep_text, (
        "frontendContainerApp module missing from main.bicep. The frontend "
        "must run as an ACR-built Container App on the shared environment."
    )
    assert "resource functionContainerApp " in bicep_text, (
        "functionContainerApp resource missing from main.bicep. The function "
        "must run as an ACR-built Functions-on-ACA resource."
    )
    assert "kind: 'functionapp'" in bicep_text, (
        "functionContainerApp must declare `kind: 'functionapp'` so the "
        "Container Apps runtime hosts it as an Azure Functions app."
    )


def test_blob_event_subscription_targets_blob_events_queue(bicep_text: str) -> None:
    """The Event Grid blob subscription must deliver to the `blob-events`
    queue (via `blobEventsQueueName`), never raw `doc-processing`.

    This is the exact regression that defined BUG-0054: if the
    subscription destination is repointed to `doc-processing`, the
    backend admin upload AND the Event Grid fan-out both enqueue the
    same document, double-ingesting every uploaded blob. The
    `blob_event` queue trigger exists precisely to translate BlobCreated
    into a single `doc-processing` envelope (and BlobDeleted into a
    de-index), so the subscription must land on `blob-events` and let
    the trigger own the hand-off (ADR 0028).
    """
    blob_events_pins = bicep_text.count("queueName: blobEventsQueueName")
    assert blob_events_pins == 2, (
        "Both Event Grid blob subscriptions (the new-topic path and the "
        "existing-topic reuse path) must pin their destination to "
        f"blobEventsQueueName ('blob-events') in main.bicep; found "
        f"{blob_events_pins} of 2. Repointing *either* subscription off "
        "blob-events re-creates the BUG-0054 double-ingest: the backend "
        "upload and the Event Grid fan-out would both enqueue the same "
        "document."
    )
    assert "queueName: docProcessingQueueName" not in bicep_text, (
        "An Event Grid blob subscription destination is pointed at "
        "doc-processing in main.bicep. That is the exact BUG-0054 "
        "regression: the subscription must land on blob-events and let "
        "the blob_event trigger own the single doc-processing hand-off "
        "(ADR 0028), never enqueue doc-processing directly."
    )
    for event_type in (
        "'Microsoft.Storage.BlobCreated'",
        "'Microsoft.Storage.BlobDeleted'",
    ):
        assert event_type in bicep_text, (
            f"{event_type} missing from the Event Grid subscription "
            "includedEventTypes filter in main.bicep. Both BlobCreated and "
            "BlobDeleted must fan out to blob-events so the blob_event "
            "trigger can ingest creates and de-index deletes."
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


# ADR-0018 drift-guard pair: backend + function env blocks must wire the
# AppI connection string from the AppI module output, so the telemetry
# exporter inside each workload knows where to send telemetry. The env
# entry lives inside an `enableMonitoring ? [...] : []` ternary so it stays
# absent in non-monitoring builds (no SDK auto-init against an empty
# string); the drift-guard fires on the static Bicep source text and so is
# flag-agnostic.
#
# The two workloads bind DIFFERENT env-var names on purpose (BUG-0055):
#   - Backend ACA is a plain container with no host-level App Insights
#     agent. Its Python lifespan calls `configure_azure_monitor` with the
#     connection string read from the AZURE_-prefixed typed setting
#     (`ObservabilitySettings`, `env_prefix="AZURE_"`), so the container
#     must receive `AZURE_APP_INSIGHTS_CONNECTION_STRING`. The standard
#     name was wired here originally and the typed setting stayed empty, so
#     telemetry never initialized in the cloud.
#   - The Function host reads the standard `APPLICATIONINSIGHTS_CONNECTION_STRING`
#     natively, so the function app keeps that name.
@pytest.mark.parametrize(
    "slice_fixture,expected_env_name",
    [
        ("backend_aca_slice", "AZURE_APP_INSIGHTS_CONNECTION_STRING"),
        ("function_app_slice", "APPLICATIONINSIGHTS_CONNECTION_STRING"),
    ],
)
def test_appinsights_connection_string_bound_to_workload(
    slice_fixture: str, expected_env_name: str, request: pytest.FixtureRequest
) -> None:
    """Backend wires the typed name; function wires the standard name (ADR-0018, BUG-0055)."""
    module_slice: str = request.getfixturevalue(slice_fixture)
    assert f"'{expected_env_name}'" in module_slice, (
        f"{expected_env_name} missing from {slice_fixture}. "
        "Wire it inside an `enableMonitoring ? [...] : []` ternary sourced "
        "from `applicationInsights!.outputs.connectionString` so the "
        "workload telemetry exporter knows where to ingest telemetry "
        "(ADR-0018, BUG-0055)."
    )
    assert "applicationInsights!.outputs.connectionString" in module_slice, (
        f"{slice_fixture} must source the AppI connection string from "
        "`applicationInsights!.outputs.connectionString` (Bicep output), "
        "not a hand-set secret or runtime `az config appsettings set` "
        "patch (Hard Rule #7 + ADR-0018)."
    )


# ---------------------------------------------------------------------------
# Phase 8 (agent_framework default + Foundry IQ Knowledge Base): KB wiring.
#
# The agent_framework orchestrator grounds on a Foundry IQ knowledge base
# resolved by name through the Project-Search connection. main.bicep must
# (a) pass `knowledgeBaseName` into the `aiProjectSearchConnection` module,
# (b) bind the KB name/source/api-version onto the backend Container App
# `env:` array so the agent can build the Search MCP retrieval URL, and
# (c) emit the same three values as outputs so the azd postprovision hook
# (post_provision.py) seeds a knowledge base whose names match what the
# backend reads. The api-version is operator-tunable, so it must reach the
# container as an env var rather than a baked-in URL.
# ---------------------------------------------------------------------------

_BACKEND_KB_ENVS = (
    "AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME",
    "AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME",
    "AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION",
)


@pytest.mark.parametrize("env_name", _BACKEND_KB_ENVS)
def test_backend_aca_env_block_binds_knowledge_base_settings(
    backend_aca_slice: str, env_name: str
) -> None:
    """Backend ACA `env:` array must bind every Foundry IQ KB setting.

    `SearchSettings` (env_prefix AZURE_AI_SEARCH_) reads these to resolve
    and query the Foundry IQ knowledge base for the agent_framework
    orchestrator. The api-version is operator-tunable (Phase 8 / ADR 0021),
    so it must reach the container as an env var, not a baked-in URL.
    """
    assert f"'{env_name}'" in backend_aca_slice, (
        f"{env_name} missing from backend Container App env block. Add it "
        "to the backend ACA `env: union([...])` array in main.bicep so "
        "SearchSettings can populate it; the agent_framework orchestrator "
        "needs it to resolve and query the Foundry IQ knowledge base."
    )


def test_search_connection_module_receives_knowledge_base_name(
    bicep_text: str,
) -> None:
    """The `aiProjectSearchConnection` module call must pass `knowledgeBaseName`.

    The module records the KB the agent resolves through the
    Project-Search connection. Without the pass-through the module falls
    back to its own default and an operator's `searchKnowledgeBaseName`
    override never reaches the connection metadata.
    """
    module_call = _slice_module(
        bicep_text,
        "module aiProjectSearchConnection ",
        "// Storage account. Triple-purpose",
    )
    assert "knowledgeBaseName: searchKnowledgeBaseName" in module_call, (
        "aiProjectSearchConnection module call must pass "
        "`knowledgeBaseName: searchKnowledgeBaseName` so the Project-Search "
        "connection records the KB the agent_framework orchestrator resolves."
    )


@pytest.mark.parametrize("output_name", _BACKEND_KB_ENVS)
def test_main_bicep_outputs_knowledge_base_settings(
    bicep_text: str, output_name: str
) -> None:
    """main.bicep must emit each KB setting as an output for post_provision.py.

    post_provision.py (the azd postprovision hook) seeds the knowledge
    source + knowledge base from these azd-env values. Emitting them keeps
    the seeded names / api-version in lock-step with what the backend
    container reads, so an operator override flows to both halves.
    """
    assert f"output {output_name} string =" in bicep_text, (
        f"{output_name} output missing from main.bicep. Emit it so the azd "
        "postprovision hook (post_provision.py) seeds a Foundry IQ knowledge "
        "base / knowledge source whose names match what the backend reads."
    )


def test_search_service_location_param_declared(bicep_text: str) -> None:
    """`searchServiceLocation` must be an optional, empty-default param.

    The empty default co-locates Azure AI Search with `location`
    (backward compatible). An operator sets it to a different region
    when the primary region returns `InsufficientResourcesAvailable`
    for Azure AI Search. Renaming or dropping it removes the only knob
    that unblocks a capacity-constrained primary region.
    """
    assert "param searchServiceLocation string = ''" in bicep_text, (
        "searchServiceLocation must be declared as `param searchServiceLocation "
        "string = ''` (optional, empty default). It lets an operator place "
        "Azure AI Search in a capacity region when the primary region is full."
    )


def test_search_service_location_has_location_fallback(bicep_text: str) -> None:
    """The effective search location must fall back to `location` when empty.

    `effectiveSearchLocation = empty(searchServiceLocation) ? location :
    searchServiceLocation` keeps the default deploy single-region; only an
    explicit override moves Search. Losing the ternary would force the
    operator to always supply a region.
    """
    assert (
        "var effectiveSearchLocation = empty(searchServiceLocation) "
        "? location : searchServiceLocation" in bicep_text
    ), (
        "effectiveSearchLocation must be `empty(searchServiceLocation) ? "
        "location : searchServiceLocation` so an empty override co-locates "
        "Search with the non-AI resources."
    )


def test_ai_search_module_binds_effective_location(bicep_text: str) -> None:
    """The `aiSearch` module must bind `location: effectiveSearchLocation`.

    Binding the raw `location` param instead would ignore the
    `searchServiceLocation` override and keep deploying Search into the
    capacity-constrained primary region.
    """
    aisearch_module = _slice_module(
        bicep_text,
        "module aiSearch ",
        "module aiProjectSearchConnection ",
    )
    assert "location: effectiveSearchLocation" in aisearch_module, (
        "aiSearch module must bind `location: effectiveSearchLocation` so the "
        "searchServiceLocation override takes effect."
    )
    assert "location: location" not in aisearch_module, (
        "aiSearch module must not bind the raw `location` param -- that ignores "
        "the searchServiceLocation override."
    )


# ---------------------------------------------------------------------------
# Deployer storage data-plane RBAC.
#
# The post-deploy seed hook uploads sample documents and enqueues
# doc-processing messages while running locally under the deployer
# identity (DefaultAzureCredential), not the workload UAMI. main.bicep
# must therefore grant the deployer Storage Blob Data Contributor and
# Storage Queue Data Message Sender on the storage account, in addition
# to the UAMI grants the running workloads use.
# ---------------------------------------------------------------------------

_STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
_STORAGE_QUEUE_DATA_MESSAGE_SENDER_ROLE_ID = "c6a89b2d-59bc-44d0-9896-0f6e12d7b80a"


@pytest.fixture(scope="module")
def storage_account_slice(bicep_text: str) -> str:
    """Bicep source between `module storageAccount` and the next module."""
    return _slice_module(
        bicep_text,
        "module storageAccount ",
        "module cosmosDb ",
    )


def test_bicep_declares_deployer_principal_vars(bicep_text: str) -> None:
    """main.bicep must derive the deployer principal id + type from `deployer()`.

    The seed hook runs under the deployer identity, so its object id and
    principal type must be available to the storage role assignments.
    `deployerPrincipalType` reuses the same auto-detect expression the
    Postgres admin principal uses so a `User` deployer and a CI
    `ServicePrincipal` both resolve correctly.
    """
    assert "var deployerPrincipalId = deployer().objectId" in bicep_text, (
        "main.bicep must declare `var deployerPrincipalId = "
        "deployer().objectId` so the storage role assignments can target the "
        "principal running the seed hook."
    )
    assert (
        "var deployerPrincipalType = contains(deployer(), 'userPrincipalName') "
        "? 'User' : 'ServicePrincipal'" in bicep_text
    ), (
        "main.bicep must declare `deployerPrincipalType` with the "
        "`contains(deployer(), 'userPrincipalName')` auto-detect expression "
        "so a User deployer and a ServicePrincipal CI both resolve."
    )


def test_storage_account_grants_deployer_seed_roles(
    storage_account_slice: str,
) -> None:
    """The storage module must grant the deployer the two seed-hook roles.

    The seed hook uploads sample blobs (Storage Blob Data Contributor)
    and enqueues doc-processing messages (Storage Queue Data Message
    Sender) under the deployer identity. Both role assignments target
    `deployerPrincipalId`, so the slice must reference that principal at
    least twice -- once per role -- alongside both role GUIDs.
    """
    assert (
        storage_account_slice.count("principalId: deployerPrincipalId") >= 2
    ), (
        "storageAccount roleAssignments must grant `deployerPrincipalId` at "
        "least twice (Storage Blob Data Contributor + Storage Queue Data "
        "Message Sender) so the seed hook can upload blobs and enqueue "
        "messages under the deployer identity."
    )
    assert _STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID in storage_account_slice, (
        "storageAccount roleAssignments must reference the Storage Blob Data "
        f"Contributor role id '{_STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID}' for "
        "the deployer seed grant."
    )
    assert _STORAGE_QUEUE_DATA_MESSAGE_SENDER_ROLE_ID in storage_account_slice, (
        "storageAccount roleAssignments must reference the Storage Queue Data "
        f"Message Sender role id '{_STORAGE_QUEUE_DATA_MESSAGE_SENDER_ROLE_ID}' "
        "for the deployer seed grant."
    )


# ---------------------------------------------------------------------------
# Deployer AI Search data-plane RBAC.
#
# The post-deploy seed hook polls the index document count to verify
# ingestion landed, running locally under the deployer identity. The
# aiSearch service sets disableLocalAuth=true (RBAC-only data plane), so
# main.bicep must grant the deployer Search Index Data Reader in addition
# to the UAMI + Foundry-project grants the running workloads use.
# ---------------------------------------------------------------------------

_SEARCH_INDEX_DATA_READER_ROLE_ID = "1407120a-92aa-4202-b7e9-c0e197c71c8f"


@pytest.fixture(scope="module")
def aisearch_slice(bicep_text: str) -> str:
    """Bicep source between `module aiSearch` and the next module."""
    return _slice_module(
        bicep_text,
        "module aiSearch ",
        "module aiProjectSearchConnection ",
    )


def test_aisearch_grants_deployer_index_read(aisearch_slice: str) -> None:
    """The aiSearch module must grant the deployer Search Index Data Reader.

    The seed hook polls the index document count under the deployer
    identity; with `disableLocalAuth: true` the data plane is RBAC-only,
    so the deployer needs Search Index Data Reader to read the count.
    The Foundry-project grant uses the same role id, so the discriminator
    is the presence of `deployerPrincipalId` in the aiSearch slice.
    """
    assert "principalId: deployerPrincipalId" in aisearch_slice, (
        "aiSearch roleAssignments must grant `deployerPrincipalId` so the "
        "seed hook can read the index document count under the deployer "
        "identity."
    )
    assert _SEARCH_INDEX_DATA_READER_ROLE_ID in aisearch_slice, (
        "aiSearch roleAssignments must reference the Search Index Data Reader "
        f"role id '{_SEARCH_INDEX_DATA_READER_ROLE_ID}' for the deployer "
        "seed-verify grant."
    )


def test_bicep_exports_search_index_name(bicep_text: str) -> None:
    """main.bicep must export AZURE_AI_SEARCH_INDEX for the postdeploy seed.

    The seed hook's index-population self-check reads `AZURE_AI_SEARCH_INDEX`
    from the azd env; without the output the check is skipped (the env is
    empty on a clean `azd up`). The index name is single-sourced through the
    `searchIndexName` param (Hard Rule #11) -- the backend container-app env
    binding and the azd output both reference it, so an infra rename can't
    diverge the two.
    """
    assert "param searchIndexName string = 'cwyd-index'" in bicep_text, (
        "main.bicep must declare `param searchIndexName string = "
        "'cwyd-index'` to single-source the chat index name."
    )
    assert "output AZURE_AI_SEARCH_INDEX string =" in bicep_text, (
        "main.bicep must export `AZURE_AI_SEARCH_INDEX` so the postdeploy "
        "seed hook receives the index name via the azd env and can run its "
        "index-population self-check."
    )
    assert "value: searchIndexName" in bicep_text, (
        "the backend container-app `AZURE_AI_SEARCH_INDEX` env binding must "
        "reference the `searchIndexName` param, not a bare literal, so the "
        "env value and the azd output stay single-sourced."
    )


# ---------------------------------------------------------------------------
# BUG-0054 Phase 2: search-system-MI -> OpenAI role-assignment idempotency.
#
# `searchOpenAiUserOnFoundry` and `searchOpenAiUserOnReusedOpenAi` grant the
# AI Search service's system-assigned managed identity the Cognitive
# Services OpenAI User role on the (new or reused) OpenAI account. They
# originally salted their assignment `name:` with the static literal
# `'search-system-mi'` and the bare scope *name* -- a hand-coded token with
# no tie to the actual principal-owning resource. The canonical
# deterministic key (per v2-infra.instructions.md, matching the
# `existingOpenAiUamiRole` precedent) is `guid(scope.id, identityName,
# roleDefinitionId)`: keyed on the full scope resource id plus the real
# Search service name so the key is unambiguous and self-documenting.
#
# NOTE: a role-assignment `name` must be computable at the START of
# deployment, so the Search system-MI principalId (a deploy-time module
# output) cannot appear in the name -- doing so raises BCP120. The Search
# service NAME (`srch-${solutionSuffix}`) is the start-time stand-in for
# that principal, exactly as `existingOpenAiUamiRole` uses the UAMI name.
# This guard pins both names to that shape and forbids any reversion to
# the static salt.
# ---------------------------------------------------------------------------

_COGNITIVE_SERVICES_OPENAI_USER_ROLE_ID = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"


def test_search_openai_role_assignments_use_idempotent_name(bicep_text: str) -> None:
    """Both search->OpenAI role assignments must key their name on scope.id + Search name.

    The deterministic `guid(scope.id, 'srch-${solutionSuffix}',
    roleDefinitionId)` shape ties the assignment name to the full scope
    resource id and the real Search service name, replacing the hand-coded
    `'search-system-mi'` static salt (BUG-0054 Phase 2). The Search system
    MI principalId cannot appear in the name (it is a deploy-time output;
    BCP120), so the start-time Search service name is the stand-in --
    mirroring the `existingOpenAiUamiRole` `guid(scope.id, uami.name, role)`
    precedent. The role definition is referenced as a subscription-scoped
    resource id so the key is unambiguous.
    """
    foundry_name = (
        "name: guid(aiServicesAccount.id, 'srch-${solutionSuffix}', "
        "subscriptionResourceId('Microsoft.Authorization/roleDefinitions', "
        "cognitiveServicesOpenAiUserRoleId))"
    )
    reused_name = (
        "name: guid(existingOpenAi!.id, 'srch-${solutionSuffix}', "
        "subscriptionResourceId('Microsoft.Authorization/roleDefinitions', "
        "cognitiveServicesOpenAiUserRoleId))"
    )
    var_decl = (
        f"var cognitiveServicesOpenAiUserRoleId = "
        f"'{_COGNITIVE_SERVICES_OPENAI_USER_ROLE_ID}'"
    )
    assert var_decl in bicep_text, (
        "The Cognitive Services OpenAI User role GUID must be hoisted to "
        "`var cognitiveServicesOpenAiUserRoleId = "
        f"'{_COGNITIVE_SERVICES_OPENAI_USER_ROLE_ID}'` rather than repeated as "
        "an inline literal at every role-assignment site."
    )
    assert foundry_name in bicep_text, (
        "searchOpenAiUserOnFoundry must key its assignment name on "
        "`guid(aiServicesAccount.id, 'srch-${solutionSuffix}', "
        "subscriptionResourceId('Microsoft.Authorization/roleDefinitions', "
        "cognitiveServicesOpenAiUserRoleId))` -- the full scope "
        "id plus the real Search service name, not a static salt (BUG-0054 "
        "Phase 2)."
    )
    assert reused_name in bicep_text, (
        "searchOpenAiUserOnReusedOpenAi must key its assignment name on "
        "`guid(existingOpenAi!.id, 'srch-${solutionSuffix}', "
        "subscriptionResourceId('Microsoft.Authorization/roleDefinitions', "
        "cognitiveServicesOpenAiUserRoleId))` -- the full scope "
        "id plus the real Search service name, not a static salt (BUG-0054 "
        "Phase 2)."
    )
    assert "'search-system-mi'" not in bicep_text, (
        "The static salt `'search-system-mi'` must not appear in main.bicep. "
        "It was a hand-coded token with no tie to the principal-owning "
        "resource (BUG-0054 Phase 2); both names must key on `scope.id` plus "
        "the real Search service name instead."
    )
