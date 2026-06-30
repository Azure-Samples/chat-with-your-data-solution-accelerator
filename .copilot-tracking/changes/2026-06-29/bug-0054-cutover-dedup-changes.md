<!-- markdownlint-disable-file -->
# Release Changes: BUG-0054 cloud cutover + ingestion-wiring deduplication

**Related Plan**: bug-0054-cutover-dedup-plan.instructions.md
**Implementation Date**: 2026-06-29

## Summary

Closing BUG-0054 via the Event Grid cloud cutover + stale-note reconciliation (Scenario A), and independently removing the duplicated search-provider resolution and parser-key derivation surfaced by the same investigation (Scenario B), delivered as separate decoupled phases. Two new shared modules carry a recorded Hard Rule #10 sign-off.

## Changes

### Added

* v2/src/backend/core/paths.py - new Stable Core leaf module homing `parser_key_for_path(name) -> str` (lowercase, dotless extension of a POSIX-style path/filename); single source of truth for the previously-duplicated extension-derivation expression (Phase 2).
* v2/tests/backend/core/test_paths.py - test-first unit test for `parser_key_for_path` (cases: `report.PDF`->`pdf`, `a/b/file.txt`->`txt`, `article`->`""`, `name.`->`""`, `archive.tar.gz`->`gz`) (Phase 2).

### Modified

* v2/tests/infra/test_main_bicep.py - added `test_blob_event_subscription_targets_blob_events_queue` (Phase 1), pinning the Event Grid blob subscription destination to `queueName: blobEventsQueueName` and both `Microsoft.Storage.BlobCreated` / `Microsoft.Storage.BlobDeleted` event types; closes the BUG-0054 regression-guard gap (DR-01). 35 passed.
* v2/src/functions/batch_push/blueprint.py - `_parser_key_for_filename` reduced to a 1-line delegator (`return parser_key_for_path(filename)`); dropped now-dead `from pathlib import PurePosixPath`; added top import of the shared helper (Phase 2).
* v2/src/functions/add_url/blueprint.py - `_parser_key_for_url` now derives via `parser_key_for_path(urlparse(url).path)` with the existing `or _DEFAULT_PARSER_KEY` fallback preserved; dropped dead `PurePosixPath` import (Phase 2).
* v2/src/backend/services/ingestion.py - `_blob_name_for_url` (registered-parser membership branch) and `validate_upload` (415 gate) now derive the extension via `parser_key_for_path`; dropped dead `PurePosixPath` import; surrounding fallback/gate logic unchanged (Phase 2).

### Removed

* (pending)

## Additional or Deviating Changes

* Phase 1 validation: `uv run pytest` failed with the local trampoline error "failed to canonicalize script path"; the implementor fell back to `.venv\Scripts\python.exe -m pytest`, which passed (35/35). Environment quirk, not a code issue — carried forward as the validation fallback for later phases.
* Phase 2 Phase-header deviation: the details file specified `Phase: 7` for the new `paths.py` docstring header; implemented as `Phase: 6 (Functions blueprints / modular RAG indexing pipeline)` for consistency with the sibling Phase-3 module `functions/core/search_resolution.py` (both created in the same Phase 6 dedup effort). Recorded as DE-02 in the planning log.
* Phase 2: the two Functions-side helpers (`_parser_key_for_filename`, `_parser_key_for_url`) were kept as 1-line delegators rather than removed — both are imported + called by their own blueprint tests, so deleting them would break test contracts (cleanup-before-next-step: only remove symbols with zero non-test callers).

## Release Summary

(pending — written after the final phase)
