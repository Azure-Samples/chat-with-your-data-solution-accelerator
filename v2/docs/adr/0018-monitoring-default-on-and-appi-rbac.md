# ADR 0018 — Monitoring default-on for deployed envs + `Monitoring Metrics Publisher` RBAC for UAMI on AppI

- **Status**: Accepted
- **Date**: 2026-06-05
- **Phase**: 7 (close-out, observability gap)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

The initial `cwyd-cdb-v2` deployment landed without Application Insights or Log Analytics. The Bicep already wires `APPLICATIONINSIGHTS_CONNECTION_STRING` into both the backend Container App env block and the Function App env block — sourced from `applicationInsights!.outputs.connectionString` — but the entire monitoring branch in [`v2/infra/main.bicep`](../../infra/main.bicep) is gated on `param enableMonitoring bool = false` (line 195). The default was `false`, so `appi-cwyd2bh3kb` + `log-cwyd2bh3kb` were never created.

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

1. **Wire AppI as a cross-RG runtime patch only** (e.g., point `func-cwyd2bh3kb` at `appinsights-ihzuxo24up7ky` in `rg-cwyd-dev-ctn` via `az functionapp config appsettings set`). Rejected: violates "one RG, one workload", invisible to IaC drift checks, vanishes on the next `azd provision`, and creates a telemetry sink shared with unrelated workloads.
2. **Leave `enableMonitoring=false` and rely on Flex Consumption stdout scraping.** Rejected: Flex Consumption disables `func log tail` and Kudu publishing creds; stdout scraping requires a workaround chain (custom Storage queue sink, Event Hub fan-out) that is more work than the AppI default-on it replaces.
3. **Default-on monitoring but skip the `Monitoring Metrics Publisher` role assignment.** Rejected: the silent-401 ingestion drop is the exact failure mode this ADR exists to close. Without the role, AppI looks wired and produces zero data; that is strictly worse than no AppI at all because it gives a false sense of observability.
4. **Move to system-assigned managed identity per compute resource for AppI ingestion.** Rejected for the same reason ADR 0002 rejected SAMI: it makes pre-provisioning RBAC awkward and breaks the single-identity audit story.
5. **Enable Diagnostic Settings on every resource (already in Bicep behind `enableMonitoring`) but no AppI component.** Rejected: diagnostic logs to LAW give you resource-plane traces (deploy events, throttling, RBAC denials) but not application-level stack traces from the function worker. The empty-body 500 is an application-tier crash; only AppI sees it.

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
