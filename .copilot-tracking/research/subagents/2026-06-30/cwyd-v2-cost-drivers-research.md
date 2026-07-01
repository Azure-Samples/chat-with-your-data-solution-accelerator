<!-- markdownlint-disable-file -->
# CWYD v2 — Overnight Cost Drivers Research

Status: Complete (default cosmosdb profile fully analyzed; postgresql + WAF profiles covered; external billing semantics confirmed against Microsoft Learn)

## Research questions

1. Enumerate every billable Azure resource the v2 deployment provisions (type, SKU/tier/capacity, controlling param/var with file:line).
2. Classify each resource's IDLE overnight cost: HIGH / LOW-NEGLIGIBLE / USAGE-ONLY, with reasoning.
3. Identify and rank the TOP overnight cost drivers.
4. For each top driver, the lever to reduce idle cost WITHOUT teardown; note where Bicep already does the cheap thing.
5. Any resource that CANNOT be cheaply idled (argues for full nightly `azd down`).
6. Cross-check `main.parameters.json` + azd env defaults for SKU/capacity overrides.

## TL;DR

- The **default `azd up` profile** is the cheapest one: `databaseType=cosmosdb`, and all four WAF flags (`enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking`) default to **false** in `v2/infra/main.parameters.json`. That profile is almost certainly what a shared dev sub is running.
- Even in that cheapest profile, **four resources bill 24/7 no matter how idle the app is**, and two of them have **no scale-to-zero path at all**:
  1. **Azure AI Search — Basic** (`srch-<suffix>`) — fixed hourly, ~$73–75/mo, **cannot scale to zero**. Biggest flat idle cost. (cosmosdb mode only)
  2. **Function App always-ready instances** (2 × 2 GB on Flex Consumption) — billed 24/7 baseline with **no free grant**; ~$70–140/mo. **Config-fixable** (set always-ready to 0).
  3. **App Service Plan — B1** (`asp-<suffix>`, hosts the frontend) — ~$13/mo flat, **cannot scale to zero**.
  4. **Container Registry — Basic** (`cr<suffix>`) — ~$5/mo flat, cannot scale to zero (cheap, low priority).
- Everything else in the default profile is genuinely cheap-when-idle: Cosmos DB is **serverless** (pay-per-RU, ~$0 idle), the backend Container App is **scale-to-zero** (`minReplicas: 0`), Storage is LRS pennies, and Speech / Content Safety / AI Services are **S0 pay-per-call** (no baseline). Log Analytics / App Insights are **not even deployed** (monitoring defaults off).
- Because the #1 driver (AI Search Basic) and #3 (App Service Plan B1) have **no scale-to-zero lever**, a pure "scale everything to zero overnight" strategy **cannot** get this deployment near $0. The cleanest way to guarantee ~$0 overnight is **`azd down --purge` nightly + `azd up` each morning** (the deployment is single-tenant, re-seedable dev data). See the recommendation section.

## Q1 — Billable resource inventory (default cosmosdb profile)

All file:line refs are in `v2/infra/main.bicep` unless noted. "Gate" = the condition under which the resource is deployed. Default profile = `databaseType=cosmosdb`, `enableMonitoring=false`, `enableScalability=false`, `enableRedundancy=false`, `enablePrivateNetworking=false`.

