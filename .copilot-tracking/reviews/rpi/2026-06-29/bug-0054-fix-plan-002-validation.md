<!-- markdownlint-disable-file -->
# RPI Validation: BUG-0054 in-repo fix — Phase 2 (stale-doc reconciliation)

**Validation date**: 2026-06-29
**Phase under validation**: Phase 2 — stale-doc reconciliation (steps 2.1, 2.2, 2.3)
**Validator mode**: RPI Validator (read-only)

## Inputs

- Implementation Plan: [.copilot-tracking/plans/2026-06-29/bug-0054-fix-plan.instructions.md](../../../plans/2026-06-29/bug-0054-fix-plan.instructions.md)
- Changes Log: [.copilot-tracking/changes/2026-06-29/bug-0054-fix-changes.md](../../../changes/2026-06-29/bug-0054-fix-changes.md)
- Research Document: [.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md](../../../research/2026-06-29/bug-0054-fix-research.md)
- Planning Log: [.copilot-tracking/plans/logs/2026-06-29/bug-0054-fix-log.md](../../../plans/logs/2026-06-29/bug-0054-fix-log.md)
- Details: [.copilot-tracking/details/2026-06-29/bug-0054-fix-details.md](../../../details/2026-06-29/bug-0054-fix-details.md)

## Phase status

**PASSED.**

All three Phase 2 steps (2.1, 2.2, 2.3) are implemented in the repository exactly as the Changes
Log claims, are consistent with research Gap 2 and Selected approach step 2, and the deliberate
deviation DD-01 (correct-the-note rather than delete-the-note) is justified and transparently
recorded. The BUG-0054 `Status` line remains `open` as required. All Phase 2 plan checkboxes are
marked `[x]`. No critical or major findings.

## Per-step evidence

### Step 2.1 — Correct the ADR 0028 `## Follow-ups` messageEncoding bullet — PASS

- Plan: [bug-0054-fix-plan.instructions.md](../../../plans/2026-06-29/bug-0054-fix-plan.instructions.md) checklist Step 2.1, marked `[x]`.
- Expected: first `## Follow-ups` bullet now states the BUG-0056 `messageEncoding=none` back-port
  has **landed** in host.json (not "still not in host.json/bicep").
