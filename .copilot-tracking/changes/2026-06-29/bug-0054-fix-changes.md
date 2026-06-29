<!-- markdownlint-disable-file -->
# Release Changes: BUG-0054 in-repo fix — blob_event always-ready + stale-doc reconciliation

**Related Plan**: bug-0054-fix-plan.instructions.md
**Implementation Date**: 2026-06-29

## Summary

Close the in-repo remainder of BUG-0054: add the `blob_event` queue trigger to the Flex
Consumption `alwaysReady` set (test-first, mirroring the BUG-0053 fix for `batch_push`) and
reconcile three documentation notes left stale by the already-landed `messageEncoding=none`
back-port. The cloud cutover (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` to
`event_grid`) and the dead `ingestion_job_id` cleanup remain deferred follow-on work.

## Changes

### Added

* (none)

### Modified

* v2/tests/infra/test_main_bicep.py - added `test_function_app_keeps_blob_event_always_ready` grep guard (test-first; failed against the unmodified bicep, then passed).
* v2/infra/main.bicep - added `{ name: 'function:blob_event', instanceCount: 1 }` to the Flex `functionAppConfig.scaleAndConcurrency.alwaysReady` set and updated the adjacent comment to cover both queue triggers.
* v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md - reworded the first `## Follow-ups` bullet: the BUG-0056 `messageEncoding=none` back-port has landed in `host.json` (authoritative on every deploy; no bicep app-setting parity needed).
* v2/docs/bugs.md - BUG-0056 durable back-port marked "done" (host.json carries the setting); BUG-0054 "To resume" updated to note the `function:blob_event` alwaysReady bicep entry has landed, leaving cloud-only deploy + flag-flip work.
* v2/src/backend/models/admin.py - (post-review WI-02 Option B, user-authorized) clarified the `ingestion_job_id` field description on `UploadResponse` + `IngestUrlResponse` to state the id is informational under `EVENT_GRID` (no enqueued push job to correlate to), aligning the models with ADR 0028 Consequences. Doc-only -- no wire, behavior, or test change.

### Removed

* (none)

## Additional or Deviating Changes

* Phase 1 validation: `uv run python -m pytest v2/tests/infra/test_main_bicep.py` → 1 failed first (test-first), then 34 passed after the bicep edit; `az bicep build --file v2/infra/main.bicep --stdout` compiled clean (exit 0).
* Phase 2 nuance (deviation from the plan's "remove the stale note" framing): `host.json` carries `messageEncoding=none` but `main.bicep` does NOT, and none is needed — the package-level `host.json` is authoritative, so the corrected notes say the back-port landed in host.json rather than implying a bicep parity gap.
* Final validation: `uv run python -m pytest v2/tests/infra/` → 38 passed.
* PD-01 (dead `ingestion_job_id` under `event_grid`) and the cloud cutover remain deferred follow-on (WI-01, WI-02 in the Planning Log); not touched inline.
* Post-review WI-02 (Option B), authorized by the user ("all rework that improve the code"): the mark-informational half landed as a doc-only field-description clarification on `UploadResponse` + `IngestUrlResponse`. Investigation confirmed the drop half (Option C) is a regression, not an improvement, because `ingestion_job_id` is live under the current `DIRECT_ENQUEUE` trigger (queue-message id + structured-log field), is a consistent 3-sibling wire contract, and is asserted by FE tests; the drop stays gated on the cloud cutover (WI-01). Validation: `uv run python -m pytest v2/tests/backend/test_admin.py v2/tests/backend/test_services_ingestion.py` → 159 passed.

## Release Summary

Four files changed, all in the in-repo scope of BUG-0054 (no cloud actions):

* Created: none.
* Modified (4):
  * v2/infra/main.bicep — `function:blob_event` added to the Flex `alwaysReady` set (prevents the BUG-0053 scale-from-zero loss on the `blob-events` queue trigger).
  * v2/tests/infra/test_main_bicep.py — new grep guard locking the `function:blob_event` always-ready entry in place (test-first).
  * v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md — Follow-ups bullet reconciled (host.json back-port landed).
  * v2/docs/bugs.md — BUG-0056 back-port marked done; BUG-0054 "To resume" trimmed to cloud-only work.
* Dependencies / infrastructure: no new packages, no Bicep modules added, no role assignments. One entry added to an existing Bicep array (not a structural change).
* Validation: infra tests 38/38 pass; `az bicep build` compiles clean.
* Deployment notes: this change ships on the next `azd provision` (bicep) / `azd deploy function` (host.json already carried the setting). BUG-0054 stays `open` — its cloud cutover (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` to `event_grid`) is deferred follow-on, gated on BUG-0058 cloud verification + the Flex remote-build timeout. No git staging/commit performed.
