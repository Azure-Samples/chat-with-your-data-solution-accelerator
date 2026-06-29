<!-- markdownlint-disable-file -->
# CWYD v2 — Why Functions don't ingest files after `azd up` (research, read-only)

Scope: trace the intended `azd up → seed → trigger → process → index` chain end-to-end, find the exact break point(s) for "functions are not processing the files," and evaluate the operator's six candidate root causes. **No code was modified.** All evidence is file + line citations under `v2/`.

---

## TL;DR — root cause(s)

Two independent, high-confidence root causes, both of which produce the exact symptom "site deploys fine but nothing gets ingested," and both of which `azd up` reports as **success**:

1. **RC-1 — the post-deploy sample-data seed is SILENTLY SKIPPED under `azd up`.** `upload_sample_data.py` resolves its scope as `--set` → `AZURE_ENV_SAMPLE_DATA` env → interactive menu → **skip**. Under `azd up` there is no TTY (`sys.stdin.isatty()` is `False`), and with no `AZURE_ENV_SAMPLE_DATA` override the script returns `SeedScope.SKIP` and exits `0`. The hook is `continueOnError: true`, so the skip is invisible. **No blobs are uploaded and nothing is enqueued → the function has nothing to process.** This is the single most likely cause of a freshly-deployed, empty site.
   - Seed resolution: [v2/scripts/upload_sample_data.py](../../../../v2/scripts/upload_sample_data.py) `resolve_selection` (`if not is_tty: return SeedScope.SKIP`) and `main` (`sys.stdin.isatty()` passed in; `SKIP → print "skipping seed"; return 0`).
   - Hook config: [v2/azure.yaml](../../../../v2/azure.yaml) `hooks.postdeploy` (`run: ./scripts/upload-sample-data.sh`, `continueOnError: true`, `interactive: true`) and its own comment: "a non-interactive shell with no override skips the seed."
   - Confirmed live in the worklog: [v2/docs/worklog/2026-06-25.md](../../../../v2/docs/worklog/2026-06-25.md) Gotcha 2 — "the postdeploy sample-data hook prints its interactive menu but `input()` hits EOF under azd (no TTY) … the seed is skipped (swallowed by `continueOnError: true`)." The same worklog shows the seed working only when forced with `--set all` / `AZURE_ENV_SAMPLE_DATA=all`.

2. **RC-2 — reused-resource network/topology drift (this is a REUSED-storage deployment).** The env reuses pre-existing data resources (`existingStorageName` set → `useExistingStorage = true`). The v2 Bicep guards every storage module with `if (!useExistingStorage)`, so it **never manages the reused account's network posture or its stray Event Grid subscriptions.** The reused storage account is left `publicNetworkAccess=Disabled` from a prior life while the Container Apps env is **not** VNet-integrated (`enablePrivateNetworking=false`), so the Flex function host can't reach storage → host stays `503` and `azd deploy function`'s package upload is refused `403`. A leftover **v1 Event Grid subscription** also dumps raw `BlobCreated` envelopes onto `doc-processing`, which `batch_push` can't deserialize → poison.
   - Reuse switch: [v2/infra/main.bicep](../../../../v2/infra/main.bicep) `param existingStorageName` / `var useExistingStorage = !empty(existingStorageName)`; the whole `storageAccount` module is `if (!useExistingStorage)`, and the reuse branch (`existingStorage*` resources) only re-declares containers/queues + RBAC — it sets **no** `networkAcls` / `publicNetworkAccess`.
   - Confirmed live: worklog Gotcha 4 (**BUG-0086** — reused Cosmos + Storage firewalls block the non-VNet runtimes), Gotcha 5 (host stays `503` until the package is re-staged), Gotcha 6 (**BUG-0087** — legacy v1 EG subscription poisons `doc-processing`), and "Backlog C — most uploads are not indexed" (Event Grid events expired during the long function/storage outage).

