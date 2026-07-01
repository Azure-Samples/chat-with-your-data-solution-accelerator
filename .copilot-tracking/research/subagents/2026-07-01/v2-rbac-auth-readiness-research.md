<!-- markdownlint-disable-file -->
# Research: CWYD v2 — RBAC + Authentication Readiness for Fresh-Tenant Deploy

Status: Complete
Date: 2026-07-01
Scope: READ-ONLY. Verify (a) bicep RBAC role assignments are complete so the shared UAMI can reach every Azure resource each runtime uses, and (b) end-user auth (Easy Auth / Entra) is wired for a brand-new tenant/subscription deploy.
Baseline: .copilot-tracking/research/subagents/2026-06-25/v2-infra-current-state.md
Files reviewed: v2/infra/main.bicep (~2560 lines), v2/infra/modules/ai-project.bicep, v2/infra/modules/ai-project-search-connection.bicep, v2/src/backend/core/settings.py, v2/src/backend/dependencies.py, v2/docs/bugs.md, v2/docs/development_plan.md §0.1, v2/docs/worklog/2026-06-29..30.md.

---

## TL;DR — the headline finding

**The 2026-06-25 baseline is STALE.** All three RBAC/endpoint gaps it reported have since been back-ported into `v2/infra/main.bicep` and are present in the current tree:

1. **Cognitive Services User on the Foundry AI Services account — CLOSED.** Granted at main.bicep:611-615 inside the `aiServices` module `roleAssignments` array (baseline said it was on Content Safety only).
2. **`AZURE_AI_SERVICES_ENDPOINT` on both runtimes — CLOSED.** Present on the backend Container App env (main.bicep:1871) and the Function App appSettings (main.bicep:2276).
3. **`ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME` env-name mismatch — CLOSED.** Backend now emits `CWYD_ORCHESTRATOR_NAME` with a mode-correct value (main.bicep:1933).

Net: **the shared UAMI's RBAC is complete for a fresh-tenant `azd up`** — every data-plane operation each runtime performs maps to a granted role on the right scope. The one thing that is **NOT** wired is **end-user authentication** (Easy Auth / Entra) — it is scaffolded in backend code but shipped OFF by design (anonymous default). See §Authentication.

---

## Q1 — Full RBAC role-assignment table (v2/infra/main.bicep)

Every role assignment in the fresh-tenant (`!useExisting*`) path plus the reuse-path equivalents. `useExisting*` vars all derive from empty `existing*Name` params (main.bicep:125-129) → **all false on a brand-new tenant**, so the new-resource `roleAssignments` arrays (with their inline role lists) are the ones that run.

Role GUID legend (declared in bicep):
- Cognitive Services OpenAI User = `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` (`cognitiveServicesOpenAiUserRoleId`, main.bicep:131-133)
- Storage Queue Data Message Sender = `c6a89b2d-59bc-44d0-9896-0f6e12d7b80a` (`storageQueueDataMessageSenderRoleId`, main.bicep:2161)
- Storage Blob Data Owner = `b7e6dc6d-f1e8-4753-8033-0f276bb0955b` (`storageBlobDataOwnerRoleId`, main.bicep:2162)