| # | Resource | Name | SKU / tier / capacity (default) | Controlling param/var (file:line) | Gate |
|---|----------|------|----------------------------------|-----------------------------------|------|
| 1 | User-assigned Managed Identity | `id-<suffix>` | n/a (free) | UAMI module ~L313 | always |
| 2 | Log Analytics Workspace | `log-<suffix>` | PerGB2018, retention 30d | `dataRetention: enableRedundancy ? 90 : 30` ~L332 | `enableMonitoring` (OFF by default) |
| 3 | Application Insights | `appi-<suffix>` | workspace-based | module ~L346 | `enableMonitoring` (OFF by default) |
| 4 | Virtual Network + NSGs + subnets | `vnet-<suffix>` | n/a (free) | module ~L392 | `enablePrivateNetworking` (OFF) |
| 5 | Private DNS Zones (×N) | per-service | ~negligible | ~L458 | `enablePrivateNetworking` (OFF) |
| 6 | Azure Bastion + Standard Public IP | `bas-<suffix>` | **Standard** | `sku: 'Standard'` ~L487; `publicIPAddressObject` ~L498 | `enablePrivateNetworking` (OFF) |
| 7 | AI Services account (Foundry) | `aisa-<suffix>` | kind=AIServices, **S0** | account module ~L524 | always (unless `useExistingOpenAi`) |
| 7a | — gpt model deployment | gpt-5.1 | **GlobalStandard**, cap 150 | `gptModelDeploymentType` params.json L30-36 | always |
| 7b | — reasoning deployment | o4-mini | **GlobalStandard**, cap 50 | `reasoningModelDeploymentType` params.json L43-49 | always |
| 7c | — embedding deployment | text-embedding-3-large | **Standard**, cap 100 | `embeddingModelDeploymentType` params.json L56-62 | always |
| 8 | Foundry Project (child) | project | n/a (control-plane) | `modules/ai-project.bicep` | always |
| 9 | Speech Services | `spch-<suffix>` | kind=SpeechServices, **S0** | account ~L765 | always (no gate) |
| 10 | Content Safety | `cs-<suffix>` | kind=ContentSafety, **S0** | account ~L840 | always (no gate) |
| 11 | Azure AI Search | `srch-<suffix>` | **basic**, replicas 1, partitions 1, semantic=free | `sku: enableScalability ? 'standard' : 'basic'` ~L903; `replicaCount: enableRedundancy ? 3 : 1` | `databaseType==cosmosdb && !useExistingSearch` |
| 12 | Storage Account | `st<suffix>` | StorageV2, **Standard_LRS**, Hot | `skuName: enableRedundancy ? 'Standard_ZRS' : 'Standard_LRS'` L1103 | always |
| 13 | Cosmos DB | `cosno-<suffix>` | **Serverless** (EnableServerless) | `capabilitiesToAdd: enableRedundancy ? [] : ['EnableServerless']` ~L1385 | `databaseType==cosmosdb && !useExistingCosmos` |
| 14 | PostgreSQL Flexible Server | `psql-<suffix>` | **Standard_B2s Burstable**, 32 GB, HA off | `skuName: enableScalability ? 'Standard_D4ds_v5' : 'Standard_B2s'` ~L1525; `tier` ~L1526 | `databaseType==postgresql` (OFF by default) |
| 15 | Container Apps Managed Environment | `cae-<suffix>` | **Consumption** workload profile | `workloadProfiles: [Consumption]` ~L1660; `zoneRedundant: enableRedundancy` | always |
| 16 | Backend Container App | `ca-backend-<suffix>` | 0.5 vCPU / 1 GiB, **minReplicas 0**, max 3 | `scaleSettings.minReplicas: enableScalability ? 1 : 0` ~L1820 | always |
| 17 | Container Registry | `cr<suffix>` | **Basic** | `acrSku: 'Basic'` ~L1793 | always |
| 18 | App Service Plan | `asp-<suffix>` | **B1** (Linux), 1 worker | `appServicePlanSkuName = enableRedundancy \|\| enableScalability ? 'P1v3' : 'B1'` ~L1998; `appServicePlanSkuCapacity = enableRedundancy ? 3 : 1` | always |
| 19 | Frontend Web App | `app-frontend-<suffix>` | runs on plan #18 (no extra charge) | `frontendWebApp` module ~L2010 | always |
| 20 | Function App Plan | `plan-func-<suffix>` | **FC1** (Flex Consumption), skuCapacity 0 | `functionsPlanSkuName = 'FC1'` ~L2150 | always |
| 21 | Function App | `func-<suffix>` | Flex Consumption, instanceMemoryMB **2048**, **alwaysReady batch_push:1 + blob_event:1**, max 40 | `alwaysReady: [...]` ~L2255; `instanceMemoryMB: 2048` ~L2253; `maximumInstanceCount: enableScalability ? 100 : 40` | always |
| 22 | Event Grid system topic + subscription | `evgt-<suffix>` | pay-per-op (100k free/mo) | module ~L2355 | `!useExistingEventGridTopic` |

