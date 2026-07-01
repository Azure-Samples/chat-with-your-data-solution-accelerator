<!-- markdownlint-disable-file -->
# CWYD v2 — Model Reference Inventory & Foundry Model-Retirement Audit

Research date: 2026-07-01
Scope: READ-ONLY. Enumerate every model reference under `v2/**`, cross-check each against the Microsoft Foundry model-retirement schedule, and recommend a fresh-deploy replacement matrix.

Status: Complete

---

## Executive summary

- The **deployable configuration** (bicep params + `main.parameters.json` + `main.waf.parameters.json` + `azure.yaml` + `.env.sample`) contains **ZERO `gpt-4*` literals**. It is already standardized on:
  - Chat: `gpt-5.1` / version `2025-11-13`
  - Reasoning: `o4-mini` / version `2025-04-16`
  - Embedding: `text-embedding-3-large` / version `1`
- **One deployable model is a retirement problem: `o4-mini`.** Per the schedule it is **Deprecated**, retirement **2026-10-16** (~3.5 months from today). Every other deployable model is GA with long runway.
- **`gpt-5.1` (chat) and `text-embedding-3-large` (embedding) are both current-GA with the longest runway** in their families (chat 2027-05-15, embedding 2027-04-15). Keep both.
- **All 56 `gpt-4*` references live in tests, docstrings, and docs** — never in deploy config. As *models*, every `gpt-4*` referenced (gpt-4o, gpt-4o-mini, gpt-4.1, GPT-4 Vision) is **Deprecated/retiring** (2026-10-01 / 2026-10-14) or already retired, but they are only fixture values / narrative, so they carry no runtime retirement risk.
- `gpt-4` count: **infra 0 · top-level v2 config 0 · src 2 (docstring examples) · tests 43 · docs 11 = 56 total.** Retiring/retired as models: 100% of the distinct model names referenced — but 0 in deployable config.

---

## 1. Foundry model-retirement schedule (fetched)

Source: <https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule>
Page `ms.date` 2026-04-23, `updated_at` 2026-06-05. Retrieved 2026-07-01.

### 1a. Azure OpenAI — chat / completions / reasoning rows relevant to CWYD

| Model | Version | Lifecycle | Retirement date | Replacement |
| --- | --- | --- | --- | --- |
| gpt-4o | 2024-05-13 | Deprecated | 2026-10-01 | gpt-5.1 |
| gpt-4o | 2024-08-06 | Deprecated | 2026-10-01 | gpt-5.1 |
| gpt-4o | 2024-08-06-ev3 | Deprecated | **2026-03-31 (already retired)** | gpt-5.1 |
| gpt-4o | 2024-11-20 | Deprecated | 2026-10-01 | gpt-5.1 |
| gpt-4o-mini | 2024-07-18 | Deprecated | 2026-10-01 | gpt-4.1-mini |
| gpt-4.1 | 2025-04-14 | Deprecated | 2026-10-14 | — |
| gpt-4.1-mini | 2025-04-14 | Deprecated | 2026-10-14 | — |
| gpt-4.1-nano | 2025-04-14 | Deprecated | 2026-10-14 | — |
| gpt-5 | 2025-08-07 | GA | 2027-02-06 | — |
| gpt-5-mini | 2025-08-07 | GA | 2027-02-06 | — |
| gpt-5-nano | 2025-08-07 | GA | 2027-02-06 | — |
| gpt-5-pro | 2025-10-06 | GA | 2027-04-07 | — |
| gpt-5-chat | 2025-08-07 | **Retired** | 2026-06-29 | gpt-chat-latest |
| gpt-5-chat | 2025-10-03 | **Retired** | 2026-05-13 | gpt-chat-latest |
| **gpt-5.1** | **2025-11-13** | **GA** | **2027-05-15** | — |
| gpt-5.1-chat | 2025-11-13 | **Retired** | 2026-06-29 | gpt-chat-latest |
| gpt-5.2 | 2025-12-11 | GA | 2026-12-12 | — |
| gpt-5.4 | 2026-03-05 | GA | 2027-03-05 | — |
| gpt-5.4-mini | 2026-03-17 | GA | 2027-03-18 | — |
| gpt-5.4-nano | 2026-03-17 | GA | 2027-03-18 | — |
| gpt-5.4-pro | 2026-03-05 | GA | 2027-03-06 | — |
| gpt-5.5 | 2026-04-24 | GA | 2027-04-23 | — |
| gpt-chat-latest | 2026-05-05 | Preview | 2026-11-05 | — |
| o1 | 2024-12-17 | Deprecated | 2026-07-15 | — |
| o1-pro | 2025-03-19 | GA | 2026-09-18 | — |
| o3 | 2025-04-16 | GA | 2026-10-16 | — |
| o3-mini | 2025-01-31 | Deprecated | 2026-08-02 | o4-mini |
| o3-pro | 2025-06-10 | GA | 2026-12-10 | — |
| **o4-mini** | **2025-04-16** | **Deprecated** | **2026-10-16** | — |

