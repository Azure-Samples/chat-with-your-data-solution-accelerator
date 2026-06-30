<!-- markdownlint-disable-file -->
# Task Research: BUG-0054 cutover fix (Event Grid ingestion trigger)

Close out BUG-0054 by unblocking the cloud cutover that flips the ingestion
trigger to `event_grid`. The bug's translator code (`blob_event`, ADR 0028) is
already implemented, reviewed, committed, and deployed. The registry row stays
`open` only because the operator cutover step — `azd provision` to flip the
trigger — **fails every time** on an unrelated infrastructure error:

```
ERROR: A role assignment already exists for this identity.
RoleAssignmentExists: The role assignment already exists.
The ID of the existing role assignment is 70d96d3a34c948878eb204191fdec8b1.
deployment failed: error deploying infrastructure
```

This research drives to one fix that lets the cutover complete.

## Task Implementation Requests

* Find the root cause of the `RoleAssignmentExists` failure during `azd provision` and the smallest durable fix in `v2/infra/**`.
* Determine the complete, minimal cutover path for BUG-0054 (flip trigger → re-validate → drain poison), and whether a full `azd provision` is actually required or a targeted change suffices.

## Scope and Success Criteria

* Scope: the infrastructure/role-assignment blocker plus the BUG-0054 operator cutover steps. **Excludes** any re-review of the already-fixed `blob_event` ingestion code — that is done.
* Assumptions:
  * Today is 2026-06-29; active phase is Phase 6.
  * The `blob_event` translator + `ingestion_trigger` flag are deployed (BUG-0080, 6 functions on the cloud Function App).
  * Subscription `CSA-CTO-Engineering-Dev` (`<AZURE_SUBSCRIPTION_ID>`), resource group `<RESOURCE_GROUP>`, suffix `<SUFFIX>` — real values live only in `.azure/<AZD_ENV_NAME>/.env`.
  * The conflicting role assignment name (GUID) is `70d96d3a-34c9-4887-8eb2-04191fdec8b1`.
* Success Criteria:
  * The exact non-idempotent role-assignment Bicep block is identified, with the principal + role + scope it targets.
  * A single recommended fix is specified (with the precise edit) that makes `azd provision` idempotent so the cutover completes.
  * The minimal cutover step list is confirmed against the actual wiring (env var name, Event Grid subscription target queue, poison-queue drain).

## Outline

* Blocker A — RoleAssignmentExists root cause + idempotency fix (subagent A).
* Path B — BUG-0054 cutover step list + whether full provision is needed (subagent B).
* Selected approach — one recommended fix, with edit + cutover runbook.

## The single most important finding

**The BUG-0054 cutover does not require `azd provision` at all.** The ingestion
trigger is consumed by **exactly one runtime** — the backend Container App
app-setting `AZURE_INGESTION_TRIGGER` — so it flips with one targeted
`az containerapp update --set-env-vars`. That decouples closing BUG-0054 from the
blocked provision entirely. The loop existed only because the cutover was
(incorrectly) assumed to require a clean `azd provision`, which a *separate*,
*unrelated* stale role assignment keeps failing.

## Potential Next Research

* Confirm the AVM `search-service` module version was bumped between the two RG deployments (proves the orphan rename mechanism). Reasoning: closes the root-cause loop on why the orphan exists. Reference: subagent A Q4.
* Add a `v2/tests/infra/test_main_bicep.py` assertion pinning the Event Grid subscription `queueName` to `blob-events`. Reasoning: a future edit could silently repoint it back to `doc-processing`. Reference: subagent B §8.
* Clean up the legacy `evgt-<OLD_SUFFIX>` topic + `st<OLD_SUFFIX>` storage account left in the RG from an earlier provision (operator-gated, destructive). Reference: subagent B §6/§8.

## Research Executed

### File Analysis

* v2/src/backend/core/settings.py
  * `class IngestionTrigger(StrEnum)` line 109; members `DIRECT_ENQUEUE = "direct_enqueue"` (128), `EVENT_GRID = "event_grid"` (129).
  * `class StorageSettings(BaseSettings)` `env_prefix="AZURE_"` (273); field `ingestion_trigger: IngestionTrigger = IngestionTrigger.DIRECT_ENQUEUE` (279) → reads env `AZURE_INGESTION_TRIGGER`.
* v2/src/backend/services/ingestion.py
  * `upload_document` — the ONLY production branch on the flag: `backend_enqueues = (settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE)`; only enqueues a `BatchPushQueueMessage` when `backend_enqueues`.
* v2/infra/main.parameters.json
  * line 20: `"ingestionTrigger": { "value": "${AZURE_ENV_INGESTION_TRIGGER=direct_enqueue}" }` — unset azd var → literal default `direct_enqueue`.
