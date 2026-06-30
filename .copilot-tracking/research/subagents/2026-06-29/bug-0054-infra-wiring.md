# Research: BUG-0054 — Event Grid / queue wiring & `ingestion_trigger`

Status: Complete
Date: 2026-06-29
Output: `.copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md`

## TL;DR

- BUG-0054 is **open but the code/IaC fix is already implemented in the working tree** (status row line 113 of `v2/docs/bugs.md`; detail block lines 973–1003). What remains is **cloud-only**: deploy the `blob_event` Function + flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid`.
- The committed bicep Event Grid subscription **already delivers to the dedicated `blob-events` queue** (the fix), NOT `doc-processing` (the original bug). The *subscription resource name* is deliberately kept as `blob-created-to-doc-processing` so the destination repoint is an in-place azd update.
- `ingestion_trigger` default is `direct_enqueue` (backend enqueues to `doc-processing` itself). Live env is still on the default, so there is **no double-enqueue today**.

---

## 1. Bicep Event Grid system topic + event subscriptions

File: `v2/infra/main.bicep`.

### System topic (new-storage path)

- `module eventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.4'` — line **2350**, gated `if (!useExistingEventGridTopic)`.
  - `name: eventGridSystemTopicName` (var = `'evgt-${solutionSuffix}'`, line **2144**).
  - `source: effectiveStorageResourceId`, `topicType: 'Microsoft.Storage.StorageAccounts'`, `managedIdentities: { systemAssigned: true }` (lines ~2354–2360).
  - The subscription is intentionally NOT nested in the AVM module (BUG-0061 fix); it is a standalone sibling so the queue-sender role lands before Event Grid's delivery-authorization preflight.

### New-topic subscription — **delivers to `blob-events`** (the fix)

- `resource blobCreatedSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2024-12-15-preview'` — line **2402**, gated `if (!useExistingEventGridTopic)`.
  - `name: 'blob-created-to-doc-processing'` — line **2406** (NAME retained on purpose; comment lines 2403–2409 explain a rename would orphan the prior sub and leave it on `doc-processing`).
  - Destination: `endpointType: 'StorageQueue'`, `queueName: blobEventsQueueName` — line **2421** → resolves to `'blob-events'` (var line **2152**). **NOT `doc-processing`.**
  - Delivery: `deliveryWithResourceIdentity` with system-topic **SystemAssigned** MI (required because storage has `allowSharedKeyAccess=false`) — lines 2410–2424.
  - Filter: `includedEventTypes: ['Microsoft.Storage.BlobCreated','Microsoft.Storage.BlobDeleted']`, `subjectBeginsWith: '/blobServices/default/containers/${documentsContainerName}/'` (documents container only) — lines ~2426–2430.
  - `retryPolicy: { maxDeliveryAttempts: 30, eventTimeToLiveInMinutes: 1440 }`.
  - `dependsOn: [ eventGridSystemTopic, eventGridQueueSenderRole ]` (role-before-subscription, BUG-0061).
- Supporting role: `resource eventGridQueueSenderRole` line **2377** grants the topic's system MI **Storage Queue Data Message Sender** (`c6a89b2d-59bc-44d0-9896-0f6e12d7b80a`) on the storage account.

### Existing-topic reuse subscription — also delivers to `blob-events`

- `resource existingEventGridSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2024-12-15-preview'` — line **2472**, gated `if (useExistingEventGridTopic)`.
  - `name: 'cwyd2-blob-created-doc-processing'` (line ~2476, name retained for in-place repoint).
  - Destination `queueName: blobEventsQueueName` (= `'blob-events'`), delivery via **UserAssigned** UAMI (lines ~2479–2491).
  - Same filter/retry as the new-topic sub; `dependsOn: [ existingStorageQueueBlobEvents, existingStorageQueueContributor, existingQueueMessageSenderRole ]`.

### Verdict for question 1

**Both** Event Grid subscriptions (new-storage and reuse paths) target the dedicated **`blob-events`** queue — the committed bicep is the FIX state, not the bug state. The bug (subscription → `doc-processing` directly, schema-mismatch poison) existed on the live/legacy storage account; the repoint to `blob-events` is what `infra/main.bicep` now encodes.

### Function app `alwaysReady` / scaling

- `module functionApp 'br/public:avm/res/web/site:0.22.0'` — line **2180**.
- `scaleAndConcurrency` block (lines ~2226–2243):
  - `maximumInstanceCount: enableScalability ? 100 : 40`
  - `instanceMemoryMB: 2048`
  - `alwaysReady`: **two** entries —
    - `{ name: 'function:batch_push', instanceCount: 1 }`
    - `{ name: 'function:blob_event', instanceCount: 1 }` (added 2026-06-29; guarded by `test_function_app_keeps_blob_event_always_ready`).
  - This keeps the queue triggers warm so the first `blob-events` message after idle isn't lost to Flex scale-from-zero (the BUG-0053 class).
- Plan: `module functionPlan 'br/public:avm/res/web/serverfarm:0.7.0'` line **2161**, `skuName: 'FC1'` (Flex Consumption), `skuCapacity: 0`.
- The backend Container App separately uses `minReplicas: enableScalability ? 1 : 0` (main.bicep line **1811**) — unrelated to the function host.