### 1b. Azure OpenAI — embeddings

| Model | Version | Lifecycle | Retirement date | Replacement |
| --- | --- | --- | --- | --- |
| text-embedding-ada-002 | 1 | GA | 2027-04-15 | — |
| text-embedding-ada-002 | 2 | GA | 2027-04-15 | — |
| text-embedding-3-small | 1 | GA | 2027-04-15 | — |
| **text-embedding-3-large** | **1** | **GA** | **2027-04-15** | — |

### 1c. Notable absences (already retired long ago, dropped from the current schedule)

- `gpt-4` (base 8k), `gpt-4-32k`, `gpt-4-turbo`, `gpt-35-turbo` / `gpt-3.5-turbo` families — **not present** on the current schedule (retired before this page revision). No occurrences of these exist in `v2/**` either (searched `gpt-35`, `gpt-3.5` → 0 hits in deployable/source; one legacy `GPT-*` mention in `development_plan.old.md`).

### 1d. Highlights

- Any `gpt-4o` / `gpt-4o-mini` / `gpt-4.1*` deployment retires between **2026-10-01 and 2026-10-14**; the `gpt-4o 2024-08-06-ev3` variant is **already retired (2026-03-31)**.
- The entire **`gpt-5.x` `-chat` line is Retired** (gpt-5-chat, gpt-5.1-chat, etc. → replaced by `gpt-chat-latest`). CWYD uses the **base** `gpt-5.1` (GA), **not** `gpt-5.1-chat` — correct choice.
- **o-series is shrinking:** `o1` retires 2026-07-15, `o3-mini` 2026-08-02, `o1-pro` 2026-09-18, `o3` and `o4-mini` 2026-10-16, `o3-pro` 2026-12-10. **No o-series model has runway past 2026-12.** For a dedicated reasoning slot with long runway, the `gpt-5.x` family (which is reasoning-capable) is the correct target.
- Embeddings are stable: all three embedding models (ada-002, 3-small, 3-large) are GA to **2027-04-15**.

---

## 2. Full model-reference inventory (`v2/**`)

Search tokens (case-insensitive): `gpt-4`, `gpt-4o`, `gpt-35`, `gpt-3.5`, `gpt-4.1`, `gpt-5`, `o1`, `o3`, `o4`, `text-embedding`, `ada`, `reasoning`, `modelName`, `deployment`, `ModelDeployment`, `chatModel`, `embeddingModel`. `package-lock.json` hits are base64 integrity-hash false positives and are excluded.

### 2a. Deployable configuration (the values that actually ship)