Everything else the operator suspected (trigger env vars, RBAC, the Event Grid wiring itself, the build-functions staging) is **correctly configured in the current tree** and is not the break — details and citations below.

---

## The intended chain and where it breaks

```
azd up
 ├─ provision (Bicep)            ──►  Function App (Flex FC1), Storage, queues, Event Grid, RBAC, AI/Search
 ├─ deploy backend/frontend/function
 │     └─ function: hooks.prepackage stages build-functions/ ──► azd zip-deploys ──► Flex Oryx remote build
 └─ postdeploy hook: upload_sample_data.py
        ├─ upload sample PDFs ──► documents container          ◄── BREAK at RC-1: SKIPPED (no TTY) → 0 blobs
        └─ enqueue BatchPushQueueMessage ──► doc-processing      ◄── BREAK at RC-1: SKIPPED → 0 messages
                                  │
   doc-processing queue ──► batch_push (queue trigger)           ◄── BREAK at RC-2: host 503 / can't reach storage
        └─ download blob ──► parse ──► embed ──► write index
                                  │
   (alt path) blob upload ──► Event Grid BlobCreated ──► blob-events queue ──► blob_event ──► doc-processing
```

- **Primary path (default `ingestion_trigger=direct_enqueue`):** the seed enqueues directly to `doc-processing`; `batch_push` consumes. RC-1 stops this at the source (nothing enqueued). RC-2 stops it downstream (host can't poll/read storage).
- **Event Grid path (always provisioned in Bicep regardless of mode):** blob → system topic → `blob-events` → `blob_event` translator → `doc-processing` → `batch_push`. Note `blob_event` is a **queue trigger** and has **no `alwaysReady` instance** (only `batch_push` does), so on Flex it shares the BUG-0053 cold-start-from-zero problem in event-grid mode.

---

## Evaluation of the operator's six candidates

| # | Candidate | Verdict | Evidence |
|---|-----------|---------|----------|
| i | build-functions staging empty/stale | **Mostly NOT the cause now** (one open caveat) | `build-functions/` is gitignored and regenerated by `prepackage_function.py` on every deploy ([v2/.gitignore](../../../../v2/.gitignore)); empty-on-disk is expected. The prepackage hook is now **service-scoped** in [v2/azure.yaml](../../../../v2/azure.yaml) (fixes BUG-0058 on targeted deploy). Historical staging failures are all fixed: BUG-0078 (stale allow-list), BUG-0080 (the umbrella `agent-framework` dep hung the Oryx remote build for ~2 days; repinned to `agent-framework-core`). **Open caveat:** BUG-0058 (azd skipping the prepackage hook on the per-service `deploy` path) is still marked OPEN. |
| ii | Missing trigger env vars | **NO** | Function App `appSettings` are complete: `AzureWebJobsStorage__accountName/__credential=managedidentity/__clientId`, `AZURE_DOC_PROCESSING_QUEUE=doc-processing`, `AZURE_AI_SERVICES_ENDPOINT`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_DOCUMENTS_CONTAINER` ([v2/infra/main.bicep](../../../../v2/infra/main.bicep) `functionApp` siteConfig). `batch_push` binds `queue_name="%AZURE_DOC_PROCESSING_QUEUE%"`; `blob_event` binds the literal `blob-events`; both exist. Queue base64/raw mismatch (BUG-0056) is durably fixed in [v2/src/functions/host.json](../../../../v2/src/functions/host.json) (`extensions.queues.messageEncoding: "none"`), matching the seed/backend producers' raw-JSON `QueueClient(message_encode_policy=None)`. |
| iii | Event source not provisioned / not pointed at the function | **NO for the default path; INVERTED for reused storage** | Event Grid is fully wired: system topic + `blob-created-to-doc-processing` subscription filtering `BlobCreated`+`BlobDeleted` under `/containers/documents/` → `blob-events` queue, with the role-before-subscription fix (BUG-0061) ([v2/infra/main.bicep](../../../../v2/infra/main.bicep) `eventGridSystemTopic` / `blobCreatedSubscription` / `eventGridQueueSenderRole`). The real reused-storage problem is the **opposite**: a leftover *extra* v1 subscription delivering raw events to `doc-processing` (BUG-0087). Also `blob_event` has no `alwaysReady` instance, so event-grid mode shares BUG-0053. Default mode is `direct_enqueue`, so this path is not the primary break. |
| iv | Missing RBAC for the function identity | **NO** | The shared UAMI holds everything ingestion needs: Storage Blob Data Contributor (`ba92f5b4…`) + Storage Queue Data Contributor (`974c5e8b…`) + Storage Account Contributor (`17d1049b…`) on the account, plus Storage Blob Data Owner (`b7e6dc6d…`) for the Flex deployment package; Cognitive Services OpenAI User (`5e0bd9bd…`) + Cognitive Services User (`a97b65f3…`) for embeddings/parsing; Search Index Data Contributor + Search Service Contributor for index writes ([v2/infra/main.bicep](../../../../v2/infra/main.bicep) storage `roleAssignments`, AI Services `roleAssignments`, `flexDeploymentRole`). BUG-0052's missing Cognitive Services User is now in Bicep. |
| v | Post-deploy script uploads to the wrong container | **NO (right container) — but this is where RC-1 lives** | The seed uploads to `AZURE_DOCUMENTS_CONTAINER` (= `documents`) and enqueues to `AZURE_DOC_PROCESSING_QUEUE` (= `doc-processing`); both are emitted as azd outputs ([v2/infra/main.bicep](../../../../v2/infra/main.bicep) `output AZURE_DOCUMENTS_CONTAINER` / `AZURE_DOC_PROCESSING_QUEUE` / `AZURE_STORAGE_ACCOUNT_NAME` / `AZURE_INGESTION_TRIGGER`), so the "missing env → exit 2" sub-hypothesis is false. The actual defect is **RC-1**: the seed is *skipped* under azd's non-interactive shell, so it uploads to the *right* container — just *never runs*. |
| vi | Functions not deployed at all | **YES, historically and on reused-storage** | BUG-0080 (umbrella dep hung the Flex Oryx build → "deploy SUCCESS while shipping nothing" for ~2 days; fixed 2026-06-24). BUG-0062 + worklog Gotcha 2 (`azd deploy function` `403 InaccessibleStorageException` when storage `publicNetworkAccess=Disabled`, because the package zip uploads from the workstation over public internet). Worklog Gotcha 5 (the Flex host stays `503` after a storage outage until the package is **re-staged** via `azd deploy function`). On a reused-storage env (RC-2), this is a live failure mode. |

---

## The reused-resource dimension (most important context)

This deployment is **not a clean greenfield `azd up`** — it reuses pre-existing data resources (`existingStorageName`, and per the worklog also `AZURE_ENV_EXISTING_COSMOS_NAME`). That single fact drives most of the breakage, because the v2 Bicep deliberately does not touch a reused resource's runtime posture:

- **Network posture is unmanaged on reuse.** New-storage path sets `networkAcls.defaultAction = enablePrivateNetworking ? 'Deny' : 'Allow'` ([v2/infra/main.bicep](../../../../v2/infra/main.bicep) storage `networkAcls`). The reuse path (`existingStorage*` resources) sets containers/queues/RBAC but **no** `publicNetworkAccess` / `networkAcls`. So a reused account left `Disabled` from a prior life is unreachable by the non-VNet (`enablePrivateNetworking=false`) Flex host and Container App → function host `503`, package upload `403` (BUG-0086, Gotcha 4/5).
- **Stray subscriptions are unmanaged on reuse.** A leftover v1 `BlobCreated → doc-processing` (plain-delivery) Event Grid subscription on the reused account's system topic poisons `doc-processing` (BUG-0087, Gotcha 6).
- **Backlog of un-indexed blobs.** ~90 blobs sit in `documents` but only ~8 distinct PDFs are indexed — most uploads' Event Grid events expired during the extended outage; recovery is `POST /api/admin/documents/reprocess` ("Backlog C").

The worklog's own remediation plan (2026-06-25 §"Root-cause remediation plan — Option A") proposes self-healing this in `post_provision.py` (U2 reconcile network posture, U3 prune stray EG subscriptions) — i.e. the maintainers have already identified RC-2 as the recurring root-cause class.

---

## Deploy-mechanics caveats that mask the symptom

- **`azd deploy <service>` updates only the image; env/infra changes need `azd provision`/`azd up`.** The worklog's closing "Cross-cutting deploy discipline" note calls this out explicitly. Several past fixes were applied as live `az ... update` hotfixes (BUG-0051/0052/0059/0062/0063/0064) and back-ported to Bicep later or "pending," so a deployed env can drift from the IaC.
- **Observability is effectively off** (BUG-0055 App Insights zero telemetry; BUG-0089 backend read `environment=local`). When the function silently poisons or the host won't start, there are no traces — so "not processing" is a blind dig, which is exactly the operator's experience.
- **`.docx` specifically fails** (BUG-0088, OPEN). If the seeded/test corpus includes the MSFT 10-K `.docx`, those documents poison in `batch_push` while PDFs succeed — a partial-ingestion variant of the symptom.

---

## What's missing vs a MACAE-style "just works" flow

- **No non-interactive default for the seed.** MACAE-style accelerators seed deterministically. Here the seed defaults to *skip* under automation. A robust fix is to default the postdeploy scope to `all` (or read it from an azd env var the template sets) instead of skipping when there's no TTY.
- **No reconciliation of reused resources.** A clean `azd up` against fresh resources would set network posture and own the only Event Grid subscription. The reuse path needs the planned `post_provision.py` reconcile (network posture + stray-subscription prune) to be self-healing.
- **No `alwaysReady` for `blob_event`.** Only `batch_push` is kept warm; the event-grid path's translator can cold-start-stall on Flex (BUG-0053 class).

---

## Root-cause summary (crisp)

For "after `azd up`, the functions are not processing the files," in priority order:

1. **The sample-data seed is skipped** because `azd up` runs it without a TTY and no `AZURE_ENV_SAMPLE_DATA` override → zero blobs uploaded, zero messages enqueued, and the skip is hidden by `continueOnError: true`. **(RC-1 — the most probable cause of an empty, freshly-deployed site.)** Verify: did the operator pass `AZURE_ENV_SAMPLE_DATA=all` / `--set all`? If not, no data was ever seeded.
2. **Reused-storage network drift** leaves the Flex function host unable to reach storage (`publicNetworkAccess=Disabled` + non-VNet runtime), so the host returns `503`/can't poll the queue and `azd deploy function` is refused `403` — the function never actually runs. **(RC-2.)** A stray v1 Event Grid subscription separately poisons `doc-processing`.
3. **Function-deploy failures** (umbrella dependency hanging the Oryx build — fixed 2026-06-24; package not re-staged after a storage outage) can leave a `503`/empty function while `azd` reports success. **(Candidate vi.)**

Refuted as causes: missing trigger env vars (ii), missing RBAC (iv), and the core Event Grid wiring / wrong container (iii/v) — all are correctly configured in the current tree; the env vars, `host.json` `messageEncoding=none`, the UAMI role set, and the EG subscription are all present and correct.

**Fastest confirmation for the operator:** (a) check whether the seed ran — `documents` container blob count and `doc-processing` queue depth right after deploy; if both are empty, it's RC-1. (b) `GET <function>/api/health` — if `503`, it's RC-2 (storage unreachable / host not started). (c) `doc-processing-poison` depth > 0 with raw `BlobCreated` envelopes → RC-2's stray v1 EG subscription (BUG-0087) or `.docx` (BUG-0088).
