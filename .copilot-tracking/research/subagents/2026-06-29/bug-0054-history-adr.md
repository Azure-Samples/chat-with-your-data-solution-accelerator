# Research — BUG-0054 current state and designed fix

Status: Complete
Date: 2026-06-29
Output file: .copilot-tracking/research/subagents/2026-06-29/bug-0054-history-adr.md

## Research questions

1. Full BUG-0054 detail from v2/docs/bugs.md (symptom, root cause, severity/area/status, dated updates, referenced SHAs/ADRs/bugs).
2. Full ADR 0028 (decision, blob_event translator design, ingestion_trigger flag, consequences, rejected alternatives).
3. Worklog mentions of BUG-0054 / blob_event / ingestion_trigger / event_grid / doc-processing-poison — implemented in-repo vs deferred to cloud, with dates.
4. development_plan.md §0.1/§0.2 and WI-01/WI-02 tracked items for BUG-0054.
5. Implemented vs remaining split; which bugs gate the cloud cutover.

---

## 1. BUG-0054 — verbatim from v2/docs/bugs.md (detail subsection, lines ~973–991)

**Heading:** `### BUG-0054 — Event Grid blob-created events poison the doc-processing queue (schema mismatch)`

**Classification:** Area: infra. Severity: medium. **Status: open** — fix implemented + proven locally; cloud deploy of the `blob_event` translator **deferred**. (found 2026-06-16, fix designed + locally validated 2026-06-20).

**Symptom:** the `doc-processing-poison` queue holds 10 base64 `Microsoft.Storage.BlobCreated` Event Grid envelopes (inserted 13:46–13:48).

**Root cause:** a stray/legacy Event Grid subscription on the storage account delivers blob-created events into `doc-processing`, but `batch_push` expects CWYD ingestion envelopes (`{container, blob_filename, ingestion_job_id, …}`), not the Event Grid `Microsoft.Storage.BlobCreated` schema. The events fail validation, retry, and land in poison. **Noise/poison accumulation only — the events are distinct messages from the CWYD envelopes, so it does NOT block ingestion** — but it pollutes the poison queue and indicates a stray Event Grid → queue wiring that should be removed or pointed at a handler that understands the blob-event schema. The same 8-envelope artifact was noted under BUG-0034's poison cleanup.

**Fix design (ADR 0028):** a `blob_event` queue-trigger blueprint (`src/functions/blob_event/`) translates the raw Event Grid `BlobCreated` envelope into the CWYD `doc-processing` message, so the schema mismatch can never poison `doc-processing`. The Event Grid subscription is repointed off `doc-processing` onto a dedicated `blob-events` queue (with `blob-events-poison`) that only `blob_event` drains. A new `StorageSettings.ingestion_trigger` setting (`direct_enqueue` | `event_grid`; env `AZURE_INGESTION_TRIGGER`; bicep param `ingestionTrigger`; default `direct_enqueue`) lets the backend stop double-enqueuing once Event Grid owns ingestion — under `event_grid` the admin upload stores the blob and lets Event Grid drive the pipeline; under `direct_enqueue` (default) the backend enqueues to `doc-processing` as before.

**Locally validated end-to-end (2026-06-20):** with the local Functions host running `blob_event` against cloud storage, a blob dropped into the `documents` container flowed Event Grid → `blob-events` → `blob_event` → `doc-processing` → `batch_push` → pgvector, and the document appeared in `GET /api/admin/documents`. Test artifacts cleaned up afterward.

**Cloud deploy deferred (operator decision, 2026-06-20):** `azd deploy function` uploaded the package but exceeded azd's 20-minute wait (Flex Consumption remote-build slowness — same env friction class as BUG-0058 / BUG-0062). The cloud Function App still served the prior five functions (`add_url`, `batch_push`, `batch_start`, `health`, `search_skill`); `blob_event` was NOT registered, and a forced `syncfunctiontriggers` confirmed nothing new deployed. Separately, `blob_event` is a queue trigger, so in Flex it carries the same **BUG-0053** scale-from-zero risk `batch_push` had — cloud `blob_event` reliability is coupled to that always-ready config.

