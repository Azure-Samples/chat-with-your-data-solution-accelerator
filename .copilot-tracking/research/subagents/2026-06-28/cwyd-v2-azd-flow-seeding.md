<!-- markdownlint-disable-file -->
# CWYD v2 — `azd up` lifecycle + post-deploy seeding map, and divergence from MACAE

Reference target: `c:\workstation\Microsoft\github\cwyd-cdb\v2\` (on disk).
MACAE reference: prior capture `.copilot-tracking/research/subagents/2026-06-25/macae-identity-env-hooks.md` (§4 hooks, §5 outputs) + public MACAE `main`. MACAE is NOT on disk.

Status: Complete.

Goal restated: the user wants a single `azd up` that (a) provisions infra + config, (b) builds and deploys frontend + backend + functions, and (c) runs a post-deploy data-load that leaves a fully functional, ready-to-use site — mirroring MACAE's default `azd up`. This doc maps CWYD's entire azd lifecycle + the seed step, finds where it diverges from MACAE, states whether seeding is automatic or manual, whether it depends on the (currently fragile) functions pipeline, and the ordering/race risks.

---

## 0. TL;DR (crisp summary)

- CWYD v2's `azd up` is a **full build+deploy** pipeline (unlike MACAE's prebuilt-image, provision-only default): provision Bicep → build+deploy backend (ACR remote build), frontend (App Service build-from-source), function (prepackaged Flex zip) → `postdeploy` seed hook.
- **Two hooks do the data work**, not one: `postprovision` (`post_provision.py`) creates the structural substrate (pgvector ext / `cwyd-index` search index / Foundry-IQ KB + KB-source / `cwyd-kb-mcp` connection); `postdeploy` (`upload_sample_data.py`) uploads sample docs + enqueues ingestion.
- **Seeding is wired as an automatic hook but is de-facto manual in the cloud.** The `postdeploy` hook is `interactive: true` and prompts an `input()` menu; under `azd up` there is **no TTY**, so `input()` hits EOF, the menu is skipped, and `continueOnError: true` swallows it → **nothing is seeded** unless the operator pre-sets `AZURE_ENV_SAMPLE_DATA=all` (or `--set all`). Confirmed in worklog 2026-06-25 "Gotcha 2".
- **CWYD's seed is ASYNC and depends on the functions pipeline.** It only uploads blobs + enqueues `doc-processing` messages; the actual parse→chunk→embed→index work is done later by the `batch_push` queue-triggered Function. **This is the core divergence from MACAE**, whose `index_datasets.py` builds the index **synchronously in-script** (AzureCliCredential, reads blobs, PUTs documents) with no function in the loop. If CWYD's `batch_push` is broken/cold/poisoning (the BUG-0034/0053/0056/0057/0080 class), the seed reports success (blobs uploaded, messages enqueued) but **the index stays empty** — exactly the silent-empty-index risk the user flagged.
- **No hard message-loss race in `direct_enqueue` mode** (the default): the seed enqueues to a durable `doc-processing` queue; `batch_push` (with `alwaysReady: function:batch_push:1`) drains it whenever it is healthy. The race exists only in `event_grid` mode (off by default) and as a *processing* (not delivery) failure when the Function code is broken.
- **All seed inputs are emitted as Bicep outputs** → land in `.azure/<env>/.env` → read by the script via the azd-exported env. No missing output. The one input that is NOT an output and NOT a typed prompt is `AZURE_ENV_SAMPLE_DATA` (the seed scope), which the operator must set by hand — the root reason seeding silently no-ops.

---

## 1. `v2/azure.yaml` — full hook inventory

File: [v2/azure.yaml](../../../../v2/azure.yaml) (whole file read). `name: chat-with-your-data-v2`, `infra.provider: bicep`, `infra.path: infra`, `infra.module: main`. `requiredVersions.azd: ">= 1.18.0 != 1.23.9"`.

### 1.1 Typed-prompt parameters (surfaced by `azd up` / `azd provision`)

`parameters:` block (azure.yaml L40–88): `databaseType` (default `cosmosdb`, allowed `cosmosdb|postgresql`), `azureAiServiceLocation` (default `eastus2`), `enableMonitoring` (default `false`), `enableScalability` (false), `enableRedundancy` (false), `enablePrivateNetworking` (false). **No `sampleData` / seed-scope parameter exists** — the seed scope is NOT a typed prompt, so `azd up` never asks for it.

### 1.2 Per-service definitions + service-scoped hooks

`services:` (azure.yaml L100–183):

| Service | project | host | language | build mechanism | service hook |
|---|---|---|---|---|---|
| `backend` | `./src/backend` | `containerapp` | py | `docker.path: ../../docker/Dockerfile.backend`, `context: ../..`, **`remoteBuild: true`** (ACR builds the image; no local Docker) | none |
| `frontend` | `./src/frontend` | `appservice` | js | **build-from-source**, `dist: ./build-output` | `prepackage` (service-scoped) |
| `function` | `./build-functions` | `function` | py | Flex zip from a pre-staged `build-functions/` tree | `prepackage` (service-scoped) |

**frontend `prepackage`** (azure.yaml L160–171): posix `../../scripts/package-frontend.sh`, windows `../../scripts/package-frontend.ps1`; `continueOnError: false`, `interactive: false`. Runs `npm ci && npm run build`, then stages a self-contained App Service artifact at `./build-output` (server `frontend_app.py` + `requirements.txt` beside the Vite `dist/`; layout contract in `v2/scripts/package_frontend.py`). Service-scoped so it also fires on a targeted `azd deploy frontend`. Note: comments cite BUG-0081 (the `host: appservice` + `docker:` mismatch was the original deploy bug; the `docker:` block was removed, build-from-source is the fix).

**function `prepackage`** (azure.yaml L173–183): posix `../scripts/prepackage-function.sh`, windows `../scripts/prepackage-function.ps1`; `continueOnError: false`, `interactive: false`. Regenerates `v2/build-functions/` from `src/functions/` + `src/backend/` (function_app.py + host.json at root, a `functions/` subpackage carrying the blueprint tree, a `backend/` subpackage, generated `requirements.txt` + `.funcignore`). Service-scoped (NOT project-scoped) specifically so a targeted `azd deploy function` re-stages the artifact (BUG-0058 root cause: a project-level `package` hook does not fire on per-service `deploy`).

### 1.3 Project-level hooks (the data hooks)

`hooks:` (azure.yaml L205–227):

| Hook | posix | windows | continueOnError | interactive | What it does |
|---|---|---|---|---|---|
| `postprovision` | `./scripts/post-provision.sh` | `./scripts/post-provision.ps1` | **false** | **true** | pgvector ext (pg mode) + ensure `cwyd-index` search index + seed Foundry-IQ KB + seed `cwyd-kb-mcp` connection (cosmos mode) + print AZURE_* summary |
| `postdeploy` | `./scripts/upload-sample-data.sh` | `./scripts/upload-sample-data.ps1` | **true** | **true** | upload sample docs to the documents container + enqueue ingestion (the seed) |

There is **no** `preprovision`, `predeploy`, project-level `prepackage`, `prebuild`, or per-service `postdeploy` hook. The wrappers are thin shims: each `*.ps1` / `*.sh` runs `uv run python <script>.py @args` and exits with the script's code (read: `post-provision.ps1`, `upload-sample-data.ps1`, `upload-sample-data.sh`).

**The seed hook (`postdeploy`) IS automatic** in the azd lifecycle (it runs every `azd deploy` / `azd up`), but its *effect* is gated by `interactive: true` + an `input()` menu — see §5 for why this makes it de-facto manual in the cloud.

---

## 2. The seeding / data-load scripts

Directory: `v2/scripts/` — `post_provision.py`, `upload_sample_data.py` (+ the `*.sh`/`*.ps1` shims), `package_frontend.py`, `prepackage_function.py`. The two data scripts:

### 2.1 `post_provision.py` (the `postprovision` hook — structural substrate)

File: [v2/scripts/post_provision.py](../../../../v2/scripts/post_provision.py). Pillar Stable Core; auth = `DefaultAzureCredential` (works for interactive deployer, SP in CI, or MI). `main()` order (post_provision.py ~L622–667):

1. Require `AZURE_DB_TYPE`, validate it is `cosmosdb|postgresql`.
2. **postgresql mode** → `_enable_pgvector()` (post_provision.py ~L171): acquire Entra token (`https://ossrdbms-aad.database.windows.net/.default`), connect as `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME@AZURE_POSTGRES_HOST/postgres`, `CREATE EXTENSION IF NOT EXISTS vector`. Has a private-networking pre-flight that fails loudly with a Bastion-tunnel command if the host is `*.private.postgres.database.azure.com`.
3. `_ensure_search_index(dry_run)` (~L368): cosmos mode only (skips when `AZURE_AI_SEARCH_ENDPOINT` empty). Idempotent get-or-create of the chat index `cwyd-index` (fields `id/content/title/url/content_vector`, 1536-dim HNSW vector profile, semantic config `default`). **This is the index the whole RAG path reads/writes — its schema is the contract.**
4. `_ensure_knowledge_base(dry_run)` (~L470): cosmos mode only. Idempotent create-or-update of a Foundry-IQ `searchIndex` **knowledge source** (`cwyd-index-ks`, wrapping `cwyd-index`, exposing `title/url/content` as citation `sourceDataFields`) + **knowledge base** (`cwyd-kb`, referencing the source + the chat OpenAI deployment for query planning). The KB is a *pointer* over the live index — no per-document reseed. KB model is the **chat** deployment (`AZURE_OPENAI_GPT_DEPLOYMENT`), not the reasoning one (BUG-0023 fix). API version from `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION` (default `2025-11-01-preview`).
5. `_ensure_kb_mcp_connection(dry_run)` (~L560): cosmos mode only (skips without `AZURE_AI_SEARCH_ENDPOINT` + `AZURE_AI_PROJECT_RESOURCE_ID`). Idempotent ARM control-plane PUT of the project RemoteTool connection `cwyd-kb-mcp` (`category: RemoteTool`, `target` = KB `/mcp` URL, `authType: ProjectManagedIdentity`, `audience: https://search.azure.com`). This was migrated out of Bicep into `post_provision.py` on 2026-06-25 (worklog 2026-06-25) — the reference-architecture way; the backend's `AZURE_AI_SEARCH_CONNECTION_NAME` points at this seeded `cwyd-kb-mcp` name.
6. `_print_summary()` (~L353): prints the AZURE_* outputs an operator needs.

