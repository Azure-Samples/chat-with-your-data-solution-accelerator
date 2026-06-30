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
* v2/src/functions/core/search_resolution.py - new Stable Core leaf module homing the frozen `ResolvedSearch` struct (`provider: BaseSearch`, `pool_helper: PgVectorPool | None`) + `async resolve_search_provider(*, settings, credential)`; registry-keys on `settings.database.index_store`, stands up the pgvector pool on that path, runs `ensure_schema()` once, and closes any partially-opened resources before re-raising on failure (Hard Rule #14). Single source of truth for the three function blueprints' search-provider resolution (Phase 3).
* v2/tests/functions/core/test_search_resolution.py - test-first unit test covering the AzureSearch path (`pool_helper is None`, `ensure_schema` once) and the pgvector path (pool constructed + acquired, `pool` kwarg wired, `pool_helper` returned) (Phase 3).

### Modified

* v2/tests/infra/test_main_bicep.py - added `test_blob_event_subscription_targets_blob_events_queue` (Phase 1), pinning the Event Grid blob subscription destination to `blobEventsQueueName` and both `Microsoft.Storage.BlobCreated` / `Microsoft.Storage.BlobDeleted` event types; closes the BUG-0054 regression-guard gap (DR-01). Review-rework (2026-06-29): tightened the single whole-file membership assert into `bicep_text.count("queueName: blobEventsQueueName") == 2` plus a scoped negative `"queueName: docProcessingQueueName" not in bicep_text`, so the guard now fails on a *single*-subscription repoint (the exact BUG-0054 vector) — resolving review findings DR-A (Major) and DR-C (Minor). 35 passed; an in-memory mutation simulation confirms both new asserts fire on a one-subscription regression.
* v2/src/functions/batch_push/blueprint.py - `_parser_key_for_filename` reduced to a 1-line delegator (`return parser_key_for_path(filename)`); dropped now-dead `from pathlib import PurePosixPath`; added top import of the shared helper (Phase 2).
* v2/src/functions/add_url/blueprint.py - `_parser_key_for_url` now derives via `parser_key_for_path(urlparse(url).path)` with the existing `or _DEFAULT_PARSER_KEY` fallback preserved; dropped dead `PurePosixPath` import (Phase 2).
* v2/src/backend/services/ingestion.py - `_blob_name_for_url` (registered-parser membership branch) and `validate_upload` (415 gate) now derive the extension via `parser_key_for_path`; dropped dead `PurePosixPath` import; surrounding fallback/gate logic unchanged (Phase 2).
* v2/src/functions/batch_push/blueprint.py - `_execute` search/pgvector/ensure_schema/finally block replaced with `resolve_search_provider(...)` + caller-owned teardown; embedder construction and its outer `finally` and the `ContainerClient` async-with preserved; dead `IndexStore` / `PgVectorPool` / `Any` imports dropped (Phase 3).
* v2/src/functions/add_url/blueprint.py - `_execute` search block replaced with `resolve_search_provider(...)`; `add_url_handler(..., resolved.provider)` call + embedder preserved (Phase 3).
* v2/src/functions/blob_event/blueprint.py - `_execute` DELETE branch repointed to `resolve_search_provider(...)` + `handle_blob_deleted(event.ref, resolved.provider)`; CREATE branch (QueueClient enqueue) left untouched (Phase 3).
* v2/tests/functions/add_url/test_blueprint.py - Phase 3 blueprint test updated for the shared `resolve_search_provider` seam (patches/asserts the helper in place of the removed inline search/pgvector/ensure_schema block). Previously omitted from this log; added during review-rework (CL-INVENTORY).
* v2/tests/functions/batch_push/test_blueprint.py - Phase 3 blueprint test updated for the shared `resolve_search_provider` seam. Previously omitted from this log; added during review-rework (CL-INVENTORY).
* v2/tests/functions/blob_event/test_blueprint.py - Phase 3 blueprint test updated for the shared `resolve_search_provider` seam (delete-branch). Previously omitted from this log; added during review-rework (CL-INVENTORY).
* v2/docs/bugs.md - BUG-0054 reconciliation (Phase 4 Step 4.1): both the detail block (L973-991) and the summary row (L113) updated to record that `blob_event` was deployed to the cloud Function App on 2026-06-24 (BUG-0080, 5 -> 6 functions); remaining work restated as the four operator close-out steps (flip `AZURE_ENV_INGESTION_TRIGGER`->`event_grid` + `azd provision`; verify the live Event Grid subscription targets `blob-events`; cloud create+delete re-validation — the BUG-0058 gate; drain the 4 historical `doc-processing-poison` messages). BUG-0054 Status stays `open`; placeholders per Hard Rule #18.

### Removed

* (pending)

## Additional or Deviating Changes

* Phase 1 validation: `uv run pytest` failed with the local trampoline error "failed to canonicalize script path"; the implementor fell back to `.venv\Scripts\python.exe -m pytest`, which passed (35/35). Environment quirk, not a code issue — carried forward as the validation fallback for later phases.
* Phase 2 Phase-header deviation: the details file specified `Phase: 7` for the new `paths.py` docstring header; implemented as `Phase: 6 (Functions blueprints / modular RAG indexing pipeline)` for consistency with the sibling Phase-3 module `functions/core/search_resolution.py` (both created in the same Phase 6 dedup effort). Recorded as DE-02 in the planning log.
* Phase 2: the two Functions-side helpers (`_parser_key_for_filename`, `_parser_key_for_url`) were kept as 1-line delegators rather than removed — both are imported + called by their own blueprint tests, so deleting them would break test contracts (cleanup-before-next-step: only remove symbols with zero non-test callers).
* Phase 3 reconciliation: the verbatim details snippet had a bare resolve-then-return body; the implementor wrapped pool-acquire + provider-construct + `ensure_schema` in `try/except BaseException` that closes any already-opened provider/pool before re-raising. This preserves the close-on-failure contract the existing blueprint tests assert and satisfies Hard Rule #14 (no asyncpg pool / SDK client leak on a mid-resolution failure). Recorded as DE-03 in the planning log.
* Review-rework (2026-06-29, post-`/task-review`): the review surfaced two test-only / doc-only findings, both addressed in this turn with no production-code or structural change. (a) DR-A (Major) + DR-C (Minor) \u2014 the Phase 1 guard used a single whole-file substring membership assert, which catches a *total* regression but not the original BUG-0054 single-subscription repoint; tightened to a `count == 2` pin plus a scoped negative assert (see the `test_main_bicep.py` Modified entry). (b) CL-INVENTORY (Minor) + DR-B (Minor) \u2014 this Changes Log under-counted the modified set (omitted the three Phase-3 `test_blueprint.py` files and labelled 8 modified files as 5) and overstated the guard's coverage; both reconciled above. The DR-B coverage claim is now accurate because the guard was tightened to actually back it.

## Release Summary

**Phases 1, 2, 3, 5 complete and green; Phase 4 in-repo portion (Step 4.1) complete, operator steps (4.2/4.3) blocked.**

Scenario B (deduplication refactor) is fully landed and validated. Scenario A (cloud cutover) is reconciled in the docs and now waits only on an operator-driven, gated cloud cutover.

* **Files affected: 12** (4 added, 8 modified, 0 removed). Span covers commit `4c2bf280` (Phase 1 + Phase 2) plus the working tree (Phase 3 + Phase 4 Step 4.1 + review-rework).
  * Added (4): `v2/src/backend/core/paths.py`, `v2/tests/backend/core/test_paths.py`, `v2/src/functions/core/search_resolution.py`, `v2/tests/functions/core/test_search_resolution.py`.
  * Modified (8): `v2/tests/infra/test_main_bicep.py` (Phase 1 guard test + review-rework tightening), `v2/src/functions/batch_push/blueprint.py`, `v2/src/functions/add_url/blueprint.py`, `v2/src/backend/services/ingestion.py` (Phase 2 parser-key repoints + Phase 3 search-resolution repoint for batch_push/add_url), `v2/src/functions/blob_event/blueprint.py` (Phase 3 delete-branch repoint), `v2/tests/functions/add_url/test_blueprint.py`, `v2/tests/functions/batch_push/test_blueprint.py`, `v2/tests/functions/blob_event/test_blueprint.py` (Phase 3 blueprint tests repointed to the shared `resolve_search_provider` seam), `v2/docs/bugs.md` (Phase 4 Step 4.1 BUG-0054 reconciliation).
* **Duplication removed:** one `parser_key_for_path` helper now replaces four copies of the `PurePosixPath(...).suffix.lstrip(".").lower()` derivation; one `resolve_search_provider` helper now replaces three copies of the inline search/pgvector/ensure_schema/finally block across the function blueprints. `backend/app.py` (Site 4) stays intentionally bespoke.
* **Regression guard added:** `test_blob_event_subscription_targets_blob_events_queue` fails if *either* Event Grid subscription regresses off the `blob-events` queue (closes the BUG-0054 gap). Backed by `count("queueName: blobEventsQueueName") == 2` (both subscriptions pinned) plus the scoped negative `"queueName: docProcessingQueueName" not in bicep_text` — the whole-file membership assert that originally only caught a *total* regression (review finding DR-A) was tightened during review-rework so a single-subscription repoint now fails the guard.
* **Dependency / infra changes:** none (no new package, no new top-level folder; two new leaf modules under already-enumerated packages, both with recorded Hard Rule #10 sign-off).
* **Validation:** full sweep `2514 passed, 1 skipped` (the skip + 31 warnings are pre-existing and unrelated); pyright `0 errors / 0 warnings / 0 information` on `src/backend` + `src/functions/core`.
* **Deployment / close-out notes:** BUG-0054 remains `open`. The remaining close-out is operator-driven and gated on a clean BUG-0058 deploy state + an authenticated `azd` session: (1) `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision`; (2) verify the live Event Grid subscription targets `blob-events`; (3) cloud create+delete E2E (the BUG-0058 gate); (4) drain the 4 historical `doc-processing-poison` messages; then flip BUG-0054 -> `fixed` + worklog entry. Plan Steps 4.2/4.3 hold these.