| # | Role (name) | Role GUID | Assignee (principal) | Scope resource | Line | Gating condition |
|---|---|---|---|---|---|---|
| 1 | Monitoring Metrics Publisher | (name string) | UAMI | Application Insights | 348-353 | `if (enableMonitoring)` |
| 2 | Cognitive Services OpenAI User | 5e0bd9bd… | UAMI | AI Services (Foundry) account `aisa-<suffix>` | 597-603 | always (new account) |
| 3 | Azure AI User | 53ca6127-db72-4b80-b1b0-d745d6d5456d | UAMI | AI Services (Foundry) account | 604-609 | always |
| 4 | **Cognitive Services User** | **a97b65f3-24c7-4388-baec-2e87135dc908** | **UAMI** | **AI Services (Foundry) account** | **610-616** | **always** (was the baseline gap; now present) |
| 5 | Cognitive Services OpenAI User | 5e0bd9bd… | UAMI | reused v1 OpenAI account | 703-712 | `if (useExistingOpenAi)` |
| 6 | Azure AI User | 53ca6127… | UAMI | Foundry **Project** scope | ai-project.bicep:64-77 | always (module) |
| 7 | Cognitive Services Speech User | f2dc8367-1007-4938-bd23-fe263f013447 | UAMI | Speech account `spch-<suffix>` | 788-795 | always |
| 8 | Cognitive Services User | a97b65f3… | UAMI | **Content Safety** account `cs-<suffix>` | 863-870 | always |
| 9 | Search Index Data Contributor | 8ebe5a00-799e-43f5-93ac-243d3dce84a7 | UAMI | Search service `srch-<suffix>` | 926-932 | `databaseType=='cosmosdb' && !useExistingSearch` |
| 10 | Search Service Contributor | 7ca78c08-252a-4471-8644-bb5ff32d4ba0 | UAMI | Search service | 933-938 | cosmos, new search |
| 11 | Search Index Data Reader | 1407120a-92aa-4202-b7e9-c0e197c71c8f | Foundry Project MI | Search service | 939-944 | cosmos, new search |
| 12 | Search Service Contributor | 7ca78c08… | Foundry Project MI | Search service | 945-951 | cosmos, new search |
| 13 | Search Index Data Reader | 1407120a… | **deployer** | Search service | 952-957 | cosmos, new search (seed self-check reads index count) |
| 14 | Search Index Data Contributor | 8ebe5a00… | UAMI | existing Search service | 996-1004 | `cosmos && useExistingSearch` |
| 15 | Search Service Contributor | 7ca78c08… | UAMI | existing Search | 1006-1014 | cosmos, reuse |
| 16 | Search Index Data Reader | 1407120a… | Foundry Project MI | existing Search | 1016-1024 | cosmos, reuse |
| 17 | Cognitive Services OpenAI User | 5e0bd9bd… | **Search service system MI** | Foundry account | 1042-1052 | `cosmos && !useExistingSearch && !useExistingOpenAi` (KB query-planning model call) |
| 18 | Cognitive Services OpenAI User | 5e0bd9bd… | Search service system MI | reused v1 OpenAI account | 1054-1064 | `cosmos && !useExistingSearch && useExistingOpenAi` |
| 19 | Storage Blob Data Contributor | ba92f5b4-2d11-453d-a403-e96b0029c9fe | UAMI | Storage account `st<suffix>` | 1160-1166 | `!useExistingStorage` |
| 20 | Storage Queue Data Contributor | 974c5e8b-45b9-4653-ba55-5f855dd0fb88 | UAMI | Storage account | 1167-1172 | new storage |
| 21 | Storage Account Contributor | 17d1049b-9a84-46fb-8f53-869881c3d3ab | UAMI | Storage account | 1173-1178 | new storage |
| 22 | Storage Blob Data Contributor | ba92f5b4… | **deployer** | Storage account | 1179-1184 | new storage (seed docs) |
| 23 | Storage Queue Data Message Sender | c6a89b2d… | **deployer** | Storage account | 1185-1190 | new storage (seed enqueue) |
| 24 | Storage Blob Data Contributor | ba92f5b4… | UAMI | existing Storage | 1318-1326 | `useExistingStorage` |
| 25 | Storage Queue Data Contributor | 974c5e8b… | UAMI | existing Storage | 1329-1337 | reuse |
| 26 | Storage Account Contributor | 17d1049b… | UAMI | existing Storage | 1340-1348 | reuse |
| 27 | Cosmos DB Built-in Data Contributor | 00000000-0000-0000-0000-000000000002 | UAMI | Cosmos account (data-plane SQL role) | 1404-1409 | `cosmos && !useExistingCosmos` |
| 28 | Cosmos DB Built-in Data Contributor | 00000000…0002 | UAMI | existing Cosmos account | 1468-1475 | `cosmos && useExistingCosmos` |
| 29 | (Postgres) Entra administrator | n/a (admin, not RBAC) | UAMI (`id-<suffix>`) | Postgres Flexible Server | 1543-1548 | `databaseType=='postgresql'` |
| 30 | (Postgres) Entra administrator | n/a | deployer principal | Postgres Flexible Server | 1549-1558 | postgres, if `postgresAdminPrincipalId` set |
| 31 | AcrPull | 7f951dda-4ed3-4680-a7ca-43fe172d538d | UAMI | Container Registry `cr<suffix>` | 1766-1771 | always |
| 32 | Storage Blob Data Owner | b7e6dc6d… | UAMI | Storage account (Flex pkg pull) | 2331-2338 | always (`flexDeploymentRole`) |
| 33 | Storage Queue Data Message Sender | c6a89b2d… | **Event Grid system topic MI** | Storage account | 2380-2391 | `!useExistingEventGridTopic` |
| 34 | Storage Queue Data Message Sender | c6a89b2d… | UAMI | existing Storage (reused EG path) | 2466-2473 | `useExistingEventGridTopic` |