| File:line | Literal | Role | Status per schedule | Recommended |
| --- | --- | --- | --- | --- |
| v2/infra/main.bicep:143 | `param gptModelName string = 'gpt-5.1'` | chat name | **GA, retire 2027-05-15** | KEEP |
| v2/infra/main.bicep:146 | `param gptModelVersion string = '2025-11-13'` | chat version | matches gpt-5.1 GA | KEEP |
| v2/infra/main.bicep:153 | `gptModelDeploymentType = 'GlobalStandard'` | chat SKU | n/a | KEEP |
| v2/infra/main.bicep:157 | `gptModelCapacity int = 150` | chat TPM(k) | n/a | KEEP |
| v2/infra/main.bicep:161 | `param reasoningModelName string = 'o4-mini'` | reasoning name | **Deprecated, retire 2026-10-16** | **REPLACE** |
| v2/infra/main.bicep:164 | `param reasoningModelVersion string = '2025-04-16'` | reasoning version | matches o4-mini (deprecated) | **REPLACE** |
| v2/infra/main.bicep:171 | `reasoningModelDeploymentType = 'GlobalStandard'` | reasoning SKU | n/a | KEEP/verify |
| v2/infra/main.bicep:175 | `reasoningModelCapacity int = 50` | reasoning TPM(k) | n/a | KEEP/verify |
| v2/infra/main.bicep:179 | `param embeddingModelName string = 'text-embedding-3-large'` | embedding name | **GA, retire 2027-04-15** | KEEP |
| v2/infra/main.bicep:182 | `param embeddingModelVersion string = '1'` | embedding version | matches GA | KEEP |
| v2/infra/main.bicep:189 | `embeddingModelDeploymentType = 'Standard'` | embedding SKU | n/a | KEEP |
| v2/infra/main.bicep:193 | `embeddingModelCapacity int = 100` | embedding TPM(k) | n/a | KEEP |
| v2/infra/main.bicep:196 | `azureOpenAiApiVersion = '2025-01-01-preview'` | OpenAI API ver | not a model; current | KEEP |
| v2/infra/main.bicep:199 | `azureAiAgentApiVersion = '2025-05-01'` | Agent API ver | not a model; current | KEEP |
| v2/infra/main.parameters.json:26 | `gptModelName ... =gpt-5.1` | chat name | GA 2027-05-15 | KEEP |
| v2/infra/main.parameters.json:29 | `gptModelVersion ... =2025-11-13` | chat version | GA | KEEP |
| v2/infra/main.parameters.json:37 | `reasoningModelName ... =o4-mini` | reasoning name | **Deprecated 2026-10-16** | **REPLACE** |
| v2/infra/main.parameters.json:41 | `reasoningModelVersion ... =2025-04-16` | reasoning version | deprecated | **REPLACE** |
| v2/infra/main.parameters.json:49 | `embeddingModelName ... =text-embedding-3-large` | embedding name | GA 2027-04-15 | KEEP |
| v2/infra/main.parameters.json:53 | `embeddingModelVersion ... =1` | embedding version | GA | KEEP |
| v2/infra/main.waf.parameters.json:~23–26 | `gptModelName=gpt-5.1` / `gptModelVersion=2025-11-13` | chat | GA 2027-05-15 | KEEP |
| v2/infra/main.waf.parameters.json:~36–40 | `reasoningModelName=o4-mini` / `reasoningModelVersion=2025-04-16` | reasoning | **Deprecated 2026-10-16** | **REPLACE** |
| v2/infra/main.waf.parameters.json:~48–52 | `embeddingModelName=text-embedding-3-large` / `Version=1` | embedding | GA 2027-04-15 | KEEP |
| v2/azure.yaml:55 | comment "Restricted to regions with GPT-5.1 GlobalStandard capacity." | region gate note | GA | KEEP (update if chat model changes) |
| v2/.env.sample:28 | `AZURE_OPENAI_GPT_DEPLOYMENT=gpt-5.1` | local chat | GA | KEEP |
| v2/.env.sample:29 | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large` | local embedding | GA | KEEP |
| v2/.env.sample:30 | `AZURE_OPENAI_API_VERSION=2024-12-01-preview` | API ver | not a model; older than bicep's `2025-01-01-preview` (cosmetic drift) | OPTIONAL align |

Notes:
- `.env.sample` does **not** set `AZURE_OPENAI_REASONING_DEPLOYMENT` (reasoning is optional locally).
- `v2/.env` (gitignored, live env) sets `AZURE_OPENAI_GPT_DEPLOYMENT=gpt-5.1`; `.scratch/azd-provision.log` confirms a live account deployed `gpt-5.1`, `o4-mini`, and an embedding model — i.e. the deprecated `o4-mini` was actually provisioned.

### 2b. Backend settings (env-driven, no hardcoded model literals)

| File:line | Symbol | Default | Note |
| --- | --- | --- | --- |
| v2/src/backend/core/settings.py:172 | `api_version: str` | `""` | env `AZURE_OPENAI_API_VERSION` |
| v2/src/backend/core/settings.py:173 | `gpt_deployment: str` | `""` | env `AZURE_OPENAI_GPT_DEPLOYMENT` |
| v2/src/backend/core/settings.py:174 | `reasoning_deployment: str` | `""` | env `AZURE_OPENAI_REASONING_DEPLOYMENT` |
| v2/src/backend/core/settings.py:175 | `embedding_deployment: str` | `""` | env `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` |
| v2/src/backend/core/settings.py:176 | `embedding_dimensions: int` | `1536` | env `AZURE_OPENAI_EMBEDDING_DIMENSIONS` — **truncates `text-embedding-3-large` (native 3072) to 1536** to match the search index `content_vector`. Not a retirement issue; dimension-consistency note. |

No model name is hardcoded in `settings.py` — all defaults are `""` and supplied by env/bicep.

### 2c. Source code (docstring / comment examples only — not runtime values)

| File:line | Literal | Kind |
| --- | --- | --- |
| v2/src/backend/core/providers/llm/foundry_iq.py:659 | `gpt-4o` | docstring example ("non-reasoning model (e.g. gpt-4o)") |
| v2/src/backend/core/providers/llm/registry.py:17 | `deployment="gpt-4o"` | module docstring usage example |
| v2/src/backend/core/providers/search/pgvector.py:25 | `text-embedding-3-large` (3072) | docstring dimension example |

### 2d. post_provision seed script (env-driven; docstring examples)

| File:line | Literal | Kind |
| --- | --- | --- |
| v2/scripts/post_provision.py:72 | `# text-embedding-3-small / -ada-002` | comment (dim default rationale) |
| v2/scripts/post_provision.py:354–355, 435–439 | `gpt-4o-mini, gpt-4.1, gpt-5.1` | docstring — KB accepts *chat* models only; o-series rejected (BUG-0023) |
| v2/scripts/post_provision.py:446–451 | reads `AZURE_OPENAI_GPT_DEPLOYMENT` as KB query-planning model | runtime = chat deployment (`gpt-5.1`), **not** the reasoning one |

