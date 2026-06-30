---
applyTo: '.copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: BUG-0054 cloud cutover + ingestion-wiring deduplication

## Overview

Close BUG-0054 by cutting the cloud over to the Event Grid ingestion trigger and reconciling its remaining stale defect note (Scenario A), and independently remove the duplicated search-provider resolution and parser-key derivation that the same investigation surfaced (Scenario B), with the two tracks delivered as separate, decoupled phases.

## Objectives

### User Requirements

* Plan both the BUG-0054 close-out and the deduplication refactor as separate phases — Source: vscode_askQuestions answer "Both — A and B as separate phases" (2026-06-29).
* Approve and plan the two new shared modules the refactor needs — Source: vscode_askQuestions answer "Approve both new modules" (2026-06-29); satisfies Hard Rule #10 structural sign-off.
* "fix it improving the code and reducing duplicated code or bad implementation" — Source: original research request (conversation, 2026-06-29).

### Derived Objectives

* Add the missing infra regression-guard test pinning the Event Grid subscription destination to `blob-events` — Derived from: research found this is the exact regression that defined BUG-0054 and there is currently no test covering it (.copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md §5 "Coverage GAP").
* Keep Scenario A and Scenario B uncoupled — Derived from: the research Selected Approach, which closes the bug via ops/docs and treats the refactor as separable debt reduction (.copilot-tracking/research/2026-06-29/bug-0054-research.md "Selected Approach").
* Preserve every existing `_execute` monkeypatch seam so route-level tests stay green — Derived from: the consolidation design notes the seam tests sit above the helper (.copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md "Affected test files").

## Context Summary

### Prior completed work (not re-done here)

The earlier `bug-0054-fix` plan (.copilot-tracking/plans/2026-06-29/bug-0054-fix-plan.instructions.md) is fully implemented: it added the `function:blob_event` Flex `alwaysReady` entry (guarded by `test_function_app_keeps_blob_event_always_ready`) and reconciled the ADR 0028 / BUG-0056 `messageEncoding=none` notes plus the BUG-0054 "To resume" always-ready note. This plan covers the *remaining* close-out (cloud cutover) plus the newly-scoped deduplication refactor — it does not repeat the always-ready or messageEncoding work.

### Project Files

* v2/docs/bugs.md - BUG-0054 (open, infra, medium) detail block still lists "deploy blob_event" as pending; BUG-0080 (the 2026-06-24 deploy) and BUG-0058 (the cloud-verify gate) are the reconciling records.
* v2/src/functions/batch_push/blueprint.py - Site 1 of the duplicated search block (`_execute`, lines ~114-150); `_parser_key_for_filename` parser-key Site 1 (lines ~72-81).
* v2/src/functions/add_url/blueprint.py - Site 2 of the duplicated search block (`_execute`, lines ~113-145); `_parser_key_for_url` parser-key Site 2 (lines ~71-92).
* v2/src/functions/blob_event/blueprint.py - Site 3 of the duplicated search block (delete branch of `_execute`, lines ~120-148).
* v2/src/backend/app.py - Site 4 (lifespan); intentionally bespoke, OUT of scope (different pool source + disabled-search gate).
* v2/src/backend/services/ingestion.py - parser-key Sites 3 (`_blob_name_for_url`, line ~94) and 4 (`validate_upload`, line ~217).
* v2/src/functions/core/pgvector_pool.py - `PgVectorPool` lifecycle (`acquire()` / `aclose()`) the new helper composes.
* v2/src/backend/core/providers/search/base.py - `ensure_schema()` / `aclose()` contract the helper drives.
* v2/infra/main.bicep - Event Grid subscriptions (lines ~2402, ~2472) already target `blob-events`; `ingestionTrigger` param (line 100).
* v2/tests/infra/test_main_bicep.py - existing `test_function_app_keeps_blob_event_always_ready` (line 202); the new guard test lands next to it.

### References

* .copilot-tracking/research/2026-06-29/bug-0054-research.md - consolidated research deliverable (selected approach, scenarios, Hard-Rule audit).
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-history-adr.md - history + ADR trail.
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-code-analysis.md - duplication-site analysis.
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md - bicep / Event Grid / `ingestion_trigger` wiring + test gap.
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md - the helper design (signatures, home modules, teardown ownership, deploy reconciliation).
* v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md - trigger model, `AZURE_INGESTION_TRIGGER`, `blob-events` queue.

### Standards References

* .github/copilot-instructions.md - Hard Rules #1 (one unit/turn), #2 (test-first), #4 (registry dispatch), #10 (structural sign-off), #11 (StrEnum / no `Any` in plumbing / types-at-runtime), #14 (SDK boundary resilience), #15 (typed-model dict/struct returns), #16 (no process narrative in src), #17 (imports-at-top), #19 (durable worklog + bugs.md).
* .github/instructions/v2-functions-core.instructions.md - functions/core conventions for the new `search_resolution.py`.
* .github/instructions/v2-functions.instructions.md - blueprint conventions for the three call-site edits.
* .github/instructions/v2-tests.instructions.md - test-first contract + fixture conventions for the new unit tests.

