<!-- markdownlint-disable-file -->
# RPI Validation: BUG-0054 in-repo fix — Phase 1 (blob_event always-ready, test-first)

**Validation date**: 2026-06-29
**Phase under validation**: Phase 1 — blob_event always-ready (test-first) — steps 1.1, 1.2, 1.3
**Status**: **VERIFIED (Passed)**

## Inputs

| Artifact | Path |
|----------|------|
| Implementation Plan | [.copilot-tracking/plans/2026-06-29/bug-0054-fix-plan.instructions.md](../../../plans/2026-06-29/bug-0054-fix-plan.instructions.md) |
| Implementation Details | [.copilot-tracking/details/2026-06-29/bug-0054-fix-details.md](../../../details/2026-06-29/bug-0054-fix-details.md) |
| Changes Log | [.copilot-tracking/changes/2026-06-29/bug-0054-fix-changes.md](../../../changes/2026-06-29/bug-0054-fix-changes.md) |
| Research Document | [.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md](../../../research/2026-06-29/bug-0054-fix-research.md) |
| Planning Log | [.copilot-tracking/plans/logs/2026-06-29/bug-0054-fix-log.md](../../../plans/logs/2026-06-29/bug-0054-fix-log.md) |

## Executive summary

Phase 1 is fully implemented and the Changes Log accurately reflects the repository state. All
three expected outcomes are verified against the live files:

1. The grep guard `test_function_app_keeps_blob_event_always_ready` exists and asserts
   `'function:blob_event'` is present in the bicep text.
2. The `{ name: 'function:blob_event', instanceCount: 1 }` entry is present in
   `functionAppConfig.scaleAndConcurrency.alwaysReady` next to `function:batch_push`, and the
   adjacent comment now names both queue triggers.
3. Step 1.3 validation ran; re-running the suite during this review yields **34 passed**, exactly
   matching the Changes Log claim.

All Phase 1 plan checkboxes are marked `[x]`. The change matches research **Gap 1** and the
**Selected approach step 1** verbatim. **No critical or major findings.** One minor informational
note (test-first "failing-first" state is verified by design + documented, not independently
re-reproduced under the read-only protocol).

## Per-step evidence

### Step 1.1 — failing grep guard for `function:blob_event` — VERIFIED

- **Plan claim**: add `test_function_app_keeps_blob_event_always_ready(bicep_text)` asserting
  `"'function:blob_event'"` in `bicep_text` (test-first; fails against unmodified bicep).