**Live state left coherent:** the backend stays on `direct_enqueue` (`AZURE_ENV_INGESTION_TRIGGER` is unset → the default), so admin uploads keep working via the direct enqueue path. The env flag was deliberately NOT flipped to `event_grid` (that would remove the backend enqueue while no cloud `blob_event` drains `blob-events`, breaking cloud ingestion). The Event Grid subscription points at `blob-events` (matching the committed `infra/main.bicep`); those events only drain while the local Functions host is running. A prepackage gap surfaced (staged artifact omitted `blob_event`) and was fixed under BUG-0078 with a guard test.

**To resume (verbatim):** the `alwaysReady` instance for `function:blob_event` is now in `infra/main.bicep` (added 2026-06-29, guarded by `tests/infra/test_main_bicep.py::test_function_app_keeps_blob_event_always_ready`), so the remaining work is **cloud-only** — deploy `blob_event` to the cloud Function App (retry `azd deploy function --timeout 2400`, or diagnose the Flex remote-build hang), then `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision` to flip off the backend double-enqueue, and re-validate end-to-end in the cloud.

**References + related bugs:** worklog/2026-06-16.md, worklog/2026-06-20.md; ADR 0028; related **BUG-0053** (scale-from-zero), **BUG-0058** (stale deploy artifact), **BUG-0078** (prepackage allow-list), **BUG-0077** (BlobDeleted follow-up).

**Commit SHA referenced (from the BUG-0077 table row / line 113):** `a214182` (2026-06-22) — the BlobDeleted classification + de-index path + both EG subscriptions filtering create+delete.

> NOTE / staleness: This detail subsection was last edited 2026-06-29 but its "cloud deploy deferred" / "blob_event not registered" prose predates **BUG-0080** (2026-06-24), whose table row states `blob_event` is now **live (6 functions)** in the cloud after the Flex deploy was fixed. See §5 reconciliation.

---

## 2. ADR 0028 — Event Grid is the single trigger for blob ingestion

File: v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md

- **Status:** Accepted. **Date:** 2026-06-20. **Phase:** 6 (Functions blueprints / modular RAG indexing pipeline; BUG-0054). **Pillar:** Stable Core (the blob-ingestion trigger contract).
- **Companion:** ADR 0002 (UAMI + RBAC, no shared keys). References BUG-0054, BUG-0056, BUG-0053, BUG-0058.
- **Revised 2026-06-20:** the delivery mechanism changed from an Event Grid *trigger* (AzureFunction destination, option B2) to a dedicated `blob-events` Storage Queue + a queue-trigger translator (option **B1**). The single-trigger architecture is unchanged; only the wire from topic → function changed.

### Context
- The infra deploys an Event Grid **system topic** (`evgt-<SUFFIX>`) on the storage account with one subscription `blob-created-to-doc-processing` forwarding every `Microsoft.Storage.BlobCreated` under `/documents/` into `doc-processing`. Intent: "drop a file → it auto-ingests."
- It never worked: the only `doc-processing` consumer is `batch_push`, which validates a CWYD `BatchPushQueueMessage` (`container_name`, `filename`, `ingestion_job_id`, `force_reindex`; frozen, `extra="forbid"`). A `BlobCreated` event is a different schema → every event fails validation, retries, poisons (BUG-0054). **No translator was ever written.**
- Reference accelerators: **MACAE** has no Event Grid ingestion (it seeds data at provision time via `infra/scripts/index_datasets.py`). **CWYD v1** *does* drive ingestion from Event Grid but via a polymorphic consumer (`code/backend/batch/batch_push_results.py`) that branches on `eventType` and handles `BlobCreated`/`BlobDeleted` directly alongside the legacy envelope. v2 deliberately does NOT copy v1's loose-dict consumer (no-imitate-v1) — B1 adds a small typed translator that keeps `batch_push` single-schema.
- **Deciding product fact:** operators bulk-upload by dropping files directly into the `documents` blob container (Storage Explorer, azd-seeded sample data) — a workflow that bypasses the admin API. Those files only fire `BlobCreated`; with no handler they were never ingested. So the path is genuinely needed.
- **Encoding fact:** Event Grid delivers to a Storage Queue as raw (non-base64) JSON, which is exactly why `messageEncoding = none` (set host-wide by BUG-0056) is the standard config — so no encoding change is needed. The `blob_event` translator additionally tolerates either raw or base64 event bodies defensively.