## Implementation Checklist

### [x] Implementation Phase 1: Infra regression-guard test (non-structural)

<!-- parallelizable: true -->

* [x] Step 1.1: Add `test_blob_event_subscription_targets_blob_events_queue` to the bicep test
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 12-36)

### [x] Implementation Phase 2: Extract `parser_key_for_path` (structural — new module)

<!-- parallelizable: false -->

* [x] Step 2.1: Create `v2/src/backend/core/paths.py` with `parser_key_for_path` + its unit test
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 42-76)
* [x] Step 2.2: Repoint the four parser-key call sites to the shared helper
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 78-102)
* [x] Step 2.3: Validate phase changes
  * Run `uv run pytest v2/tests/backend/core/test_paths.py v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/backend/test_services_ingestion.py`

### [x] Implementation Phase 3: Extract `resolve_search_provider` (structural — new module)

<!-- parallelizable: false -->

* [x] Step 3.1: Create `v2/src/functions/core/search_resolution.py` (`ResolvedSearch` + `resolve_search_provider`) + its unit test
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 113-180)
* [x] Step 3.2: Repoint the three function-blueprint `_execute` bodies to the shared helper
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 182-218)
* [x] Step 3.3: Validate phase changes
  * Run `uv run pytest v2/tests/functions/core/test_search_resolution.py v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/functions/blob_event/test_blueprint.py`

### [ ] Implementation Phase 4: BUG-0054 cloud cutover + docs reconcile (ops, gated on BUG-0058)

<!-- parallelizable: false -->

* [x] Step 4.1: Reconcile the stale BUG-0054 detail block in `v2/docs/bugs.md`
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 229-248)
  * Done: detail block (L973-991) + summary row (L113) both reconciled to the 2026-06-24 deploy; BUG-0054 stays `open`.
* [ ] Step 4.2: Flip the trigger flag and re-provision (operator-driven) — BLOCKED (gated on an authenticated `azd` session + a clean BUG-0058 deploy state; not agent-doable)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 250-274)
* [ ] Step 4.3: Cloud end-to-end re-validation (the BUG-0058 gate) + poison drain + close — BLOCKED (operator-driven; gated on Step 4.2)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 276-298)

### [x] Implementation Phase 5: Validation

<!-- parallelizable: false -->

* [x] Step 5.1: Run full backend + functions + infra + shared test suites
  * Run `uv run pytest v2/tests/backend v2/tests/functions v2/tests/infra v2/tests/shared`
  * Result: 2514 passed, 1 skipped (pre-existing, unrelated).
* [x] Step 5.2: Run the type gate on touched trees
  * Run `uv run pyright` for `v2/src/backend/**` + `v2/src/functions/core/**` (must stay `0 errors / 0 warnings / 0 information`)
  * Result: 0 errors / 0 warnings / 0 information.
* [x] Step 5.3: Fix minor validation issues; report blocking issues
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md (Lines 312-322)
  * Result: no fixes needed; both gates green on first run.

## Planning Log

See .copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md for discrepancy tracking, the Hard Rule #10 structural sign-off record, implementation paths considered, and suggested follow-on work.

## Dependencies

* `uv` (v2 Python toolchain; `uv run pytest`, `uv run pyright`).
* `azd` CLI + an authenticated Azure session (Phase 4 only; operator-driven).
* A clean BUG-0058 function deploy (Phase 4 gate) — the prepackage workaround is `uv run python v2/scripts/prepackage_function.py` before `azd deploy function`, or the 2026-06-24 `func ... publish --no-build --python` path against the locked storage account.

## Success Criteria

* The new bicep guard test fails if either Event Grid subscription's `queueName` regresses from `blob-events` — Traces to: research test gap (.copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md §5).
* `parser_key_for_path` is defined once in `v2/src/backend/core/paths.py` and all four prior derivation sites call it — Traces to: User Requirement "reducing duplicated code".
* `resolve_search_provider` is defined once in `v2/src/functions/core/search_resolution.py` and all three function-blueprint `_execute` bodies call it; `backend/app.py` is unchanged — Traces to: User Requirement "reducing duplicated code" + consolidation design 3+1 split.
* Every existing route-level `_execute` seam test and the backend lifespan test stay green — Traces to: Derived Objective "preserve seams".
* The BUG-0054 detail block in `v2/docs/bugs.md` no longer lists "deploy blob_event" as pending and reflects the 2026-06-24 deploy — Traces to: research deploy-state reconciliation (.copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md Task A).
* BUG-0054 reaches `fixed` only after the cloud E2E re-validation (create + delete) passes and the 4 historical poison messages are drained — Traces to: research ordered close-out steps (gated on BUG-0058).