Notes on inventory:
- The only billable network resource in WAF mode is **Bastion + its Standard Public IP** (L487/L498). There is **no NAT Gateway, no Azure Firewall, no DDoS plan** anywhere in the template (confirmed by grep over `v2/infra/**`). Private endpoints (blob/queue/file, Cosmos `Sql`, etc.) are billed per-PE-hour only when `enablePrivateNetworking=true`.
- `modules/ai-project.bicep` and `modules/ai-project-search-connection.bicep` create only control-plane child resources (Foundry Project + Search connection) — no independent meter.
- Model deployments (7a–7c) are **GlobalStandard / Standard** = token-billed (pay-per-call), **not** PTU/Provisioned, so they have **zero idle cost**.

## Q2 — Idle overnight cost classification

| Resource | Idle class | Reasoning |
|----------|-----------|-----------|
| AI Search — **basic** (#11) | **HIGH** | Dedicated tier: "the billing rate becomes a *fixed cost* of running the service around the clock." 1 SU (1 replica × 1 partition) billed 24/7. **No scale-to-zero, no stop.** ~$73–75/mo. *(cosmosdb mode only)* |
| Function App always-ready (#21) | **HIGH / MODERATE** | Flex Consumption always-ready = "billed for total memory provisioned across all always-ready instances (baseline) … **no free grants**." 2 instances × 2048 MB (1 vCPU each) reserved 24/7. ~$70–140/mo at typical rates. |
| App Service Plan **B1** (#18) | **MODERATE** | Basic plan = fixed hourly per worker, always-on, **no scale-to-zero**. ~$13/mo flat. Frontend Web App (#19) adds no extra charge. |
| PostgreSQL Flex **B2s** (#14) | **MODERATE** (postgresql mode only) | Burstable compute + 32 GB storage billed 24/7, ~$35–40/mo. **No scale-to-zero**, but the server **can be stopped** (`az postgres flexible-server stop`; auto-restarts after 7 days). |
| Container Registry **Basic** (#17) | **LOW** | Fixed daily registry charge ~$0.167/day ≈ $5/mo. Cannot scale to zero, but cheap. |
| Bastion **Standard** + Public IP (#6) | **HIGH** (WAF only) | Fixed hourly host + scale-unit + Standard Public IP. ~$140+/mo. Only when `enablePrivateNetworking=true`. |
| Private endpoints (×6+) (#4/#5/#12/#13) | **LOW-MOD** (WAF only) | ~$7.30/mo each + Container Apps "Dedicated Plan Management" charge when PEs are used. Only in WAF mode. |
| Cosmos DB **serverless** (#13) | **LOW / ~0** | "charged only for the RUs your operations consume and for storage … no minimum charge." Idle ≈ stored-GB only (cents). |
| Backend Container App (#16) | **LOW / ~0** | `minReplicas: 0` → "When a revision is scaled to zero replicas, no resource consumption charges are incurred." |
| Container Apps Environment — Consumption (#15) | **LOW / ~0** | Consumption workload profile has no baseline; billed per running-replica vCPU/GiB-second. ~0 when the only app is scaled to zero. |
| Storage Account LRS (#12) | **LOW** | Pay-per-GB + per-transaction. Idle = stored-GB only (cents). |
| AI Services / Speech / Content Safety **S0** (#7/#9/#10) | **USAGE-ONLY / ~0** | S0 accounts have no per-resource baseline; charge only on actual calls (tokens / STT minutes / AnalyzeText). |
| Model deployments (#7a–c) | **USAGE-ONLY / ~0** | GlobalStandard/Standard = token-billed, not provisioned. Idle = $0 (a runaway token job would be *usage*, not idle). |
| Log Analytics + App Insights (#2/#3) | **USAGE-ONLY** (and **not deployed** by default) | Per-GB ingestion. Gated off by `enableMonitoring=false` default. |
| VNet / DNS / Event Grid | **~0 / free** | VNet+NSG free; DNS pennies; Event Grid 100k ops/mo free. |

## Q3 — Ranked top overnight cost drivers

**Default cosmosdb profile (most likely shared-dev deployment):**

1. **Azure AI Search — Basic** (`srch-<suffix>`, `main.bicep` ~L903) — ~$73–75/mo flat, **no scale-to-zero**. Single biggest un-idleable cost.
2. **Function App always-ready instances** (`func-<suffix>`, `main.bicep` ~L2255) — ~$70–140/mo, 2 × 2 GB reserved 24/7, no free grant. Config-fixable.
3. **App Service Plan — B1** (`asp-<suffix>`, `main.bicep` ~L1998) — ~$13/mo flat, no scale-to-zero.
4. **Container Registry — Basic** (`cr<suffix>`, `main.bicep` ~L1793) — ~$5/mo flat, no scale-to-zero.
5. (everything else ≈ $0 idle: Cosmos serverless, Container App scale-to-zero, Storage, S0 AI accounts.)

Approx. default flat overnight burn ≈ **$140–210/mo ≈ $5–7/day** (Search + Functions always-ready + B1 plan + ACR), before any token/STT usage.

**postgresql profile:** swap driver #1 (AI Search, not deployed) for **PostgreSQL Flex B2s** (~$35–40/mo). Net: cheaper flat baseline than cosmosdb *and* the Postgres server can be stopped — but Functions always-ready + B1 plan + ACR still bill 24/7.

**WAF profile (`main.waf.parameters.json`, all four flags true):** dramatically higher — adds **Bastion Standard (~$140+/mo)**, multiple private endpoints, **App Service Plan P1v3 × 3 workers**, **AI Search standard × 3 replicas**, **provisioned (non-serverless) Cosmos with failover**, **Postgres GeneralPurpose D4ds_v5 + zone-redundant HA**, and Log Analytics at 90-day retention. Overnight burn here is many multiples of the dev profile. If the shared sub is on the WAF profile, that alone explains a fast budget-cap trip.

## Q4 — Cheapest idle-reduction lever per driver (without teardown)

| Driver | Lever WITHOUT teardown | Does Bicep already do the cheap thing? |
|--------|------------------------|----------------------------------------|
| AI Search Basic | **None via config** — Basic has no stop and no scale-to-zero. The only non-delete option is to keep it (it is already the cheapest billable tier; `enableScalability=false` already selects `basic` over `standard`). | ✅ already on the cheapest tier (`basic`, 1 replica, 1 partition, semantic=free). No cheaper idle lever exists short of deleting it. |
| Function always-ready | **Set always-ready to 0** so Flex Consumption scales to zero (accepts cold start on the first queued blob/message). Edit `alwaysReady` to `[]` in `main.bicep` ~L2255 (or make it conditional, e.g. only warm when `enableScalability`). | ❌ Bicep **hard-codes** 2 always-ready instances unconditionally — this is the one default that is NOT cheap-when-idle and is the easiest win. |
| App Service Plan B1 | **None meaningful** — B1 is near the floor; Basic cannot scale to zero. (F1 Free can't run the uvicorn build-from-source frontend reliably and has quotas.) To truly idle it you must delete the plan + web app. | ✅ already B1 (cheapest non-free tier that supports the frontend). No cheaper idle lever. |
| Container Registry Basic | **None** — Basic is the floor; no scale-to-zero. At ~$5/mo it is usually not worth touching. | ✅ already Basic. |
| Cosmos / Container App / Storage / S0 accounts | Already scale-to-zero or pay-per-use; nothing to do. | ✅ Cosmos serverless, backend `minReplicas: 0`, S0 accounts — all already cheapest-when-idle. |
| (postgresql) Postgres B2s | **Stop the server** nightly (`az postgres flexible-server stop -g <RESOURCE_GROUP> -n psql-<SUFFIX>`); it auto-restarts after 7 days, so re-stop daily or restart each morning. Not expressible in scale config. | ✅ already Burstable B2s (cheapest tier); stop is an operational action, not a Bicep setting. |

## Q5 — Resources that CANNOT be cheaply idled (argue for full teardown)

These keep billing 24/7 and have **no config-level scale-to-zero / stop** path, so they cannot be "idled" — only deleted:

- **Azure AI Search (Basic)** — no stop, no scale-to-zero. *(cosmosdb mode)*
- **App Service Plan (B1)** — no scale-to-zero.
- **Container Registry (Basic)** — no scale-to-zero (cheap, but flat).
- **Bastion (Standard)** — flat hourly, no idle state *(WAF mode only)*.
- **Private endpoints** — flat hourly each *(WAF mode only)*.

Partially idle-able-but-not-via-scale-config:
- **PostgreSQL Flexible Server** — can be *stopped* (operational `az` call), not scaled to zero. *(postgresql mode)*

Because AI Search Basic + the App Service Plan (both in the **default** profile) have no scale-to-zero, **you cannot reach ~$0 overnight by scale settings alone** — you must delete those resources or tear the whole environment down.

## Q6 — Parameter / azd-default cross-check

`v2/infra/main.parameters.json` (the file `azd up` uses by default) and `v2/azure.yaml` typed prompts both default to the **cheapest** profile:

| Param | Default (`main.parameters.json` / `azure.yaml`) | Cost effect |
|-------|--------------------------------------------------|-------------|
| `databaseType` | `cosmosdb` | Cosmos **serverless** + AI Search **basic** (no Postgres). |
| `enableMonitoring` | **false** | Log Analytics + App Insights **not deployed**. |
| `enableScalability` | **false** | Search **basic** (not standard), App Service Plan **B1** (not P1v3), Container App **minReplicas 0**, Postgres **B2s** (not D4), Functions max 40 (not 100). |
| `enableRedundancy` | **false** | Cosmos **serverless** (not provisioned), Storage **LRS** (not ZRS), Search **1 replica**, App Service Plan **1 worker**, LA retention **30d**, no zone redundancy/failover. |
| `enablePrivateNetworking` | **false** | **No VNet, no private endpoints, no Bastion.** |
| model `*DeploymentType` | GlobalStandard / Standard | token-billed, **$0 idle**. |
| `ingestionTrigger` | `direct_enqueue` | no extra cost. |

`v2/infra/main.waf.parameters.json` flips all four WAF flags to **true** — i.e., the expensive profile (Bastion, private endpoints, P1v3×3, Search standard×3, provisioned Cosmos, D4 Postgres, 90-day LA). This file is selected only if the operator points azd at it; the default `azd up` uses `main.parameters.json` (cheap profile).

**No azd env override layer raises SKUs beyond these defaults.** Every SKU/capacity is either a `main.parameters.json` default or a Bicep `enable*`-flag ternary; there is no separate `.env`-baked SKU bump. So the only way the dev sub is on expensive SKUs is if someone set `AZURE_ENV_ENABLE_*=true` in the azd env (check `azd env get-values`) or deployed with the WAF parameters file.

## Recommendation — scale-to-zero vs nightly `azd down`

**Recommendation: full nightly `azd down --purge` + morning `azd up`** for a shared dev subscription with a hard budget cap, *unless* the morning rebuild time is operationally unacceptable.

Why not "scale to zero overnight":
- The default profile's #1 and #3 flat billers — **AI Search Basic** and **App Service Plan B1** — have **no scale-to-zero or stop**. The best you can do via config is: set Function always-ready to 0 (real win), confirm Container App `minReplicas: 0` (already default), and rely on Cosmos serverless. That still leaves **Search + B1 plan + ACR** billing 24/7 (~$90/mo floor), which is exactly the always-on accrual that trips a small dev cap.

Why `azd down --purge`:
- It zeroes the un-idleable resources (Search, App Service Plan, ACR) to a true $0 overnight.
- The deployment is **single-tenant, re-seedable dev data**: `postprovision` recreates pgvector/schema, `postdeploy` re-seeds sample documents + Foundry IQ KB, and `azd deploy` rebuilds/pushes images. A morning `azd up` reconstitutes a working environment hands-free.
- **Use `--purge`**, not bare `azd down`: the AI Services, Speech, and Content Safety accounts are Cognitive Services resources with **soft-delete**; without purge, a same-name re-provision the next morning can hit soft-deleted-name conflicts.

Costs / caveats of the teardown approach (call out to the user):
- **Rebuild time** each morning: `azd up` provision + image build/push + sample re-seed (roughly 15–40 min, mostly unattended). If the team needs the env instantly at 9am, schedule the morning `azd up` earlier or accept a wait.
- **Ephemeral data loss**: `azd down` destroys Storage (uploaded test docs in the `documents` container) and Cosmos/Postgres (chat history). Fine for dev; do **not** run on anything holding data you care about.
- **Reused-resource danger**: if this env was deployed with `existingSearchName` / `existingCosmosName` / `existingStorageName` (v1-coexistence reuse path), confirm those are empty before `azd down` so it doesn't touch v1 resources. A fresh v2-only deploy has them blank → safe.

Middle path (if nightly teardown is too disruptive): keep the RG up but (a) edit `main.bicep` to make Function `alwaysReady` conditional on `enableScalability` (set to `[]` by default) — the single biggest "free" idle saving and a genuine Bicep improvement worth landing regardless; (b) nightly **delete only** the un-idleable flat billers (`srch-<suffix>` AI Search, `asp-<suffix>` plan + frontend web app) via `az ... delete`, keeping Cosmos data, Storage docs, and the ACR image so the morning re-provision is fast; (c) leave Cosmos serverless + Container App scale-to-zero as-is. This is fiddlier and not azd-native, but avoids a full rebuild.

If the sub is actually on the **WAF profile**, the answer is unambiguous: tear it down nightly (Bastion alone burns more than the entire dev profile), or stop using the WAF profile for a shared dev sub.

## Evidence / sources

- `v2/infra/main.bicep` — full resource inventory (lines cited per row in Q1).
- `v2/infra/main.parameters.json` — default (cheap) profile; all four WAF flags default false; model deployment SKUs GlobalStandard/Standard.
- `v2/infra/main.waf.parameters.json` — WAF profile; all four flags true.
- `v2/azure.yaml` — typed-prompt defaults (databaseType=cosmosdb, all enable* flags false); services backend/frontend/function; post-provision + post-deploy seeding hooks.
- `v2/infra/modules/ai-project.bicep` — Foundry Project is a control-plane child (no meter).
- grep over `v2/infra/**` — confirms no NAT Gateway / Azure Firewall / DDoS plan; the only public IP is the Bastion IP (WAF-only).
- [Azure AI Search — pricing model & tiers](https://learn.microsoft.com/en-us/azure/search/search-sku-tier): Dedicated (Basic/Standard) billing "becomes a *fixed cost* of running the service around the clock"; SU = replicas × partitions, hourly rate. (No scale-to-zero on Dedicated tiers.)
- [Azure Functions Flex Consumption plan](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan): always-ready billing = "total memory provisioned across all always-ready instances (baseline) … **no free grants**"; scale-to-zero supported when always-ready = 0; 2048 MB instance = 1 vCPU.
- [Billing in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/billing): "When a revision is scaled to zero replicas, no resource consumption charges are incurred"; Consumption profile has no environment baseline; private endpoints incur a Dedicated Plan Management charge.
- [Azure Cosmos DB serverless](https://learn.microsoft.com/en-us/azure/cosmos-db/serverless): "charged only for the RUs your operations consume and for storage … no minimum charge."

## Clarifying questions

1. **Which profile is actually deployed on the shared sub?** Run `azd env get-values | grep -E "AZURE_ENV_ENABLE_|AZURE_ENV_DATABASE_TYPE"`. If any `AZURE_ENV_ENABLE_*=true` (or the WAF parameters file was used), the overnight burn is far higher than the default-profile numbers above and full teardown is clearly justified.
2. **Is morning rebuild latency acceptable?** A nightly `azd down --purge` + morning `azd up` is the cleanest path to ~$0, but costs ~15–40 min of mostly-unattended rebuild + re-seed each morning. If the team needs the env live the instant they start, we should schedule the morning `azd up` ahead of work hours or use the middle-path selective-delete instead.
3. **Any data in the env worth keeping overnight?** `azd down` destroys Storage docs + chat history. If yes, the teardown approach needs a data-export step first (or use the selective-delete middle path that preserves Cosmos/Storage).
4. **cosmosdb or postgresql mode?** Confirms whether the #1 flat biller is AI Search Basic (cosmosdb) or Postgres B2s (postgresql) — the latter can be *stopped* nightly without a full teardown.
