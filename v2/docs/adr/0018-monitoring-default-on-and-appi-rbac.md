# ADR 0018 — Monitoring default-on for deployed envs + `Monitoring Metrics Publisher` RBAC for UAMI on AppI

- **Status**: Accepted
- **Date**: 2026-06-05
- **Phase**: 7 (close-out, observability gap)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

The initial `<AZD_ENV_NAME>` deployment landed without Application Insights or Log Analytics. The Bicep already wires `APPLICATIONINSIGHTS_CONNECTION_STRING` into both the backend Container App env block and the Function App env block — sourced from `applicationInsights!.outputs.connectionString` — but the entire monitoring branch in [`v2/infra/main.bicep`](../../infra/main.bicep) is gated on `param enableMonitoring bool = false` (line 195). The default was `false`, so `appi-<SUFFIX>` + `log-<SUFFIX>` were never created.

The cost surfaced when `POST /api/batch_start` started returning **500 with empty body** for valid input. The handler is wrapped in `@map_function_exceptions("batch_start")` ([`v2/src/functions/core/exception_mapping.py`](../../src/functions/core/exception_mapping.py)) which always returns a JSON ladder (422 / 502 / 500). An empty-body 500 means the crash is **below the decorator** — most likely a Python worker failure (lazy `ImportError`, Pydantic `ValidationError`, credential-chain crash, or SDK `HttpResponseError`). On Azure Functions **Flex Consumption** the diagnostic options are sharply constrained:

- `func azure functionapp logstream` is not supported on Flex.
- `az functionapp deployment list-publishing-credentials` returns "Invalid command. This is not currently supported for Azure Functions on the Flex Consumption plan" — no Kudu basic-auth.
- The Kudu REST endpoints (`/api/logs/recent`, `/api/vfs/...`) return 401 because there are no publishing creds to authenticate with.

Without Application Insights the function app is effectively a black box. The MVP shipped with no path to read a stack trace from a production crash. The dev-loop cost of this gap is unbounded: every cloud-only bug requires either a runtime patch attempt-and-retry cycle or a guess-and-redeploy.

There is also a **second, latent gap**. The AppI module is created with `disableLocalAuth: true` (line 320 of `main.bicep`). This is the WAF-aligned setting — the data-plane refuses instrumentation-key auth and requires Microsoft Entra ID tokens. But `main.bicep` does **not** assign the `Monitoring Metrics Publisher` role (`3913510d-42f4-4e42-8a64-81b1edca285c`) to the UAMI on the AppI scope. Without that role, even with the connection string wired, the function worker's OpenTelemetry exporter authenticates against the AppI ingestion endpoint and gets back a silent 401 — telemetry appears "wired" while no events ever reach the AppI workspace. This would have produced the same black-box symptom even if the original deployment had set `enableMonitoring=true`.

Both gaps point at the same root cause: **monitoring was treated as an optional WAF extra rather than a Stable Core invariant**. The v1 accelerator does not provision AppI by default; v2 inherited that posture without re-deciding it.

## Decision

**Monitoring is part of the Stable Core for any deployed v2 environment.** Three binding changes:

1. **`enableMonitoring` defaults to `true`** for any environment that runs `azd up` / `azd provision`. The `false` branch remains in the Bicep solely for unit tests and `bicep build` self-checks — not for live deployments. Any environment that opts out must add a `// disabled because <reason>` annotation in its `.azure/<env>/.env` or the deployment plan; the next ADR will tighten this with a CI gate.
2. **The Bicep MUST assign `Monitoring Metrics Publisher`** (`3913510d-42f4-4e42-8a64-81b1edca285c`) to the UAMI on the `applicationInsights` resource scope. Wired as `if (enableMonitoring)` alongside the AppI module itself. Without this role, ingestion silently 401s; with it, the UAMI-based OpenTelemetry exporter (the only ingestion path because `disableLocalAuth: true`) succeeds.
3. **AppI + LAW co-locate with the workload Resource Group.** No cross-RG telemetry sinks — `appi-<solutionSuffix>` and `log-<solutionSuffix>` live in the same RG as the Container App, App Service, and Function App they observe. Cross-RG patches (the runtime-only `az functionapp config appsettings set --settings "APPLICATIONINSIGHTS_CONNECTION_STRING=$conn"` against an AppI in a different RG) are explicitly **not** an acceptable substitute. They violate the "one RG, one workload" boundary, are invisible to IaC drift checks, and disappear on the next `azd provision`.

