<!-- markdownlint-disable-file -->
# Task Research: CWYD v2 dev-cloud morning resilience (subscription disable + environment wipe)

Every morning the CWYD v2 cloud environment is "messed up": the resource group `<RESOURCE_GROUP>` is emptied and the Azure subscription `<AZURE_SUBSCRIPTION_ID>` (`CSA-CTO-Engineering-Dev`) is read-only (`ReadOnlyDisabledSubscription`, observed state `Warned`). This research determines the root-cause mechanism, how to diagnose/confirm it, how to minimize or avoid the recurrence, and how to make the rebuild a single low-friction command so a daily teardown stops blocking work (e.g., the BUG-0054 live close-out).

## Task Implementation Requests

* Determine WHY the dev subscription is disabled/read-only every morning and the environment is wiped (root-cause mechanism + how to confirm which one).
* Determine HOW to avoid or mitigate the recurrence (cost governance levers, overnight cost minimization, ephemeral-environment patterns).
* Design a single-command morning recovery/rebuild runbook (purge soft-deleted Cognitive Services → clear registry endpoint → `azd up` → health wait).

## Scope and Success Criteria

* Scope: Azure subscription disablement mechanics for credit/budget-governed dev subscriptions; CWYD v2 deployment cost drivers (which resources bill 24/7 idle); `azd` ephemeral-environment lifecycle (`azd down` / `--purge`, soft-delete purge protection); a robust one-command rebuild script design. Excludes: changing the org's subscription governance (owned by the CSA CTO Engineering team) and the BUG-0054 cutover wiring (already researched).
* Assumptions:
  * The subscription is an org-managed, credit/budget-governed shared dev subscription (name `CSA-CTO-Engineering-Dev`, governance policies observed in the activity log).
  * The activity log showed zero resource-`delete` events → resources vanished via billing-plane subscription disable, not a cleanup script.
  * The user can read the subscription in the portal and can ask the subscription administrator about governance.
* Success Criteria:
  * A confirmed (or tightly-ranked) root-cause mechanism with the exact portal/CLI checks to disambiguate it.
  * A prioritized set of avoidance/mitigation options split by ownership (sub-admin vs us).
  * A concrete, reviewed one-command `morning-rebuild` runbook design grounded in the actual `v2/azure.yaml` + `v2/infra` + `v2/scripts` layout.

## Outline

1. Subscription disablement mechanics — `ReadOnlyDisabledSubscription`, `Warned`/`Disabled` lifecycle, spending limits, Cost-Management budgets with stop actions, scheduled governance; how the platform treats resources on disable; reactivation cadence.
2. CWYD v2 overnight cost drivers — per-resource 24/7-vs-idle billing (AI Search SKU, Cosmos throughput mode, AI Services/Foundry capacity, Container Apps min replicas, etc.) from `v2/infra/main.bicep`; what to shut down or scale to zero.
3. azd ephemeral-environment lifecycle — `azd down` vs `azd down --purge`; Cognitive Services / Key Vault soft-delete + purge protection; the placeholder-image chicken-and-egg and whether `azd up` can avoid the manual endpoint-clear; one-command rebuild design.

## Root-Cause Analysis — why the environment is "messed up" every morning

### The single sentence that explains every observation

Per Microsoft Learn [subscription states](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states), the **`Warned`** state: **blocks writes** (PUT/PATCH/POST return `ReadOnlyDisabledSubscription`) while allowing GET/DELETE, **is not billed**, and — critically — *"Resources in this state go offline but can be recovered when the subscription resumes an active/enabled state."*

That one sentence accounts for all three symptoms at once:

1. **The 409 `ReadOnlyDisabledSubscription`** on the write probe → `Warned` blocks writes.
2. **The resources appear "gone"** (`az resource list` empty, Container App `ResourceNotFound`, FQDN unresolved) → offline resources are hidden from ARM/ARG while the sub is `Warned`/disabled.
3. **Zero `…/delete` activity-log events** → taking resources offline on a billing-plane subscription disable is a subscription-wide platform state change; it does **not** emit per-resource ARM `DELETE` operations. A delete-issuing cleanup runbook *would* leave delete events. There are none.

