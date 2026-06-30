<!-- markdownlint-disable-file -->
# Release Changes: BUG-0054 cutover fix (Event Grid ingestion trigger)

**Related Plan**: bug-0054-cutover-fix-plan.instructions.md
**Implementation Date**: 2026-06-29

## Summary

Close BUG-0054 by cutting the ingestion trigger over to `event_grid` (targeted backend Container App env-var flip — no `azd provision` required), durably harden the role-assignment idempotency that was blocking provision, and record the closure. Phases 1 and 3 are operator-run, confirmation-gated cloud actions; Phase 2 is repo-file-only and the only fully-autonomous code unit; Phase 4 depends on Phase 1 validation.

## Changes

### Added

* (none)

### Modified

* v2/infra/main.bicep - Hardened the two search-MI → OpenAI role-assignment names (`searchOpenAiUserOnFoundry`, `searchOpenAiUserOnReusedOpenAi`) from the static-salt `guid(<name>, 'search-system-mi', <roleDefId>)` to a scope-deterministic `guid(<scope>.id, 'srch-${solutionSuffix}', <roleDefId>)`, removing the non-idempotent token that drove the provision orphan. Review follow-ups: hoisted the Cognitive Services OpenAI User role GUID `5e0bd9bd-...` (used 7×) to `var cognitiveServicesOpenAiUserRoleId` (M-3); normalized `existingOpenAi.id` → `existingOpenAi!.id` at `searchOpenAiUserOnReusedOpenAi` for null-assertion consistency with `existingOpenAiUamiRole` (M-2). Both changes are value-identical at compile time — no role-assignment `guid()` name changes, so no new orphans.
* v2/tests/infra/test_main_bicep.py - Added regression assertions: (1) both search-OpenAI role-assignment names key on the deterministic `guid(aiServicesAccount.id / existingOpenAi!.id, 'srch-${solutionSuffix}', subscriptionResourceId(..., cognitiveServicesOpenAiUserRoleId))` form, the role GUID is hoisted to `var cognitiveServicesOpenAiUserRoleId`, and the file contains no `'search-system-mi'` literal; (2) both Event Grid blob subscriptions bind `queueName` to `blobEventsQueueName` (`blob-events`), never raw `doc-processing` — closing the BUG-0054 double-ingest regression gap.
* v2/.gitignore - Added an ignore rule for the stale, unused, pre-compiled `infra/main.json` ARM artifact (azd compiles `infra/main.bicep` directly via `azure.yaml` provider: bicep / module: main, so it is never consumed and drifts from source).

### Removed

* v2/infra/main.json - Deleted the stale git-tracked pre-compiled ARM template (review finding M-1). It still carried the obsolete `'search-system-mi'` salt and is never read by azd; regenerate on demand via `az bicep build --file infra/main.bicep`.

## Additional or Deviating Changes

* Review findings addressed (user authorized "Apply both" + "Remove + gitignore", overriding the review's "no action required" notes on M-2/M-3): M-1 `main.json` removed + gitignored; M-2 `!.id` consistency applied; M-3 role GUID hoisted to a `var`. M-3 overrides the Hard Rule #12 "do not back-fill inline" note by explicit user direction this turn.
* Phases 1 (cutover) and 3 (restore declarative provision) are operator-run cloud mutations under explicit confirmation gates — user authorized full execution this turn ("do all the phases completely and close it").
* Phase 4 (close-out documentation) depends on Phase 1 validation and is deferred until the operator runs the cutover.
* DD-02 (Phase 2 Step 2.1): the hardened role-assignment `name` salts on `'srch-${solutionSuffix}'` (start-time-knowable) instead of the deploy-time `systemAssignedMIPrincipalId` the plan text specified — forced by Bicep BCP120 (a role-assignment `name` must resolve at start-time). The objective (deterministic, idempotent, `'search-system-mi'`-free name) is fully met; verified by `az bicep build` EXIT=0 and the infra test (36/36 pass). See planning log DD-02.

## Release Summary

(pending — written after the final phase)