* v2/infra/main.bicep
  * param `ingestionTrigger` (100), `@allowed` `direct_enqueue` | `event_grid` (95-98).
  * backend Container App app-setting `{ name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }` (1945) — wired ONLY onto the backend CA; the Function App appSettings deliberately do not carry it.
  * `var blobEventsQueueName = 'blob-events'` (2152); `aiSearch` module + `roleAssignments` array (899-953); static-salt grants `searchOpenAiUserOnFoundry` (1038) / `searchOpenAiUserOnReusedOpenAi` (1050).
  * Event Grid subscriptions: `blobCreatedSubscription` (2402, SystemAssigned MI, `queueName: blobEventsQueueName` 2421); `existingEventGridSubscription` (2472, UserAssigned MI, same queue 2487). **Both committed branches already target `blob-events`.**

### Code Search Results

* `RoleAssignmentExists` failed nested deployment `avm.res.search.search-service.<SUFFIX>`; 5 search-scope role assignments all Created (`59cd631c`, `2b069a0f`, `dc5e220f`, `45f6571e`, `7c263c6c`); orphan `70d96d3a` is none of them.
* Five current search-scope tuples are all distinct `(principal, role)` pairs → template is internally idempotent. The orphan is a 6th name from a prior deployment whose name formula differed for one of these same tuples.

### External Research

* AVM module `avm/res/search/search-service:0.12.0` — default role-assignment name `guid(searchService.id, principalId, roleDefinitionId)` (deterministic, stable across runs at a fixed module version).

### Project Conventions

* Standards referenced: Hard Rule #18 (no env-specific content in tracked files — all ids tokenized below), v2-infra conventions (camelCase Bicep, deterministic `guid()` role-assignment names), config-defaults-dev-first (defaults stay `direct_enqueue`; prod flips via env var).
* Instructions followed: research-only; all edits confined to `.copilot-tracking/research/`.

## Key Discoveries

### The two problems are independent

1. **BUG-0054 cutover** — flip ingestion to `event_grid`. Single backend CA
   env var. **Not** blocked by anything; the `blob_event` translator + the
   `blob-events`-targeted Event Grid subscriptions are already deployed/committed.
2. **`azd provision` blocker** (`RoleAssignmentExists`) — a stale, cross-run
   orphan role assignment (`70d96d3a…`) on the search service scope from a prior
   deployment with a divergent name formula. Independent of BUG-0054; only
   matters if/when you want the *declarative* provision path.

### The cutover flag wiring chain (verified)

`AZURE_ENV_INGESTION_TRIGGER` (azd env var, durable) → `main.parameters.json:20`
→ bicep param `ingestionTrigger` (`main.bicep:100`) → backend CA app-setting
`AZURE_INGESTION_TRIGGER` (`main.bicep:1945`) → `StorageSettings.ingestion_trigger`
(`settings.py:279`). One consumer (`ingestion.py upload_document`).

### The blocker root cause (verified)

The `aiSearch` AVM module (`main.bicep:922-953`) emits the conflicting PUT. The
current template grants five *distinct* tuples, each once — so a clean run cannot
self-collide. The orphan `70d96d3a` is a sixth, stale name from a prior
deployment (older AVM version / divergent `guid()` input / the inline
`existingSearch*` NAME-salt path) for one of those same tuples. The search
service that carried it was rolled back, so it is no longer resolvable — a plain
re-provision *should* succeed; if a stale orphan persists, delete it by full id.
Separately, two grants are non-idempotent *by construction*
(`searchOpenAiUserOnFoundry` :1038, `searchOpenAiUserOnReusedOpenAi` :1050) — they
salt the assignment `name` with the static string `'search-system-mi'` instead of
the real principalId, so recreating the search MI would re-trigger this class.

## Technical Scenarios

### Scenario 1 — Close BUG-0054 via the targeted backend env-var flip (SELECTED)

**Requirements:** flip ingestion to `event_grid` and stop the backend
double-enqueue, without depending on the blocked `azd provision`.

**Preferred Approach:** decouple the cutover from provision. Set the durable
intent with `azd env set`, then flip the live backend Container App with a single
targeted `az containerapp update`. Verify the Event Grid subscription target
(already `blob-events` in committed bicep), re-validate end-to-end, drain the
historical poison messages, and close the bug. The role-assignment blocker is
addressed *separately* (Scenario 2) and never blocks the cutover.

**Operator runbook (the cutover):**