Notes:
- **Six principals** receive grants: the shared UAMI (`id-<suffix>`), the Foundry **Project** system MI, the Search service system MI, the Event Grid system-topic MI, the **deployer** (for post-provision sample-doc seeding + index self-check), and (monitoring only) the UAMI on App Insights.
- **Postgres uses the Entra-admin model, not an RBAC role** — the UAMI is set as a Postgres AD administrator (main.bicep:1543-1548), which is why there is no `roleAssignments` entry for Postgres data access.
- Quoted bicep for the four key/previously-contested assignments is in §Q3.

---

## Q2 — Required-vs-granted gap table (operation → identity → role → scope → status)

Data-plane operations were derived from: settings.py submodels (FoundrySettings, OpenAISettings, DatabaseSettings, StorageSettings, SpeechSettings, ContentSafety), the provider domains under `v2/src/backend/core/providers/**` (credentials, llm/foundry_iq, embedders, parsers, search, databases), the Functions blueprints under `v2/src/functions/**`, and the confirmed root-causes in bugs.md (BUG-0034/0052/0057/0059/0070/0073).

| Operation | Runtime(s) | Identity | Required role | Scope | Granted? | Line |
|---|---|---|---|---|---|---|
| OpenAI chat + reasoning inference | backend | UAMI | Cognitive Services OpenAI User | Foundry account (or reused OAI) | ✅ | 602 / 709 |
| Query/ingest embeddings (`/openai/v1/embeddings` on the AI Services account) | backend + function | UAMI | Cognitive Services OpenAI User | Foundry account | ✅ | 602 |
| Foundry Project / Agents (agent_framework) | backend | UAMI | Azure AI User | account + Project | ✅ | 608 + ai-project.bicep:64 |
| Document Intelligence + Content Understanding parsing | function (backend guards) | UAMI | **Cognitive Services User** | Foundry account | ✅ | **615** |
| AI Search retrieval (langgraph chat + admin list) | backend | UAMI | Search Index Data Contributor | Search service | ✅ | 931 |
| AI Search index/indexer mgmt + admin delete | backend | UAMI | Search Service Contributor | Search service | ✅ | 937 |
| AI Search vector write (indexing pipeline) | function | UAMI | Search Index Data Contributor (+ Service Contributor) | Search service | ✅ | 931 / 937 |
| Foundry IQ KB retrieval (server-side, agent_framework) | Foundry Project MI | Project MI | Search Index Data Reader + Search Service Contributor | Search service | ✅ | 943 / 950 |
| Foundry IQ KB query-planning model call | Search service MI | Search MI | Cognitive Services OpenAI User | Foundry (or reused OAI) account | ✅ | 1049 / 1061 |
| Cosmos chat-history read/write | backend | UAMI | Cosmos DB Built-in Data Contributor | Cosmos account | ✅ | 1408 |
| Postgres chat-history + pgvector read/write | backend + function | UAMI | Entra admin (not RBAC) | Postgres server | ✅ | 1545 |
| Blob read/write (upload, file download, ingest) | backend + function | UAMI | Storage Blob Data Contributor (+ Blob Data Owner) | Storage account | ✅ | 1165 / 2335 |
| Queue send (enqueue doc-processing) | backend | UAMI | Storage Queue Data Contributor | Storage account | ✅ | 1171 |
| Queue receive/consume (doc-processing trigger) | function | UAMI | Storage Queue Data Contributor | Storage account | ✅ | 1171 |
| AzureWebJobsStorage (Flex host + package pull) | function | UAMI | Blob Data Owner + Queue Data Contributor + Account Contributor | Storage account | ✅ | 2335 / 1171 / 1177 |
| Event Grid → blob-events queue delivery | EG system-topic MI | EG MI | Storage Queue Data Message Sender | Storage account | ✅ | 2389 |
| Speech token mint (`aad#` token → recognition) | backend | UAMI | Cognitive Services Speech User | Speech account | ✅ | 794 |
| Content Safety AnalyzeText (prompt shield) | backend | UAMI | Cognitive Services User | Content Safety account | ✅ | 869 |
| ACR image pull | backend Container App + frontend Web App + Function App | UAMI | AcrPull | Container Registry | ✅ | 1769 |
| App Insights telemetry ingest | backend + function | UAMI | Monitoring Metrics Publisher | App Insights | ✅ (monitoring on) | 352 |

