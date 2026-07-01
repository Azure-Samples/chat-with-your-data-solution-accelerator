<!-- markdownlint-disable-file -->
# Implementation Details: BUG-0054 live close-out (post-rebuild, subscription-gated)

## Context Reference

Sources: `.copilot-tracking/research/2026-06-30/bug-0054-live-close-research.md` (current state + runbook); predecessor `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-fix-plan.instructions.md` (Phase 2 done, Phases 4/5 carried forward); `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-fix-log.md` (DR-06/ID-01). All real Azure identifiers use placeholder tokens per Hard Rule #18.

## Implementation Phase 0: Precondition — subscription re-enabled

<!-- parallelizable: false -->

### Step 0.1: Confirm the subscription is active before any Azure write

Hard gate. Every Azure write returns HTTP 409 `ReadOnlyDisabledSubscription` until the user re-enables subscription `<AZURE_SUBSCRIPTION_ID>` (Azure portal → Subscriptions → Reactivate / remove spending limit). Do NOT proceed past this step until it passes.

Commands:
* `az account list --all --refresh --query "[?id=='<AZURE_SUBSCRIPTION_ID>'].{name:name,state:state}" -o json` — assert `state == "Enabled"` (`--refresh` forces a live billing-state read; `--all` includes non-Enabled subscriptions so a `Warned`/`Disabled` state is visible rather than silently filtered out). NOTE: `az account show` has no `--refresh` flag (DR-12) — use `az account list --all --refresh`.
* Write probe (definitive): `az tag update --resource-id /subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP> --operation merge --tags cwydWriteProbe=ok` then revert with `--operation delete`. A reversible ARM write that proves write-capability in ~5s without committing to a 30–40 min `azd up`. `ReadOnlyDisabledSubscription` here ⇒ still blocked (a `Warned` state can still be read-only).
* Note (DR-11/DR-12): the `state` read alone does not prove writability (`Warned` reads as not-`Enabled` but is ambiguous); the tag-merge write probe is the authoritative Phase 0 signal. The `azd up` in Step 1.2 is the final confirmation.

Success criteria:
* `az account list --all --refresh` reports `state == "Enabled"` AND the tag-merge write probe succeeds (then is reverted).
* No `ReadOnlyDisabledSubscription` on the write probe.

Dependencies:
* User has re-enabled the subscription (external billing/account action — cannot be done from CLI).

### Step 0.2: STOP-and-report if still disabled

If `state != "Enabled"`, do not issue any Azure write. Report the blocker to the user (re-enable the subscription) and end the turn. The plan resumes at Phase 1 once Step 0.1 passes.

Success criteria:
* When blocked: no Azure write attempted; user informed; turn ends cleanly.

## Implementation Phase 1: Clean rebuild (azd up)

<!-- parallelizable: false -->

Depends on Phase 0. Live cloud mutation — pre-authorized by the user ("Full re-provision + live validate, then close").

### Step 1.1: Confirm pre-staging still holds (idempotent re-check)

Verify the env prep from 2026-06-30 is intact; re-apply if drifted.

Verified binding chain (DR-09): the azd env var `AZURE_ENV_INGESTION_TRIGGER` flows into the deployed Container App — `v2/infra/main.parameters.json` L20-21 binds `ingestionTrigger` to `${AZURE_ENV_INGESTION_TRIGGER=direct_enqueue}`, `v2/infra/main.bicep` L100 declares the param (default `direct_enqueue`), L1949 sets the Container App env `AZURE_INGESTION_TRIGGER = ingestionTrigger`. So the azd-env value is the single switch; if it is unset/cleared, the deploy silently falls back to `direct_enqueue` and certifies the WRONG path. Therefore re-assert it explicitly, do not merely read it.

Commands (from `v2/`):
* `azd env get-values | Select-String 'AZURE_CONTAINER_REGISTRY_ENDPOINT|AZURE_SOLUTION_SUFFIX|AZURE_ENV_INGESTION_TRIGGER'` — expect `AZURE_CONTAINER_REGISTRY_ENDPOINT=""` (cleared), suffix `<SUFFIX>`, trigger `event_grid`.
* `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` — idempotent re-assert of the cutover intent (guards against a drifted/cleared env value before provision; does NOT touch the repo default in `main.parameters.json`, honoring config-defaults-dev-first).
* If the endpoint is non-empty again: `azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT ""`.
* `az cognitiveservices account list-deleted --query "[?contains(name, '<SUFFIX>')].name" -o json` — if any reappeared, purge each: `az cognitiveservices account purge --location <REGION> --resource-group <RESOURCE_GROUP> --name <NAME>`.

