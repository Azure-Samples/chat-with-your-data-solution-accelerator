---
applyTo: '.copilot-tracking/changes/2026-06-29/bug-0054-cutover-fix-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: BUG-0054 cutover fix (Event Grid ingestion trigger)

## Overview

Close BUG-0054 with a targeted backend Container App env-var flip to `event_grid` (no `azd provision` required), then durably harden the role-assignment idempotency that was blocking provision, and record the closure.

## Objectives

### User Requirements

* Fix the BUG-0054 issue / break the review-without-fix loop. — Source: conversation 2026-06-29 ("why … we are in infinite loop without fix the problem"; "do the final research to fix the bug 54 issue").

### Derived Objectives

* Decouple the cutover from the blocked `azd provision`. — Derived from: research finding that the ingestion trigger has exactly one consumer (backend app-setting), so a single env-var flip is a complete behavioral cutover.
* Harden the two static-salt role-assignment names so a future `azd provision` is idempotent. — Derived from: the `RoleAssignmentExists` provision blocker root cause (stale cross-run orphan + static-salt names).
* Pin the Event Grid subscription `queueName` invariant with a test. — Derived from: the research test-gap (a live sub was silently on `doc-processing`).
* Record the closure in the defect registry + worklog. — Derived from: Hard Rule #19 (durable file-based tracking).

## Context Summary

### Project Files

* v2/infra/main.bicep - the two static-salt role-assignment names (L1038, L1050) and the Event Grid subscription declarations (queueName binding).
* v2/src/backend/core/settings.py - `StorageSettings.ingestion_trigger` (the single consumer of the flipped env var); no edit, reference only.
* v2/src/backend/services/ingestion.py - `upload_document` `backend_enqueues` branch; no edit, reference only.
* v2/tests/infra/test_main_bicep.py - where the new role-assignment + queueName assertions land.
* v2/docs/bugs.md - BUG-0054 row to flip to `fixed`.
* v2/docs/worklog/2026-06-29.md - day's worklog entry.

### References

* .copilot-tracking/research/2026-06-29/bug-0054-cutover-fix-research.md - selected approach + full runbook.
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-cutover-path-research.md - cutover wiring (file:line) + ordered runbook.
* .copilot-tracking/research/subagents/2026-06-29/role-assignment-idempotency-research.md - provision blocker root cause + Bicep before/after.

### Standards References

* .github/copilot-instructions.md — Hard Rule #1 (one unit/turn), #2 (test-first), #16 (no process narrative in src), #18 (no env-specific content in tracked files), #19 (durable tracking).
* .github/instructions/v2-infra.instructions.md — Bicep + RBAC + role-assignment naming conventions.
* User memory config-defaults-dev-first — repo default stays `direct_enqueue`; prod flips via env var only.
* User memory git-ownership — never stage/commit/push on the user's behalf.

## Implementation Checklist

### [ ] Implementation Phase 1: Verify live state + targeted cutover

<!-- parallelizable: false -->

Operator/implementer-run cloud actions (authenticated `az`/`azd`). Closes BUG-0054 behaviorally WITHOUT `azd provision`. Mutating steps (1.4, 1.5, 1.7) require explicit user confirmation.

* [ ] Step 1.1: Resolve environment values (`azd env get-values`, `az account show`)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 26-40)
* [ ] Step 1.2: Verify live state — trigger value, EG sub queue, poison depth (read-only)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 41-70)
* [ ] Step 1.3: Record durable intent (`azd env set AZURE_ENV_INGESTION_TRIGGER event_grid`)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 71-83)
* [ ] Step 1.4: Flip the backend now (`az containerapp update --set-env-vars AZURE_INGESTION_TRIGGER=event_grid`) — confirmation gate
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 84-101)
* [ ] Step 1.5: Conditionally repoint the EG subscription to `blob-events` (only if 1.2 shows `doc-processing`) — confirmation gate
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 102-122)
* [ ] Step 1.6: Re-validate end-to-end (create + delete; mind BUG-0058 prepackage; clean up the test doc)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 123-138)
* [ ] Step 1.7: Drain ~4 historical `doc-processing-poison` messages — confirmation gate
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 139-157)

### [x] Implementation Phase 2: Durable Bicep idempotency hardening

<!-- parallelizable: true -->

Repo-file-only; independent of Phase 1. One code unit, test-first. NOT required to close BUG-0054.

* [x] Step 2.1: Harden both static-salt role-assignment names to `guid(scope.id, principalId, roleDefinitionId)`
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 164-193)
* [x] Step 2.2: Add infra-test assertions (deterministic names + EG sub `queueName` pinned to `blob-events`)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 194-215)
* [x] Step 2.3: Validate phase — run the infra test + `bicep build`
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 216-229)

### [ ] Implementation Phase 3: Restore declarative provision (operator-run)

<!-- parallelizable: false -->

Clears the current orphan + re-runs `azd provision` against the Phase 2 hardened template. OPTIONAL for BUG-0054 closure (Phase 1 already closed it); REQUIRED only to make `azd provision` succeed again. Depends on Phase 2 (hardened template) + Step 1.3 (durable intent). Both mutating steps are confirmation-gated.

* [ ] Step 3.1: Re-provision against the hardened template; clear the orphan role assignment only if `RoleAssignmentExists` recurs — confirmation gates
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 238-264)
* [ ] Step 3.2: Confirm provision green + `event_grid` applied declaratively
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 265-278)

### [ ] Implementation Phase 4: Close-out documentation

<!-- parallelizable: false -->

Depends on Phase 1 validation. Placeholder tokens only.

* [ ] Step 4.1: Flip BUG-0054 → `fixed` in v2/docs/bugs.md with the cutover close-out
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 285-297)
* [ ] Step 4.2: Append the worklog entry to v2/docs/worklog/2026-06-29.md
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 298-308)

### [ ] Implementation Phase 5: Validation

<!-- parallelizable: false -->

* [ ] Step 5.1: Run infra tests + env/placeholder gate + bicep build
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 313-318)
* [ ] Step 5.2: Fix minor validation issues
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 319-322)
* [ ] Step 5.3: Report blocking issues (e.g. provision still failing after hardening + orphan delete — open WI-03)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md (Lines 323-325)

## Planning Log

See .copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-fix-log.md for discrepancy tracking, implementation paths considered, and suggested follow-on work.

## Dependencies

* Authenticated `az` + `azd` session (Phase 1; Phase 3 re-provision; Phase 5 bicep build).
* uv-synced `.venv` for pytest — call `.venv\Scripts\python.exe -m pytest` directly (uv trampoline broken in this repo).
* `blob_event` Function already deployed (BUG-0080) — do not re-do the pre-flight.

## Success Criteria

* BUG-0054 closed: backend live `AZURE_INGESTION_TRIGGER=event_grid`, single-path ingestion validated (create + delete), poison drained, registry + worklog updated. — Traces to: user request "fix the bug 54 issue".
* `azd provision` idempotency hardened: no static-salt role-assignment names; infra test green; bicep compiles. — Traces to: the `RoleAssignmentExists` blocker (research Key Discoveries).
* Declarative provision restored (if Phase 3 run): `azd provision` exits 0 against the hardened template and applies `event_grid` declaratively. — Traces to: DR-05 (the lived provision loop).
* No environment-specific values in any tracked file (placeholders only). — Traces to: Hard Rule #18.