**No RBAC gaps for the shared UAMI.** Every data-plane call each runtime makes has a matching grant on the correct scope. (BUG-0055 — App Insights telemetry never arriving — is an SDK/exporter-init defect, **not** an RBAC gap; the Monitoring Metrics Publisher role is present.)

---

## Q3 — Cognitive Services User on the Foundry account: CONFIRMED PRESENT (baseline gap CLOSED)

The baseline reported this role granted **only** on Content Safety. The current bicep grants it on **both** the Foundry account and Content Safety.

Foundry account (`aiServices` module, main.bicep:610-616):
```bicep
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Cognitive Services User -- data-plane access for DocumentIntelligence
        // + Content Understanding calls against the AI Services account.
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908'
      }
```

Content Safety account (`cogContentSafety` module, main.bicep:864-870):
```bicep
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Cognitive Services User — data-plane role for the AnalyzeText
        // call used by `ContentSafetyGuard.screen()`.
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908'
      }
```

**UAMI roles on the Foundry account today (main.bicep:597-616):** Cognitive Services OpenAI User (602) + Azure AI User (608) + **Cognitive Services User (615)**. This is exactly the set BUG-0052 said to add; the durable back-port has landed.

---

## Q4 — AZURE_AI_SERVICES_ENDPOINT env: CONFIRMED PRESENT on BOTH runtimes (baseline gap CLOSED)

Backend Container App env (main.bicep:1869-1871):
```bicep
            // AI Services / Foundry account endpoint -- the data-plane base
            // for DocumentIntelligence + Content Understanding calls.
            { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiServices.outputs.endpoint }
```

Function App appSettings (main.bicep:2274-2276):
```bicep
          // AI Services / Foundry account endpoint -- the data-plane base
          // for DocumentIntelligence + Content Understanding calls.
          { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiServices.outputs.endpoint }
```

Code contract (what reads it / what breaks if absent):
- `FoundrySettings` reads env prefix `AZURE_AI_`, field `services_endpoint` (settings.py:154-161). Default is `""`.
- `DocumentIntelligenceParser._get_client` builds its endpoint from `settings.foundry.services_endpoint`; when empty it yields endpoint `"/"`, and the Azure SDK bearer-token policy rejects auth on the non-HTTPS URL → every PDF/Office parse throws → poison queue (bugs.md BUG-0034 detail, line 93/695-699; the parser doc note at parsers/base.py:57 and functions/core/parsers/document_intelligence_parser.py:23).
- `FoundryIQ._get_embeddings_client()` targets `AZURE_AI_SERVICES_ENDPOINT` + `/openai/v1` for embeddings (foundry_iq.py:275-281; bugs.md BUG-0057). Empty endpoint → embedding 404/auth failure.
- Backend upload guard `services/ingestion.py:195` returns an honest 503 when `AZURE_AI_SERVICES_ENDPOINT` is unset/non-HTTPS (BUG-0034 unit-d).

