<!-- markdownlint-disable-file -->
# Research: BUG-0054 live close-out (post-rebuild, subscription-gated)

## Scope

Capture the current, directly-observed state of BUG-0054 (single Event Grid ingestion-trigger cutover) as of 2026-06-30 and the remaining runbook to drive it to a live close. This is a lightweight planning research doc grounded in this session's live `az`/`azd` observations and the predecessor research corpus under `.copilot-tracking/research/2026-06-29/`; it does not re-derive the cutover wiring (already established).

## Key facts (directly observed this session, 2026-06-30)

### The fix is proven

* `azd deploy backend` (run 2026-06-29) **succeeded**: `Done [2m16s]`, backend image built + pushed to ACR via remote build, Container App revision updated, live endpoint returned. The deploy-sequencing fix (image must reach ACR independently before the Container App can leave `Failed`) is validated.

### The environment was wiped by a disabled subscription (NEW hard blocker)

* Overnight the resource group `<RESOURCE_GROUP>` was emptied — `az resource list` returns zero resources; the backend Container App returns `ResourceNotFound`; its FQDN no longer resolves.
* Root cause: `azd up` failed at the provision step with HTTP 409 **`ReadOnlyDisabledSubscription`** — subscription `<AZURE_SUBSCRIPTION_ID>` is **disabled and marked read-only**. No write action (provision/deploy) can run until it is re-enabled.
* This is an external billing/account blocker (commonly: spending limit reached, credits expired, admin-disabled). It cannot be resolved from code or CLI; the user must re-enable the subscription (Azure portal → Subscriptions → Reactivate).

### Pre-staging already completed this session (idempotent, safe)

* `AZURE_CONTAINER_REGISTRY_ENDPOINT` was **cleared** in the azd env (`azd env set ... ""`) so the FIRST provision of a clean rebuild uses the placeholder image `mcr.microsoft.com/k8se/quickstart:latest` and avoids the `MANIFEST_UNKNOWN` chicken-and-egg (Container App pointing at a real-image path before the image exists).
* The 3 soft-deleted Cognitive Services accounts left by the teardown (`spch-<SUFFIX>`, `aisa-<SUFFIX>`, `cs-<SUFFIX>`) were **purged** (`az cognitiveservices account purge`), clearing the `FlagMustBeSetForRestore` provision blocker.
* The azd env is otherwise intact: suffix `<SUFFIX>`, `AZURE_ENV_INGESTION_TRIGGER=event_grid` (durable single-path intent recorded).

### Source-side work already landed (prior sessions, verified)

* Phase 2 Bicep idempotency hardening + 3 review minors (M-1 remove/gitignore `main.json`; M-2 `existingOpenAi!.id`; M-3 hoist `cognitiveServicesOpenAiUserRoleId` to a `var`) are committed in `v2/infra/main.bicep`.
* `v2/tests/infra/test_main_bicep.py` pins the deterministic role-assignment names + the Event Grid subscription `queueName: blob-events` invariant. **36/36 pass.** `az bicep build` EXIT=0.

## The clean-rebuild runbook (once the subscription is active)

1. **Precondition gate** — confirm the subscription is enabled again (`az account show` → `state == "Enabled"`; a trivial write-capable read such as `az group show -n <RESOURCE_GROUP>`). Do NOT issue any Azure write until this passes.
2. **Clean rebuild** — `AZURE_CONTAINER_REGISTRY_ENDPOINT` already cleared; re-purge any soft-deleted Cognitive Services that reappeared; `azd up --no-prompt`. `azd up` = package → provision (placeholder image, succeeds, creates ACR) → captures the new ACR endpoint into the env → deploy (builds + pushes the real images, updates the Container Apps). Confirm Container App `provisioningState=Succeeded` + `runningStatus=Running` + backend `/api/health` responds.
3. **Live cutover validation** — resolve the backend ingress URL; upload a test document; confirm it ingests through the SINGLE Event Grid `blob_event` path (not the legacy direct-enqueue path) and returns a citation in chat; delete it; confirm de-index. Then CLEAN UP the test doc/blob/index entry (cleanup-before-next-step). Mind BUG-0058 (prepackage) during validation.
4. **Drain poison** — drain the historical `doc-processing-poison` messages (a clean rebuild starts the queue empty, so this may be a no-op; verify depth and drain only if present).
5. **Close-out** — flip BUG-0054 → `fixed` in `v2/docs/bugs.md` (placeholders only); append the close-out to `v2/docs/worklog/2026-06-30.md`; mark the superseded 2026-06-29 plan checkboxes / supersession pointer.
6. **Validation gate** — infra tests (`.venv\Scripts\python.exe -m pytest tests/infra`), the env/placeholder gate, and `az bicep build`.

## Fallback (only if `azd up` cannot place the backend image)

* `az acr build --registry cr<SUFFIX> --image cwyd-backend:latest --file docker/Dockerfile.backend .` (from `v2/`) to push the image, then `azd provision --no-prompt` to finalize. Then re-confirm Running and proceed to validation.

## Constraints (binding)

* Hard Rule #18 / user memory `azure-env-ids-never-commit` — placeholders only in tracked files; real names allowed only in terminal commands.
* User memory `config-defaults-dev-first` — repo default stays `direct_enqueue`; do NOT edit `Configuration.tsx` or `main.parameters.json`; prod flips via env var only.
* User memory `cleanup-before-next-step` — delete the test blob, de-index the test doc, drain poison after validation.
* User memory `git-ownership` — never stage/commit/push; report `git status --short` then stop.
* uv trampoline broken — call `.venv\Scripts\python.exe -m pytest` directly from `v2/`.

## Predecessor artifacts (superseded / carried forward)

* `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-fix-plan.instructions.md` — the predecessor plan; Phase 2 done, Phase 1 (targeted env-var flip) superseded by the full-rebuild reality (DR-06/ID-01), Phases 4/5 carried forward here.
* `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-fix-log.md` — DR-06 (RG torn down) + ID-01 (full re-provision authorized) already recorded; this plan extends that with the disabled-subscription blocker.
* `.copilot-tracking/research/2026-06-29/bug-0054-cutover-fix-research.md` — selected cutover approach + full wiring runbook (file:line).
