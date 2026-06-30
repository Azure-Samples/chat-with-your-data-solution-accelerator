<!-- markdownlint-disable-file -->
# Release Changes: BUG-0054 live close-out (post-rebuild, subscription-gated)

**Related Plan**: bug-0054-live-close-plan.instructions.md
**Implementation Date**: 2026-06-30

## Summary

Live close-out of BUG-0054 (single Event Grid ingestion-trigger cutover). Execution is gated on Phase 0 — the disabled Azure subscription being re-enabled. This run reached Phase 0 and **stopped**: the subscription is still read-only.

## Changes

### Added

* .copilot-tracking/changes/2026-06-30/bug-0054-live-close-changes.md - this changes log.

### Modified

* (none — no source, infra, or doc files changed; Phase 0 gate not satisfied)

### Removed

* (none)

## Additional or Deviating Changes

* **Phase 0 BLOCKED — subscription still read-only.** `az account list --all --refresh` reports subscription `<AZURE_SUBSCRIPTION_ID>` in state `Warned` (improved from fully `Disabled`, but not `Enabled`). A cheap reversible write probe (`az tag update --operation merge` on `<RESOURCE_GROUP>`) returned HTTP `ReadOnlyDisabledSubscription` — writes are still denied.
  * Reason: the subscription's billing/account issue is not fully resolved; `Warned` does not permit writes here. No Phase 1+ work can run until the state is `Enabled` and a write probe succeeds.
  * No Azure mutation attempted beyond the read-only state check + the reversible (and rejected) write probe; the probe tag never landed.

## Release Summary

Run halted at the Phase 0 precondition. Zero files changed except this changes log. Resumption point: re-run Phase 0 (Step 0.1 state check + write probe) once the user has fully re-enabled subscription `<AZURE_SUBSCRIPTION_ID>` (Azure portal → Subscriptions → Reactivate / resolve billing). When the write probe succeeds, proceed to Phase 1 (clean `azd up` rebuild) → Phase 2 (live validation) → Phases 3–5 (drain, close-out docs, validation). All pre-staging from prior turns (cleared `AZURE_CONTAINER_REGISTRY_ENDPOINT`, purged soft-deleted Cognitive Services) remains valid.