Bonus (also fixed, related class): `CWYD_ORCHESTRATOR_NAME` is now emitted mode-correctly (main.bicep:1933): `value: databaseType == 'postgresql' ? 'langgraph' : 'agent_framework'`. The old dead `ORCHESTRATOR` var is gone.

---

## Q5 — End-user authentication: SCAFFOLDED IN CODE, SHIPPED OFF (anonymous by design; opt-in)

This is the **one real "authorization" area that a fresh deploy does NOT turn on**. It is deliberate (MACAE-faithful anonymous default), not a bug — but the user should know the deployed app is **open** out of the box.

### Infra posture (both fronts explicitly OFF)

Frontend App Service — Easy Auth **declaratively disabled** (main.bicep:2050-2069):
```bicep
    // Frontend Easy Auth declaratively disabled so the public profile
    // serves the SPA anonymously (the FastAPI backend owns auth). ...
    configs: [
      {
        name: 'authsettingsV2'
        properties: {
          globalValidation: {
            requireAuthentication: false
            unauthenticatedClientAction: 'AllowAnonymous'
          }
          platform: { enabled: false }
        }
      }
    ]
```

Backend Container App — **no `authConfigs` sub-resource at all** (grep for `Microsoft.App/containerApps/authConfigs` / `authConfig` returns only the Postgres `authConfig` at main.bicep:1537 and the frontend `authsettingsV2` above). The backend admin auth wall is **off** by default (main.bicep:1858-1866):
```bicep
            // Admin auth wall (AppSettings.require_admin_auth). 'false' (the
            // MACAE-faithful default) leaves /api/admin/* reachable without
            // Easy Auth claims. ...
            { name: 'AZURE_REQUIRE_ADMIN_AUTH', value: 'false' }
```

### Code posture (fully implemented, waiting for headers)

The backend is written to consume App Service / Container Apps Easy Auth headers when they exist (dependencies.py:280-430+):
- `x-ms-client-principal-id` (`_PRINCIPAL_ID_HEADER`, dependencies.py:314) → the caller's Entra oid → `get_user_id` (dependencies.py:346) → per-user chat-history partition.
- `x-ms-client-principal` (`_PRINCIPAL_HEADER`, dependencies.py:315) → base64 JSON claims blob → `_decode_easy_auth_principal` + `_extract_roles` → the `requires_role("admin")` factory (admin gate), accepting both `typ="roles"` and the full schema-URI role claim.
- **Fail-open logic:** `get_user_id` folds a missing principal-id header into the synthetic `local-dev` partition when `environment == Environment.LOCAL` **OR** `not require_admin_auth`. In production with `require_admin_auth=True` a missing header → 401. Because bicep pins `AZURE_ENVIRONMENT=production` (main.bicep:1856, the BUG-0069 fix) **and** `AZURE_REQUIRE_ADMIN_AUTH=false`, a fresh cloud deploy runs **anonymous but production-mode** — chat callers all share the `local-dev` partition, and `/api/admin/*` is reachable without claims. The admin **role** check still fails closed whenever a claims blob IS present (the flag only relaxes the wall, never role enforcement).
- Security note (BUG-0046): the browser-forwarded principal-id is **not** a trust boundary (chat partitioning only); admin RBAC stays anchored on the server-injected claims blob, which the SPA deliberately never forwards.

### Classification

**(c) Absent by design / opt-in — not wired in infra, expected to be enabled post-deploy.** To enforce real end-user auth an operator must, out-of-band: (1) enable App Service / Container Apps Easy Auth with an Entra app registration (identity provider, clientId, issuer) on the frontend and/or backend; (2) flip `AZURE_REQUIRE_ADMIN_AUTH=true`; (3) assign the app-role that `requires_role("admin")` checks to admin users. There is **no Entra app registration, no clientId, and no identity-provider block anywhere in `v2/infra/**`** — grep confirms the only `clientId` values are the UAMI `clientId` used for managed-identity auth (main.bicep:1844-1845, 2266-2267), not an auth app registration. No auth ADR/runbook exists under `v2/docs/` (file search for `*auth*` returned nothing; the design rationale lives inline in the bicep comments + dependencies.py docstrings + bugs.md BUG-0046/0047).