### Decision (5 points)
1. **Build the missing handler as a queue-trigger translator behind a dedicated `blob-events` Storage Queue (option B1).** New Functions blueprint `blob_event` (`v2/src/functions/blob_event/`) is a `@bp.queue_trigger` on a new `blob-events` queue. The EG system topic delivers `BlobCreated` to `blob-events` (StorageQueue destination, same managed-identity delivery). The translator reads the raw event, extracts the blob `subject`, builds a `BatchPushQueueMessage`, and enqueues it to `doc-processing` via the existing `enqueue_push_message` producer. `batch_push` is unchanged; `doc-processing` stays single-schema, single-encoding. Pure bicep (queue exists at provision time — no function-existence dependency).
2. **Event Grid becomes the single trigger for blob ingestion (no double-processing).** Any blob written to `documents/` (bulk drop, admin upload, anything) ingests through exactly one path: Event Grid → `blob-events` → `blob_event` → `doc-processing` → `batch_push`. Consequently the backend admin upload (`backend.services.ingestion.upload_document`) reduces to **write-the-blob-only** under `event_grid`; its direct `doc-processing` enqueue is removed.
3. **`batch_start` / reprocess stays as the explicit "reprocess everything" admin action** (enqueues existing blobs; never double-fires EG). `add_url` is unaffected (fetches a URL, indexes inline; no blob written).
4. **Repoint the subscription; delete nothing.** Bicep subscription destination changes `doc-processing` queue → `blob-events` queue (still StorageQueue, managed-identity delivery, `deliveryWithResourceIdentity`, since `allowSharedKeyAccess = false`). System topic + `BlobCreated` + `documents/` filter kept; the account-scoped Storage Queue Data Message Sender role kept. A `blob-events` (+ `blob-events-poison`) queue is added.
5. **Rollout order preserves a working pipeline at every step.** Land the `blob_event` handler + bicep repoint first (EG starts working; brief harmless idempotent double-ingest during rollout), validate live, then remove the backend enqueue **last** (eliminating the double → clean single-trigger).

