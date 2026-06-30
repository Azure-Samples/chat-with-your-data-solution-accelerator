# BUG-0054 cutover path — verified research

Status: **Complete (repo state fully verified; live-cloud state partially blocked by ARM read flakiness — see §6).**

Scope question (verbatim): *the COMPLETE, MINIMAL cutover step list, verified
against the actual wiring, and specifically whether the cutover truly requires a
full `azd provision` or can be done with a targeted change.*

Constraint: research only. No file outside `.copilot-tracking/research/` was
modified; only read-only `az` / `azd env get-values` were run against the cloud.

Placeholder tokens (Hard Rule #18) used below — real values live only in
`.azure/<AZD_ENV_NAME>/.env`, discoverable with `azd env get-values`:

- `<RESOURCE_GROUP>` — the azd resource group
- `<SUFFIX>` — the resource-name suffix
- `<SOLUTION>` — the azd solution name
- `<STORAGE_ACCOUNT>` — the active storage account (`st<SUFFIX>`)
- `<BACKEND_CA>` — backend Container App (`ca-backend-<SUFFIX>`)
- `<EVENT_GRID_TOPIC>` — system topic (`evgt-<SUFFIX>`)

---

## 1. One-line answer

**No — the cutover does NOT strictly require a full `azd provision`.** The
ingestion-trigger flip is consumed by **exactly one runtime** (the backend
Container App app-setting `AZURE_INGESTION_TRIGGER`), so it can be flipped with a
single targeted `az containerapp update --set-env-vars`. The Event Grid
subscription repoint to the `blob-events` queue is already encoded in committed
bicep and (per intermittent live reads) appears already applied; if the live
subscription still targets `doc-processing`, it can also be repointed with one
targeted `az eventgrid` command. A full `azd provision` is the *durable /
declarative* path but is **currently blocked** by a `RoleAssignmentExists`
idempotency error (§6). The minimal unblocked cutover is targeted `az` commands
plus `azd env set` to keep the flip durable for the next provision.

---

## 2. The cutover flag — full wiring chain (verified, file:line)

The whole cutover hinges on one setting whose value flows through five hops:

1. **azd env var** `AZURE_ENV_INGESTION_TRIGGER` — currently **unset** (so the
   default applies). Confirmed via `azd env get-values`: the env exposes
   `AZURE_INGESTION_TRIGGER="direct_enqueue"` (the resolved app-setting value)
   but **not** `AZURE_ENV_INGESTION_TRIGGER`.
2. **bicep parameter binding** — v2/infra/main.parameters.json line 20:
   `"ingestionTrigger": { "value": "${AZURE_ENV_INGESTION_TRIGGER=direct_enqueue}" }`.
   Unset azd var → literal default `direct_enqueue`.
3. **bicep param** — v2/infra/main.bicep line 100:
   `param ingestionTrigger string = 'direct_enqueue'`, `@allowed` set
   `direct_enqueue` | `event_grid` (lines 95-98).
4. **backend Container App app-setting** — v2/infra/main.bicep line 1945:
   `{ name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }`. This app-setting
   is wired **only** onto the backend Container App; the Function App appSettings
   deliberately do **not** carry it.
5. **Python typed setting** — v2/src/backend/core/settings.py:
   - `class IngestionTrigger(StrEnum)` line 109; members
     `DIRECT_ENQUEUE = "direct_enqueue"` line 128, `EVENT_GRID = "event_grid"`
     line 129.
   - `class StorageSettings(BaseSettings)` `model_config` `env_prefix="AZURE_"`
     line 273.
   - field `ingestion_trigger: IngestionTrigger = IngestionTrigger.DIRECT_ENQUEUE`
     line 279 → reads env `AZURE_INGESTION_TRIGGER`.

**Exact strings to report:**

| What | Value |
|---|---|
| azd env var (durable knob) | `AZURE_ENV_INGESTION_TRIGGER` |
| backend app-setting (live knob) | `AZURE_INGESTION_TRIGGER` |
| settings field | `StorageSettings.ingestion_trigger` |
| StrEnum | `IngestionTrigger` |
| StrEnum members | `direct_enqueue` (default), `event_grid` |

---

## 3. The single runtime branch on the flag (verified)

There is exactly **one** production branch on `ingestion_trigger`, in the backend
admin upload path — v2/src/backend/services/ingestion.py, `upload_document`:

```python
backend_enqueues = (
    settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE
)
# ... upload_blob ...
if backend_enqueues:
    message = BatchPushQueueMessage(...)
    await enqueue_push_message(queue_client, message)
```

- `direct_enqueue` → backend writes the blob **and** enqueues a
  `BatchPushQueueMessage` to `doc-processing` (today's working path).
- `event_grid` → backend writes the blob **only**; Event Grid →
  `blob-events` → `blob_event` Function → `doc-processing` → `batch_push` owns
  ingestion (no double-ingest).

Because this is the only consumer, **flipping the backend app-setting alone is a
complete behavioral flip.** No Function App redeploy is needed for the flag.

---

## 4. The Event Grid subscription — already repointed in committed bicep

Both topic branches in v2/infra/main.bicep target the `blob-events` queue
(`var blobEventsQueueName = 'blob-events'` line 2152). The subscription **name is
deliberately retained** in each branch so the destination change is an *in-place
update*, never a rename that would orphan the old sub still pointing at
`doc-processing`:

- **New-topic branch** (`if (!useExistingEventGridTopic)`):
  resource `blobCreatedSubscription` line 2402, name
  `'blob-created-to-doc-processing'` line 2408, `deliveryWithResourceIdentity`
  **SystemAssigned** MI, `destination.properties.queueName: blobEventsQueueName`
  line 2421, filter `BlobCreated` + `BlobDeleted` on the documents container,
  retry 30× / 1440 min.
- **Existing-topic branch** (`if (useExistingEventGridTopic)`):
  resource `existingEventGridSubscription` line 2472, name
  `'cwyd2-blob-created-doc-processing'` line 2475, `deliveryWithResourceIdentity`
  **UserAssigned** MI, same `queueName: blobEventsQueueName` line 2487, same
  filter.

`useExistingEventGridTopic = !empty(existingEventGridTopicName)` (line 128);
`eventGridSystemTopicName = 'evgt-${solutionSuffix}'` (line 2144). A
role-before-subscription `dependsOn` (the queue-sender grant) guards the EG
delivery preflight (BUG-0061).

**Implication:** committed bicep is *already the fix state* — the bug was the
historical/stray subscription on the live storage that pointed at
`doc-processing`. Whether the live deploy used the new- or existing-topic branch,
the committed declaration repoints to `blob-events`.

---

## 5. Does the cutover need a full `azd provision`? — analysis

The cutover is two independent cloud changes:

**(A) Flip the ingestion trigger** (turn off backend double-enqueue):
- *Durable / declarative path:* `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid`
  then `azd provision`. Re-derives the backend app-setting from the param.
  **Currently blocked** — see §6.
- *Targeted / unblocked path:*
  `az containerapp update -g <RESOURCE_GROUP> -n <BACKEND_CA> --set-env-vars "AZURE_INGESTION_TRIGGER=event_grid"`.
  Rolls one new backend revision; takes effect immediately. **Non-durable** — the
  next successful `azd provision` re-applies the param value (unset
  `AZURE_ENV_INGESTION_TRIGGER` → reverts to `direct_enqueue`). Precedent: the
  BUG-0059 live env-var flip used exactly this pattern.
- *Recommended:* do **both** — `azd env set` now (so the value is durable when
  provision next succeeds) **and** the targeted `containerapp update` to flip
  immediately without waiting on the blocked provision.

**(B) Ensure the live Event Grid subscription delivers to `blob-events`:**
- If the last successful provision already applied the §4 repoint, **nothing to
  do** (intermittent live reads suggest this is the case, but could not be
  confirmed — §6).
- If the live subscription still targets `doc-processing`, either a successful
  `azd provision` **or** a targeted
  `az eventgrid system-topic event-subscription update` (repoint
  `--storage-queue-name blob-events`) fixes it. This is the one fact requiring
  live confirmation before acting.

**Conclusion:** a full `azd provision` is *sufficient but not necessary* and is
*currently blocked*. The minimal cutover is targeted `az` for (A) and only-if-
needed targeted `az` for (B), plus `azd env set` to keep (A) durable.

---

## 6. Live-cloud state (read-only; partially blocked)

Auth confirmed: `az account show` → subscription `CSA-CTO-Engineering-Dev`,
user `friesco@...`, correct tenant.

Observed (intermittently — see caveat) from prior read-only `az` calls this
session:

- Backend Container App: `<BACKEND_CA>` = `ca-backend-<SUFFIX>` **exists**.
- **Two** Event Grid system topics in `<RESOURCE_GROUP>`: `evgt-<SUFFIX>`
  (current) **and** a legacy `evgt-<OLD_SUFFIX>`.
- **Two** storage accounts: `st<SUFFIX>` (current) and a legacy `st<OLD_SUFFIX>`.
  → the RG has artifacts from two provisions; the **current** suffix is the live
  one.
- `azd provision` is **blocked**: last run failed with
  `RoleAssignmentExists: The role assignment already exists. The ID of the
  existing role assignment is <ROLE_ASSIGNMENT_GUID>` (a BUG-0061-class
  idempotency conflict). `ERROR: A role assignment already exists for this
  identity.`
- azd env: `AZURE_INGESTION_TRIGGER="direct_enqueue"`,
  `AZURE_ENV_INGESTION_TRIGGER` **unset**.

**Caveat / block:** ARM read calls in this session were **intermittently empty**
— `az containerapp list`, `az eventgrid system-topic list`, and even
`az rest` against the ARM management endpoint returned `[]` or "no output" on some
calls and full data on others, within minutes, for the same RG. This looks like
throttling / replication lag on the subscription right now, **not** a query error
(`az version` and `az account show` returned reliably). Consequently the three
*current-state* facts below **could not be pinned with confidence** and should be
re-checked by the operator before acting:

1. Live backend `AZURE_INGESTION_TRIGGER` value (expected `direct_enqueue`).
2. Live `evgt-<SUFFIX>` subscription destination queue (`blob-events` vs
   `doc-processing`).
3. `doc-processing-poison` depth (expected ~4 historical messages).

Operator verification commands (read-only):

```pwsh
# (1) live ingestion-trigger value
az containerapp show -g <RESOURCE_GROUP> -n <BACKEND_CA> `
  --query "properties.template.containers[0].env[?name=='AZURE_INGESTION_TRIGGER'].value | [0]" -o tsv

# (2) live Event Grid subscription destination queue
az eventgrid system-topic event-subscription list `
  --system-topic-name <EVENT_GRID_TOPIC> -g <RESOURCE_GROUP> `
  --query "[].{name:name, queue:deliveryWithResourceIdentity.destination.properties.queueName}" -o json

# (3) historical poison depth (storage has allowSharedKeyAccess=false → --auth-mode login)
az storage queue stats --name doc-processing-poison --account-name <STORAGE_ACCOUNT> --auth-mode login 2>$null
az storage message peek --queue-name doc-processing-poison --account-name <STORAGE_ACCOUNT> --auth-mode login --num-messages 10
```

---

## 7. Ordered minimal cutover runbook (verified against §2-§4 wiring)

Pre-flight already done (do not repeat): `blob_event` Function deployed to the
cloud app 2026-06-24 (app at 6 functions, BUG-0080); `blob_event` `alwaysReady`
instance in bicep (BUG-0053 scale-from-zero guard).

1. **Confirm live state** — run the three §6 verification commands. Decide whether
   step 3 (EG repoint) is needed.

2. **Make the flip durable for future provisions:**
   ```pwsh
   azd env set AZURE_ENV_INGESTION_TRIGGER event_grid
   ```
   (Records the intent in `.azure/<AZD_ENV_NAME>/.env`; no cloud change yet.)

3. **Flip the backend now (targeted, unblocked):**
   ```pwsh
   az containerapp update -g <RESOURCE_GROUP> -n <BACKEND_CA> `
     --set-env-vars "AZURE_INGESTION_TRIGGER=event_grid"
   ```
   Backend rolls a new revision and stops double-enqueuing. (If/when the
   `RoleAssignmentExists` block is cleared, `azd provision` makes this durable and
   this targeted change becomes a no-op.)

4. **Only if §6(2) shows the live subscription still on `doc-processing`** —
   repoint it to `blob-events`:
   ```pwsh
   # new-topic / SystemAssigned MI deploy:
   az eventgrid system-topic event-subscription update `
     --name blob-created-to-doc-processing `
     --system-topic-name <EVENT_GRID_TOPIC> -g <RESOURCE_GROUP> `
     --endpoint-type storagequeue `
     --endpoint /subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Storage/storageAccounts/<STORAGE_ACCOUNT>/queueServices/default/queues/blob-events
   ```
   (Use the existing-topic subscription name `cwyd2-blob-created-doc-processing`
   if the live deploy used the reuse branch. Prefer a successful `azd provision`
   if the role-assignment block can be cleared, since the committed bicep already
   encodes this.)

5. **Cloud re-validate end-to-end** — drop a blob into the `documents` container,
   confirm it flows EG → `blob-events` → `blob_event` → `doc-processing` →
   `batch_push` → vector store and shows in `GET /api/admin/documents`; then
   delete and confirm de-index (BlobDeleted path, BUG-0077). Note the BUG-0058
   cloud-verify gate: `azd deploy function` may ship a stale prepackage artifact —
   if `blob_event` behaves stale, run the prepackage hook explicitly before
   deploy.

6. **Drain the 4 historical poison messages:**
   ```pwsh
   az storage message clear --queue-name doc-processing-poison `
     --account-name <STORAGE_ACCOUNT> --auth-mode login
   ```
   (Or peek + delete individually to keep an audit trail.)

7. **Close BUG-0054** once steps 3-6 pass.

---

## 8. Recommended follow-ups (not blocking the cutover)

- [ ] Unblock `azd provision` — clear the `RoleAssignmentExists`
      (`<ROLE_ASSIGNMENT_GUID>`) idempotency conflict so the durable path works
      (BUG-0061 class). Until then the cutover relies on the targeted `az` flip.
- [ ] **Test gap (from prior infra-wiring research):** no test pins the Event Grid
      subscription `queueName` to `blob-events`. Add an assertion in
      `v2/tests/infra/test_main_bicep.py` so a future edit can't silently repoint
      it back to `doc-processing`.
- [ ] Investigate / clean up the **legacy** `evgt-<OLD_SUFFIX>` topic and
      `st<OLD_SUFFIX>` storage account left in the RG from the earlier provision
      (confirm they are not the source of any stray live subscription before
      deleting — destructive, operator-gated).

---

## 9. Clarifying questions for the user

1. **Perform vs document?** This is read-only research, so only the path is
   documented. Should a follow-up turn actually execute the cutover (targeted
   `az` flip), or hold until `azd provision` is unblocked?
2. **Targeted vs durable?** Given `azd provision` is blocked, is the targeted
   `az containerapp update` flip acceptable as the live cutover (with
   `azd env set` recording the durable intent), or must the
   `RoleAssignmentExists` block be fixed first so the flip lands via provision?
3. **EG repoint confirmation** — the live subscription's destination queue could
   not be pinned this session (ARM read flakiness). OK to gate step 4 on the
   operator running the §6(2) command, or should research retry the live read
   later?

---

## 10. Source references (workspace-relative, plain text)

- v2/docs/bugs.md — BUG-0054 block (close-out steps, live-state note)
- v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md — B1 design + rollout order
- v2/src/backend/core/settings.py — `IngestionTrigger` (109/128/129), `StorageSettings.ingestion_trigger` (273/279)
- v2/src/backend/services/ingestion.py — `upload_document` `backend_enqueues` branch
- v2/infra/main.parameters.json — `ingestionTrigger` binding (line 20)
- v2/infra/main.bicep — param (100), backend app-setting (1945), new-topic sub (2402-2444), existing-topic sub (2472-2495), `blobEventsQueueName` (2152), `useExistingEventGridTopic` (128)
- v2/src/functions/blob_event/ — translator blueprint (deployed, locally validated)