### Wire shape (binding)

- AppI connection string → container env var, sourced from `applicationInsights!.outputs.connectionString` at deploy time. Identical pattern to every other Bicep output. Never a hand-set secret, never a runtime `az config appsettings set` patch.
- The role assignment uses the existing `flexDeploymentRole` pattern in `main.bicep` (~line 2005): `resource appiMonitoringRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableMonitoring) { ... }`, scoped to the AppI component, principalId from `userAssignedIdentity.outputs.principalId`.
- Two drift-guard assertions added to [`v2/tests/infra/test_main_bicep.py`](../../tests/infra/test_main_bicep.py): (a) `enableMonitoring=true` emits a `Microsoft.Authorization/roleAssignments` block scoped to `applicationInsights` with role id `3913510d-...`; (b) `APPLICATIONINSIGHTS_CONNECTION_STRING` appears in both backend and function env blocks under `enableMonitoring=true`.

### Out of scope — what this ADR does NOT decide

- **AppI alerts, availability tests, and saved KQL queries.** Tracked separately. Adding `Microsoft.Insights/scheduledQueryRules` resources lands in a follow-up ADR if/when it becomes operationally necessary.
- **AppI dashboards or Azure Workbooks.** Same as above.
- **OpenTelemetry SDK choice and exporter configuration.** The function host's built-in instrumentation handles the worker-process traces. Explicit `azure-monitor-opentelemetry-distro` wiring in backend code is a future decision if app-level custom metrics become a requirement.
- **Sampling strategy.** Defaults from `azure-functions-host` apply. A future cost ADR may revisit this.

## Consequences

### Positive

- **A live production environment is always observable.** Stack traces, dependency timings, and outgoing call failures land in AppI within ~30–60 s of the event. The "empty-body 500" diagnosis cycle that triggered this ADR becomes a five-minute KQL query instead of a multi-hour spelunk.
- **UAMI + Entra-only ingestion stays.** `disableLocalAuth: true` is preserved; we close the silent-401 gap without weakening the auth posture. This is the WAF-aligned path.
- **No cross-RG telemetry sinks.** Each environment owns its observability stack inside its own RG. Tear-down is a single `az group delete`.
- **IaC drift checks cover monitoring.** The two new test_main_bicep assertions fail loudly if a future refactor removes the role assignment or the env-var wiring.
- **Aligns with Hard Rule #7** (no Key Vault for app secrets — connection string flows from Bicep output → env var, not a vault reference) and with [ADR 0002](0002-no-key-vault-uami-rbac.md) (UAMI + RBAC + Bicep-output env vars).

### Negative

- **LAW + AppI ingestion cost** at the default `PerGB2018` SKU is ~$2–5/day for a low-volume MVP. Accepted as the cost of having a runnable solution. The 30-day retention default keeps storage tractable; long-term archival is a separate decision.
- **`azd provision` runtime grows by ~2–3 minutes** for environments that currently skip the monitoring branch. Acceptable for a once-per-env operation.
- **Existing environments need a one-time targeted re-provision** to materialize `appi-*` + `log-*` + the role assignment. Additive change — no existing resource is destroyed, no data is lost — but the operator must run `azd provision` once after this ADR lands.

### Neutral

- The flag `enableMonitoring` does not disappear; flipping its default is a non-breaking behavioral change. Any unit test that calls the Bicep with `enableMonitoring=false` continues to compile and produce the no-monitoring shape.

