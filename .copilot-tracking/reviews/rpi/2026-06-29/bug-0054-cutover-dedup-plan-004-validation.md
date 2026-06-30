<!-- markdownlint-disable-file -->
# RPI Validation — BUG-0054 cutover-dedup plan, Phase 4

## Metadata

- **Plan**: `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-dedup-plan.instructions.md`
- **Details**: `.copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md` (Phase 4 = Lines 225-298)
- **Changes Log**: `.copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md`
- **Planning Log**: `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md` (DR-02, DR-03, WI-01)
- **Research**: `.copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md` (Task A)
- **Phase validated**: Phase 4 — BUG-0054 cloud cutover + docs reconcile
- **Validation date**: 2026-06-29
- **Overall status**: **Passed** (Step 4.1 verified; Steps 4.2/4.3 correctly Blocked, not falsely claimed)

## Phase 4 through-line summary

Phase 4 has one agent-doable, in-repo step (4.1: reconcile the stale BUG-0054 record in `v2/docs/bugs.md`) and two operator-driven steps (4.2 flip-trigger + provision, 4.3 cloud E2E + poison drain + close) that are gated on an authenticated `azd` session and a clean BUG-0058 deploy state and were intentionally **not** attempted. The validation confirms the in-repo work landed exactly as specified, was extended (summary row) with a properly-recorded discrepancy, and that the operator steps are honestly marked Blocked with BUG-0054 still `open`.

## Per-step validation

### Step 4.1 — Reconcile the stale BUG-0054 record in `v2/docs/bugs.md` — **Verified**