- **Evidence**: [v2/tests/infra/test_main_bicep.py](../../../../v2/tests/infra/test_main_bicep.py#L202-L217)
  — function `test_function_app_keeps_blob_event_always_ready(bicep_text: str)` with assertion
  `assert "'function:blob_event'" in bicep_text` at
  [line 212](../../../../v2/tests/infra/test_main_bicep.py#L212).
- **Pattern conformance**: uses the module `bicep_text` fixture and a substring assert, matching
  the existing grep-guard style; no Bicep CLI dependency. The details file explicitly permitted
  `bicep_text` **or** `function_app_slice`; the broader `bicep_text` choice is within spec.
- **Docstring**: states what the code is (always-ready instance prevents Flex scale-from-zero loss
  on `blob-events`); no unit IDs / phase narrative. (Note: `v2/tests/**` is outside the
  `test_no_process_narrative_in_src.py` gate scope, which walks `v2/src/` only.)
- **Result**: matches the Changes Log "Modified" entry. ✔

### Step 1.2 — bicep `alwaysReady` entry — VERIFIED

- **Plan claim**: add `{ name: 'function:blob_event', instanceCount: 1 }` next to
  `function:batch_push`; update the adjacent comment to cover both queue triggers; content edit
  (not structural, Hard Rule #10).
- **Evidence**: [v2/infra/main.bicep](../../../../v2/infra/main.bicep#L2229-L2241):
  - Comment at [line 2229](../../../../v2/infra/main.bicep#L2229):
    `// Keep the batch_push + blob_event queue triggers warm (avoid Flex scale-from-zero cold-start on the first queued message).`
  - `function:batch_push` entry at [lines 2232-2235](../../../../v2/infra/main.bicep#L2232-L2235).
  - `function:blob_event` entry at [lines 2236-2239](../../../../v2/infra/main.bicep#L2236-L2239).
- **camelCase / no new variable**: confirmed — reuses existing `name` / `instanceCount` literal
  fields, no hoisted variable for a single literal.
- **Line drift**: the research/plan cited `alwaysReady ≈ 2229-2234`; the array now spans ~2230-2241
  (+6 lines from the added entry). Expected and consistent — not a discrepancy.
- **Result**: matches the Changes Log "Modified" entry and research Gap 1. ✔

### Step 1.3 — validation run — VERIFIED

- **Plan claim**: run `uv run pytest v2/tests/infra/test_main_bicep.py` and (optionally)
  `az bicep build --file v2/infra/main.bicep --stdout`.
- **Changes Log claim**: `1 failed first (test-first), then 34 passed`; `az bicep build` exit 0;
  final `uv run pytest v2/tests/infra/` → 38 passed.
- **Independent re-run (this review)**: `uv run python -m pytest tests/infra/test_main_bicep.py -q`
  → **34 passed in 0.04s**. Matches the post-edit count exactly.
- **Result**: green state confirmed. ✔

## Plan checkbox audit

| Item | Marked | Verified |
|------|--------|----------|
| `### [x] Implementation Phase 1: blob_event always-ready (test-first)` | `[x]` | ✔ |
| `[x] Step 1.1: Add a failing grep guard` | `[x]` | ✔ |
| `[x] Step 1.2: Add the function:blob_event entry` | `[x]` | ✔ |
| `[x] Step 1.3: Validate phase changes` | `[x]` | ✔ |

All Phase 1 checkboxes are marked `[x]` and substantiated by repository evidence.

## Consistency with research

- **Research Gap 1** ("`blob_event` missing from Flex `alwaysReady`"): closed — the entry is
  present and test-guarded. ✔
- **Research Selected approach step 1** ("Add `{ name: 'function:blob_event', instanceCount: 1 }`
  to the bicep `alwaysReady` array, guarded by a new `test_main_bicep.py` grep test (test-first)"):
  implemented verbatim. ✔
- **Hard Rule #2 (test-first)**: honored — guard asserts on a string that exists only after the
  Step 1.2 edit, so the failing-first state is structurally guaranteed and is documented in the
  Changes Log. ✔
- **Hard Rule #10 (structure)**: honored — a single array-element addition, correctly treated as a
  content edit, no confirmation gate. ✔

## Findings by severity

### Critical

- None.

### Major

- None.

### Minor

- **MIN-01 (informational)**: The test-first "failing-first" state could not be *independently
  re-reproduced* during this review because doing so would require reverting
  `v2/infra/main.bicep`, which the read-only validation protocol forbids. It is nonetheless
  verified by design (the assertion targets a substring introduced solely by Step 1.2) and is
  documented in the Changes Log (`1 failed first … then 34 passed`). No action required.

## Coverage assessment

Phase 1 coverage is **complete**. Every plan item (1.1, 1.2, 1.3), every Phase 1 success criterion
in the plan, and the two relevant research anchors (Gap 1, Selected approach step 1) are satisfied
by verified repository state. The Changes Log contains no Phase 1 claim that the repository
contradicts. Deferred items (PD-01 / WI-01 / WI-02) are explicitly out of Phase 1 scope and
correctly recorded in the Planning Log; they are not Phase 1 gaps.

## Recommended next validations (not performed this session)

- [ ] Phase 2 — stale-doc reconciliation (steps 2.1–2.3): ADR 0028 Follow-ups bullet, bugs.md
      BUG-0056 back-port note, bugs.md BUG-0054 "To resume" note.
- [ ] Phase N — full infra validation (`uv run pytest v2/tests/infra/` → claimed 38 passed) and
      `az bicep build` clean compile, plus confirmation that WI-01/WI-02/PD-01 follow-on items are
      logged and untouched inline.
- [ ] Cross-check that no removed/deferred item (Gap 3 `ingestion_job_id`) was changed inline in
      `v2/src/backend/services/ingestion.py`.

## Clarifying questions

- None. The artifacts and repository state are internally consistent for Phase 1.