## Alternatives considered

1. **Wire AppI as a cross-RG runtime patch only** (e.g., point `func-<SUFFIX>` at `<APPI_NAME>` in `<APPI_RESOURCE_GROUP>` via `az functionapp config appsettings set`). Rejected: violates "one RG, one workload", invisible to IaC drift checks, vanishes on the next `azd provision`, and creates a telemetry sink shared with unrelated workloads.
2. **Leave `enableMonitoring=false` and rely on Flex Consumption stdout scraping.** Rejected: Flex Consumption disables `func log tail` and Kudu publishing creds; stdout scraping requires a workaround chain (custom Storage queue sink, Event Hub fan-out) that is more work than the AppI default-on it replaces.
3. **Default-on monitoring but skip the `Monitoring Metrics Publisher` role assignment.** Rejected: the silent-401 ingestion drop is the exact failure mode this ADR exists to close. Without the role, AppI looks wired and produces zero data; that is strictly worse than no AppI at all because it gives a false sense of observability.
4. **Move to system-assigned managed identity per compute resource for AppI ingestion.** Rejected for the same reason ADR 0002 rejected SAMI: it makes pre-provisioning RBAC awkward and breaks the single-identity audit story.
5. **Enable Diagnostic Settings on every resource (already in Bicep behind `enableMonitoring`) but no AppI component.** Rejected: diagnostic logs to LAW give you resource-plane traces (deploy events, throttling, RBAC denials) but not application-level stack traces from the function worker. The empty-body 500 is an application-tier crash; only AppI sees it.

## Amendment 1 (2026-06-23) — per-workload App Insights env-var names (BUG-0055)