- Actual: [v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md](../../../../v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md#L58-L60) — heading `## Follow-ups` at L58; first bullet at L60 now reads
  *"`BUG-0056` encoding back-port — landed in `host.json`. `host.json` now sets
  `extensions.queues.messageEncoding = none`, so every deploy ships it … and no bicep app-setting
  parity is required because the package-level `host.json` is authoritative."*
- Verdict: the stale "still not in host.json / bicep" claim is gone; the corrected text matches the
  Changes Log "Modified" claim and does **not** falsely assert bicep carries the setting. Hard
  Rule #18 placeholders preserved (no real env values). **Matches reality.**

### Step 2.2 — Correct the bugs.md BUG-0056 durable-back-port note — PASS

- Plan: checklist Step 2.2, marked `[x]`.
- Expected: BUG-0056 durable-back-port note marks the back-port "done" (host.json carries the
  setting) and clarifies no bicep app-setting parity is needed because host.json is authoritative.
- Actual: [v2/docs/bugs.md](../../../../v2/docs/bugs.md#L1019) — within the BUG-0056 "Fix (applied live …)" paragraph (L1019):
  *"Durable back-port — done: `host.json` now carries `extensions.queues.messageEncoding = none`,
  so every deploy ships the setting … No bicep function-app-setting parity is needed because the
  package-level `host.json` is authoritative."*
- Verdict: exact match to the expected outcome and the Changes Log claim. Placeholder convention
  (`<RESOURCE_GROUP>`, `<SUFFIX>`) preserved in the adjacent `az` command. **Matches reality.**

### Step 2.3 — Update the bugs.md BUG-0054 "To resume" note — PASS

- Plan: checklist Step 2.3, marked `[x]`.
- Expected: "To resume" note reflects that the `function:blob_event` alwaysReady bicep entry has
  landed (with a reference to the test guard), leaving only cloud-only deploy + flag-flip work;
  the BUG-0054 `Status` line must remain `open`.
- Actual:
  - [v2/docs/bugs.md](../../../../v2/docs/bugs.md#L989) (L989) — *"To resume: the `alwaysReady` instance for `function:blob_event`
    is now in `infra/main.bicep` (added 2026-06-29, guarded by
    `tests/infra/test_main_bicep.py::test_function_app_keeps_blob_event_always_ready`), so the
    remaining work is cloud-only — deploy `blob_event` … then `azd env set
    AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision` … re-validate end-to-end in the
    cloud."*
  - Status line at [v2/docs/bugs.md](../../../../v2/docs/bugs.md#L975) (L975) — *"Area: infra. Severity: medium. Status: **open** — fix
    implemented + proven locally; cloud deploy … **deferred**"* — unchanged.
- Corroborating evidence the landed claim is true: [v2/infra/main.bicep](../../../../v2/infra/main.bicep#L2230-L2236) `alwaysReady` (L2230) now lists
  both `function:batch_push` (L2232) and `function:blob_event` (L2236); the named guard exists.
- Verdict: matches the expected outcome and Changes Log claim; `Status` correctly preserved as
  `open`. **Matches reality.**

## DD-01 deviation assessment — JUSTIFIED and ACCURATELY RECORDED

DD-01 (per the user brief): the plan framed Phase 2 as "remove the stale note", but the
implementation **corrected** the notes to "landed in host.json" rather than implying a bicep
app-setting parity gap.

Verification of the factual premise:

- host.json **does** carry the setting — [v2/src/functions/host.json](../../../../v2/src/functions/host.json#L15-L19) `extensions.queues.messageEncoding = "none"` at L17 (block L15-L19). Confirmed by direct read.
- main.bicep does **not** carry a messageEncoding app-setting — a repository grep for
  `messageEncoding` across [v2/infra/main.bicep](../../../../v2/infra/main.bicep) returned **zero** matches. Confirmed.
- The corrected docs do **not** falsely claim bicep carries it — both the ADR (L60) and bugs.md
  (L1019) explicitly state *"no bicep app-setting parity is required/needed because the
  package-level `host.json` is authoritative."* Confirmed accurate.

Assessment:

- **Justified.** The original stale note asserted the back-port was pending in *both* host.json
  *and* bicep. A literal "delete the bullet" would have discarded the still-useful follow-up
  context (the live `az`-applied override being redundant on next deploy). Correcting the note to
  the true state — landed in host.json, authoritative, no bicep parity needed — is the more
  accurate and complete reconciliation, and aligns with the plan's own Derived Objective ("remove
  documentation drift that contradicts shipped code") and Success Criteria ("no longer claim the
  back-port is pending"). The Details file Step 2.1 explicitly anticipated this nuance ("leaving
  only any bicep app-setting parity note if one genuinely remains").
- **Accurately recorded.** The Changes Log "Additional or Deviating Changes" section records the
  deviation verbatim: *"Phase 2 nuance (deviation from the plan's 'remove the stale note'
  framing): `host.json` carries `messageEncoding=none` but `main.bicep` does NOT, and none is
  needed — the package-level `host.json` is authoritative, so the corrected notes say the
  back-port landed in host.json rather than implying a bicep parity gap."* This is faithful to the
  on-disk state.

## Consistency checks

- **Research Gap 2** named three stale notes (ADR 0028 Follow-ups; bugs.md BUG-0056 ≈L1019;
  bugs.md BUG-0054 "To resume" ≈L987). All three are reconciled. **Consistent.**
- **Research Selected approach step 2** ("Reconcile the three stale doc notes"). All three
  reconciled, none deleted. **Consistent.**
- **Planning Log DD-01 / DR / WI items**: PD-01 (`ingestion_job_id`) and the cloud cutover
  (WI-01/WI-02) are confirmed *not* touched inline — out of Phase 2 scope, correctly deferred.
- **Hard Rule #16** (no process narrative in production code): the `added 2026-06-29` date stamp
  appears in bugs.md (the defect registry / tracking doc), **not** under `v2/src/**`, so it is not
  a violation. **OK.**
- **Plan checkboxes**: Phase 2 header `[x]`; steps 2.1, 2.2, 2.3 all `[x]`. **Confirmed.**

## Findings by severity

### Critical

- (none)

### Major

- (none)

### Minor

- (none)

### Informational (no action)

- INF-1: bugs.md root-cause narratives at L115 and L1015 still describe the *historical* state
  ("never propagated to host.json …") for BUG-0056's original discovery. These are accurate
  descriptions of the defect at discovery time (not "still-pending" follow-up claims) and were not
  in the research Gap 2 scope of three notes. No change warranted; flagged only for completeness.

## Coverage assessment

Phase 2 coverage is **complete**. Every plan item for the phase (steps 2.1–2.3) has a verified,
matching change in the repository; no Phase 2 plan item is missing an implementation, and no
out-of-scope or undocumented Phase 2 change was detected.

## Clarifying questions

- (none) — all Phase 2 claims were resolvable from the available artifacts and repository state.

## Recommended next validations (not performed this session)

- [ ] Validate **Phase 1** (blob_event always-ready, test-first): confirm
  [v2/tests/infra/test_main_bicep.py](../../../../v2/tests/infra/test_main_bicep.py) `test_function_app_keeps_blob_event_always_ready` exists, asserts the
  `function:blob_event` entry, and passes; confirm the bicep `alwaysReady` edit and clean
  `az bicep build`.
- [ ] Validate **Phase N** (final validation): confirm `uv run pytest v2/tests/infra/` reports
  38 passed as the Changes Log claims.
- [ ] Confirm the deferred follow-on (WI-01 cloud cutover, WI-02 / PD-01 `ingestion_job_id`)
  remain logged and untouched in source after the full change set.