Success criteria:
* Registry endpoint cleared; `AZURE_ENV_INGESTION_TRIGGER=event_grid` explicitly set; zero soft-deleted Cognitive Services for the suffix.

Dependencies:
* Phase 0 passed.

### Step 1.2: Run `azd up`

`azd up --no-prompt` = package → provision (placeholder image, creates ACR + all infra) → captures the new ACR endpoint into the env → deploy (builds + pushes real images, updates the Container Apps). Long-running (~30–40 min); run async and monitor the log.

Commands (from `v2/`):
* `$env:AZD_SKIP_UPDATE_CHECK='1'; azd up --no-prompt 2>&1 | Tee-Object -FilePath "$env:TEMP\cwyd-azd-up-rebuild.log"` (async).
* Monitor for `provision` success then `Deploying (Updating container app revision)` → `Done`.

Success criteria:
* `azd up` exits 0; backend/frontend/function services all `Done`.

Dependencies:
* Step 1.1.

### Step 1.3: Confirm the Container App recovered + backend healthy

Commands:
* `az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> --query "{state:properties.provisioningState,running:properties.runningStatus,image:properties.template.containers[0].image,fqdn:properties.configuration.ingress.fqdn}" -o json` — expect `Succeeded` / `Running` / real ACR image path.
* `Invoke-WebRequest https://<BACKEND_FQDN>/api/health` — expect 200.

Success criteria:
* Container App `Succeeded` + `Running`; backend `/api/health` returns 200.

Dependencies:
* Step 1.2.

### Step 1.4: Fallback if the backend image is not placed

Only if Step 1.3 shows the Container App still `Failed`/`MANIFEST_UNKNOWN`.

Before building manually, confirm the image name azd actually references on the Container App so the manual build targets the SAME repository/tag (azd names service images after the `backend` service; a mismatched manual tag leaves the Container App still pointing at the missing image):
* `az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> --query "properties.template.containers[0].image" -o tsv` — note the exact `cr<SUFFIX>.azurecr.io/<repo>:<tag>`; build to that `<repo>:<tag>`.

Commands (from `v2/`):
* `az acr build --registry cr<SUFFIX> --image <repo>:<tag> --file docker/Dockerfile.backend .` (use the `<repo>:<tag>` read above; the azd-managed default is `cwyd-backend:latest`).
* `azd provision --no-prompt`
* Re-run Step 1.3 checks.

Success criteria:
* Image present in ACR (`az acr repository show-tags -n cr<SUFFIX> --repository <repo>`); Container App `Running`.

Dependencies:
* Step 1.3 showed a failed image placement.

## Implementation Phase 2: Live cutover validation

<!-- parallelizable: false -->

Depends on Phase 1 (Running backend). The behavioral proof that closes BUG-0054. Mind BUG-0058 (prepackage) during ingestion.

### Step 2.1: Resolve the backend ingress URL + confirm the deployed trigger

Resolve the backend FQDN AND confirm the deployed Container App is actually on `event_grid` before running the ingestion test (DR-09) — this reads the live env var, closing the loop on the Step 1.1 re-assert.

Commands:
* `az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> --query properties.configuration.ingress.fqdn -o tsv`.
* `az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> --query "properties.template.containers[0].env[?name=='AZURE_INGESTION_TRIGGER'].value | [0]" -o tsv` — assert `event_grid`. If it reads `direct_enqueue`, STOP: the cutover did not take; re-check Step 1.1 (`AZURE_ENV_INGESTION_TRIGGER`) and re-provision before validating.

Success criteria:
* Backend FQDN resolved; deployed `AZURE_INGESTION_TRIGGER == event_grid`.

Dependencies:
* Phase 1.

### Step 2.2: Upload a test document + confirm single-path Event Grid ingestion

Upload one throwaway document; confirm it ingests through the SINGLE Event Grid `blob_event` path (not the legacy direct-enqueue path) and lands in the index. Proving "single" requires BOTH a positive (the `blob_event` path fired) AND a negative (the backend did NOT also direct-enqueue) — a dual-path regression would pass a positive-only check (DR-10).

Steps:
* Upload by writing the blob DIRECTLY into the ingestion container (portal blob upload or `az storage blob upload`) so the Event Grid subscription is the trigger under test. Prefer this over the backend admin upload endpoint, which can itself enqueue and mask a dual-path regression.
* Positive: confirm the Functions `blob_event` trigger fired (Function invocation log / Application Insights) and the chunk landed in the search index.
* Negative (DR-10): confirm the backend did NOT also direct-enqueue — immediately after upload, the `doc-processing` queue on `st<SUFFIX>` shows no new backend-originated message (depth unchanged / no backend enqueue), and exactly one ingest occurred. With the backend deployed on `event_grid` (confirmed in Step 2.1), the direct-enqueue branch is off; this check proves it at runtime.