```pwsh
# 0. Resolve real values for this turn
azd env get-values   # → <RESOURCE_GROUP>, <SUFFIX>, <STORAGE_ACCOUNT>, <BACKEND_CA>, <EVENT_GRID_TOPIC>

# 1. Confirm live state (read-only)
az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> `
  --query "properties.template.containers[0].env[?name=='AZURE_INGESTION_TRIGGER'].value | [0]" -o tsv
az eventgrid system-topic event-subscription list `
  --system-topic-name evgt-<SUFFIX> -g <RESOURCE_GROUP> `
  --query "[].{name:name, queue:deliveryWithResourceIdentity.destination.properties.queueName}" -o json
az storage message peek --queue-name doc-processing-poison `
  --account-name st<SUFFIX> --auth-mode login --num-messages 10

# 2. Record durable intent (no cloud change yet)
azd env set AZURE_ENV_INGESTION_TRIGGER event_grid

# 3. Flip the backend now (targeted, unblocked)
az containerapp update -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> `
  --set-env-vars "AZURE_INGESTION_TRIGGER=event_grid"

# 4. ONLY if step-1 shows the live sub still on doc-processing — repoint it
az eventgrid system-topic event-subscription update `
  --name blob-created-to-doc-processing `
  --system-topic-name evgt-<SUFFIX> -g <RESOURCE_GROUP> `
  --endpoint-type storagequeue `
  --endpoint /subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Storage/storageAccounts/st<SUFFIX>/queueServices/default/queues/blob-events

# 5. Re-validate: drop a blob in `documents`, confirm EG → blob-events →
#    blob_event → doc-processing → batch_push → vector store → GET /api/admin/documents;
#    then delete + confirm de-index. (Mind BUG-0058: azd deploy function may ship a
#    stale prepackage — run the prepackage hook first if blob_event behaves stale.)

# 6. Drain the ~4 historical poison messages
az storage message clear --queue-name doc-processing-poison `
  --account-name st<SUFFIX> --auth-mode login

# 7. Close BUG-0054 in v2/docs/bugs.md
```

**Why selected:** smallest change that actually closes the bug; breaks the loop
immediately; does not touch the (separate) provision blocker; honors
config-defaults-dev-first (the repo default stays `direct_enqueue`, prod flips via
the env var). The one consumer means the env-var flip is a complete behavioral
flip with no Function App redeploy.

### Scenario 2 — Unblock `azd provision` (separate, durable; not required to close BUG-0054)

**Requirements:** make `azd provision` idempotent again so the declarative path
works (and makes the step-3 flip durable, turning it into a no-op).

**Preferred Approach (two parts):**

1. **Clear the stale orphan.** Try a plain re-run first (the orphan scope was
   rolled back). If `RoleAssignmentExists` recurs, delete the orphan by full id
   then re-provision:

   ```bash
   az role assignment delete --ids "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Search/searchServices/srch-<SUFFIX>/providers/Microsoft.Authorization/roleAssignments/70d96d3a-34c9-4887-8eb2-04191fdec8b1"
   ```

   (If a different orphan id appears, list at the reported scope and delete that one.)

2. **Durable Bicep hardening** — fix the static-salt names so this class can't
   recur. In `v2/infra/main.bicep`:

   `searchOpenAiUserOnFoundry` (L1038) — replace
   `name: guid(aiServicesName, 'search-system-mi', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')`
   with
   `name: guid(aiServicesAccount.id, aiSearch!.outputs.systemAssignedMIPrincipalId!, subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'))`.

   `searchOpenAiUserOnReusedOpenAi` (L1050) — same pattern over `existingOpenAi.id`.

   Caveat: a name change creates a new assignment and orphans the old static-salt
   one (no conflict, just a one-time stray to clean up). This is a Bicep edit →
   triggers test-first + the implementer agent; it is **not** needed to close
   BUG-0054.

**Implementation Details:** this is infra-code work gated by Hard Rule #1/#2
(one unit + test). Recommend it as a *follow-up* turn under the coding agent,
tracked as its own debt/bug row — do not couple it to the cutover.

#### Considered Alternatives

* **Wait for / force `azd provision` to close BUG-0054 (the loop we were in)** —
  rejected. Couples an unrelated, recurring infra defect to a behavioral flip that
  needs none of it. This is precisely the infinite loop the user called out.
* **`az role assignment delete` + re-provision as the cutover path** — rejected as
  the *primary* path. It is the correct fix for the provision blocker (Scenario 2)
  but it deletes a live role assignment and re-runs a full provision to flip one
  env var — heavier and riskier than the targeted `containerapp update`, and still
  gated on the provision succeeding.
* **Edit `main.parameters.json` default to `event_grid`** — rejected. Violates
  config-defaults-dev-first (repo default must stay `direct_enqueue`; prod flips
  via the env var), and still requires a successful provision to take effect.