### 2e. docker-compose (placeholder names, not real models)

| File:line | Literal | Note |
| --- | --- | --- |
| v2/docker/docker-compose.smoke.yml:34 | `AZURE_OPENAI_GPT_DEPLOYMENT: gpt-smoke` | placeholder |
| v2/docker/docker-compose.smoke.yml:35 | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT: embed-smoke` | placeholder |

### 2f. Tests (fixture values — mocked; no live model contact)

`o4-mini` and `text-embedding-3-*` and `gpt-4*` fixture values across:

- v2/tests/backend/core/providers/agents/test_base.py:190,194,296,308,324,337,561,574 (`gpt-4o-mini`, `o4-mini`)
- v2/tests/backend/core/providers/embedders/test_azure_openai.py:28–30,71,89,94,126,170 (`gpt-4o`, `text-embedding-3-small`, `o4-mini`)
- v2/tests/backend/core/providers/llm/test_foundry_iq.py:38–40,151,171,176,262,361,426–429,532,592–601,613,659–666,717,758–763,789,893,928,981,1009,1034–1094,1154,1189,1220 (`gpt-4o`, `gpt-4o-mini`, `o4-mini`, `o3-mini`, `text-embedding-3-small`)
- v2/tests/backend/core/test_settings.py:51–53,110,505 (`gpt-4.1`, `o4-mini`, `text-embedding-3-small`, dim 1536 comment)
- v2/tests/backend/core/tools/test_post_prompt.py:153–154 (`gpt-4o`)
- v2/tests/backend/core/tools/test_qa.py:82–83 (`gpt-4o`)
- v2/tests/backend/core/tools/test_text_processing.py:89–90 (`gpt-4o-mini`)
- v2/tests/backend/test_admin.py:81–82,389–391,398–400 (`gpt-4o`, `text-embedding-3-large`, `o3-mini`)
- v2/tests/backend/test_app_lifespan.py:24–25 (`gpt-4o`, `text-embedding-3-small`)
- v2/tests/backend/test_health.py:172–173 (`gpt-4o`, `text-embedding-3-small`)
- v2/tests/backend/test_services_health.py:27–28 (`gpt-4o`, `text-embedding-3-small`)
- v2/tests/functions/{add_url,batch_push,batch_start,blob_event,search_skill}/test_blueprint.py (`gpt-4.1`, `o4-mini`, `text-embedding-3-small`)
- v2/tests/scripts/test_post_provision.py:152,185,219,292 (`gpt-4.1`, `o4-mini`)
- v2/tests/frontend/api/admin.test.tsx:48 and v2/tests/frontend/AppNavigation.test.tsx:34 (`text-embedding-3-large`)

### 2g. Docs (historical narratives + planning docs)

| File:line | Literal | Kind |
| --- | --- | --- |
| v2/docs/cloud_deployment.md:48–50 | `gpt-5.1` / `text-embedding-3-large` / `o4-mini` | env-var reference table (`o4-mini` row is the deprecated one) |
| v2/docs/infrastructure.md:94,96,220 | `GPT-5.1` / `gpt-5.1 / o4-mini / text-embedding-3-large` | param table + quota note (`o4-mini` deprecated) |
| v2/docs/local_development.md:226–227,286–287,376,381 | `gpt-5.1` / `text-embedding-3-large` / `-small` mismatch note | local config + a deployed-mismatch note |
| v2/docs/status_presentation.md:185,346 | `gpt-5.1 · o4-mini · text-embedding-3-large` | architecture diagram + prose |
| v2/docs/development_plan.md:119,210,220,232,233,475,722 | `gpt-5`, `text-embedding-3-*`, reasoning-model | plan narrative |
| v2/docs/development_plan.old.md:66,84,100 | `text-embedding-3-small`, `GPT-*` | v1 historical |
| v2/docs/env-vars.md:182,203 | v1→v2 env mapping (`AZURE_OPENAI_MODEL` → `_GPT_DEPLOYMENT`) | migration table |
| v2/docs/bugs.md (many) | `gpt-4o`, `gpt-4.1`, `gpt-5.1`, `o4-mini`, `text-embedding-3-*` | historical defect records (BUG-0023/0028/0029/0035/0057…) |
| v2/docs/worklog/2026-06-*.md (many) | same | historical worklog narrative |
| v2/docs/plan/business-cases.md:195,214,273 | **`GPT-4 Vision`** | roadmap (advanced image processing) — the only *forward-looking* gpt-4 model mention |
| v2/docs/plan/modernization-plan.md:301,443 | `model: str = "gpt-4.1"`, `AZURE_OPENAI_MODEL=gpt-4.1` | superseded modernization snippet |

---

## 3. All `gpt-4*` references (dedicated list, per user directive)

Total: **56** (`infra 0 · top-level v2 config 0 · src 2 · tests 43 · docs 11`). All are fixtures / docstrings / narrative — **none in deployable config**.

- **Must-remove/replace-if-scrubbing (deprecated/retiring models, but low risk because non-runtime):**
  - `gpt-4o` (Deprecated → 2026-10-01): src foundry_iq.py:659, llm/registry.py:17; tests test_azure_openai.py:28, test_foundry_iq.py:38/151/532/758/761/763/893/928/981/1154/1189/1220, test_post_prompt.py:153–154, test_qa.py:82–83, test_admin.py:81/389/398, test_app_lifespan.py:24, test_health.py:172, test_services_health.py:27; docs bugs.md:81/465/467, worklog/2026-06-12.md:152, worklog/2026-06-14.md:117, worklog/2026-06-16.md:190.
  - `gpt-4o-mini` (Deprecated → 2026-10-01): tests test_base.py:190/296/308/324/561/574, test_foundry_iq.py:171/176, test_text_processing.py:89–90.
  - `gpt-4.1` (Deprecated → 2026-10-14): tests test_settings.py:51/110, functions test_blueprint.py ×5 (add_url:43, batch_push:49, batch_start:44, blob_event:52, search_skill:44), test_post_provision.py:152/185; docs modernization-plan.md:301/443; also named in bugs.md/worklog KB allow-list narratives.
  - `GPT-4 Vision` (base gpt-4 vision, effectively retired): docs business-cases.md:195/214/273 — **forward-looking roadmap item**, worth revisiting since GPT-4 Vision no longer exists as a standalone deployable model (vision is now folded into gpt-4o/gpt-5 multimodal).
- **Acceptable-current `gpt-4*`:** none. Every `gpt-4*` model name on the current schedule is Deprecated. If any `gpt-4*` is to remain as an *example*, the safe modern substitute is `gpt-5.1` (chat) or `gpt-5-mini` (small chat).

Interpretation of the user directive "remove any reference of gpt-4": literally this is all 56 sites, but only 0 of them affect what gets deployed. The high-value action is replacing **`o4-mini`** (see §5); the rest is cosmetic scrubbing of fixtures/docstrings/narrative (see Clarifying Questions).

---

## 4. Bicep model-deployment resource review

Two deployment code paths, identical model wiring:

- **Foundry account (default path)** — `v2/infra/main.bicep` ~L558–597 `deployments:` array on the `Microsoft.CognitiveServices/accounts` AVM module. Three entries, each `model.format: 'OpenAI'`, `model.name` = param, `model.version` = param, `sku.name`/`sku.capacity` = params. Chat + reasoning carry `raiPolicyName: 'Microsoft.DefaultV2'`; embedding has none.
- **Existing-OpenAI reuse path** — `v2/infra/main.bicep` ~L663–700 (`existingOpenAiGptDeployment`, `existingOpenAiReasoningDeployment` as `Microsoft.CognitiveServices/accounts/deployments@2024-10-01`). Same `format/name/version/sku`. Comment at L555/671 states embedding is assumed to pre-exist on the reused v1 account as **`text-embedding-3-small`** — a dimension/name divergence from the v2 default `text-embedding-3-large` (BUG-0057 lineage).

Effective values (both paths):

| Role | format | name | version | sku.name | sku.capacity | Deployability (2026-07-01, eastus2) |
| --- | --- | --- | --- | --- | --- | --- |
| chat | OpenAI | `gpt-5.1` | `2025-11-13` | GlobalStandard | 150 | GA — deployable; region gated to GPT-5.1 GlobalStandard (eastus2 is on the allow-list) |
| reasoning | OpenAI | `o4-mini` | `2025-04-16` | GlobalStandard | 50 | **Deprecated** — still deployable today, but new deployments of a deprecated model are discouraged and it retires 2026-10-16 |
| embedding | OpenAI | `text-embedding-3-large` | `1` | Standard | 100 | GA — deployable |

Region: `azureAiServiceLocation` default `eastus2` (`v2/infra/main.bicep:74`, `azure.yaml:56`). The `azure.yaml` allow-list is explicitly "regions with GPT-5.1 GlobalStandard capacity" and includes `eastus2`, so the recommended replacements (`gpt-5.1`, `gpt-5-mini`, `text-embedding-3-large`) are available there. `gpt-5-mini` (GlobalStandard) and `text-embedding-3-large` (Standard) are broadly available in the same GPT-5-capable regions; verify quota with `az cognitiveservices account list-skus` / the quota tool before pinning.

---

## 5. Recommended replacement matrix (fresh 2026 deploy)

Principle: prefer the longest runway per the schedule; change only what is retiring.

| Logical role | Current (deployable) | Status | Recommendation | Version | API version | Runway |
| --- | --- | --- | --- | --- | --- | --- |
| Chat / gpt | `gpt-5.1` | GA | **KEEP `gpt-5.1`** | `2025-11-13` | `2025-01-01-preview` | 2027-05-15 (longest in gpt-5.x GA) |
| Reasoning / o-series | `o4-mini` | **Deprecated 2026-10-16** | **REPLACE →** primary: `gpt-5-mini` (distinct low-cost reasoning-capable model, long runway); alternative: collapse onto `gpt-5.1` (chat model auto-detects reasoning — see worklog 2026-06-14) | `gpt-5-mini` → `2025-08-07` | `2025-01-01-preview` (chat) / `2025-05-01` (agent) | gpt-5-mini 2027-02-06 |
| Embedding | `text-embedding-3-large` | GA | **KEEP `text-embedding-3-large`** | `1` | `2024-12-01-preview` / `2025-01-01-preview` | 2027-04-15 |

Reasoning-slot note: **No dedicated o-series model has runway past 2026-12** (o3/o4-mini 2026-10-16, o3-pro 2026-12-10). Do **not** swap `o4-mini` for `o3` — same 2026-10-16 date, no gain. The durable choices are gpt-5 family (reasoning-capable). Pick `gpt-5-mini` if you want a cheaper distinct reasoning deployment; pick `gpt-5.1` (reuse the chat model) if you want to avoid a second deployment + quota. Confirm whether a **separate** reasoning deployment is still needed at all — worklog 2026-06-14 (L48/L138) records that the shipped `gpt-5.1` chat model already auto-detects and emits reasoning, making the standalone `o4-mini` deployment largely vestigial in current behavior.

### 5a. Exact edit sites to change (reasoning `o4-mini` → replacement)

Primary (deployable — required):
- v2/infra/main.bicep:161 — `param reasoningModelName string = 'o4-mini'` → `'gpt-5-mini'`
- v2/infra/main.bicep:164 — `param reasoningModelVersion string = '2025-04-16'` → `'2025-08-07'`
- v2/infra/main.bicep:171 — verify `reasoningModelDeploymentType` (`GlobalStandard` ok for gpt-5-mini)
- v2/infra/main.parameters.json:37 — `"${AZURE_ENV_REASONING_MODEL_NAME=o4-mini}"` → `gpt-5-mini`
- v2/infra/main.parameters.json:41 — `"${AZURE_ENV_REASONING_MODEL_VERSION=2025-04-16}"` → `2025-08-07`
- v2/infra/main.waf.parameters.json:~36 — `reasoningModelName` default `o4-mini` → `gpt-5-mini`
- v2/infra/main.waf.parameters.json:~40 — `reasoningModelVersion` default `2025-04-16` → `2025-08-07`

Docs to keep consistent (not deployable, but user-facing):
- v2/docs/cloud_deployment.md:50 — `AZURE_OPENAI_REASONING_DEPLOYMENT | o4-mini`
- v2/docs/infrastructure.md:96 — `gpt-5.1 / o4-mini / text-embedding-3-large`
- v2/docs/infrastructure.md:220 — quota note `o4-mini GlobalStandard (50K TPM)`
- v2/docs/status_presentation.md:185,346 — architecture diagram / prose `o4-mini`

Optional cosmetic (fixtures / docstrings; only if scrubbing all `gpt-4*` / deprecated names):
- src: foundry_iq.py:659, llm/registry.py:17 (`gpt-4o` docstring example → `gpt-5.1`)
- tests: all `gpt-4o`/`gpt-4o-mini`/`gpt-4.1`/`o4-mini` fixtures in §2f (values are mocked; changing them is purely for freshness and does not affect test outcomes — but changing `o4-mini` fixtures may require re-checking any test that asserts o-series *reasoning* routing, e.g. test_foundry_iq.py reasoning tests and test_base.py:194/337).
- docs: business-cases.md `GPT-4 Vision` roadmap rows (revisit as gpt-5 multimodal); modernization-plan.md:301/443 superseded snippet.

If choosing the "collapse onto gpt-5.1" alternative instead of gpt-5-mini: set `reasoningModelName=gpt-5.1` / `reasoningModelVersion=2025-11-13` at the same sites (double-provisions the chat model under a second deployment name — wastes quota, so gpt-5-mini or dropping the reasoning deployment is cleaner).

---

## 6. Gaps / observations

1. **`o4-mini` is the single deployable retirement risk.** Everything else deployable is GA with 9+ months runway. This is the one required change for a clean 2026 deploy.
2. **Embedding dimension nuance (not retirement):** default `embedding_dimensions=1536` truncates `text-embedding-3-large` (native 3072) to fit the 1536-dim search index / pgvector column. Documented history: BUG-0037/0057 and local_development.md:376 note a deployed env that used `text-embedding-3-small` (native 1536) vs the config default `-large`. Keep the model but keep dimensions explicitly at 1536 to match the index. Not a schedule issue.
3. **API-version drift (cosmetic):** `.env.sample` pins `AZURE_OPENAI_API_VERSION=2024-12-01-preview` while bicep pins `2025-01-01-preview`. Both are valid (API versions aren't on the retirement schedule); align if desired.
4. **`gpt-5.1` vs `gpt-5.1-chat`:** the schedule shows the `-chat` variant is **Retired**; CWYD correctly uses the base `gpt-5.1` (GA). No action, just confirming the pin is the surviving one.
5. **`GPT-4 Vision` roadmap rows** (business-cases.md) reference a model that no longer exists standalone; advanced image processing on a fresh deploy would use gpt-4o/gpt-5 multimodal. Roadmap-doc concern, not deployable.
6. **`.scratch/azd-provision.log`** shows a live account that already provisioned `o4-mini` — a redeploy after the swap would create the new reasoning deployment; the old `o4-mini` deployment on the account should be deleted to avoid an orphaned deprecated deployment (cleanup step, per the user's "clean up before next step" preference).

---

## 7. Clarifying questions

1. **Scope of "remove any reference of gpt-4":** required change is the deprecated **`o4-mini`** reasoning model (the only deployable retirement risk); the 56 `gpt-4*` references are all test fixtures / docstrings / historical narrative that do not affect deployment. Do you want (a) only the deployable-config fix (`o4-mini` → replacement), or (b) a full cosmetic scrub of every `gpt-4*`/`o4-mini`/deprecated name across tests + src docstrings + docs too? Note Hard Rule #16 (no process narrative) and that `bugs.md`/`worklog/*` are historical records — rewriting their model names would falsify history and is not recommended.
2. **Reasoning slot decision:** for the o4-mini replacement, prefer (a) `gpt-5-mini` (distinct cheap reasoning-capable, runway 2027-02-06), (b) reuse `gpt-5.1` for reasoning (no second model, but double-provision), or (c) drop the dedicated reasoning deployment entirely since `gpt-5.1` already auto-emits reasoning? My recommendation is (a) or (c).
3. **Region confirmation:** should I (in a follow-up) verify live `gpt-5-mini` + `text-embedding-3-large` GlobalStandard/Standard quota availability in `eastus2` (or your target region) before you pin the replacement, via the quota tooling?