---

## Q6 — bugs.md + dev_plan §0.1 cross-reference

### bugs.md (v2/docs/bugs.md)

The infra RBAC/endpoint defects were all found + live-fixed 2026-06-16/17 and the durable bicep back-port was noted as "pending (bicep paused)". **The back-ports have since landed** (bicep was un-paused; BUG-0069 explicitly says "Bicep wired 2026-06-22", and the cloud was deploying successfully on 2026-06-29). Current-bicep verification:

| Bug | Defect | Durable bicep back-port | Landed in current bicep? |
|---|---|---|---|
| BUG-0051 (line 110) | Storage env vars missing on backend Container App | mirror 3 storage vars onto backend env | ✅ main.bicep:1931-1933 (`AZURE_STORAGE_ACCOUNT_NAME`/`_DOCUMENTS_CONTAINER`/`_DOC_PROCESSING_QUEUE`) |
| BUG-0052 (line 111) | `AZURE_AI_SERVICES_ENDPOINT` on neither runtime + UAMI missing Cognitive Services User on Foundry | env var on both runtimes + role assignment | ✅ endpoint 1871 + 2276; role 615 |
| BUG-0059 (line, `back-port … pending`) | `AZURE_AI_SEARCH_CONNECTION_NAME` = wrong (`search-srch-…`, no MCP audience) → agent_framework KB 401 | point env var at the `cwyd-kb-mcp` RemoteTool connection + create it + Project-MI Search Service Contributor | ⚠️ **PARTIAL** — env var value now `'${searchKnowledgeBaseName}-mcp'` = `cwyd-kb-mcp` (main.bicep:1917) and Project MI **does** get Search Service Contributor (950); but the `aiProjectSearchConnection` module still creates a `CognitiveSearch`/bare-`AAD` connection named `search-<searchServiceName>` (ai-project-search-connection.bicep:38-58), **not** a `cwyd-kb-mcp` RemoteTool connection with `audience: https://search.azure.com`. The `cwyd-kb-mcp` connection appears to be created by `post_provision.py`'s KB seed, not bicep. See §Residual. |
| BUG-0061 | Event Grid subscription preflighted before its MI role existed | split subscription out of the topic module, `dependsOn` the role | ✅ standalone subscription + `eventGridQueueSenderRole` (main.bicep:2380-2391, and the standalone `blobCreatedSubscription` note ~2396) |
| BUG-0062 | Storage `networkAcls.defaultAction=Deny` blocked Flex pkg upload | flip to `Allow` on the no-private-net profile | ✅ main.bicep:1927 `defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'` |
| BUG-0063 | `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` wired to human deployer UPN, not UAMI | set to `id-<suffix>` | ✅ backend 1918 + function 2262 (`id-${solutionSuffix}`) |
| BUG-0064 | `ORCHESTRATOR` env name wrong + hardcoded value | rename to `CWYD_ORCHESTRATOR_NAME`, mode-conditional value | ✅ main.bicep:1933 |
| BUG-0069 | `AZURE_ENVIRONMENT` unset → cloud reported `local` (admin bypass risk) | set `production` on both runtimes | ✅ backend 1856 + function 2269 |

**Still OPEN infra bugs (none are RBAC/auth gaps):** BUG-0054 (Event Grid single-trigger cutover — blocked only by a disabled subscription, worklog 2026-06-30), BUG-0055 (App Insights telemetry export unwired — observability, not RBAC), BUG-0058 (azd skips the prepackage hook on `deploy function` — packaging).

### dev_plan §0.1 debt queue (v2/docs/development_plan.md:98-…)