### The `ingestion_trigger` flag
- `IngestionTrigger` `StrEnum`: `direct_enqueue` | `event_grid`. Hard `StrEnum` with no `str` arm (env discriminator, no registry dispatch — Hard Rule #11).
- `StorageSettings.ingestion_trigger` field; env var `AZURE_INGESTION_TRIGGER`; default `direct_enqueue` (so local dev + every existing deploy keep the backend-side enqueue).
- bicep param `ingestionTrigger` (`@allowed(['direct_enqueue','event_grid'])`, default `direct_enqueue`), bound as `AZURE_INGESTION_TRIGGER` on the **backend** Container App only (not the Functions app — only the backend's `upload_document` reads it). Mapped in both `main.parameters.json` + `main.waf.parameters.json` as `${AZURE_ENV_INGESTION_TRIGGER=direct_enqueue}` so an operator flips it with `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid`.
- `upload_document` enqueues the `BatchPushQueueMessage` only when the trigger is `DIRECT_ENQUEUE`; under `EVENT_GRID` it writes the blob only and returns `queued=False`.

### Consequences
- **+** Bulk-drop ingestion works (no admin-API call). Exactly one ingestion path; backend decoupled from `doc-processing` for uploads. Dedicated `blob-events` queue keeps `doc-processing` single-schema; `batch_push` untouched. Managed-identity delivery preserved; change is pure bicep. Nothing deleted (subscription repointed).
- **−** Admin upload now depends on async Event Grid delivery (was synchronous in-process enqueue). Mitigated by EG retry (30×/24h) + `batch_start` reprocess valve. No UX regression (upload already returned before ingestion completed).
- **−** `UploadResponse` changes: `ingestion_job_id` no longer correlates to the real ingest job under `event_grid` (the `blob_event` handler mints its own envelope id), and `queued` shifts meaning. The field is dropped or marked informational; the UX polls `GET /api/admin/documents` either way.
- **−** A new `blob-events` (+ poison) queue and a small translator are added (one extra hop). Depends on host `messageEncoding = none`; tolerates base64 defensively.
- **−** In the cloud, all queue-driven ingestion (existing + new) is gated by **BUG-0053** (Flex scale-from-zero never wakes `batch_push`); full cloud bulk-ingest may require that resolved. Local dev unaffected.

### Rejected alternatives
- **B2 — Event Grid *trigger* function (AzureFunction destination).** Originally chosen, then rejected: (a) `AzureFunction` destination does NOT support managed-identity delivery — EG fetches the function's *access key* (deviates from ADR 0002 no-keys posture); (b) requires the target function to already exist so EG can fetch its key at subscription-creation, which fails the azd provision-before-deploy order (would force a `postdeploy az eventgrid` script). The chosen B1 queue destination has neither problem.
- **C — MACAE-style provision-time batch indexing.** A post-provision script ingests `data/` and leaves the EG subscription idle. Rejected as the primary mechanism: does NOT deliver runtime bulk-drop auto-ingest (the operator's actual need); could complement B1 for first-boot seeding.
- **2c — accept idempotent double-ingestion.** Keep both the admin enqueue + EG handler; admin uploads ingest twice (correct result, double embedding cost). Rejected: permanent redundant path + avoidable cost.
- **Delete the Event Grid subscription.** Minimal cleanup if blob-drop auto-ingest were unwanted. Rejected: the operator uses bulk upload, so the feature is needed.

### Follow-ups (in ADR)
- BUG-0056 encoding back-port — landed in `host.json` (`extensions.queues.messageEncoding = none`); the live `az`-applied app-setting override is redundant once the package deploys.
- BUG-0053 (cloud scale-from-zero) — tracked separately; gates cloud bulk-ingest end-to-end.
- BUG-0058 (stale `build-functions/` artifact) — the function redeploy that ships `blob_event` must run `prepackage` first.

---

## 3. Worklog mentions — implemented in-repo vs deferred to cloud

### worklog/2026-06-16.md (discovery)
- BUG-0054 first logged as "Event Grid poison (open)": `doc-processing-poison` holds 10 base64 `BlobCreated` envelopes from a stray EG → `doc-processing` wiring. Noise/poison only; should be removed. Listed alongside the BUG-0053 scale-from-zero investigation. Poison queues later cleared with operator confirmation (`doc-processing-poison` 22→0, `doc-processing-local-poison` 10→0).

### worklog/2026-06-20.md (design + full in-repo build + local validation + deferral)
Implemented in-repo this day (all green, tests-first):
- **Wrote ADR 0028.**
- **U1** — `event_parser.py` `parse_blob_created_subject(subject) -> ParsedBlobRef | None` (extracts container + filename; skips non-blob/malformed). 11 tests.
- **U2** — `blob_event_handler(subject, queue_client)` → builds `BatchPushQueueMessage`, enqueues to `doc-processing` via `enqueue_push_message`. 4 tests.
- **U3** (later removed) — `log_event_grid_errors` decorator (pre-pivot).
- **U4** (later reworked) — `@bp.event_grid_trigger` blueprint + `function_app.py` registration.
- **Pivot B2 → B1** (operator-confirmed): EG → dedicated `blob-events` Storage Queue → `blob_event` *queue* trigger.
- **B1 Unit A** — `subject_from_event_message(raw)` (later removed as dead code). 7 tests.
- **B1 Unit B** — blueprint reworked to `@bp.queue_trigger` on literal `blob-events`, wrapped by `log_queue_errors`. 28 tests.
- **B1 Unit C** — removed the dead `log_event_grid_errors` decorator + alias + 4 tests.
- **U5 (bicep)** — added `blobEventsQueueName = 'blob-events'` + `blob-events` (+ `blob-events-poison`) queues to both new-storage and existing-storage paths; repointed BOTH subscriptions' StorageQueue destination `doc-processing` → `blob-events` (AVM `blob-created-to-doc-processing` + v1-reuse `cwyd2-blob-created-doc-processing`); kept managed-identity delivery + sender role. Subscription names retained deliberately (rename would orphan under azd incremental). `az bicep build` exit 0.
- **U6** — `IngestionTrigger` StrEnum + `StorageSettings.ingestion_trigger` (env `AZURE_INGESTION_TRIGGER`, default `direct_enqueue`); `upload_document` conditional enqueue (EG mode writes blob only, `queued=False`). 4 tests.
- **U6-infra (bicep)** — `@allowed` `ingestionTrigger` param (default `direct_enqueue`) → `AZURE_INGESTION_TRIGGER` on backend container + output + both params files mapped `${AZURE_ENV_INGESTION_TRIGGER=direct_enqueue}`. `az bicep build` exit 0.
- **Live-validated end-to-end** (local host vs cloud storage): `eg-live-test.txt` dropped into cloud `documents` → ingested via EG → `blob-events` → `blob_event` → `doc-processing-local` → `batch_push` → pgvector → appeared in admin list (chunks=1), `blob-events-poison=0`. "The Event Grid architecture is proven." Test artifacts cleaned up.
- **BUG-0078** — prepackage allow-list omitted `blob_event`; fixed + guard test.
- **Cloud `blob_event` deploy stalled → deferred (operator decision):** `azd deploy function` uploaded but exceeded the 20-min azd timeout (Flex remote-build slowness). `az functionapp function list` showed only the prior five functions; `syncfunctiontriggers` returned `{}`. Coupled to BUG-0053. Backend left on `direct_enqueue` (`AZURE_ENV_INGESTION_TRIGGER` unset); flag NOT flipped.
- **Next (cloud cutover) listed:** deploy `blob_event` (prepackage first, BUG-0058/0078); add `alwaysReady` for `function:blob_event` (BUG-0053); validate in cloud; flip `AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision`; U7 close.

### worklog/2026-06-22.md (BUG-0077 BlobDeleted unification — committed `a214182`)
In-repo (Phase 1 of BUG-0054 / BUG-0077):
- **Unit A** — `event_parser.py` event-type-aware: `BlobEventType(StrEnum)` (CREATED/DELETED) + `_EVENT_TYPE_BY_VALUE` reverse map (no try/except control flow); `ParsedBlobEvent(BaseModel, frozen, extra="forbid")`; `_decode_event_payload(raw)`; `parse_blob_event(raw) -> ParsedBlobEvent | None`. 11 new tests (29 total).
- **Unit B+C (merged)** — `handler.py`: `handle_blob_created(ref, queue_client)` (enqueue) + `handle_blob_deleted(ref, search)` (`await search.delete_by_source(ref.filename)`); both return frozen `BlobEventOutcome`. `blueprint.py` `_execute` classifies via `parse_blob_event` and branches: CREATED → queue client → `handle_blob_created`; DELETED → registry-first search provider (mirrors `batch_push`; pgvector pool only on pgvector path) → `handle_blob_deleted`.
- **Unit D (bicep)** — `Microsoft.Storage.BlobDeleted` added to `includedEventTypes` on BOTH EG subscriptions. `az bicep build` exit 0.
- **Dead-code cleanup** — removed `subject_from_event_message` + its 7 tests (dead since blueprint switched to `parse_blob_event`).
- **Phase 2 (deploy + trigger flip) deferred** behind BUG-0058 (prepackage) + BUG-0053 (alwaysReady). Both BUG-0054 + BUG-0077 stay open until Phase 2 lands + live verify (delete blob → confirm chunks drop).

### worklog/2026-06-29.md (alwaysReady in-repo fix + WI-02 doc fix — current)
- **BUG-0054 in-repo fix:** added `{ name: 'function:blob_event', instanceCount: 1 }` to the Flex `functionAppConfig.scaleAndConcurrency.alwaysReady` set in `main.bicep` (test-first, mirroring the BUG-0053 fix for `batch_push`), guarded by new `test_function_app_keeps_blob_event_always_ready` in `tests/infra/test_main_bicep.py`. Infra suite 38/38; `az bicep build` exit 0.
- **Doc reconciliation:** verified `host.json` carries `extensions.queues.messageEncoding = none` (main.bicep does not, nor needs to). Reworded stale ADR 0028 Follow-ups + BUG-0056 note to "landed in host.json"; trimmed BUG-0054 "To resume" to cloud-only.
- **WI-02 (Option B):** clarified the `ingestion_job_id` field description on `UploadResponse` + `IngestUrlResponse` in `models/admin.py` to state the id is informational under `EVENT_GRID`. Doc-only. `test_admin.py` + `test_services_ingestion.py` → 159 passed.
- **Deferred (not touched inline):** the BUG-0054 cloud cutover (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid`) = **WI-01**, gated on BUG-0058 + Flex remote-build timeout; and the dead `ingestion_job_id` *drop* (Option C). BUG-0054 stays open.
- **PD-01 re-decided A → B:** dropping `ingestion_job_id` (Option C) is a regression while `DIRECT_ENQUEUE` is the live trigger (the id is a real queue-message id + structured-log field, a 3-sibling wire contract, asserted by FE tests). Applied the safe mark-informational half (Option B); the drop (Option C) stays gated on WI-01.

### worklog/2026-06-23.md
- Only a passing mention (line 34): on a fresh func host start, `blob_event` faulted state cleared — local-host operational note, not a BUG-0054 milestone.

---

## 4. development_plan.md §0.1/§0.2 + WI-01/WI-02

- **No §0.1 / §0.2 debt-queue row for BUG-0054, blob_event, ingestion_trigger, event_grid, or ADR 0028.** Grep over `v2/docs/development_plan.md` for `BUG-0054` and for `BUG-0054|blob_event|ingestion_trigger|WI-01|WI-02|0028` returned **empty**.
- This is by design per Hard Rule #12 (defect-vs-debt split): §0.1/§0.2 hold *phase debt and tasks*; *defects* live in `bugs.md`. BUG-0054 is a defect, so its tracking is entirely in `bugs.md` + the worklogs. (No §0.1 pointer row was added because BUG-0054 needs no phase-audit visibility.)
- **WI-01 and WI-02 are session-scoped work-item labels introduced in worklog/2026-06-29.md** — they are NOT development_plan.md rows:
  - **WI-01** = the BUG-0054 **cloud cutover** (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid`). State: **deferred**, gated on BUG-0058 cloud verification + the Flex remote-build timeout.
  - **WI-02** = the `ingestion_job_id` mark-informational rework on `UploadResponse` / `IngestUrlResponse`. State: **done** (Option B applied 2026-06-29, doc-only). The Option C *drop* is deferred to WI-01.

---

## 5. Implemented vs remaining

### Implemented in-repo (all merged, green)
- `blob_event` blueprint package complete: `event_parser.py` (`parse_blob_created_subject`, `parse_blob_event`, `BlobEventType`, `ParsedBlobRef`, `ParsedBlobEvent`, `_decode_event_payload`), `handler.py` (`handle_blob_created`, `handle_blob_deleted`, `BlobEventOutcome`), `blueprint.py` (`@bp.queue_trigger` on `blob-events`, classify + dispatch), registered in `function_app.py`.
- `IngestionTrigger` StrEnum + `StorageSettings.ingestion_trigger` (env `AZURE_INGESTION_TRIGGER`, default `direct_enqueue`).
- `upload_document` conditional enqueue (only `DIRECT_ENQUEUE` enqueues; `EVENT_GRID` writes blob only, `queued=False`).
- bicep: `blob-events` (+ `blob-events-poison`) queues; both EG subscriptions repointed `doc-processing` → `blob-events`; `Microsoft.Storage.BlobDeleted` added to both subscriptions' `includedEventTypes` (BUG-0077 Phase 1).
- bicep: `ingestionTrigger` param + `AZURE_INGESTION_TRIGGER` backend env + output + both params files mapped.
- bicep: `{ name: 'function:blob_event', instanceCount: 1 }` in the Flex `alwaysReady` set (2026-06-29), guarded by `test_function_app_keeps_blob_event_always_ready`.
- `host.json`: `extensions.queues.messageEncoding = none` (BUG-0056 back-port; authoritative, no bicep parity needed).
- prepackage allow-list includes `blob_event` (BUG-0078 fixed + guard test).
- WI-02: `ingestion_job_id` field description marked informational under `EVENT_GRID` on `UploadResponse` + `IngestUrlResponse` (doc-only).
- Locally validated end-to-end (local host vs cloud storage), 2026-06-20.

### Remaining / OPEN (cloud-only = WI-01)
- **Flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid`** via `azd env set` + `azd provision` — NOT done. Backend is still on `direct_enqueue` (the env var is unset). This is the actual remaining gate that closes BUG-0054.
- **Cloud end-to-end re-validation** with EG owning ingestion (stop the local host, drop a test blob, confirm it ingests via cloud `blob_event`).
- **Option C** (drop `ingestion_job_id` from `UploadResponse`) — deferred to WI-01, applies only once `EVENT_GRID` is live.
- **BUG-0077 Phase 2** — cloud deploy + live blob-delete verification (delete a blob in Storage Explorer → confirm its chunks drop). Still open.

### Reconciliation note — deploy of `blob_event` may already be done
- The BUG-0054 detail subsection + the 2026-06-29 worklog still describe the **cloud cutover** as "deploy `blob_event` + flip the env var", implying `blob_event` is NOT yet deployed.
- **BUG-0080 (2026-06-24, fixed)** contradicts this: it root-caused the multi-day Flex deploy hang to the `agent-framework==1.7.0` umbrella meta-package (pulled `agent-framework-hyperlight` → `hyperlight-sandbox-backend-wasm`, unresolvable on the Functions host's Python 3.11). Fix: repin to `agent-framework-core==1.7.0`, ship via pre-built `.python_packages` + `func azure functionapp publish --no-build`. Result (verbatim): "**`blob_event` now live (6 functions)**, `released-package.zip` advanced 2026-06-17 → 2026-06-24, `/api/health` → ok. **Unblocks cloud verification of BUG-0054 / BUG-0055 / BUG-0058 / BUG-0077.**"
- So as of 2026-06-24 `blob_event` appears **already deployed** to the cloud Function App, and the **only** genuinely remaining cutover step is the `AZURE_ENV_INGESTION_TRIGGER` → `event_grid` flip + re-validation. The "deploy `blob_event`" half of WI-01 looks stale in the BUG-0054 detail + 2026-06-29 worklog (which weren't reconciled against BUG-0080).

---

## Bugs that gate the cloud cutover (status)
- **BUG-0053** (Flex scale-from-zero never wakes a queue trigger) — addressed by the `alwaysReady` config; `function:blob_event` added to that set 2026-06-29.
- **BUG-0058** (stale `build-functions/` artifact / prepackage hook scope) — fixed in code 2026-06-23 (hook moved to service-scoped `services.function.hooks.prepackage`); stays open only until a live `azd deploy function` confirms regeneration.
- **BUG-0078** (prepackage allow-list omitted `blob_event`) — fixed 2026-06-20 + guard test.
- **BUG-0062** (Flex storage 403 firewall) — fixed live; durable bicep pending. Same env-friction class as the deploy timeout.
- **BUG-0080** (agent-framework umbrella → Flex Oryx build hang) — fixed 2026-06-24; the actual unblock that got `blob_event` live (6 functions) in the cloud.
- **BUG-0077** (BlobDeleted de-index follow-up) — Phase 1 code+bicep done (`a214182`); Phase 2 cloud verify shares the same deploy gate; still open.

---

## Clarifying questions
1. **Is `blob_event` already deployed to the cloud Function App?** BUG-0080 (2026-06-24) says "blob_event now live (6 functions)", but the BUG-0054 detail + 2026-06-29 worklog still frame "deploy blob_event" as pending under WI-01. If BUG-0080's deploy stuck, the remaining BUG-0054 work is just the `AZURE_ENV_INGESTION_TRIGGER` → `event_grid` flip + cloud re-validation — and the BUG-0054 detail/2026-06-29 worklog "To resume" text is stale and should be reconciled.
2. Is the current task to (a) reconcile the stale BUG-0054 status against BUG-0080, (b) perform the cloud `event_grid` flip + validation, or (c) something else? Research did not assume an action.

## Recommended next research (not done this session)
- [ ] Read the BUG-0080 detail subsection in full (only the table row was read) to confirm exactly which functions are live post-2026-06-24 and whether the env flip was attempted.
- [ ] Inspect `v2/infra/main.bicep` to confirm the live committed state of the `ingestionTrigger` param default + the `alwaysReady` set + both EG subscription destinations/filters (this research relied on worklog/bug prose, not a direct bicep read).
- [ ] Confirm the current `blob_event` source files exist on disk as described (`event_parser.py`, `handler.py`, `blueprint.py`) and match the documented symbols (not read directly this session).
- [ ] Check for any worklog after 2026-06-29 (e.g. a later session) that may have performed the env flip.