`--dry-run` validates env + prints summary without any SDK call. RBAC need (worklog 2026-06-25 "Next"): the connection PUT needs `Microsoft.CognitiveServices/accounts/projects/connections/write` on the Foundry account; the azd deploy principal holds it.

**post_provision.py does NOT upload any sample documents and does NOT build any index content.** It only creates the empty structural substrate (index schema, KB pointer, connection). All content comes from the separate `postdeploy` seed.

### 2.2 `upload_sample_data.py` (the `postdeploy` hook — the actual data seed)

File: [v2/scripts/upload_sample_data.py](../../../../v2/scripts/upload_sample_data.py). Pillar Stable Core, "Phase 7 (post-deploy sample-data seed)". Auth = `DefaultAzureCredential`.

Required env (upload_sample_data.py L104–106): `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_DOCUMENTS_CONTAINER`, `AZURE_DOC_PROCESSING_QUEUE`. Optional: `AZURE_STORAGE_BLOB_ENDPOINT` (sovereign-cloud override), `AZURE_INGESTION_TRIGGER` (default `direct_enqueue`), `AZURE_ENV_SAMPLE_DATA` (scope override).

`main()` (L223–305) order:

1. Resolve scope via `resolve_selection` (L186): `--set` > `AZURE_ENV_SAMPLE_DATA` env > **interactive `input()` menu (TTY only)** > **skip** (non-TTY, no override). Tokens: `default|contract|employee|all|none`. Menu default key `4` = "All".
2. If scope is `SeedScope.SKIP` → print + return 0 (no-op).
3. Resolve files from the **repo-root `data/` folder** (`Path(__file__).resolve().parents[2] / "data"` — i.e. `cwyd-cdb/data/`, the v1-shared corpus, **NOT** `v2/data/`). `files_for_selection` (L150): `default`/`employee` → a curated benefits set (`Benefit_Options.pdf`, `employee_handbook.pdf`, `PerksPlus.pdf`, `role_library.pdf`, `Northwind_Standard_Benefits_Details.pdf`, `Northwind_Health_Plus_Benefits_Details.pdf`); `contract` → glob of `data/contract_data/**` PDFs/DOCX; `all` → root globs + contract_data globs.
4. `trigger = AZURE_INGESTION_TRIGGER or direct_enqueue`; `enqueue = (trigger == direct_enqueue)`.
5. For each file: `upload_blob_if_absent` (skip-if-present, idempotent). On a *new* upload, **only in `direct_enqueue` mode**, `enqueue_ingest_message` sends a raw-JSON `BatchPushQueueMessage(container_name, filename)` to `doc-processing` (the `QueueClient` is built with `message_encode_policy=None` so it sends raw JSON, matching the host's `messageEncoding: none` — the BUG-0056 contract). In `event_grid` mode, enqueue is suppressed (the Event Grid → `blob-events` → `blob_event` Function owns the push, no double-ingest).
6. `--dry-run` prints planned uploads without auth.

**Key fact for the user's question:** the seed's job ends at "blob uploaded + message enqueued." It **does not** parse, chunk, embed, or write any index document, and it **does not** seed any KB content (the KB is a pointer; structural seed already happened at postprovision). The actual indexing is the async `batch_push` Function's job. The seed relies entirely on that downstream pipeline.

### 2.3 Sample data location

`c:\workstation\Microsoft\github\cwyd-cdb\data\` (repo root, shared with v1 — confirmed via `list_dir`): `Benefit_Options.pdf`, `employee_handbook.pdf`, `PerksPlus.pdf`, `role_library.pdf`, `Northwind_Standard_Benefits_Details.pdf`, `Northwind_Health_Plus_Benefits_Details.pdf`, `MSFT_FY23Q4_10K.docx`, several `Woodgrove - *.pdf`, plus `contract_data/` and `sample_code/` subdirs. **No `v2/data/` folder exists** — the seed deliberately reaches up to the repo-root corpus. No binary docs are committed under `v2/`.

---

## 3. The azd → infra → env-var round trip

azd writes every Bicep `output AZURE_*` to `.azure/<env>/.env`, then exports those plus the typed-prompt answers (`AZURE_ENV_*`) into the hook process env. The wrappers confirm this contract (post-provision.ps1 header: "every Bicep output prefixed AZURE_* is exported as an env var; AZURE_ENV_* values from the typed-prompt block are also exported").

Every input the two seed scripts read **is** emitted as a Bicep output (so the round-trip is complete — **no missing output**):

| Seed-script input | Bicep output (main.bicep line) | Value |
|---|---|---|
| `AZURE_STORAGE_ACCOUNT_NAME` | L2564 | `effectiveStorageName` |
| `AZURE_STORAGE_BLOB_ENDPOINT` | L2567 | `effectiveStorageBlobEndpoint` |
| `AZURE_DOCUMENTS_CONTAINER` | L2570 | `documentsContainerName` (`documents`) |
| `AZURE_DOC_PROCESSING_QUEUE` | L2573 | `docProcessingQueueName` (`doc-processing`) |
| `AZURE_INGESTION_TRIGGER` | L2576 | `ingestionTrigger` (default `direct_enqueue`, main.bicep L97) |
| `AZURE_DB_TYPE` | L2469 | `databaseType` |
| `AZURE_AI_SEARCH_ENDPOINT` | L2458-area (`databaseType=='cosmosdb' ? effectiveSearchEndpoint : ''`) | conditional |
| `AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME` / `_SOURCE_NAME` / `_API_VERSION` | L~2462+ | KB seed inputs |
| `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_GPT_DEPLOYMENT` / `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | L2480 / L2495 / L~2500 | KB model + index dims |
| `AZURE_AI_PROJECT_RESOURCE_ID` | L2486 | `cwyd-kb-mcp` connection PUT target |
| `AZURE_POSTGRES_HOST` / `_NAME` / `_ADMIN_PRINCIPAL_NAME` | postgres outputs | pgvector ext |
| `AZURE_BACKEND_URL` / `AZURE_FRONTEND_URL` / `AZURE_FUNCTION_APP_URL` | L2581 / L2584 / L2587 | summary print |

**The one input that is NOT a Bicep output and NOT a typed prompt: `AZURE_ENV_SAMPLE_DATA`** (the seed scope). Nothing in the lifecycle sets it. The operator must `azd env set AZURE_ENV_SAMPLE_DATA all` (or pass `--set all`) for an unattended seed. This is the single most important gap: with no TTY and no override, the seed silently no-ops (§5).

The same storage vars are also wired as **runtime env** on both the backend Container App (main.bicep L1893–1900) and the Function App (L2212–2214) so both runtimes share one container + queue. (BUG-0051 was the bug where the backend block had *not* been given the storage vars — now fixed in-Bicep.)

---

## 4. Service deploy ordering

`azd up` = `provision` → `package` (per service, fires `prepackage`) → `deploy` (all services) → `postprovision`(? see note) / `postdeploy`. Precise azd order: **`preprovision → provision → postprovision → prepackage → predeploy → deploy → postdeploy`**. So:

1. **provision** (Bicep) — creates RG, UAMI + RBAC, AI Services/Foundry, Storage (`documents` container + `doc-processing` + `blob-events` queues), Cosmos *or* Postgres, conditional AI Search, App Service Plan + frontend WebApp, Container Apps env + backend, Flex Function plan + Function App + Event Grid system topic + the `blob-events` subscription.
2. **postprovision** (`post_provision.py`) — pgvector ext / `cwyd-index` / KB / `cwyd-kb-mcp`. Runs **before** any service code is deployed (the index + KB are structural and don't need running code).
3. **prepackage** (per service) — frontend `npm ci && npm run build` → `build-output`; function regenerate `build-functions/`.
4. **deploy** — azd deploys all three services. Order within `deploy` is not contractually pinned by azd (no `dependsOn` between services in azure.yaml); in practice backend (ACR remote build), frontend (App Service zip + Oryx build), function (Flex zip) each deploy independently.
5. **postdeploy** (`upload_sample_data.py`) — runs **once**, after all service deploys succeed.

### Ordering dependencies + race risks

- **Seed vs. function readiness (the real risk).** In `direct_enqueue` mode, the seed enqueues `doc-processing` messages that `batch_push` (queue trigger, `alwaysReady: function:batch_push:1`, main.bicep ~L2160) consumes. The queue is durable, so there is **no message-loss race** even if `batch_push` is briefly cold — messages wait. **BUT** the seed's success signal ("uploaded N, enqueued N") says nothing about whether `batch_push` actually *indexed* them. If the Function is **broken** (the recurring class: BUG-0034 DI endpoint `"/"`, BUG-0056 base64 encoding mismatch, BUG-0057 embedding-deployment 404, BUG-0080 Flex Oryx build hang, BUG-0062 storage 403), every message poisons and **the index stays empty while the seed reports success.** This is exactly the silent-empty-index failure the user described.
- **Seed vs. backend health.** The seed does NOT POST any config to the backend (unlike MACAE's `upload_team_config.py`). It writes blobs + queue messages directly. So the backend being unhealthy at seed time does not block the seed — but it does mean "the site is ready to use" is not actually verified by the lifecycle.
- **`event_grid` mode race (off by default).** If `AZURE_INGESTION_TRIGGER=event_grid`, the seed uploads blobs only and relies on Event Grid `BlobCreated` → `blob-events` → `blob_event` Function → `doc-processing` → `batch_push`. The Event Grid subscription delivers to a **queue** (`blob-events`), created at provision time and decoupled from function deployment (main.bicep ~L2258 comment: "A queue destination — not an Event Grid AzureFunction trigger — keeps managed-identity delivery and deploys at provision time (the queue exists; a function would not yet)"). So events are durably queued even before the function deploys. The race here is again *processing*: if `blob_event` is not deployed/healthy (BUG-0078 stale allow-list dropped it; BUG-0054 deploy deferred), the `blob-events` messages sit/poison and nothing indexes. The default is `direct_enqueue` precisely to avoid depending on `blob_event` + Event Grid wiring (main.bicep L96 comment: "Flip to event_grid only after the blob_event Function blueprint is deployed").
- **Reused-resource drift (cloud-only, not a code race).** When the env reuses pre-existing data resources (`AZURE_ENV_EXISTING_COSMOS_NAME`/`_STORAGE_NAME`), the v2 Bicep data modules are guarded `if (!useExisting*)` and never manage the reused account's firewall/Event-Grid posture → BUG-0086 (Cosmos/Storage left `publicNetworkAccess=Disabled` blocks the non-VNet backend/function), BUG-0087 (a stale v1 Event Grid subscription dumps raw events on `doc-processing` → poison per upload). These break seeding/ingestion in the cloud independently of the hook wiring (worklog 2026-06-25 Gotchas 4 + 6). The planned fix (worklog 2026-06-25 "Option A", U2/U3) folds a self-healing `_reconcile_reused_resource_posture()` + stale-subscription prune into `post_provision.py`.

---

## 5. Comparison to MACAE — where CWYD diverges

MACAE baseline (from the 2026-06-25 capture §4–5):

- **MACAE `azd up` = provision only.** Default flavor uses **prebuilt images** (no build/deploy of code from azd); `azure.yaml` declares **exactly one hook, `postdeploy`** (no postprovision, no prepackage).
- **MACAE `postdeploy` hook only PRINTS instructions.** It detects Git-Bash vs PowerShell and prints "run `infra/scripts/post-provision/post_deploy.sh` (or `.ps1`) manually", then prints the frontend URL. It does **not** run the seed. → seeding is **explicitly manual/interactive**.
- **MACAE `post_deploy.sh` is a synchronous index-building engine** run by the operator by hand: auth → resolve azd env values → interactive use-case menu → (WAF) temporarily enable public access for seeding → `az storage blob upload-batch --auth-mode login` (content packs under `content_packs/<usecase>/`) → **`index_datasets.py`** builds the AI Search index **in-process** (AzureCliCredential + `azure.search.documents`, extracts PDF/DOCX text, PUTs documents) → `upload_team_config.py` **POSTs agent-team configs to the backend** REST API → `seed_vector_stores.py` / `seed_knowledge_bases.py` / `seed_kb_connections.py` seed Foundry-IQ vector stores + KBs + per-KB MCP connections. The deployer holds Storage Blob Data Contributor + Search Index/Service Contributor so the script can write blobs + build indexes directly.

| Dimension | MACAE | CWYD v2 | Divergence |
|---|---|---|---|
| Default `azd up` scope | provision only (prebuilt images) | provision **+ build + deploy** (backend ACR remote build, frontend build-from-source, function Flex zip) | CWYD does the full build+deploy the user wants; MACAE does not |
| Hooks declared | `postdeploy` only | `postprovision` **and** `postdeploy` (+ 2 service `prepackage`) | CWYD adds a structural `postprovision` (index/KB/connection) MACAE has no analog for |
| Seed trigger | prints command → **operator runs manually** | automatic hook **but** `interactive: true` menu → **skipped under azd (no TTY)** unless `AZURE_ENV_SAMPLE_DATA` set | Both end up manual-ish; CWYD's is "automatic-but-silently-skipped", MACAE's is "advertised, run by hand" |
| Index build | **synchronous in-script** (`index_datasets.py` reads blobs, PUTs documents) | **asynchronous via Functions** (seed only uploads+enqueues; `batch_push` does parse/embed/index later) | **Core divergence.** CWYD's readiness depends on a healthy Functions pipeline; MACAE's does not |
| Empty-index failure mode | seed fails loudly in-script if indexing fails (operator sees it) | seed reports success while index stays empty if `batch_push` poisons | CWYD has the silent-empty-index risk; MACAE does not |
| Backend config seeding | `upload_team_config.py` POSTs team configs to backend | none (no backend POST in the seed) | CWYD has no agent-team config concept; its persona/config is admin-UI + RuntimeConfig |
| KB seeding | per-use-case vector stores + KBs created from uploaded content | KB is a **pointer** over the live `cwyd-index` (one-time structural seed at postprovision; no per-doc reseed) | CWYD's idempotent push-ingestion means the KB never needs content reseed (ADR 0021) |
| Network for seeding | WAF runs temporarily flip public access on, restore via EXIT trap | no auto network toggle; reused-resource private-only drift breaks the seed (BUG-0086), fixed manually | CWYD lacks MACAE's enable-public-access-for-seeding helper (planned U2) |
| Sample data location | in-repo `content_packs/<usecase>/` + `pack.json` manifest | repo-root `data/` + `data/contract_data/`, selected by `AssistantType` scope (no manifest) | Different layout; CWYD has no `pack.json` schema |

---

## 6. Is CWYD seeding automatic or manual? Does it depend on the broken Functions pipeline?

- **Automatic in wiring, manual in practice.** The `postdeploy` hook fires automatically on every `azd up`, so unlike MACAE (which only prints a command) CWYD *intends* automation. But `interactive: true` + the `input()` menu means under azd's non-TTY shell the menu read hits EOF, the choice can't be read, and `continueOnError: true` swallows the skip → **nothing seeds** (worklog 2026-06-25 Gotcha 2: "the menu choice cannot be read and the seed is skipped"). The supported unattended path is `AZURE_ENV_SAMPLE_DATA=all` (or `azd deploy --set all` / run the script directly). So today an operator who runs a bare `azd up` gets an **empty site** unless they knew to set that env var first.
- **Yes, the seed depends on the Functions pipeline (async).** The seed only uploads blobs + enqueues `doc-processing` messages; `batch_push` does the parse→chunk→embed→index. If `batch_push` is unhealthy the seed succeeds but the index is empty. The pipeline has been the single most defect-dense area (BUG-0034/0049/0053/0054/0056/0057/0058/0078/0080/0088). As of worklog 2026-06-25 the cloud Function is healthy (`/api/health` 200, queues drained, `batch_push` + `blob_event` live after the BUG-0080 `agent-framework-core` repin) — **but `.docx` ingestion is still failing (BUG-0088, open)** and observability is effectively off (BUG-0055/0089), so a `.docx` in the seed corpus (e.g. `MSFT_FY23Q4_10K.docx`) would silently fail. PDFs are the guaranteed-happy path.

---

## 7. Ordering / race risk register

| # | Risk | Mode | Mechanism | Mitigation today | Status |
|---|---|---|---|---|---|
| R1 | Silent empty index | both | Seed reports success (blob + enqueue) but `batch_push` poisons every message → index empty | `alwaysReady` warm instance; durable queue; PDF-only happy path | **Live risk** (BUG-0088 `.docx`; no telemetry BUG-0055/0089) |
| R2 | Seed silently skipped | `azd up` | `interactive: true` menu + no TTY → `input()` EOF → `continueOnError: true` swallows | set `AZURE_ENV_SAMPLE_DATA=all` or `--set all` | **Live gap** (worklog 2026-06-25 Gotcha 2) |
| R3 | `event_grid` delivery before function ready | event_grid only | Off by default; even on, EG delivers to a durable `blob-events` **queue** (provision-time), decoupled from function deploy | default `direct_enqueue`; queue durability | Low (mode off) |
| R4 | Reused-resource firewall/EG drift | cloud reuse | Private-only Cosmos/Storage block non-VNet backend/function; stale v1 EG sub poisons `doc-processing` | manual `az` fixes; planned `post_provision.py` self-heal (U2/U3) | **Open** (BUG-0086/0087) |
| R5 | Function deploy fails but azd reports success | deploy | stale `build-functions/` artifact (prepackage not fired on per-service deploy) | `prepackage` now service-scoped; subpackage guard test | Fixed (BUG-0058/0078) |
| R6 | Seed-script blocked by private storage | cloud | `az storage blob upload-batch`/SDK from workstation refused on `publicNetworkAccess=Disabled` | open storage before seed, re-lock after (manual) | **Open** (worklog 2026-06-25 Gotcha 2) |
| R7 | Admin/site not actually usable post-seed | deploy | No Easy Auth identity source on backend → admin 401 in prod | pending auth-architecture decision | **Open** (BUG-0090) |

---

## 8. Step-by-step map of CWYD's *intended* `azd up → deploy → seed → usable` flow

1. **`azd up`** prompts the typed parameters (databaseType, region, WAF flags) — **not** the seed scope.
2. **provision** ([v2/infra/main.bicep](../../../../v2/infra/main.bicep)) — UAMI + RBAC (no Key Vault), Foundry/AI Services, Storage (`documents` container, `doc-processing` + `blob-events` queues), Cosmos *or* Postgres, conditional AI Search (cosmos only), frontend WebApp, backend Container App, Flex Function App + Event Grid system topic + `blob-events` subscription. All AZURE_* outputs → `.azure/<env>/.env`.
3. **postprovision** ([v2/scripts/post_provision.py](../../../../v2/scripts/post_provision.py) via `post-provision.{sh,ps1}`) — pg: enable `vector`; cosmos: ensure `cwyd-index`, seed Foundry-IQ KB (`cwyd-kb` + `cwyd-index-ks`) + `cwyd-kb-mcp` connection; print summary. **Structural only — no documents yet.**
4. **prepackage** (frontend [package_frontend.py](../../../../v2/scripts/package_frontend.py); function [prepackage_function.py](../../../../v2/scripts/prepackage_function.py)) — build SPA `build-output`; regenerate `build-functions/`.
5. **deploy** — backend (ACR remote build → Container App), frontend (zip + Oryx `pip install`, needs `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, BUG-0085), function (Flex zip, needs the `agent-framework-core` pin, BUG-0080).
6. **postdeploy** ([v2/scripts/upload_sample_data.py](../../../../v2/scripts/upload_sample_data.py) via `upload-sample-data.{sh,ps1}`) — resolve scope (`--set` > `AZURE_ENV_SAMPLE_DATA` > menu/TTY > skip); upload sample PDFs/DOCX from repo-root `data/` to `documents`; in `direct_enqueue` mode enqueue raw-JSON `BatchPushQueueMessage` per new blob to `doc-processing`.
7. **(async, off the azd timeline) `batch_push`** drains `doc-processing` → parse (DocumentIntelligence/Text/Html) → chunk → embed (`text-embedding-3-small` on the AI Services account, BUG-0057 route) → push to `cwyd-index` (cosmos) or pgvector (pg). The KB pointer already covers the index, so chat grounds as soon as chunks land.
8. **usable** — frontend SPA reads backend URL from `/config`; chat grounds on the index/KB. (Caveat: prod admin needs an Easy Auth identity source still unwired — BUG-0090.)

**Where it breaks vs. intent:** step 6 silently no-ops under bare `azd up` (R2), and even when it runs, step 7's async indexing can fail silently leaving an empty index (R1) — so "fully functional, ready-to-use site after one `azd up`" is **not** guaranteed today. To match the user's goal you would: (a) make the seed run unattended by default (drop `interactive`, default scope `all`, or set `AZURE_ENV_SAMPLE_DATA` in `azure.yaml`/env), and (b) either make the seed verify indexing completed (poll the index/`list_sources`) or — MACAE-style — index synchronously in-script so readiness no longer depends on the async Functions pipeline.

---

## 9. Clarifying questions / decisions for the follow-up

1. **Seed-scope unattended default.** Should `azd up` seed `all` by default (drop `interactive`, set a default scope) so a bare `azd up` produces a populated site, matching the user's "ready-to-use" goal? Today it skips silently without `AZURE_ENV_SAMPLE_DATA`.
2. **Sync vs async indexing for the seed.** Keep the async Functions pipeline (current, fragile, but production-realistic) and add a completion check (poll `GET /api/admin/documents` / index count) so the seed fails loudly on an empty index — or add a MACAE-style synchronous in-script indexer for the seed path so readiness doesn't depend on `batch_push`?
3. **Reused-resource self-heal.** Land the planned `post_provision.py` U2 (`_reconcile_reused_resource_posture`) + U3 (stale-EG-subscription prune) so reused-account drift (BUG-0086/0087) stops breaking the cloud seed/ingestion.
4. **`.docx` happy path.** BUG-0088 (open) means a `.docx` in the seed corpus silently fails. Either fix the `.docx` parser or scope the default seed to PDFs only until it's fixed.
5. **Prod admin identity.** BUG-0090 (open) — the deployed site's admin panel is unreachable until an Easy Auth identity source is wired; "fully functional" should include resolving this.