### The reframe (highest-impact discovery)

**The morning "wipe" is most likely NOT a permanent deletion.** Resources taken offline by a `Warned`/disabled subscription are **recoverable when the subscription returns to `Enabled`** — within Azure's retention window. This means the correct first action after re-enable is to **check whether the resources came back online before assuming a full rebuild is needed.** A blind `azd up` rebuild may be unnecessary churn.

Caveat: `Microsoft.CognitiveServices/accounts` have their own soft-delete behavior and can land in a soft-deleted state (we observed + purged 3 this session). Purging them is destructive and forfeits any recover-on-re-enable for those specific accounts. So the recover-first check applies cleanly to non-CogSvc resources; CogSvc may still need a purge + redeploy.

### What is doing the disabling

* **Azure Policy is NOT the disabler.** The overnight `auditIfNotExists` / `deployIfNotExists` `…/action` events are governance side-effects (policy can audit/deploy, it cannot disable a subscription).
* **Pure credit/spending-limit exhaustion is a *monthly* event** (`Disabled` + portal banner), not a clean nightly `Warned`↔`Enabled` cycle.
* **A recurring nightly disable points to external scheduled automation** — a Cost Management **budget wired to a disable/cancel action group**, or an **org/internal cost-governance runbook/Logic App** that suspends dev subscriptions outside business hours and re-enables them later. Budgets are evaluated on a ~24h cadence, which is how a disable recurs "every morning."

### The pivotal question — RESOLVED: schedule/governance-driven on an over-budget shared internal subscription

The disambiguation was run (read-only, 2026-06-30) and the answer is definitive:

* `az rest GET …/subscriptions/<AZURE_SUBSCRIPTION_ID>?api-version=2022-12-01` → `quotaId = "Internal_2014-09-01"`, `spendingLimit = "Off"`, `state = "Warned"`.
  * `Internal_*` quotaId ⇒ this is an **internal Microsoft subscription under central cost governance** (not a customer/credit offer).
  * `spendingLimit = Off` ⇒ organic credit/spending-limit exhaustion is **impossible** — so the nightly disable is **not** caused by a credit running out.
* `az consumption budget list` → a **subscription-wide cost-governance budget is materially exceeded**: actual spend is **~167% of the monthly cap** (the subscription-level governance budget is blown, and a second central/owner budget tracks the same overspend). Budget notifications fan out to the **central cost-admin owner** (`<SUBSCRIPTION_COST_ADMIN>`) and an owner action group — i.e. **central cost enforcement**, not a user spending limit.

**Conclusion (high confidence):** the morning disable is **central internal cost-governance enforcement on a shared subscription that is well over its monthly budget.** Microsoft-internal subscriptions that exceed their governance budget are put into `Warned`/read-only by central automation on a recurring (≈daily) basis; the subscription is re-enabled during the day and re-`Warned` by the next sweep because it is **still over budget**.

### The decisive corollary — CWYD's own cost is NOT the cause and cannot be the fix

The subscription's **total** monthly spend is **~$25K** (driven by many workloads on this shared CTO-Engineering dev subscription). CWYD's entire default-profile footprint is **~$90–150/month** — **under ~1% of the subscription total.** Therefore:

* **Reducing CWYD's overnight cost will not stop the disable.** Scaling Search/Function/ASP to zero or tearing CWYD down nightly saves ~$3–5/day against a ~$10K/month *over*-budget — it cannot move the subscription back under its cap.
* **The over-budget condition is owned by the subscription, not by CWYD.** Only the subscription owner / the larger workload owners (or a budget increase) can clear it.
* The `alwaysReady=[]` change remains worthwhile **hygiene**, but must not be sold as a fix for the morning disable — it isn't one.

## Potential Next Research

* ~~Run the disambiguating `az rest` subscription-properties check~~ — **DONE 2026-06-30**: `Internal_2014-09-01` + `spendingLimit Off` + subscription-wide budget at ~167% ⇒ **schedule/governance-driven on an over-budget shared internal sub** (see Root-Cause Analysis).
* When the sub next returns to `Enabled`, run `az resource list -g <RESOURCE_GROUP>` BEFORE any rebuild to test the recover-on-re-enable hypothesis.
  * Reasoning: if resources auto-recover, the daily rebuild is unnecessary; only CogSvc may need attention.
