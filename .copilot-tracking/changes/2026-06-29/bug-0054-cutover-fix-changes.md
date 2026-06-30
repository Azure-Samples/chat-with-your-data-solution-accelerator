<!-- markdownlint-disable-file -->
# Release Changes: BUG-0054 cutover fix (Event Grid ingestion trigger)

**Related Plan**: bug-0054-cutover-fix-plan.instructions.md
**Implementation Date**: 2026-06-29

## Summary

Close BUG-0054 by cutting the ingestion trigger over to `event_grid` (targeted backend Container App env-var flip — no `azd provision` required), durably harden the role-assignment idempotency that was blocking provision, and record the closure. Phases 1 and 3 are operator-run, confirmation-gated cloud actions; Phase 2 is repo-file-only and the only fully-autonomous code unit; Phase 4 depends on Phase 1 validation.

## Changes

### Added

* (pending)

### Modified

* v2/infra/main.bicep - Hardened the two search-MI → OpenAI role-assignment names (`searchOpenAiUserOnFoundry`, `searchOpenAiUserOnReusedOpenAi`) from the static-salt `guid(<name>, 'search-system-mi', <roleDefId>)` to a scope-deterministic `guid(<scope>.id, 'srch-${solutionSuffix}', <roleDefId>)`, removing the non-idempotent token that drove the provision orphan.
* v2/tests/infra/test_main_bicep.py - Added regression assertions: (1) both search-OpenAI role-assignment names key on the deterministic `guid(aiServicesAccount.id / existingOpenAi.id, 'srch-${solutionSuffix}', ...)` form and the file contains no `'search-system-mi'` literal; (2) both Event Grid blob subscriptions bind `queueName` to `blobEventsQueueName` (`blob-events`), never raw `doc-processing` — closing the BUG-0054 double-ingest regression gap.

### Removed

* (pending)

## Additional or Deviating Changes

* Phases 1 (cutover) and 3 (restore declarative provision) are operator-run cloud mutations under explicit confirmation gates — not executed autonomously by an implementation subagent.
* Phase 4 (close-out documentation) depends on Phase 1 validation and is deferred until the operator runs the cutover.
* DD-02 (Phase 2 Step 2.1): the hardened role-assignment `name` salts on `'srch-${solutionSuffix}'` (start-time-knowable) instead of the deploy-time `systemAssignedMIPrincipalId` the plan text specified — forced by Bicep BCP120 (a role-assignment `name` must resolve at start-time). The objective (deterministic, idempotent, `'search-system-mi'`-free name) is fully met; verified by `az bicep build` EXIT=0 and the infra test (36/36 pass). See planning log DD-02.

## Release Summary

(pending — written after the final phase)
