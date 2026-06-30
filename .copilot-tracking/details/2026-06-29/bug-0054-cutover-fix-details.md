<!-- markdownlint-disable-file -->
# Implementation Details: BUG-0054 cutover fix (Event Grid ingestion trigger)

## Context Reference

Sources:
* .copilot-tracking/research/2026-06-29/bug-0054-cutover-fix-research.md — consolidated research, selected approach, runbook.
* .copilot-tracking/research/subagents/2026-06-29/role-assignment-idempotency-research.md — provision blocker root cause + Bicep before/after.
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-cutover-path-research.md — cutover wiring (file:line) + ordered runbook.

Placeholder tokens (Hard Rule #18 — real values live only in `.azure/<AZD_ENV_NAME>/.env`, via `azd env get-values`):
`<RESOURCE_GROUP>`, `<SUFFIX>`, `<STORAGE_ACCOUNT>` (`st<SUFFIX>`), `<BACKEND_CA>` (`ca-backend-<SUFFIX>`), `<EVENT_GRID_TOPIC>` (`evgt-<SUFFIX>`), `<AZURE_SUBSCRIPTION_ID>`, `<AZD_ENV_NAME>`.

Key facts carried from research:
* The ingestion trigger has exactly ONE consumer — backend Container App app-setting `AZURE_INGESTION_TRIGGER` → `StorageSettings.ingestion_trigger` (settings.py:279) → `ingestion.py upload_document` `backend_enqueues` branch. Flipping the backend env var is a complete behavioral flip; no Function App redeploy.
* Committed Bicep already targets the `blob-events` queue in both Event Grid subscription branches (main.bicep:2421 / 2487). The historical bug was a stray live sub on `doc-processing`.
* `azd provision` is blocked by a stale cross-run orphan role assignment (`<ORPHAN_ROLE_ASSIGNMENT_GUID>`) on the search-service scope. This blocker is INDEPENDENT of the cutover and is addressed separately (Phase 2 hardening + Phase 3 restore).
* Repo default stays `direct_enqueue` (config-defaults-dev-first); prod flips via the env var only.

## Implementation Phase 1: Verify live state + targeted cutover

<!-- parallelizable: false -->

This phase is operator/implementer-run cloud actions requiring an authenticated `az`/`azd` session. It closes BUG-0054 behaviorally WITHOUT `azd provision`. Mutating steps (1.4, 1.5, 1.7) are shared-infra / destructive and require explicit user confirmation before running (operational safety).

### Step 1.1: Resolve environment values

Read the active azd env so every later command uses real names without hardcoding them in any tracked file.

Commands:
* `azd env get-values` — capture `<RESOURCE_GROUP>`, `<SUFFIX>`, derive `<BACKEND_CA>`=`ca-backend-<SUFFIX>`, `<STORAGE_ACCOUNT>`=`st<SUFFIX>`, `<EVENT_GRID_TOPIC>`=`evgt-<SUFFIX>`.
* `az account show` — confirm the correct subscription + tenant before any mutation.

Success criteria:
* Real env values resolved into the operator's session (never written to a tracked file).
* Subscription confirmed as the intended target.

Dependencies:
* Authenticated `az` + `azd` session.

### Step 1.2: Verify live state (read-only)

Pin the three facts the cutover branches on, since prior ARM reads were intermittently throttled.

Commands:
```pwsh
# (1) live ingestion-trigger value (expected: direct_enqueue, pre-cutover)
az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> `
  --query "properties.template.containers[0].env[?name=='AZURE_INGESTION_TRIGGER'].value | [0]" -o tsv

# (2) live Event Grid subscription destination queue (expected: blob-events)
az eventgrid system-topic event-subscription list `
  --system-topic-name evgt-<SUFFIX> -g <RESOURCE_GROUP> `
  --query "[].{name:name, queue:deliveryWithResourceIdentity.destination.properties.queueName}" -o json

# (3) historical poison depth (expected: ~4)
az storage message peek --queue-name doc-processing-poison `
  --account-name st<SUFFIX> --auth-mode login --num-messages 10
```

Discrepancy references:
* Addresses DR-02 (live EG sub queue could not be pinned during research — confirm here).

Success criteria:
* Decision recorded: is Step 1.5 (EG repoint) needed (only if (2) shows `doc-processing`)?
* Poison depth known for Step 1.7.

Dependencies:
* Step 1.1.

### Step 1.3: Record durable intent

Persist the cutover decision so the next successful `azd provision` keeps `event_grid` instead of reverting to the param default.

Commands:
* `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` (writes to gitignored `.azure/<AZD_ENV_NAME>/.env`; no cloud change).

Success criteria:
* `azd env get-values` shows `AZURE_ENV_INGESTION_TRIGGER=event_grid`.

Dependencies:
* Step 1.1.

### Step 1.4: Flip the backend now (targeted, unblocked)

Roll one backend revision so the backend stops double-enqueuing immediately — independent of the blocked provision.

Commands:
```pwsh
az containerapp update -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> `
  --set-env-vars "AZURE_INGESTION_TRIGGER=event_grid"
```

Confirmation gate: rolls a new revision on shared cloud infra — confirm with the user first.

Success criteria:
* New revision active; re-running the Step 1.2(1) read returns `event_grid`.

Dependencies:
* Step 1.2 (state confirmed), Step 1.3 (durable intent recorded).

### Step 1.5: Conditionally repoint the Event Grid subscription

ONLY if Step 1.2(2) shows the live subscription still delivering to `doc-processing`. If it already targets `blob-events`, this is a no-op — skip.

Commands (new-topic / SystemAssigned MI deploy; use the existing-topic sub name `cwyd2-blob-created-doc-processing` if the reuse branch was deployed):
```pwsh
az eventgrid system-topic event-subscription update `
  --name blob-created-to-doc-processing `
  --system-topic-name evgt-<SUFFIX> -g <RESOURCE_GROUP> `
  --endpoint-type storagequeue `
  --endpoint /subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Storage/storageAccounts/st<SUFFIX>/queueServices/default/queues/blob-events
```

Confirmation gate: modifies shared Event Grid infra — confirm with the user first.

Success criteria:
* Step 1.2(2) read now returns `blob-events` for the subscription.

Dependencies:
* Step 1.2 decision.

### Step 1.6: Re-validate end-to-end (create + delete)

Prove the `event_grid` path works before closing the bug.

Actions:
* Upload a test document to the `documents` container; confirm it flows Event Grid → `blob-events` → `blob_event` Function → `doc-processing` → `batch_push` → vector store and appears in `GET /api/admin/documents`.
* Delete it; confirm de-index (BlobDeleted path).
* BUG-0058 gate: `azd deploy function` may ship a stale prepackage. If `blob_event` behaves stale, run the prepackage hook (`v2/scripts/prepackage_function.py`) before re-deploying the function.
* Clean up the validation document afterward (delete blob + de-index) per cleanup-before-next-step.

Success criteria:
* Single-path ingestion confirmed (no double-ingest); create + delete both reflected in the admin documents list.

Dependencies:
* Steps 1.4 (and 1.5 if it ran).

### Step 1.7: Drain historical poison messages

Clear the ~4 stale `doc-processing-poison` messages left by the pre-fix Event Grid envelopes.

Commands:
```pwsh
az storage message clear --queue-name doc-processing-poison `
  --account-name st<SUFFIX> --auth-mode login
```
(Or peek + delete individually to keep an audit trail.)

Confirmation gate: destructive queue drain — confirm with the user first.

Success criteria:
* `doc-processing-poison` depth is 0.

Dependencies:
* Step 1.6 (validation passed — do not drain before the new path is proven).

## Implementation Phase 2: Durable Bicep idempotency hardening

<!-- parallelizable: true -->

Independent of Phase 1 (touches repo files only; no dependency on the cutover). Unblocks future `azd provision` durably and removes the static-salt anti-pattern. This is the one code unit; it is test-first per Hard Rule #1/#2 and NOT required to close BUG-0054.

### Step 2.1: Harden the two static-salt role-assignment names

Replace the static `'search-system-mi'` salt with the canonical deterministic key `guid(scopeResourceId, principalId, roleDefinitionId)` so recreating the search MI can never reuse a name for a different principal.

Files:
* v2/infra/main.bicep — `searchOpenAiUserOnFoundry` (L1038) and `searchOpenAiUserOnReusedOpenAi` (L1050).

Edits:
* `searchOpenAiUserOnFoundry` (L1038) — replace
  `name: guid(aiServicesName, 'search-system-mi', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')`
  with
  `name: guid(aiServicesAccount.id, aiSearch!.outputs.systemAssignedMIPrincipalId!, subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'))`.
* `searchOpenAiUserOnReusedOpenAi` (L1050) — replace
  `name: guid(existingOpenAiName, 'search-system-mi', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')`
  with
  `name: guid(existingOpenAi.id, aiSearch!.outputs.systemAssignedMIPrincipalId!, subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'))`.

Discrepancy references:
* Implements DD-01 (research scoped this as a separate task; plan bundles it because the user has been blocked by provision).

Success criteria:
* Both role-assignment `name` expressions key on `scope.id + principalId + roleDefinitionId`; no static `'search-system-mi'` salt remains.
* `existingOpenAi` symbolic reference resolves at L1050 (verify the symbolic name in context before editing — confirm it is `existingOpenAi` vs `existingOpenAiName`).

Context references:
* .copilot-tracking/research/subagents/2026-06-29/role-assignment-idempotency-research.md (Q5 — exact before/after) - hardening edit.

Dependencies:
* None (independent of Phase 1).

### Step 2.2: Add infra-test assertions

Pin the new invariants so a future edit cannot regress them.

Files:
* v2/tests/infra/test_main_bicep.py — add (or extend) assertions:
  1. The two search-OpenAI role-assignment `name` expressions contain `systemAssignedMIPrincipalId` and do NOT contain the literal `'search-system-mi'`.
  2. Both Event Grid subscription declarations bind `queueName` to `blobEventsQueueName` / `'blob-events'` (closes the research test-gap so the sub can't be silently repointed to `doc-processing`).

Discrepancy references:
* Addresses WI-02 (EG queueName test-gap) folded into this phase.

Success criteria:
* New assertions execute and pass against the edited `main.bicep`.
* Test fails if either invariant regresses (verify by a scratch revert, then restore).

Context references:
* v2/tests/infra/test_main_bicep.py - existing bicep-assertion patterns to mirror.

Dependencies:
* Step 2.1.

### Step 2.3: Validate phase changes

Files: none (validation only).

Validation commands:
* `.venv\Scripts\python.exe -m pytest v2/tests/infra/test_main_bicep.py -q` — the infra assertions (uv trampoline is broken; call the venv python directly per repo memory).
* `az bicep build --file v2/infra/main.bicep --stdout` (or `bicep build`) — confirm the edited template still compiles clean.

Success criteria:
* Infra test green; bicep compiles with no new diagnostics.

Dependencies:
* Steps 2.1, 2.2.

## Implementation Phase 3: Restore declarative provision (operator-run)

<!-- parallelizable: false -->

Clears the current orphan and re-runs `azd provision` against the Phase 2 hardened template so the declarative deployment is green again. This is the research's primary provision-unblock (DR-05): the Phase 2 Bicep hardening alone does NOT clear the existing orphan `<ORPHAN_ROLE_ASSIGNMENT_GUID>` — only a re-run (or the fallback delete + re-run) does. This phase is OPTIONAL for closing BUG-0054 (Phase 1 already closed it behaviorally) and is REQUIRED only for the separate "make `azd provision` succeed again" goal. Both mutating steps are confirmation-gated.

Depends on: Phase 2 (hardened template in the working tree — `azd provision` compiles local `main.bicep`, so no commit needed) AND Step 1.3 (`AZURE_ENV_INGESTION_TRIGGER=event_grid` set, so the re-provision applies `event_grid` to the backend and makes Step 1.4's manual flip durable).

### Step 3.1: Re-provision; clear the orphan only if it recurs

Try the plain re-run first (the orphan scope was rolled back, so it may already succeed); fall back to the targeted delete only if `RoleAssignmentExists` recurs. The real orphan GUID is the one named in the `RoleAssignmentExists` error / `azd provision` output (substitute it for `<ORPHAN_ROLE_ASSIGNMENT_GUID>` below — do not write the literal into any tracked file).

Commands:
```pwsh
# (1) primary: plain re-run against the hardened template
azd provision --no-prompt

# (2) fallback ONLY if (1) fails again with RoleAssignmentExists
az role assignment delete --ids `
  "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Search/searchServices/srch-<SUFFIX>/providers/Microsoft.Authorization/roleAssignments/<ORPHAN_ROLE_ASSIGNMENT_GUID>"
# then re-run:
azd provision --no-prompt
```

Confirmation gates: `az role assignment delete` removes a live (orphaned) RBAC grant; `azd provision` redeploys shared infra. Confirm each with the user before running.

Discrepancy references:
* Addresses DR-05 (research primary unblock now an explicit step).

Success criteria:
* `azd provision` exits 0 (no `RoleAssignmentExists`).

Dependencies:
* Phase 2 (hardened template), Step 1.3 (durable intent).

### Step 3.2: Confirm provision green + env var applied

Verify the declarative path now produces the intended state, so Step 1.4's manual flip is no longer the only thing holding `event_grid`.

Commands:
* Re-run the Step 1.2(1) read — backend `AZURE_INGESTION_TRIGGER` should still be `event_grid` (now set declaratively).
* Confirm no rollback in the `azd provision` output.

Success criteria:
* Declarative provision is green and the backend trigger remains `event_grid` without manual intervention.

Dependencies:
* Step 3.1.

## Implementation Phase 4: Close-out documentation

<!-- parallelizable: false -->

Records the closure durably (Hard Rule #19) once Phase 1 validation passes. Placeholder tokens only (Hard Rule #18).

### Step 4.1: Flip BUG-0054 to fixed in the defect registry

Files:
* v2/docs/bugs.md — set BUG-0054 `Status` → `fixed`, add the `Fixed` date (2026-06-29), and record the cutover close-out (targeted `az` flip + EG sub on `blob-events` + poison drained). Keep the §0.1 pointer row (if present) consistent.
* v2/docs/bugs.md — additionally add a NEW discrete `BUG-####` row for the static-salt role-assignment non-idempotency (defect-by-construction; Area infra), `Status` → `fixed` by Phase 2, so the latent defect has standalone traceability per the research (DR-04) rather than being buried inside the BUG-0054 entry. Only add this row if Phase 2 actually landed this session.

Success criteria:
* BUG-0054 no longer appears in the open-bug list; close-out summary present with placeholders only.
* If Phase 2 ran: a discrete `BUG-####` row records the static-salt idempotency fix, cross-referenced to the Phase 2 hardening.

Dependencies:
* Phase 1 complete (Steps 1.4–1.7 validated). The discrete static-salt row additionally depends on Phase 2.

### Step 4.2: Append the worklog entry

Files:
* v2/docs/worklog/2026-06-29.md — append the day's BUG-0054 cutover entry: the loop diagnosis, the decouple decision, the targeted flip, validation, poison drain, the durable Bicep hardening (Phase 2), and the provision restore (Phase 3, if run). Create the file if absent (verify today's date first).

Success criteria:
* Worklog reflects the cutover + hardening + provision restore with next steps (any deferred follow-on items).

Dependencies:
* Phase 1 (and Phases 2/3 if executed in the same session).

## Implementation Phase 5: Validation

<!-- parallelizable: false -->

### Step 5.1: Run full relevant validation

Execute:
* `.venv\Scripts\python.exe -m pytest v2/tests/infra/test_main_bicep.py v2/tests/shared/test_no_env_specific_content*.py -q` — infra assertions + the placeholder/env gate over the edited docs (confirm the actual gate test name first).
* `az bicep build --file v2/infra/main.bicep --stdout` — template compiles.

### Step 5.2: Fix minor validation issues

Iterate on lint/test failures only when the fix is straightforward and isolated (e.g. a placeholder token missed in bugs.md/worklog, a test-assertion typo).

### Step 5.3: Report blocking issues

If validation surfaces anything beyond minor fixes (e.g. `azd provision` still fails after the Phase 2 hardening AND the Phase 3 orphan delete), document it, open the dedicated provision-idempotency follow-up (WI-03), recommend a separate turn, and do not attempt large-scale changes inline.

## Dependencies

* Authenticated `az` + `azd` session (Phase 1; Phase 3 re-provision; Phase 5 bicep build).
* uv-synced `.venv` for pytest (call `.venv\Scripts\python.exe -m pytest` directly).
* The `blob_event` Function already deployed (BUG-0080) — pre-flight done, do not redo.

## Success Criteria

* BUG-0054 closed: backend live `AZURE_INGESTION_TRIGGER=event_grid`, single-path ingestion validated (create + delete), poison drained, registry + worklog updated. — Traces to user request "fix the bug 54 issue".
* `azd provision` idempotency hardened: no static-salt role-assignment names; infra test green; bicep compiles. — Traces to the RoleAssignmentExists blocker (research Key Discoveries).
* Declarative provision restored (if Phase 3 run): `azd provision` exits 0 against the hardened template and applies `event_grid` declaratively. — Traces to DR-05 (the lived provision loop).
* No environment-specific values written to any tracked file (placeholders only). — Traces to Hard Rule #18.
