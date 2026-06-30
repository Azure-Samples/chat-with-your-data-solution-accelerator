---
applyTo: '.copilot-tracking/changes/2026-06-30/bug-0054-live-close-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: BUG-0054 live close-out (post-rebuild, subscription-gated)

## Overview

Drive BUG-0054 (single Event Grid ingestion-trigger cutover) to a live close by rebuilding the wiped environment with `azd up`, validating single-path ingestion end-to-end, then flipping the bug to `fixed` — gated on the user first re-enabling the disabled Azure subscription.

## Objectives

### User Requirements

* Close BUG-0054 — drive the cutover fix to a verified live close. — Source: conversation 2026-06-29/30 ("do all the phases completely and close it"; "Full re-provision + live validate, then close").

### Derived Objectives

* Gate all work on the subscription being re-enabled. — Derived from: live `azd up` failure HTTP 409 `ReadOnlyDisabledSubscription` (subscription disabled overnight); no Azure write succeeds until reactivated.
* Rebuild via the clean placeholder-image flow. — Derived from: the proven `MANIFEST_UNKNOWN` chicken-and-egg; clearing `AZURE_CONTAINER_REGISTRY_ENDPOINT` lets the first provision use the placeholder image, then `azd up`'s deploy phase pushes the real image.
* Prove single-path ingestion behaviorally, not just in source. — Derived from: BUG-0054's closure criteria are behavioral (a doc must ingest through the single Event Grid path in cloud).
* Record the live close durably. — Derived from: Hard Rule #19 (durable file-based tracking).

## Context Summary

### Project Files

* v2/infra/main.bicep - Container App image branch (placeholder vs real ACR path) + the Phase 2 hardened role-assignment names; no edit, reference only.
* v2/src/backend/core/settings.py - `StorageSettings.ingestion_trigger` (single consumer of `event_grid`); no edit, reference only.
* v2/docs/bugs.md - BUG-0054 row to flip to `fixed` (Phase 4).
* v2/docs/worklog/2026-06-30.md - day's worklog; blocker already recorded, close-out appended in Phase 4.
* v2/tests/infra/test_main_bicep.py - infra gate (Phase 5).

### References

* .copilot-tracking/research/2026-06-30/bug-0054-live-close-research.md - current state + clean-rebuild runbook + fallback.
* .copilot-tracking/research/2026-06-29/bug-0054-cutover-fix-research.md - cutover wiring + runbook (file:line).
* .copilot-tracking/plans/2026-06-29/bug-0054-cutover-fix-plan.instructions.md - predecessor plan (Phase 2 done; superseded Phase 1).
* .copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-fix-log.md - DR-06 (RG torn down) + ID-01 (full re-provision authorized).

### Standards References

* .github/copilot-instructions.md — Hard Rule #18 (no env-specific content in tracked files), #19 (durable tracking).
* User memory config-defaults-dev-first — repo default stays `direct_enqueue`; do NOT edit `Configuration.tsx` or `main.parameters.json`.
* User memory cleanup-before-next-step — delete test blob, de-index test doc, drain poison after validation.
* User memory git-ownership — never stage/commit/push; report `git status --short` then stop.

## Implementation Checklist

### [ ] Implementation Phase 0: Precondition — subscription re-enabled

<!-- parallelizable: false -->

Hard external gate. No Azure write succeeds until the user re-enables subscription `<AZURE_SUBSCRIPTION_ID>`.

* [ ] Step 0.1: Confirm the subscription is active (`az account show --refresh` → `state == "Enabled"`)
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 12-26)
* [ ] Step 0.2: STOP-and-report if still disabled (no Azure write; end the turn)
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 28-33)

### [ ] Implementation Phase 1: Clean rebuild (azd up)

<!-- parallelizable: false -->

Depends on Phase 0. Live cloud mutation — pre-authorized.

* [ ] Step 1.1: Confirm pre-staging holds + re-assert `AZURE_ENV_INGESTION_TRIGGER=event_grid` (endpoint cleared, no soft-deleted Cognitive Services)
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 41-57)
* [ ] Step 1.2: Run `azd up --no-prompt` (placeholder-first provision → deploy real images)
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 59-71)
* [ ] Step 1.3: Confirm Container App `Succeeded`/`Running` + backend `/api/health` 200
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 73-83)
* [ ] Step 1.4: Fallback — `az acr build` (to the azd-named image) + `azd provision` only if the image was not placed
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 85-101)

### [ ] Implementation Phase 2: Live cutover validation

<!-- parallelizable: false -->

Depends on Phase 1. Mind BUG-0058 (prepackage).

* [ ] Step 2.1: Resolve the backend ingress URL + confirm deployed `AZURE_INGESTION_TRIGGER == event_grid`
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 109-121)
* [ ] Step 2.2: Upload a test doc (direct blob write) + confirm single-path `blob_event` ingestion with a negative no-direct-enqueue assertion
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 123-136)
* [ ] Step 2.3: Confirm a citation in chat
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 138-146)
* [ ] Step 2.4: Delete + confirm de-index, then clean up the test artifact
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 148-156)

### [ ] Implementation Phase 3: Drain poison queue

<!-- parallelizable: false -->

* [ ] Step 3.1: Check + drain `doc-processing-poison` (likely empty post-rebuild)
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 164-173)

### [ ] Implementation Phase 4: Close-out documentation

<!-- parallelizable: false -->

Depends on Phase 2 validation. Placeholder tokens only.

* [ ] Step 4.1: Flip BUG-0054 → `fixed` in v2/docs/bugs.md
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 181-192)
* [ ] Step 4.2: Append the close-out to v2/docs/worklog/2026-06-30.md
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 194-205)
* [ ] Step 4.3: Mark the superseded 2026-06-29 plan + this plan's checkboxes
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 207-219)

### [ ] Implementation Phase 5: Validation

<!-- parallelizable: false -->

* [ ] Step 5.1: Run infra tests + placeholder gate + `bicep build`
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 225-233)
* [ ] Step 5.2: Fix minor validation issues
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 235-240)
* [ ] Step 5.3: Report blocking issues (open a follow-on WI if a gate fails beyond minor fixes)
  * Details: .copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md (Lines 242-247)

## Planning Log

See .copilot-tracking/plans/logs/2026-06-30/bug-0054-live-close-log.md for discrepancy tracking, implementation paths considered, and suggested follow-on work.

## Dependencies

* User re-enables subscription `<AZURE_SUBSCRIPTION_ID>` (Phase 0 gate — external billing/account action).
* Authenticated `az` + `azd` session.
* uv-synced `.venv` — call `.venv\Scripts\python.exe -m pytest` directly from `v2/` (uv trampoline broken).
* Pre-staging from 2026-06-30 (cleared ACR endpoint; purged soft-deleted Cognitive Services) — re-checked idempotently in Step 1.1.

## Success Criteria

* BUG-0054 closed live: deployed `AZURE_INGESTION_TRIGGER == event_grid` confirmed, single Event Grid `blob_event` path validated with a negative no-direct-enqueue assertion (create → cite → delete → de-index), test artifacts cleaned, poison drained. — Traces to: user request "close it".
* Rebuild green: `azd up` exits 0; backend Container App `Running` + `/api/health` 200. — Traces to: the disabled-subscription wipe + the proven deploy-sequencing fix.
* Registry + worklog updated; predecessor plan superseded cleanly. — Traces to: Hard Rule #19.
* No environment-specific values in any tracked file (placeholders only). — Traces to: Hard Rule #18.