| Required (details L229-248) | Evidence | Status |
| --- | --- | --- |
| Detail block no longer lists "deploy `blob_event`" as remaining work | `v2/docs/bugs.md` L989 close-out enumerates only the four operator steps; "function-deploy step is **done**" | Verified |
| Records the 2026-06-24 deploy (BUG-0080; 5 → 6 functions; `func ... publish --no-build --python` after the `agent-framework-core` repin) | `v2/docs/bugs.md` L975 ("deployed to the cloud Function App 2026-06-24 (5 → 6 functions, see BUG-0080)"), L983 (deferred 06-20 → completed 06-24 under BUG-0080), L991 references BUG-0080 ("`agent-framework-core` repin") | Verified |
| Four remaining close-out steps: (1) flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid` + `azd provision`; (2) verify EG subscription target; (3) cloud E2E create+delete (BUG-0058 gate); (4) drain 4 historical `doc-processing-poison` | `v2/docs/bugs.md` L989 lists all four verbatim (delete path noted as covered by BUG-0077) | Verified |
| Placeholder tokens only — no real env IDs (Hard Rule #18) | Detail block L973-991 + summary row L113 contain only `<SUFFIX>`-style references, BUG ids, dates, queue/flag names; no subscription/tenant/RG/GUID/suffix literals | Verified |
| BUG-0054 stays `open` | `v2/docs/bugs.md` L975 ("Status: open"), L989 ("BUG-0054 stays **open** until all four pass"), summary row L113 (`open`) | Verified |
| Closed-set Area/Severity/Status fields intact | Summary row L113 `infra | medium | open`; detail block L975 "Area: infra. Severity: medium. Status: open" | Verified |

Plan checklist marks Step 4.1 `[x]` with a "Done:" note recording both the detail block (L973-991) and summary row (L113) reconciliation. Changes Log "Modified" + "Release Summary" sections describe the same work accurately.

### Step 4.2 — Flip the trigger flag + re-provision (operator-driven) — **Blocked (correctly)**

| Check | Evidence | Status |
| --- | --- | --- |
| Marked incomplete + Blocked, not falsely done | Plan checklist Step 4.2 `[ ]` "BLOCKED (gated on an authenticated `azd` session + a clean BUG-0058 deploy state; not agent-doable)" | Blocked |
| Changes Log does not claim the flip happened | Release Summary: "operator steps (4.2/4.3) blocked"; "The env flag is **not yet** flipped" mirrored in `bugs.md` L987 | Blocked |
| Matches research finding (flag NOT flipped) | Research Task A Q2 → "NO ... Backend is still `direct_enqueue`" | Consistent |

### Step 4.3 — Cloud E2E re-validation + poison drain + close (operator-driven) — **Blocked (correctly)**

| Check | Evidence | Status |
| --- | --- | --- |
| Marked incomplete + Blocked, gated on Step 4.2 | Plan checklist Step 4.3 `[ ]` "BLOCKED (operator-driven; gated on Step 4.2)" | Blocked |
| No premature "BUG-0054 fixed" assertion | `bugs.md` keeps `open` in both places; Plan Success Criteria: "BUG-0054 reaches `fixed` only after the cloud E2E re-validation ... and the 4 historical poison messages are drained"; Changes Log: "BUG-0054 remains `open`" | Blocked |
| Cloud cutover did NOT happen — accurately reflected | Research Task A Q1-Q3 (deploy=YES, flip=NO, drain=NO); no artifact claims create/delete E2E ran | Consistent |
| Phase 4 header itself not marked complete | Plan checklist "Implementation Phase 4" header is `[ ]` | Blocked |

## Findings by severity

### Critical — 0

None.

### Major — 0

None.

### Minor — 0

None.

### Info — 3

- **INFO-1 (positive, properly documented extension).** Step 4.1 details (L229-248) named only the detail block (`lines ~973-1003`). The implementation additionally reconciled the **summary table row** at `v2/docs/bugs.md` L113. This extension is recorded in Planning Log DR-02 ("reconciled BOTH the detail block (L973-991) AND the previously-overlooked summary row (L113)") and in the Changes Log "Modified" entry. It is consistent with the bug-reconciliation intent and the bugs.md two-surface convention (summary row + detail block). No discrepancy — completeness improvement, traced.
- **INFO-2 (estimate drift, no impact).** Details L229 estimated the detail block at "lines ~973-1003"; the actual block ends at ~L991 (close-out L989, references L991). The plan checklist and Changes Log both use the accurate `L973-991`. Estimate-vs-actual drift only.
- **INFO-3 (out-of-scope deviations, properly logged).** Planning Log records DE-01 (`uv run pytest` trampoline fallback), DE-02 (Phase-header value `Phase: 6` vs details' `Phase: 7`), and DE-03 (`resolve_search_provider` close-on-failure wrapper). These belong to Phases 1-3, not Phase 4, and are correctly logged; noted here only to confirm they do not bleed into the Phase 4 assessment.

## Discrepancy-reference cross-check

- **DR-02** (stale "deploy blob_event" note vs. 2026-06-24 BUG-0080 deploy) — **Addressed.** Both surfaces reconciled; matches Step 4.1 success criterion.
- **DR-03** (live deploy/flag/poison state reconciled from doc trail only; no live `az` run) — **Deferred to Phase 4 operator close-out**, accurately scoped (read-only confirmations gate the close, not the plan). Not a Phase-4-in-repo obligation.
- **WI-01** (three read-only live confirmations before closing BUG-0054) — correctly carried as operator follow-on folded into Phase 4; not claimed done.

## Hard Rule conformance (Phase 4 surface)

- **Hard Rule #18** (no env-specific IDs in tracked files): the BUG-0054 edits introduce no real subscription/tenant/RG/suffix/GUID — placeholder convention preserved. **Pass.**
- **Hard Rule #19** (durable bugs.md as canonical defect registry; defect-vs-debt split): BUG-0054 detail + summary updated in `bugs.md` (not buried in memory). **Pass.**
- **Hard Rule #12** (defect lives in `bugs.md`, not a phase-debt ledger): reconciliation kept in `bugs.md`. **Pass.**

## Coverage assessment

Phase 4 in-repo scope is **fully covered**: the single agent-doable step (4.1) is implemented exactly per the details file, extended (summary row) with a traced discrepancy, and the two operator steps are honestly Blocked with BUG-0054 still `open`. No required content is missing; no false completion or premature `fixed` claim exists anywhere across the plan, details, Changes Log, or `bugs.md`.

## Recommended next validations (not performed here)

- [ ] Validate Phase 1 (infra regression-guard test `test_blob_event_subscription_targets_blob_events_queue`).
- [ ] Validate Phase 2 (`parser_key_for_path` extraction + four call-site repoints; including DE-02 Phase-header deviation).
- [ ] Validate Phase 3 (`resolve_search_provider` extraction + three blueprint repoints; including DE-03 close-on-failure wrapper / Hard Rule #14).
- [ ] Validate Phase 5 (full-suite + pyright gate claims: `2514 passed, 1 skipped`; `0/0/0` pyright).
- [ ] (Operator) Post-cutover re-validation of Steps 4.2/4.3 once an authenticated `azd` session and a clean BUG-0058 deploy state exist — confirm trigger flip, live EG subscription target, cloud create+delete E2E, poison drain, then the `open → fixed` flip + worklog entry.

## Clarifying questions

None. All Phase 4 in-repo claims are resolvable from the artifacts and the live `v2/docs/bugs.md` content; the operator-driven steps are unambiguously scoped as Blocked.