* Escalate to the subscription cost-admin owner (`<SUBSCRIPTION_COST_ADMIN>`): the subscription is materially over its monthly governance budget; ask for the re-enable cadence/SLA, whether CWYD's RG can be excluded from the nightly sweep, or whether to move CWYD to a non-over-budget subscription.
  * Reasoning: the disable is owned by the subscription's budget state, not by CWYD; only the owner (or a budget increase / other-workload reduction) can clear it.
* (Optional) Pull Azure Cost Management grouped by resource to confirm CWYD is <1% of the subscription total (validates that CWYD cost reduction is irrelevant to the disable) and to confirm the live profile/db type (`azd env get-values | Select-String 'AZURE_ENV_ENABLE_|DATABASE_TYPE'`).

## Research Executed

### Conversation Context (this session, directly observed)

* `az account list --all --refresh` → subscription `<AZURE_SUBSCRIPTION_ID>` state `Warned` (not `Enabled`).
* Reversible write probe `az tag update --operation merge` on `<RESOURCE_GROUP>` → HTTP `ReadOnlyDisabledSubscription` (writes still denied).
* `az monitor activity-log list --start-time 2026-06-29T12:00:00Z` (300 events) → almost all `…/write` (yesterday's `azd up` provisioning) + governance policy actions (`auditIfNotExists`, `deployIfNotExists`); **zero `…/delete` events**.
* `az resource list -g <RESOURCE_GROUP>` → empty; backend Container App `ResourceNotFound`; FQDN no longer resolves.

### File Analysis (CWYD v2 cost drivers — default `cosmosdb` profile)

Source: subagents/2026-06-30/cwyd-v2-cost-drivers-research.md. `v2/infra/main.parameters.json` + `v2/azure.yaml` default to `databaseType=cosmosdb` with all four WAF flags (`enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking`) **false** — the cheapest profile. Ranked overnight drivers:

* **#1 Azure AI Search — Basic** (`srch-<SUFFIX>`, `v2/infra/main.bicep` ~L903 `sku: enableScalability ? 'standard' : 'basic'`) — ~$73–75/mo flat, **no scale-to-zero, no stop**. Lever: none via config (already the floor for `cosmosdb` mode); only delete it. **Un-idleable.**
* **#2 Function App always-ready instances** (`func-<SUFFIX>`, `v2/infra/main.bicep` ~L2255 `alwaysReady: [batch_push:1, blob_event:1]`, `instanceMemoryMB: 2048`) — 2×2 GB reserved 24/7, no free grant, ~$70–140/mo. Lever: **set `alwaysReady: []`** → Flex scales to zero (cold-start tradeoff). **The one default that is NOT cheap-when-idle and the easiest real win** — currently hard-coded unconditionally.
* **#3 App Service Plan — B1** (`asp-<SUFFIX>`, `v2/infra/main.bicep` ~L1998) — ~$13/mo flat, no scale-to-zero. Lever: delete plan + frontend web app to idle.
* **#4 Container Registry — Basic** (`cr<SUFFIX>`, `v2/infra/main.bicep` ~L1793) — ~$5/mo flat (low priority).
* **~$0 idle (Bicep already cheap):** Cosmos DB serverless (`~L1385` `EnableServerless`), backend Container App `minReplicas: 0` (`~L1820`), Storage LRS, S0 AI Services/Speech/Content Safety (pay-per-call), GlobalStandard/Standard model deployments (token-billed), Log Analytics/App Insights **not deployed**.
* `postgresql` mode swaps Search for a Postgres B2s flexible server that **can be stopped** (`az postgres flexible-server stop`) — a cheaper idle story than `cosmosdb`+Search. WAF profile adds Bastion Standard (~$140+/mo), private endpoints, P1v3×3, Search standard×3, provisioned Cosmos, D4 Postgres.

### File Analysis (azd lifecycle + scripts)

Source: subagents/2026-06-30/azd-ephemeral-env-rebuild-runbook-research.md. `v2/azure.yaml` services: `backend` (py / containerapp / `remoteBuild`), `frontend` (js / appservice / build-from-source), `function` (py / function). Hooks: `postprovision` (pgvector ext / search index / KB seed) + `postdeploy` (`upload_sample_data.py` seed); **no `preprovision` hook**. Seed prompt is suppressed by `azd up --no-prompt` or `azd env set AZURE_ENV_SAMPLE_DATA none`. **Only soft-delete-protected type is `Microsoft.CognitiveServices/accounts`** (4: AIServices, OpenAI, Speech, ContentSafety) — **no Key Vault, no App Configuration** declared in `v2/infra`. **No existing teardown/rebuild script**; `v2/Makefile` has only `typecheck`/`test`/`lint` → new scripts are greenfield (Hard Rule #10 confirm before adding).

### External Research

* Microsoft Learn — [Subscription states](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states): `Warned` blocks writes, not billed, resources offline+recoverable; `Disabled`/`Expired` lifecycle; reactivation paths.
* Microsoft Learn — Cost Management **budgets** (evaluated ~24h; can trigger action groups, incl. automation that disables/cancels a subscription).
* Microsoft Learn — **azd** `down` / `--purge`: deletes Azure resources only (env `.env` + captured outputs survive); `--purge` purges soft-deletes **for resources azd itself deletes in that run**.
* azd source (`cli/azd/pkg/...` `PurgeCognitiveAccount`) — confirms azd purges CogSvc only for resources it enumerates/deletes.

### Project Conventions

* Standards referenced: Hard Rule #18 (placeholders only in tracked files), Hard Rule #10 (ask before adding new scripts/structure), `config-defaults-dev-first` (do not flip `main.parameters.json` defaults), `cleanup-before-next-step`, `git-ownership`.

## Key Discoveries

1. **`Warned` = writes blocked + resources offline-but-recoverable + no `DELETE` events.** The morning "wipe" is a billing-plane subscription disable, not a teardown script — and likely **not a permanent deletion**. Check `az resource list` after re-enable before rebuilding.
2. **The disabler is external scheduled automation or a budget action**, not Azure Policy and not (on a nightly cadence) organic credit burn. One read-only `az rest` call on the subscription's `quotaId`/`spendingLimit` disambiguates cost-driven vs schedule-driven, which selects the mitigation.
3. **A pure "scale to zero" strategy cannot reach $0** on the default `cosmosdb` profile because **AI Search Basic** and **App Service Plan B1** have no scale-to-zero. Only a full teardown reaches ~$0.
4. **The single biggest cheap win is the Function App `alwaysReady`** — currently `[batch_push:1, blob_event:1]` (2×2 GB reserved 24/7, ~$70–140/mo). Setting it to `[]` (or gating on `enableScalability`) lets Flex scale to zero. This is the only default that is expensive-when-idle and config-fixable.
5. **`AZURE_CONTAINER_REGISTRY_ENDPOINT` survives `azd down`**, so the next `azd up` re-fires the `MANIFEST_UNKNOWN` chicken-and-egg — **any rebuild script MUST clear it first** (until WI-04 self-healing preprovision hook lands).
6. **`azd down --purge` does NOT clean up the overnight soft-deletes** because the billing-plane wipe happens before any `azd down` (azd has nothing to enumerate). The **manual `az cognitiveservices account purge`** step stays in the rebuild runbook.
7. **WI-04 (auto-placeholder on first provision) is feasible via a `preprovision` hook** that clears the endpoint when the backend image isn't in ACR; a Bicep-side image-existence gate is not cleanly feasible (no ACR manifest probe without a heavyweight `deploymentScript`).

## Technical Scenarios

### Selected Approach — Diagnose first, then embrace ephemerality with a one-command rebuild (staged)

**Rationale:** the mitigation hinges on the cost-driven-vs-schedule-driven question, and the recover-on-re-enable hypothesis may make rebuilds unnecessary. So the approach is staged — diagnosis first (**now done**), then the matching durable mitigation — rather than committing to a nightly teardown/rebuild blind.

**Stage 1 — Diagnose (DONE 2026-06-30).**
* Result: `quotaId = Internal_2014-09-01`, `spendingLimit = Off`, subscription-wide governance budget at **~167%** of cap → **schedule/governance-driven on an over-budget shared internal subscription.** CWYD is <1% of the subscription's ~$25K/month total, so CWYD cost reduction cannot influence the disable.
* Therefore the **schedule-driven branch of Stage 3 is the selected path** (the cost-driven branch is not applicable as a *fix*).

**Stage 2 — On the next `Enabled`, test recover-on-re-enable.**
* `az resource list -g <RESOURCE_GROUP>` *before* any write. If resources are back online, no rebuild is needed (only verify health + re-run the BUG-0054 validation). If only CogSvc are missing/soft-deleted, purge + targeted redeploy.

**Stage 3 — Durable mitigation (SELECTED: schedule-driven branch).**
* **Selected (schedule-driven):** the disable is central cost-governance on an over-budget shared internal sub — **not preventable by CWYD-side changes.** Mitigation: (a) escalate to the subscription cost-admin owner (`<SUBSCRIPTION_COST_ADMIN>`) for the re-enable cadence/SLA, an RG exclusion, or a budget increase; (b) if persistent uptime matters, **move CWYD to a non-over-budget subscription**; (c) otherwise **rely on recover-on-re-enable (Stage 2) + the one-command morning rebuild (Stage 4) as the safety net.**
* **Not applicable (cost-driven):** would have landed `alwaysReady=[]` + nightly teardown to stay under a cap — irrelevant here because CWYD is <1% of spend. The `alwaysReady=[]` change is retained only as optional **hygiene**, explicitly *not* a fix for the disable.

**Stage 4 — Build the one-command rebuild safety net (greenfield `v2/scripts/`, Hard Rule #10 confirm).**
* `morning-rebuild.ps1`: subscription-enabled gate + write probe (STOP if read-only) → purge soft-deleted Cognitive Services for `<SUFFIX>` → clear `AZURE_CONTAINER_REGISTRY_ENDPOINT` → `azd up --no-prompt` → poll Container App `provisioningState`/`runningStatus` + backend `/api/health` → print endpoint. Idempotent, placeholder-only, no git ops.
* Optional `evening-teardown.ps1`: `azd down --force --purge` → verify CogSvc purge.
* Full drafts: subagents/2026-06-30/azd-ephemeral-env-rebuild-runbook-research.md (Q7).

```text
v2/
  scripts/
    morning-rebuild.ps1      # NEW (greenfield) — gated clean rebuild
    evening-teardown.ps1     # NEW (optional) — azd down --purge + verify
  infra/
    main.bicep               # EDIT (cost-driven only) — Function alwaysReady → [] / gated on enableScalability
```

**Implementation Details:**

* The rebuild script's subscription gate reuses this session's proven Phase 0 pattern: `az account list --all --refresh` for `state`, then a reversible `az tag update --operation merge`/`delete` write probe (a read alone does not prove writability — `Warned` reads as not-`Enabled` but the probe is authoritative).
* The Function `alwaysReady` edit, if pursued, is a Stable-Core infra change → test-first (extend `v2/tests/infra/test_main_bicep.py` to pin the new value) and Hard Rule #10 confirmation before touching `main.bicep`.

#### Considered Alternatives

* **Scenario B — Keep the env up, only minimize idle cost (no teardown).** Land `alwaysReady=[]`, delete Search + ASP nightly, keep Cosmos/Storage/ACR for a fast rebuild. *Rejected as the primary* because (a) if the cause is schedule-driven, minimizing cost does nothing to prevent the disable, and (b) Search Basic + B1 still bill — it never reaches $0. Retained as the **cost-driven middle path** inside Stage 3.
* **Scenario C — Blind nightly `azd down --purge` + `azd up` regardless of cause.** Simple and reaches $0, but burns 15–40 min every morning and destroys uploaded test docs + chat history even when (per the recover-on-re-enable discovery) the resources might simply come back for free. *Rejected* as wasteful until Stage 1/2 rule out the cheaper paths.
* **WI-04 now (preprovision self-healing hook).** Feasible, removes the manual endpoint-clear, but is a structural addition (Hard Rule #10) and orthogonal to closing the immediate morning-resilience question. *Deferred* to a follow-on once the rebuild script exists.
