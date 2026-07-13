# ADR 0010 — `development_plan.md` §0.1 debt rows are drained in chronological-creation order during the end-of-phase audit turn

- **Status**: Accepted
- **Date**: 2026-06-02
- **Phase**: Phase 7 close-out
- **Pillar**: Process / Governance (no code pillar)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR **extends** [Hard Rule #12](../../.github/copilot-instructions.md) (no mid-phase back-fills; §4 tasks execute in numeric order) with an intra-phase ordering rule that applies specifically to [`development_plan.md`](../development_plan.md) §0.1 debt-queue drainage during the single end-of-phase audit turn.

## Context

[Hard Rule #12](../../.github/copilot-instructions.md) in [`copilot-instructions.md`](../../.github/copilot-instructions.md) governs *new work added during a phase*: debt items discovered mid-phase are appended to [`development_plan.md`](../development_plan.md) §0.1, never implemented inline, and §4 tasks execute in numeric order with no out-of-order pulls from later phases or "while we're here" additions. That rule is binding and unambiguous **for §4 task execution**.

Hard Rule #12 is **silent on §0.1 drainage order**. The end-of-phase audit turn is the single dedicated pass that clears all queued §0.1 debt rows accumulated during a phase, but the rule doesn't say *in what order* those rows should be cleared. In practice the queue tends toward priority-order or convenience-order, which makes "what's left to clear?" hard to read at a glance: the next-to-clear row depends on the auditor's mental model, not on a deterministic property of the file.

During the Phase 7 close-out audit a concrete instance of this gap surfaced. `EXTENSION-DISCOVERY-PIPELINE` was opened and worked through *ahead of* three Phase-6 debt rows that were already queued chronologically earlier. The `U-P7-AUDIT-3` audit row that closed the affected segment recorded the queue-jump as a discipline note — reactively, after the fact — but did not retroactively unwind the work, because the work was complete and unwinding it would have been pure churn.

The reactive discipline note worked as a one-off, but it sets a bad precedent: any future queue-jump can be "discipline-noted" after the fact, which empties the rule of preventive force. The right shape is a *preventive* rule — chronological-creation order is the default, exceptions need approval *before* the work starts, and the audit row that closes the affected segment cites the exception with a reason.

## Decision

**During the single end-of-phase audit turn, [`development_plan.md`](../development_plan.md) §0.1 debt rows are drained in *chronological-creation order* — top-to-bottom in the order they were appended to the queue. Queue-jumps require (a) explicit user approval *before* the out-of-order row starts, and (b) a discipline note on the audit row that closes the affected segment, citing the jumped row's ID and the reason for the jump.**

Concretely:

1. The audit turn begins by listing the §0.1 rows that are open at end-of-phase, in file-order (which equals chronological order, because rows are *appended*, never inserted).
2. The auditor drains them top-to-bottom. Each closed row's status flips from `⏳` / `☐` to `✅` in the same turn it's cleared.
3. If a later row needs to be cleared before an earlier one — most commonly because the later row is a blocker for closing the phase and the earlier one isn't — the auditor pauses, surfaces the situation to the user, and gets explicit approval *before* starting the out-of-order work.
4. The audit row that closes the affected segment of the phase (e.g. `U-P7-AUDIT-3`) carries a discipline note: "Out-of-order: closed `<ROW-ID>` before `<EARLIER-ROW-ID>` because `<reason>`. Approved by maintainer." The note cites both row IDs so the queue-jump is reconstructible from the audit row alone.
5. **No retroactive unwinding.** A discipline-noted jump is not undone. The note exists to make the jump visible and accountable, not to penalize the work.

This rule complements [Hard Rule #12](../../.github/copilot-instructions.md). Hard Rule #12 governs *§4 task* execution order during the phase (numeric, strict, no carve-outs except for the documented "literally cannot proceed" exception). This ADR governs *§0.1 debt-row* drainage order during the end-of-phase audit (chronological, default-with-approval-carve-out). The two rules operate on different ledger surfaces at different points in the phase lifecycle.

The `EXTENSION-DISCOVERY-PIPELINE` jump that prompted this ADR is **not retroactively unwound** — the discipline note in `U-P7-AUDIT-3` remains in place as the historical record of the precedent, and this ADR codifies the rule going forward starting with the next end-of-phase audit (Phase 7 close-out or later).

## Consequences

### Positive

- **End-of-phase audit reads top-to-bottom.** A reader (or agent) can answer "what's left to clear?" by scanning §0.1 in file order, with no need to mentally re-sort by creation date or priority. The first un-closed row is the next-to-clear row.
- **Queue-jumps stay visible.** The discipline-note convention from `U-P7-AUDIT-3` becomes a rule, not a one-off. Any future reader of the audit row knows both that a jump happened and why.
- **Codifies the existing precedent without rewriting it.** `U-P7-AUDIT-3`'s discipline note is preserved as-written; this ADR is what makes that note's *form* (cite jumped row + reason) the standard going forward.
- **No new tooling required.** The rule is enforced by audit-turn discipline + the existing approval-gate flow with the maintainer. No script, no test gate, no new file format.

### Negative

- **A high-priority newly-added debt row sits behind older lower-priority rows during the audit.** This is acceptable: high-priority debt should be worked *inline* during the phase via [Hard Rule #12](../../.github/copilot-instructions.md)'s "literally cannot proceed without the missed item" carve-out (annotated in §0.1 with reason), not by jumping the queue during the audit. The audit is for *queued* debt, not for *blocking* debt — blocking debt should never reach the audit because it should have been resolved inline.
- **Approval-before-jump adds one user-interaction roundtrip per jump.** Acceptable cost — the cost is paid only when a jump is actually needed, and the alternative (reactive notes) empties the rule of preventive force.

### Neutral

- **The rule applies only to §0.1 (backend debt).** §0.2 (frontend debt) is a separate sub-section with its own drainage cadence — frontend-tier rows aren't part of the same end-of-phase audit. If §0.2 ever grows enough to need its own drainage rule, a follow-up ADR can extend this one.
- **Tasks pulled into the phase from §4 task tables follow [Hard Rule #12](../../.github/copilot-instructions.md), not this ADR.** This ADR is the §0.1 counterpart, not a replacement.

## Alternatives considered

1. **Add as Hard Rule #18 in [`copilot-instructions.md`](../../.github/copilot-instructions.md).** Hard Rules are continuous code-time enforcement; this rule fires only during the end-of-phase audit turn (a specific point in the phase lifecycle) and governs decision-style queue ordering rather than continuous code discipline. The Hard Rule path also requires the structural-change approval gate ([Hard Rule #10](../../.github/copilot-instructions.md)) for any subsequent edit, which is heavier than this rule warrants. Rejected.
2. **Permit priority-order drainage; auditor decides per-audit.** Priority is subjective and changes per audit (one auditor might prioritize "smallest first" to ship fast; another might prioritize "blockers first" to de-risk). Chronological order is mechanical, reproducible, and identical regardless of who runs the audit. The single decision point — "is this jump justified?" — moves from per-row priority judgment to a single approval gate, which is easier to enforce. Rejected.
3. **Permit jumps without prior approval if the audit row records the jump after-the-fact.** This is exactly what happened with `EXTENSION-DISCOVERY-PIPELINE` — a reactive discipline note. The note was useful as a one-off but doesn't constrain future jumps, because any auditor can declare any jump "discipline-noted" after the fact. The rule needs preventive force, not just descriptive force. Rejected.
4. **Retroactively unwind the `EXTENSION-DISCOVERY-PIPELINE` jump.** The work is complete and shipping; unwinding would be pure churn for zero benefit. The discipline note in `U-P7-AUDIT-3` already documents the jump for the historical record. Rejected.
5. **Drain §0.1 in arbitrary order; document only that order is the auditor's choice.** Rejected — leaves the door open to every audit having a different order, which is exactly the readability problem this ADR is solving.

## References

- [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) Hard Rule #12 — no mid-phase back-fills; §4 task numeric ordering. This ADR extends Hard Rule #12 with the §0.1 drainage rule.
- [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) Hard Rule #10 — structural-change approval gate (cited under Alternatives #1).
- [`development_plan.md`](../development_plan.md) §0.1 — the backend debt queue this ADR governs.
- [`development_plan.md`](../development_plan.md) `U-P7-AUDIT-3` audit row — the precedent that prompted this ADR; preserves the `EXTENSION-DISCOVERY-PIPELINE` queue-jump discipline note as historical record per [Hard Rule #16](../../.github/copilot-instructions.md).
- [ADR 0008](0008-lazy-foundry-agent-bootstrap.md) — precedent for ADRs whose Pillar field carries a process / governance label rather than one of the four code pillars.
- [ADR 0009](0009-single-owner-no-separate-team-framing.md) — companion governance ADR drafted in the same turn for related `development_plan.md` framing.