---

## 2. `ingestion_trigger` setting

### Type / default

File: `v2/src/backend/core/settings.py`.

- `class IngestionTrigger(StrEnum)` — line **109**. Members: `DIRECT_ENQUEUE = "direct_enqueue"` (line **128**), `EVENT_GRID = "event_grid"` (line **129**). Hard `StrEnum`, **no `str` arm** (closed-set env discriminator, no registry dispatch, Hard Rule #11) — docstring lines 110–127.
- `StorageSettings.ingestion_trigger: IngestionTrigger = IngestionTrigger.DIRECT_ENQUEUE` — line **279** (env `AZURE_INGESTION_TRIGGER`, prefix `AZURE_`).
- **Default = `direct_enqueue`** (backend writes the `doc-processing` message itself; works without any Event Grid subscription; the only local-dev option).

### Branch sites

- `v2/src/backend/services/ingestion.py` → `upload_document(...)`:
  - `backend_enqueues = (settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE)` — line **301**.
  - `if backend_enqueues:` gate around building + enqueuing the `BatchPushQueueMessage` — the single behavioral branch (line ~309, inside the `storage_clients` async-with). Under `EVENT_GRID` the helper writes the blob only and returns `queued=False`.
- This is the **only** runtime branch on the flag. All other references are docstrings: `backend/models/admin.py` (lines 194, 217–218, 236, 240, 262), `backend/routers/admin.py` (line 555).

### Wiring through IaC

- Bicep param `param ingestionTrigger string = 'direct_enqueue'` — line **100**, `@allowed(['direct_enqueue','event_grid'])` lines 95–98.
- Bound onto the **backend Container App** appSettings: `{ name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }` — line **1945**.
- The param value sources from azd env: `main.parameters.json` / `main.waf.parameters.json` line 21 → `"${AZURE_ENV_INGESTION_TRIGGER=direct_enqueue}"`.
- Live azd env: `v2/.azure/cwyd-cdb-v2/.env` line 45 → `AZURE_INGESTION_TRIGGER="direct_enqueue"` (still default).
- The **Function App** appSettings (block starting ~line 2290) deliberately do **NOT** carry `AZURE_INGESTION_TRIGGER` — only the backend consumes it; the function host always translates whatever lands on `blob-events`.

---

## 3. Double-enqueue risk + guard status

**Risk shape:** if (a) the backend runs `direct_enqueue` (writes a `doc-processing` message on upload) AND (b) an Event Grid subscription also fires `BlobCreated` for that same uploaded blob, the blob could be ingested twice.

**Guard — design-level (mutually exclusive paths):**
- The `ingestion_trigger` flag is the guard. Under `DIRECT_ENQUEUE` the backend enqueues and Event Grid is expected NOT to own ingestion; under `EVENT_GRID` the backend `upload_document` skips the enqueue (`if backend_enqueues:` is false) and only Event Grid → `blob-events` → `blob_event` → `doc-processing` drives ingestion. The two paths are meant to be flipped together, never both active for the same writer.
- Because the Event Grid subscription now targets **`blob-events`** (not `doc-processing`) and `blob_event` is the only drainer of `blob-events`, the live default (`direct_enqueue`, no deployed `blob_event`) yields exactly one `doc-processing` message per upload — no double-ingest today. The detail block (bugs.md lines 994–998) confirms the env flag was deliberately left unflipped precisely to avoid breaking ingestion while no cloud `blob_event` drains `blob-events`.

**Guard — idempotency backstop (even if both fire):**
- `functions/blob_event/handler.py::handle_blob_created` builds `BatchPushQueueMessage(..., force_reindex=False)` (lines ~71–80); `batch_push` **upserts on document id**, so a re-upload overwrites the same blob and re-indexing is idempotent (handler docstring lines 8–18). So a double-delivery would re-process (waste) but not create duplicate index entries.

**Net:** No hard dedup/idempotency token prevents *re-processing* if both paths were misconfigured simultaneously; the protection is (1) the mutually-exclusive `ingestion_trigger` flag and (2) upsert-on-id idempotency. There is **no** code that detects "this blob already has an in-flight `doc-processing` message."

> Clarifying question: should the fix add an explicit guard/assertion that `event_grid` mode is never selected while the backend also enqueues (today it's convention + operator discipline), or is the flag + upsert idempotency considered sufficient?

---

## 4. Queue names + constant locations

Queues declared (new-storage path) in the storage AVM module `queueServices.queues` array — `v2/infra/main.bicep` lines **1148–1153**:
- `doc-processing` (1148), `doc-processing-poison` (1149), `blob-events` (1150), `blob-events-poison` (1151), `add-url` (1152), `add-url-poison` (1153).

Reuse-storage path declares the same queues as standalone `existing`-storage child resources — lines **1277** (`doc-processing`), **1283** (`doc-processing-poison`), **1289/1291** (`blob-events`), **1295/1297** (`blob-events-poison`), **1301/1307** (`add-url` / poison).

Bicep vars:
- `var docProcessingQueueName = 'doc-processing'` — line **2148**.
- `var blobEventsQueueName = 'blob-events'` — line **2152**.

Python:
- `doc-processing` is **not** a python literal — it flows as env `AZURE_DOC_PROCESSING_QUEUE` → `StorageSettings.doc_processing_queue` (settings.py) and is read as `settings.storage.doc_processing_queue` (e.g. `functions/batch_start/blueprint.py` line 66, `functions/blob_event/blueprint.py` `QueueClient(... queue_name=settings.storage.doc_processing_queue ...)`).
- `blob-events` IS a hard-coded python literal: `_BLOB_EVENTS_QUEUE = "blob-events"` — `functions/blob_event/blueprint.py` line ~71 (module constant, used only as the trigger-binding queue name; the blueprint docstring lines 41–47 justify the literal vs `%APP_SETTING%`).

### Duplicate-literal note (Hard Rule #11/#15 hygiene)

- Within **bicep**, `'doc-processing'` appears as the `var docProcessingQueueName` (2148) **and** as bare array literals `{ name: 'doc-processing' }` (1148) and the reuse child `name: 'doc-processing'` (1279). The var is NOT reused by the queue-declaration array — the array uses raw literals. Same pattern for `'blob-events'` (var 2152 vs literals 1150/1291) and `'doc-processing-poison'` / `'blob-events-poison'`. This is a mild duplication: the queue names are literal strings in 2–3 bicep sites each rather than every site referencing the single `var`. A fix could hoist all queue-name literals to the `var`s and reference them in both the storage module array and the reuse children (note: AVM storage module's `queues` array may constrain this).
- Cross-language (`blob-events` in bicep var + python `_BLOB_EVENTS_QUEUE`) is expected — bicep and python can't share a constant; they are independently pinned to the same string and both are documented as the fixed infra constant.

---

## 5. Test coverage a fix must keep green

### Settings / flag

- `v2/tests/backend/core/test_settings.py`:
  - imports `IngestionTrigger` (line 21).
  - `test_ingestion_trigger_defaults_to_direct_enqueue` (line **179**) — asserts default `DIRECT_ENQUEUE`.
  - additional `ingestion_trigger` round-trip assertions (grep shows ~9 matches in this file).
- `v2/tests/backend/test_services_ingestion.py`:
  - imports `IngestionTrigger` (line 17); helper default `ingestion_trigger=IngestionTrigger.DIRECT_ENQUEUE` (line 149); asserts the enqueue happens under `DIRECT_ENQUEUE` and is skipped under `EVENT_GRID` (grep ~6 matches) — this is the **double-enqueue guard test**.
- `v2/tests/scripts/test_upload_sample_data.py` line 354 — clears `AZURE_INGESTION_TRIGGER` env in a fixture.

### Bicep infra

- `v2/tests/infra/test_main_bicep.py`:
  - `test_function_app_keeps_blob_event_always_ready` (line **202**) — asserts `'function:blob_event'` is in the Flex `alwaysReady` set. **A fix must keep this green.**
  - **Coverage GAP:** there is **no** test asserting the Event Grid subscription's `queueName` is `blob-events` (not `doc-processing`), nor asserting `includedEventTypes` / `subjectBeginsWith`. The only Event-Grid-adjacent assertion is the always-ready one. A BUG-0054 fix that touches the subscription should ADD a guard test pinning `queueName: blobEventsQueueName` so the destination can't silently regress to `doc-processing`.

### blob_event Function

- `v2/tests/functions/blob_event/test_blueprint.py`, `test_event_parser.py`, `test_handler.py` — cover the create→enqueue / delete→de-index translation and the `Microsoft.Storage.BlobCreated|BlobDeleted` parse paths. A fix must keep these green.
- `v2/tests/functions/test_prepackage_subpackages.py` (line 55) — guards the BUG-0078 prepackage allow-list so `blob_event` ships in the deploy artifact (the gap that would make the cloud cutover ship a handler-less Function App).

---

## Cross-references

- ADR: `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md` (the single-trigger / queue-destination design).
- bugs.md: BUG-0054 row line 113 + detail 973–1003; related BUG-0053 (scale-from-zero), BUG-0058 (stale deploy artifact), BUG-0061 (role-before-subscription), BUG-0077 (BlobDeleted follow-up), BUG-0078 (prepackage allow-list), BUG-0087 (stale v1 Event Grid sub dead-letter on reuse storage).
- worklog: `v2/docs/worklog/2026-06-20.md`, `2026-06-22.md`, `2026-06-23.md`, `2026-06-29.md`.

## Open clarifying questions

1. Is the intent of this BUG-0054 work the **cloud cutover** (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid`), or a **code/IaC change** in the working tree? The IaC fix appears already committed; the remaining work per bugs.md is cloud-only and gated on BUG-0058 (Flex remote-build timeout).
2. Should the fix add the missing infra guard test pinning the Event Grid subscription `queueName` to `blob-events`? (Recommended — it's the exact regression that defined the bug.)
3. Should an explicit double-enqueue assertion be added (reject `event_grid` mode while backend enqueue is active), or is the flag + upsert idempotency sufficient?