**No open row tracks a bicep RBAC/endpoint back-port.** Per Hard Rule #12/#19 the split is deliberate: §0.1 holds *phase debt/tasks*; *defects* (including the durable bicep fixes) live in `bugs.md`. §0.1's remaining open-ish items are Phase-6 Functions-pipeline units and the withdrawn/closed admin items (#35d cleared, #35g withdrawn by ADR 0024, #39 cleared). The `#39` row is the one that shipped the `requires_role("admin")` gate; it is ✅ cleared (2026-05-06).

---

## Residual / lower-priority items (not blocking RBAC readiness)

1. **BUG-0059 durable bicep completeness (agent_framework KB auth, cosmos mode only).** The backend is told the connection is `cwyd-kb-mcp` (main.bicep:1917) but the only Project↔Search connection **bicep** creates is the `CognitiveSearch`/AAD one named `search-<searchServiceName>` (ai-project-search-connection.bicep:38-58). If the `cwyd-kb-mcp` RemoteTool connection (audience `https://search.azure.com`) is created **only** by `post_provision.py`, then a fresh `azd up` depends on that hook running to avoid a repeat of the BUG-0059 401 at first agent_framework chat. **Not an RBAC gap** and **cosmos-mode-only** (postgres mode grounds app-side, no KB), but worth confirming the `cwyd-kb-mcp` connection is created idempotently by the post-provision seed. Recommend a follow-up read of `v2/scripts/post_provision.py` `_ensure_knowledge_base` to confirm it PUTs the `cwyd-kb-mcp` connection.
2. **End-user auth is opt-in** (§Q5). If the fresh-tenant deploy is expected to be access-controlled, the operator must enable Easy Auth + an Entra app registration + flip `AZURE_REQUIRE_ADMIN_AUTH=true`. There is no infra or doc for this today.

---

## Q7 — Fresh-tenant assumptions (brand-new tenant/subscription)

Concrete things a brand-new tenant/subscription must satisfy that the template assumes:

1. **Deployer must be Owner or User Access Administrator on the target scope.** The template creates **34 role assignments** (`Microsoft.Authorization/roleAssignments`) plus Cosmos SQL role assignments and Postgres AD-admin membership. `Contributor` alone **cannot** create role assignments — a fresh-tenant deployer with only Contributor will fail at the first `roleAssignments` write. Owner (or Contributor + User Access Administrator) is required.
2. **Deployer identity is used at runtime for seeding.** `deployerPrincipalId = deployer().objectId` / `deployerPrincipalType` (main.bicep:262-263) is granted Storage Blob Data Contributor + Queue Data Message Sender + Search Index Data Reader so the post-provision hook can seed sample docs and self-check the index. A service-principal deployer works (type auto-detected), but the SP must be the same identity that runs `azd`/`az` for the post-provision data-plane calls to authenticate.
3. **Resource-provider registration.** A brand-new subscription often has providers **unregistered**. This template touches: `Microsoft.ManagedIdentity`, `Microsoft.CognitiveServices` (AIServices + ContentSafety + SpeechServices), `Microsoft.Search`, `Microsoft.DocumentDB`, `Microsoft.DBforPostgreSQL`, `Microsoft.Storage`, `Microsoft.App` (Container Apps), `Microsoft.Web` (App Service + Functions), `Microsoft.ContainerRegistry`, `Microsoft.EventGrid`, `Microsoft.Insights` + `Microsoft.OperationalInsights` (monitoring), `Microsoft.Network` (private networking profile), `Microsoft.Authorization`. `azd`/ARM auto-registers most on first use, but **AI model quota** (below) and some providers can 409/`MissingSubscriptionRegistration` on a cold sub — a pre-flight `az provider register` sweep de-risks this.
4. **AI model capacity/quota.** New account deploys `gpt`, `reasoning`, and `embedding` model deployments on the Foundry account (main.bicep:565-596) with operator-set capacity. A fresh subscription has **default (often zero or low) TPM quota** for gpt-5/o-series + embeddings in the chosen region (`azureAiServiceLocation`, default `eastus2`). If quota is insufficient the deployment fails at model-deployment creation. Confirm quota before `azd up`.
5. **`azd auth login` / `az login` tenant + subscription selection.** For a brand-new tenant the deployer must `az login --tenant <new-tenant>` and select the new subscription (`azd env set AZURE_SUBSCRIPTION_ID …` or the `azd up` prompt). `subscription().tenantId` (used for `AZURE_TENANT_ID` and the Postgres `authConfig.tenantId`) resolves from the deployment context, so a wrong active tenant silently wires the wrong tenant id.
6. **Postgres mode extra requirement.** `databaseType=postgresql` **requires** `postgresAdminPrincipalName` (fail-fast guard at main.bicep:1533-1540). A fresh-tenant postgres deploy that omits it aborts template expansion by design.
7. **Region availability.** Foundry `AIServices` + the specific model versions + Container Apps Workload-Profile Consumption must all be available in the selected region; a brand-new tenant has no prior region enablement.