The original wire-shape bound `APPLICATIONINSIGHTS_CONNECTION_STRING` onto **both**
the backend Container App and the Function App. In the cloud this left the backend
emitting **zero** telemetry: the backend ACA container has no host-level App
Insights agent, so its Python lifespan must call `configure_azure_monitor` with the
connection string read from `ObservabilitySettings` — and that settings class uses
`env_prefix="AZURE_"`, so it reads `AZURE_APP_INSIGHTS_CONNECTION_STRING`, never the
standard name. The container only ever received the standard name, so the typed
setting stayed empty and the exporter never initialized. (The original ADR's
"function host's built-in instrumentation handles the worker-process traces"
assumption in *Out of scope* is why the backend's distinct requirement was missed.)

Resolution — the two workloads bind **different** env-var names by design:

- **Backend Container App** → `AZURE_APP_INSIGHTS_CONNECTION_STRING` (matches the
  Python `configure_azure_monitor` read path; the typed setting honors only the
  `AZURE_`-prefixed name).
- **Function App** → `APPLICATIONINSIGHTS_CONNECTION_STRING` (the Functions host
  reads the standard name natively).

Both still source the value from `applicationInsights!.outputs.connectionString`
under the `enableMonitoring` ternary, so the no-Key-Vault / Bicep-output invariant
is unchanged. The `test_appinsights_connection_string_bound_to_workload`
drift-guard is now parametrized per workload to assert the correct name for each.
This durable fix takes effect on the next `azd provision`; the **function half** of
BUG-0055 (app-level OTel export from the function worker) remains open.

## Amendment 2 (2026-07-02) — enable App Insights local auth to match MACAE (BUG-0055)

Amendment 1 fixed the backend env-var name but both runtimes still emitted **zero**
telemetry. The remaining cause is the AppI ingestion auth posture itself. The App
Insights component (`avm/res/insights/component`) is provisioned with
`disableLocalAuth: true`, so the data plane **refuses** instrumentation-key /
connection-string ingestion and requires a Microsoft Entra bearer token. But CWYD's
application code calls `configure_azure_monitor(connection_string=...)` with **no
`credential=`** at both sites (the backend lifespan and the functions worker), so the
exporter never presents a token and every ingestion request silently returns 401 —
telemetry looks "wired" while no events ever reach the workspace.

**What changed.** The App Insights component `disableLocalAuth` flips from `true` to
`false` in [`v2/infra/main.bicep`](../../infra/main.bicep). The
`Monitoring Metrics Publisher` role assignment on the App Insights component
(introduced by Decision #2 above) is **retained** even though it is now unused, kept
in place to preserve a clean revert path (see below). No application code changes.

**Why.** This matches MACAE (the Multi-Agent Custom Automation Engine Solution
Accelerator), whose App Insights `avm/res/insights/component` **omits** `disableLocalAuth`
— defaulting to `false` — and ingests telemetry with connection-string /
instrumentation-key auth, granting no `Monitoring Metrics Publisher` role at all.
CWYD's application code is **already** connection-string-only
(`configure_azure_monitor(connection_string=...)`), so enabling local auth restores
ingestion with **zero application-code change**. This is the smallest possible fix for
BUG-0055: App Insights was receiving zero telemetry precisely because
`disableLocalAuth: true` rejected the ikey ingestion path and the exporter presented
no Entra credential.

**Tradeoff.** Instrumentation-key / connection-string ingestion is a **weaker auth
bar** than Entra-token ingestion. Accepted because MACAE — a shipped Microsoft
reference accelerator — uses exactly this posture. This amendment therefore
**reverses** the original ADR's Decision #2 (Entra-only ingestion via
`disableLocalAuth: true`) and its *Positive* consequence "**UAMI + Entra-only ingestion
stays**". The original ADR never enumerated an explicit "leave local auth enabled"
alternative — it treated `disableLocalAuth: true` as settled — so this amendment
introduces that posture deliberately. (The role assignment from Decision #2 is
retained, not reversed; only rejected Alternative #3's "drop the role" stance is
untouched here.)

**Revert path.** To return to Entra-only ingestion, flip `disableLocalAuth` back to
`true` and pass a **synchronous** `azure.identity.ManagedIdentityCredential(client_id=...)`
to `configure_azure_monitor(connection_string=..., credential=...)` at **both** sites:
the backend lifespan in [`v2/src/backend/app.py`](../../src/backend/app.py) and the
functions worker in [`v2/src/functions/core/telemetry.py`](../../src/functions/core/telemetry.py).
Because the `Monitoring Metrics Publisher` role assignment is retained, no RBAC change
is required for the revert. (This credential-based approach is the research doc's
rejected alternative, preserved here for reference.)

## References

- [`v2/infra/main.bicep`](../../infra/main.bicep) — `enableMonitoring` param (line 195), `logAnalyticsWorkspace` + `applicationInsights` modules (lines 287–321), `disableLocalAuth: true` (line 320), backend env wiring (lines 1702–1703 + 1816–1817), function env wiring (lines 1980–1986). New `appiMonitoringRole` lands near the `flexDeploymentRole` block (~line 2005).
- [`v2/tests/infra/test_main_bicep.py`](../../tests/infra/test_main_bicep.py) — drift-guard suite; new assertions land here.
- [`v2/src/functions/core/exception_mapping.py`](../../src/functions/core/exception_mapping.py) — `map_function_exceptions` decorator; explains why an empty-body 500 means the crash bypassed it.
- [ADR 0002](0002-no-key-vault-uami-rbac.md) — UAMI + RBAC + Bicep-output env vars baseline.
- [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md) — credential singleton flow that AppI ingestion piggybacks on.
- [`copilot-instructions.md` Hard Rule #7](../../../.github/copilot-instructions.md) — no Key Vault, AppI connection string flows as Bicep output.
- Azure Monitor / Application Insights Entra-only ingestion: <https://learn.microsoft.com/azure/azure-monitor/app/azure-ad-authentication>.
- Azure Functions Flex Consumption limitations: <https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan>.
- `Monitoring Metrics Publisher` built-in role: <https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/monitor#monitoring-metrics-publisher> (role id `3913510d-42f4-4e42-8a64-81b1edca285c`).
