---
applyTo: '.copilot-tracking/changes/2026-06-29/bug-0054-fix-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: BUG-0054 in-repo fix — blob_event always-ready + stale-doc reconciliation

## Overview

Close the in-repo remainder of BUG-0054 by adding the `blob_event` queue trigger to the Flex
`alwaysReady` set (test-first) and reconciling three stale documentation notes, while deferring
the dead `ingestion_job_id` cleanup and the cloud cutover as follow-on work gated on BUG-0058.

## Objectives

### User Requirements

* Review BUG-0054, inspect the code, and check for code debt / inconsistency before fixing —
  Source: conversation ("review what is the problem, check the code and see if we have any code
  debt or any code inconsistency before we fix it").
* Fix the open bugs in numerical order, BUG-0054 first — Source: conversation ("sort them in
  numerical order and we will solve them in that order").
* Produce an actionable implementation plan for the fix — Source: conversation (`task-plan`
  prompt invocation, Task Planner mode).

### Derived Objectives

* Eliminate the Flex scale-from-zero risk on `blob_event` — Derived from: `blob_event` is a
  queue trigger and BUG-0053 proved scale-from-zero loses queue-trigger work; only `batch_push`
  currently has an always-ready instance (`v2/infra/main.bicep` ≈ 2229-2234).
* Land the bicep change test-first — Derived from: Hard Rule #2 and the existing grep-style guard
  suite `v2/tests/infra/test_main_bicep.py`.
* Remove documentation drift that contradicts shipped code — Derived from: ADR 0028 Follow-ups +
  bugs.md BUG-0056 both claim the `messageEncoding=none` back-port is pending, but
  `v2/src/functions/host.json` already carries it.
* Keep the cloud cutover out of scope — Derived from: full cloud closure depends on BUG-0058
  (#3 in the queue) and the parked Flex remote-build timeout; sequencing it here would block #1
  on #3.

## Context Summary

### Project Files

* `v2/infra/main.bicep` - `functionAppConfig.scaleAndConcurrency.alwaysReady` (≈ 2229-2234)
  lists only `function:batch_push`; needs a `function:blob_event` entry.
* `v2/tests/infra/test_main_bicep.py` - grep-style infra guards (module fixture `bicep_text`,
  `function_app_slice` fixture); no `alwaysReady` assertion exists yet.
* `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md` - `## Follow-ups` first bullet
  is stale (claims `messageEncoding=none` not in host.json/bicep).
* `v2/docs/bugs.md` - BUG-0054 "To resume" (≈ 987) and BUG-0056 durable-back-port note (≈ 1019)
  are stale relative to shipped code.
* `v2/src/functions/host.json` - already carries `extensions.queues.messageEncoding = "none"`
  (evidence the doc notes are stale).
* `v2/src/backend/services/ingestion.py` - `upload_document` (≈ 253-355) mints + returns a dead
  `ingestion_job_id` under `event_grid` (Gap 3, deferred).

### References

* `.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md` - full review findings,
  verified evidence, dependency-order analysis.
* `v2/docs/bugs.md` BUG-0053 - the scale-from-zero precedent and fix that `blob_event` must
  inherit.

### Standards References

* `.github/copilot-instructions.md` - Hard Rule #2 (test-first), #10 (structure confirmation),
  #12 (defect vs debt), #16 (no process narrative in code), #19 (durable file tracking).
* `.github/instructions/v2-infra.instructions.md` - Bicep + azd conventions for `v2/infra/**`.

## Implementation Checklist

### [x] Implementation Phase 1: blob_event always-ready (test-first)

<!-- parallelizable: false -->

* [x] Step 1.1: Add a failing grep guard for `function:blob_event` in `alwaysReady`
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-fix-details.md (Lines 12-38)
* [x] Step 1.2: Add the `function:blob_event` entry to the bicep `alwaysReady` array
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-fix-details.md (Lines 40-66)
* [x] Step 1.3: Validate phase changes
  * Run `uv run pytest v2/tests/infra/test_main_bicep.py`
  * Run `az bicep build --file v2/infra/main.bicep --stdout` if the Bicep CLI is available

### [x] Implementation Phase 2: stale-doc reconciliation

<!-- parallelizable: true -->

* [x] Step 2.1: Correct the ADR 0028 `## Follow-ups` messageEncoding bullet
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-fix-details.md (Lines 70-90)
* [x] Step 2.2: Correct the bugs.md BUG-0056 durable-back-port note (≈ 1019)
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-fix-details.md (Lines 92-110)
* [x] Step 2.3: Update the bugs.md BUG-0054 "To resume" note (≈ 987) to reflect the landed
  always-ready entry and the remaining cloud-only steps
  * Details: .copilot-tracking/details/2026-06-29/bug-0054-fix-details.md (Lines 112-132)

### [x] Implementation Phase N: Validation

<!-- parallelizable: false -->

* [x] Step N.1: Run full infra validation
  * `uv run pytest v2/tests/infra/`
  * `az bicep build --file v2/infra/main.bicep --stdout` (if Bicep CLI present)
* [x] Step N.2: Fix minor validation issues
  * Iterate on any grep-guard / bicep-build failures introduced by Phase 1
* [x] Step N.3: Report blocking issues + record follow-on
  * Confirm the cloud cutover (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` to
    `event_grid`) and the Gap-3 `ingestion_job_id` decision remain logged as follow-on work
    in the Planning Log; do not attempt them inline.

## Planning Log

See `.copilot-tracking/plans/logs/2026-06-29/bug-0054-fix-log.md` for discrepancy tracking,
implementation paths considered, the open decision point (PD-01), and suggested follow-on work.

## Dependencies

* `uv` (Python test runner) — `uv run pytest`.
* Azure Bicep CLI (`az bicep`) — optional; the grep guard does not require it, full validation
  prefers it.

## Success Criteria

* `v2/infra/main.bicep` `alwaysReady` includes a `function:blob_event` instance — Traces to:
  research Gap 1 + BUG-0054 "To resume".
* `v2/tests/infra/test_main_bicep.py` asserts the `function:blob_event` always-ready entry and
  passes — Traces to: Hard Rule #2 + research selected approach step 1.
* ADR 0028 Follow-ups and bugs.md (BUG-0056, BUG-0054) no longer claim the `messageEncoding=none`
  back-port is pending — Traces to: research Gap 2.
* The dead `ingestion_job_id` (Gap 3) and the cloud cutover are recorded as follow-on, not
  changed inline — Traces to: research dependency-order finding + `dont-restructure-working-code`.
