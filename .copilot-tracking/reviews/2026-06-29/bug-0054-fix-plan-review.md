<!-- markdownlint-disable-file -->
# Review Log: BUG-0054 in-repo fix — blob_event always-ready + stale-doc reconciliation

## Metadata

* **Review date**: 2026-06-29
* **Implementation Plan**: .copilot-tracking/plans/2026-06-29/bug-0054-fix-plan.instructions.md
* **Changes Log**: .copilot-tracking/changes/2026-06-29/bug-0054-fix-changes.md
* **Research Document**: .copilot-tracking/research/2026-06-29/bug-0054-fix-research.md
* **Planning Log**: .copilot-tracking/plans/logs/2026-06-29/bug-0054-fix-log.md
* **Reviewer**: Task Reviewer

## Scope

In-repo remainder of BUG-0054: add `function:blob_event` to the Flex `alwaysReady` set
(test-first) and reconcile three stale documentation notes. Cloud cutover and the dead
`ingestion_job_id` cleanup are explicitly deferred follow-on (WI-01, WI-02).

Plan phases under review:

1. Phase 1 — blob_event always-ready (test-first)
2. Phase 2 — stale-doc reconciliation
3. Phase N — Validation

## Severity Summary

| Severity | Count |
|----------|-------|
| Critical | 0     |
| Major    | 0     |
| Minor    | 0     |
| Informational | 1 (BUG-0056 historical narrative retained — no action) |

## Phase Validation Findings (RPI)

Three RPI Validator runs (one per plan phase). All **Passed**; no critical/major findings.
Detailed reports under .copilot-tracking/reviews/rpi/2026-06-29/.

| Phase | Status | Evidence | Findings |
|-------|--------|----------|----------|
| Phase 1 — blob_event always-ready (test-first) | ✅ Verified | `test_function_app_keeps_blob_event_always_ready` at v2/tests/infra/test_main_bicep.py L202; `function:blob_event` entry at v2/infra/main.bicep L2236 alongside `batch_push` L2232 | None |
| Phase 2 — stale-doc reconciliation | ✅ Verified | ADR 0028 L58-60 (back-port landed); bugs.md L1019 (BUG-0056 done); bugs.md L989 + Status L975 (BUG-0054 to-resume trimmed, Status still `open`) | None (1 informational: BUG-0056 historical narrative at L1015 retained, out of scope) |
| Phase N — Validation | ✅ Verified | Independently re-ran `uv run pytest tests/infra/` → 38 passed; `az bicep build` exit 0; ingestion.py L299/L350 unmodified; WI-01/WI-02/PD-01 logged | None |

### DD-01 deviation (Phase 2) — assessed JUSTIFIED and accurately recorded

The plan framed Phase 2 as "remove the stale note"; the implementation instead **corrected** the
notes to "back-port landed in host.json". The RPI Validator confirmed independently:

* v2/src/functions/host.json L15-19 **carries** `extensions.queues.messageEncoding = "none"`.
* v2/infra/main.bicep has **zero** `messageEncoding` matches — and the corrected docs do **not**
  falsely claim it does (they state "no bicep parity needed, host.json is authoritative").
* The deviation is recorded verbatim in the Changes Log "Additional or Deviating Changes"
  ("Phase 2 nuance") and in the Planning Log DD-01.

This is a correctness-preserving deviation that avoided introducing a *new* false claim — the
correct call.

## Implementation Quality Findings

Detailed log: .copilot-tracking/reviews/impl/2026-06-29/bug-0054-fix-impl-validation.md

Verdict: **PASS** — no Critical / Major / Minor findings.

> The `Implementation Validator` subagent ran in a sandboxed session exposing only the
> read-only session-store SQL interface (no file read/write) and returned **Blocked** — an
> environment limitation, not a code finding. The quality assessment was performed directly by
> the reviewer (full file access; all changed files already read this session).

* **Conventions (v2-infra):** the `function:blob_event` entry is stylistically identical to the
  existing `function:batch_push` entry beside it (v2/infra/main.bicep L2235-2238); comment is
  descriptive, not process narrative.
* **Test quality (Hard Rule #2):** `test_function_app_keeps_blob_event_always_ready`
  (v2/tests/infra/test_main_bicep.py L202) is a real behavioral assertion with a substantive
  docstring + actionable failure message; consistent with existing grep guards.
* **Defect/debt split (Hard Rules #12, #19):** edits in the defect registry (bugs.md), none in
  dev_plan §0.1; BUG-0054 `Status` stays `open`; fix recorded in the day's worklog.
* **Env-hygiene (Hard Rule #18):** no subscription/tenant/UAMI/RG/suffix IDs or secrets in any
  changed doc line.
* **Structure (Hard Rule #10):** one element added to an existing array — not a structural
  change; no confirmation gate triggered.

## Validation Commands

| Command | Result | Source |
|---------|--------|--------|
| `uv run pytest v2/tests/infra/` | **38 passed** | reviewer (this session) + RPI Phase N (independent re-run) |
| `az bicep build --file v2/infra/main.bicep --stdout` | clean, exit 0 | Changes Log + RPI Phase N |
| `get_errors` on v2/tests/infra/test_main_bicep.py | No errors found | reviewer (this session) |

## Missing Work / Deviations

* **No missing in-scope work.** All three plan phases (1, 2, N) are complete, with every plan
  checkbox marked `[x]` and substantiated by repository state.
* **DD-01 deviation (justified):** Phase 2 corrected the stale notes to "back-port landed in
  host.json" rather than literally "removing" them — avoiding a *new* false claim of a bicep
  parity gap. Independently verified (host.json carries the setting; main.bicep does not, and the
  docs do not claim it does). Recorded in the Changes Log "Phase 2 nuance" and Planning Log DD-01.

## Follow-Up Work

Deferred from scope (recorded in the Planning Log; **not** review-discovered defects):

* **WI-01 (high)** — BUG-0054 cloud cutover: deploy `blob_event`, then
  `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision`, re-validate, and close
  BUG-0054. Gated on BUG-0058 cloud verification + the parked Flex remote-build timeout.
* **WI-02 (low)** — resolve PD-01: drop / mark-informational the dead `ingestion_job_id` in
  `UploadResponse` under `event_grid` (ADR 0028 Consequences). Best landed with WI-01.

Discovered during review: **none.**

## Overall Status

✅ **Complete.** All plan items verified against repository state; 0 Critical / 0 Major / 0 Minor
findings across three RPI phase validations + the direct quality assessment. Validation gates
reproduce green (38/38 infra tests; clean bicep build; no diagnostics). The single deviation
(DD-01) is justified and transparently recorded. BUG-0054 correctly remains `open` pending the
deferred cloud cutover (WI-01).

**Reviewer notes:** the in-repo scope is fully and cleanly delivered. No rework required. The
only open items are the two intentionally-deferred follow-ons, both durably logged.
