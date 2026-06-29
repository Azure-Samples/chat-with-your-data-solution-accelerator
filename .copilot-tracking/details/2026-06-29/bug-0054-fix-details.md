<!-- markdownlint-disable-file -->
# Implementation Details: BUG-0054 in-repo fix — blob_event always-ready + stale-doc reconciliation

## Context Reference

Sources: `.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md` (review findings,
verified evidence, dependency-order analysis); `v2/docs/bugs.md` (BUG-0054, BUG-0053, BUG-0056);
`v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md`.

## Implementation Phase 1: blob_event always-ready (test-first)

<!-- parallelizable: false -->

### Step 1.1: Add a failing grep guard for `function:blob_event` in `alwaysReady`

Add a new grep-style test in `v2/tests/infra/test_main_bicep.py` that asserts the bicep
`alwaysReady` set keeps an always-ready instance for `function:blob_event`. Mirror the existing
guard style: a `def test_function_app_keeps_blob_event_always_ready(bicep_text: str) -> None:`
that asserts `"'function:blob_event'"` is present in `bicep_text` (or in the `function_app_slice`
fixture if that fixture cleanly bounds the `scaleAndConcurrency` block). Give it a docstring that
states *what the code is* (an always-ready instance prevents Flex scale-from-zero loss on the
`blob-events` queue trigger) — no unit IDs, no phase narrative (Hard Rule #16). Run it once to
confirm it FAILS against the current bicep (the entry does not exist yet).

Files:
* `v2/tests/infra/test_main_bicep.py` - add the new grep guard alongside
  `test_function_app_settings_bind_required_phase4_settings` (≈ line 199), reusing the module
  `bicep_text` fixture (≈ 28-30) or `function_app_slice` fixture.

Discrepancy references:
* Addresses research Gap 1 (real, mergeable infra gap).

Success criteria:
* The new test exists and FAILS against the unmodified `v2/infra/main.bicep`.
* The test follows the existing grep-guard pattern (module fixture, substring assert, no Bicep
  CLI requirement).

Context references:
* `v2/tests/infra/test_main_bicep.py` (Lines 23-30) - `_BICEP` path + `bicep_text` fixture.
* `v2/tests/infra/test_main_bicep.py` (Lines 185-199) - `function_app_slice`-based guard pattern.

Dependencies:
* None.

### Step 1.2: Add the `function:blob_event` entry to the bicep `alwaysReady` array

In `v2/infra/main.bicep`, extend the `functionAppConfig.scaleAndConcurrency.alwaysReady` array
(≈ lines 2229-2234) to add a second entry for `function:blob_event` next to the existing
`function:batch_push` entry:

```bicep
alwaysReady: [
  {
    name: 'function:batch_push'
    instanceCount: 1
  }
  {
    name: 'function:blob_event'
    instanceCount: 1
  }
]
```

Use `camelCase` field names already present; do not introduce a new variable for a single
literal. This is a content edit to an existing array — not a structural change (Hard Rule #10),
so no user confirmation gate. Re-run the Step 1.1 test; it must now PASS.

Files:
* `v2/infra/main.bicep` - `alwaysReady` array under `functionAppConfig.scaleAndConcurrency`
  (≈ 2229-2234).

Discrepancy references:
* Addresses research Gap 1; satisfies the BUG-0054 "To resume" always-ready step.

Success criteria:
* `alwaysReady` contains both `function:batch_push` and `function:blob_event`, each
  `instanceCount: 1`.
* The Step 1.1 grep guard now passes.

Context references:
* `.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md` (Gap 1) - the exact target
  block + rationale.
* `v2/docs/bugs.md` - BUG-0053 (the scale-from-zero precedent `blob_event` inherits).

Dependencies:
* Step 1.1 completion (test exists and fails first).

### Step 1.3: Validate phase changes

Run the infra guard suite and, when available, the Bicep compiler.

Validation commands:
* `uv run pytest v2/tests/infra/test_main_bicep.py` - the new guard plus all existing guards pass.
* `az bicep build --file v2/infra/main.bicep --stdout` - `main.bicep` still compiles (skip if the
  Bicep CLI is not installed; note the skip in the changes file).

## Implementation Phase 2: stale-doc reconciliation

<!-- parallelizable: true -->

### Step 2.1: Correct the ADR 0028 `## Follow-ups` messageEncoding bullet

In `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md`, locate the `## Follow-ups`
section's first bullet (the `BUG-0056` encoding back-port) which states the
`AzureFunctionsJobHost__extensions__queues__messageEncoding = none` setting is "still not in
`host.json` / bicep". Rewrite it to reflect that `host.json` now carries
`extensions.queues.messageEncoding = "none"` (the back-port has landed), leaving only any
bicep app-setting parity note if one genuinely remains. Keep the placeholder convention for any
env values (Hard Rule #18).

Files:
* `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md` - `## Follow-ups`, first bullet.

Discrepancy references:
* Addresses research Gap 2.

Success criteria:
* The ADR no longer claims `messageEncoding=none` is absent from `host.json`.

Context references:
* `v2/src/functions/host.json` - confirms `extensions.queues.messageEncoding = "none"` present.

Dependencies:
* None (doc-only; independent of Phase 1 files).

### Step 2.2: Correct the bugs.md BUG-0056 durable-back-port note (≈ 1019)

In `v2/docs/bugs.md`, update the BUG-0056 entry's durable-back-port line (≈ line 1019) that says
the host setting still needs adding to `host.json` (bicep edits paused). Reflect that the
back-port has landed in `host.json`. Anchor the edit on the row's/line's unique tail per the
`markdown-table-edits` discipline if the entry is a long single line; read the full line range
first. Do not change the BUG-0056 `Status` unless the user directs it — this is a note
correction, not a status change.

Files:
* `v2/docs/bugs.md` - BUG-0056 entry durable-back-port note (≈ line 1019).

Discrepancy references:
* Addresses research Gap 2.

Success criteria:
* The BUG-0056 note no longer claims the `host.json` back-port is pending.

Context references:
* `v2/src/functions/host.json` - the landed setting.

Dependencies:
* None (doc-only).

### Step 2.3: Update the bugs.md BUG-0054 "To resume" note (≈ 987)

In `v2/docs/bugs.md`, update the BUG-0054 "To resume" note (≈ line 987) so the "add an
`alwaysReady` instance for `function:blob_event` per BUG-0053" step is marked done (it lands in
Phase 1), leaving only the cloud-only remainder: `azd deploy function` shipping `blob_event`,
then `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision`, then re-validate.
Keep BUG-0054 `Status: open` (cloud cutover still pending, gated on BUG-0058). Read the full
line range before editing; anchor on a unique tail substring.

Files:
* `v2/docs/bugs.md` - BUG-0054 "To resume" note (≈ line 987).

Discrepancy references:
* Reflects Phase 1 outcome; keeps the defect registry truthful (Hard Rule #19).

Success criteria:
* The "To resume" note lists only the remaining cloud steps; the always-ready step is recorded
  as done; `Status` stays `open`.

Context references:
* `.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md` (dependency-order finding) -
  why the cloud cutover stays deferred behind BUG-0058.

Dependencies:
* Phase 1 completion (so the note can truthfully say the always-ready entry has landed).

## Implementation Phase N: Validation

<!-- parallelizable: false -->

### Step N.1: Run full infra validation

* `uv run pytest v2/tests/infra/`
* `az bicep build --file v2/infra/main.bicep --stdout` (if the Bicep CLI is present)

### Step N.2: Fix minor validation issues

Iterate on any grep-guard or bicep-build failures introduced by Phase 1. Apply fixes directly
when they are straightforward (typo in the new test assertion, array formatting).

### Step N.3: Report blocking issues + record follow-on

* Confirm PD-01 (dead `ingestion_job_id` under `event_grid`) and WI-01 (cloud cutover) remain in
  the Planning Log as deferred follow-on, gated on BUG-0058. Do not attempt either inline.
* If the Bicep CLI is unavailable, note in the changes file that `az bicep build` was skipped and
  only the grep guards ran.

## Dependencies

* `uv` for `pytest`.
* Azure Bicep CLI (optional, for full validation).

## Success Criteria

* `function:blob_event` is an always-ready instance in `v2/infra/main.bicep` and guarded by a
  passing `v2/tests/infra/test_main_bicep.py` test.
* ADR 0028 + bugs.md (BUG-0056, BUG-0054) no longer contradict the shipped `host.json`.
* Gap 3 + cloud cutover remain recorded as follow-on, untouched inline.