---

## Prioritized fixes (exact file+line targets)

Given the current state, **RBAC needs no changes** — the prioritized list is short and mostly verification/opt-in:

| Priority | Item | Action | File+line |
|---|---|---|---|
| P1 (verify) | Confirm the `cwyd-kb-mcp` RemoteTool Project↔Search connection is created idempotently by the post-provision seed (BUG-0059 residual, cosmos mode) | Read `_ensure_knowledge_base` and confirm it PUTs a connection named `cwyd-kb-mcp` with `audience: https://search.azure.com`; if not, add it to `v2/infra/modules/ai-project-search-connection.bicep` or the seed | v2/scripts/post_provision.py `_ensure_knowledge_base`; ai-project-search-connection.bicep:38-58 (connection block); consumed by main.bicep:1917 |
| P2 (decision) | Decide whether the fresh-tenant deploy should enforce end-user auth | If yes: add Easy Auth + Entra app registration to `v2/infra/**`, flip `AZURE_REQUIRE_ADMIN_AUTH` to `true`, and document the app-role assignment | main.bicep:1866 (`AZURE_REQUIRE_ADMIN_AUTH`), main.bicep:2050-2069 (frontend `authsettingsV2`), backend has no `authConfigs` today |
| P3 (pre-flight) | Ensure the deployer has Owner/UAA and providers+quota are ready on the new sub | `az provider register` sweep + quota check + `az role assignment` verification before `azd up` | operator step, no file |
| — | RBAC role assignments (UAMI + Project MI + Search MI + EG MI + deployer) | **No change needed — complete.** | main.bicep §Q1 table |
| — | `AZURE_AI_SERVICES_ENDPOINT`, Cognitive Services User on Foundry, `CWYD_ORCHESTRATOR_NAME`, storage env, `AZURE_ENVIRONMENT`, postgres admin name, EG role ordering, storage networkAcls | **No change needed — all back-ported.** | §Q6 table |

---

## Clarifying questions

1. Is the fresh-tenant deploy **intended to be anonymous/open** (the current MACAE-faithful default), or should end-user auth (Easy Auth + Entra) be enforced? This is the single biggest "is authorization ready" decision and is currently opt-in with no infra scaffolding.
2. Will the deploy run in **cosmosdb** or **postgresql** mode? Only cosmos mode uses the Foundry IQ KB path where the BUG-0059 `cwyd-kb-mcp` residual (P1) matters.

## Recommended follow-on research (not completed here)

- [ ] Read `v2/scripts/post_provision.py` `_ensure_knowledge_base` to confirm the `cwyd-kb-mcp` RemoteTool connection (audience `https://search.azure.com`) is created there — resolves the only open RBAC-adjacent question (BUG-0059 residual, P1).
- [ ] Confirm sample-data seeding actually uploads documents on a fresh `azd up` (the deployer got Blob/Queue seed roles at main.bicep:1179-1190; the 2026-06-29 worklog shows a frontend "seed prompt" — verify the hook path and that an empty-index deploy is no longer the default).
- [ ] Verify Foundry model quota + provider registration on the specific target subscription/region before `azd up` (Q7 items 3-4) — environment-specific, cannot be resolved from the repo.