Success criteria:
* Document ingested via the Event Grid `blob_event` path; chunk present in the index; NO concurrent backend `doc-processing` enqueue (single-path proven).

Dependencies:
* Step 2.1.

### Step 2.3: Confirm a citation in chat

Ask a question answerable from the test doc; confirm the answer returns a citation referencing it.

Success criteria:
* Chat returns a grounded answer with a citation to the test doc.

Dependencies:
* Step 2.2.

### Step 2.4: Delete + confirm de-index, then clean up

Delete the test doc via the admin delete-by-source endpoint; confirm it leaves the index; remove the source blob. Per `cleanup-before-next-step`, leave no test artifact behind.

Success criteria:
* Test doc de-indexed; source blob removed; index back to pre-test state.

Dependencies:
* Step 2.3.

## Implementation Phase 3: Drain poison queue

<!-- parallelizable: false -->

Depends on Phase 2. A clean rebuild starts with an empty `doc-processing-poison`; verify depth and drain only if present.

### Step 3.1: Check + drain `doc-processing-poison`

Commands:
* Check approximate message count on `doc-processing-poison` (storage queue on `st<SUFFIX>`); if non-zero, clear after confirming none are in-flight legitimate retries.

Success criteria:
* `doc-processing-poison` depth is 0 (or confirmed empty post-rebuild).

Dependencies:
* Phase 2.

## Implementation Phase 4: Close-out documentation

<!-- parallelizable: false -->

Depends on Phase 2 validation passing. Placeholder tokens only (Hard Rule #18).

### Step 4.1: Flip BUG-0054 → `fixed` in v2/docs/bugs.md

Update the BUG-0054 summary row (status `open` → `fixed`) and its detailed entry with the close-out: single Event Grid `blob_event` path validated live (create → cite → delete → de-index), deploy-sequencing fix proven, Bicep idempotency hardened (Phase 2).

Files:
* v2/docs/bugs.md - BUG-0054 row + detailed entry.

Success criteria:
* BUG-0054 status `fixed`; close-out references the live validation + the hardening; no env-specific values.

Dependencies:
* Phase 2.

### Step 4.2: Append the close-out to v2/docs/worklog/2026-06-30.md

Append a "Done (close-out)" section: subscription re-enabled, rebuild green, live validation passed, BUG-0054 fixed. Verify the real current date before naming/extending the worklog file.

Files:
* v2/docs/worklog/2026-06-30.md - append close-out (do not open a second file for the same date).

Success criteria:
* Worklog records the live close with the actual outcome.

Dependencies:
* Step 4.1.

### Step 4.3: Mark the superseded 2026-06-29 plan + this plan's checkboxes

Tick the executed phases here; add a one-line supersession pointer at the top of the 2026-06-29 plan referencing this plan as the live close-out of record.

Files:
* .copilot-tracking/plans/2026-06-29/bug-0054-cutover-fix-plan.instructions.md - supersession pointer.
* .copilot-tracking/plans/2026-06-30/bug-0054-live-close-plan.instructions.md - checkbox updates.

Success criteria:
* Plan tracking reflects reality; no orphaned "open" predecessor.

Dependencies:
* Step 4.2.

## Implementation Phase 5: Validation

<!-- parallelizable: false -->

### Step 5.1: Run infra tests + placeholder gate + bicep build

Commands (from `v2/`):
* `.venv\Scripts\python.exe -m pytest tests/infra` — expect 36/36 (or current count) green.
* Run the env/placeholder gate test (no env-specific content in tracked files).
* `az bicep build --file infra/main.bicep` — EXIT=0.

Success criteria:
* Infra tests green; placeholder gate green; bicep compiles.

### Step 5.2: Fix minor validation issues

Iterate on any lint/test/placeholder findings introduced by the doc edits (Phase 4). Apply straightforward fixes directly.

Success criteria:
* All gates green after fixes.

### Step 5.3: Report blocking issues

If a gate fails beyond minor fixes (e.g. live ingestion still dual-path after rebuild), document it, open a follow-on WI, and report next steps rather than large inline changes.

Success criteria:
* Any blocker captured as a tracked WI with next steps.

## Dependencies

* User re-enables subscription `<AZURE_SUBSCRIPTION_ID>` (Phase 0 gate — external).
* Authenticated `az` + `azd` session.
* uv-synced `.venv`; call `.venv\Scripts\python.exe -m pytest` directly from `v2/`.

## Success Criteria

* BUG-0054 closed live: backend on the single Event Grid `blob_event` path, validated create → cite → delete → de-index, test artifacts cleaned, poison drained, registry + worklog updated — all with placeholder tokens only.
