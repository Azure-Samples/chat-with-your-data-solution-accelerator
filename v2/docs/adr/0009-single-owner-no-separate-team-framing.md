# ADR 0009 — Single-owner v2; `development_plan.md` rows describe work by tier, not by team

- **Status**: Accepted
- **Date**: 2026-06-02
- **Phase**: Phase 7 close-out
- **Pillar**: Process / Governance (no code pillar — first non-architecture ADR in the v2 series)
- **Deciders**: CWYD v2 maintainers
- **Supersedes (in part)**: the [`development_plan.md`](../development_plan.md) §0.2 heading "Frontend debt (separate team)" and all per-row "FE team" / "owned by frontend team" / "Frontend team backlog" annotations on **open** rows (#35d, #24, DV1, the §0 row 7 status line, the §4 task #35d summary line). Closed audit rows are preserved in place per [Hard Rule #16](../../.github/copilot-instructions.md) — they remain historical record even though their terminology is now obsolete.

## Context

CWYD v2's [`development_plan.md`](../development_plan.md) ledger had accumulated team-ownership language across §0.2 ("Frontend debt (separate team)") and several open §0.1 / §0.2 / §4 rows that read like "Owned by FE team", "stay on FE backlog", "Frontend team backlog", "Frontend team audit — ⏸ blocked — FE team owns". The framing implied a separate frontend developer or team distinct from the backend owner.

That framing is fiction. CWYD v2 is a **single-developer codebase**. There is no separate FE team, no separate FE owner, no separate FE backlog being worked on by another party. The whole project — backend, frontend, infrastructure, tests, docs — is owned by the same maintainer. The team-ownership annotations had two compounding effects:

1. **They created artificial blockers.** Phase 7 close-gate items like #50 (feedback thumbs), #53 (Ingest Data admin UI), #54 (FE half of multi-select), ⇢#35d, and ⇢#24 were marked as "FE-team-owned" and treated as a separate-team dependency in the §0 status row. In reality those items are *mine to do* — they're frontend-tier work that's deferred behind the Phase 6 backend critical path, not work waiting on another party.
2. **They masked chronological reality.** "Waiting on FE team" reads like an external blocker. "Deferred frontend-tier work behind Phase 6 backend critical path" reads like a sequencing decision. The latter is true; the former was a self-deception that made it easy to under-account for what was actually left.

The maintainer flagged this on 2026-06-02 with "we are coding the complete project — there is no FE team." That correction needs to be captured as a governance decision so the next time someone (human or agent) reads the ledger, they don't re-introduce the framing under the misapprehension that it reflected a real ownership split.

## Decision

**[`development_plan.md`](../development_plan.md) rows describe work by *tier* — frontend-tier, backend-tier, infrastructure-tier — or by *backlog* — frontend backlog, backend backlog. They never describe work by owner or team.**

The §0.2 heading is "Frontend debt" (not "Frontend debt (separate team)"). Open rows say "frontend-tier work" (not "owned by frontend team"); "stay on the frontend backlog" (not "stay on FE backlog"); "frontend tier audit" (not "Frontend team audit"). The §0 status row enumerates the specific deferred frontend-tier items by ID rather than gesturing at "FE-team-owned items".

The cleanup of open rows was applied in the same turn this ADR was drafted (9 `str_replace` edits to [`development_plan.md`](../development_plan.md) on 2026-06-02 covering: the §0.2 heading; the §0 row 7 status line; the open rows for #35d, DV1, and #24; and the §4 task #35d summary line). Closed audit rows (`U-P7-AUDIT-1`, `U-P7-54-BE`, `U-P7-AUDIT-2`, `U-P7-AUDIT-3` — lines 98, 99, 132, 143 at time of writing) were **not** edited; they preserve "FE team" wording as historical record per [Hard Rule #16](../../.github/copilot-instructions.md) (production text describes what code/decisions *are*, not the process narrative they came from; closed audit rows are the inverse — they *are* the process narrative and are protected from rewriting).

The carve-out is mechanical: a `grep_search` for `FE team|frontend team|separate team` in [`development_plan.md`](../development_plan.md) should return matches *only* inside closed audit rows. Any match on an open row, the §0 status snapshot, the §0.2 heading, or a §4 task table is a regression of this ADR.

## Consequences

### Positive

- **Honest blockers.** Phase 7 close-gate now reads "deferred frontend-tier work behind the Phase 6 backend critical path" instead of "waiting on FE team". The maintainer can no longer pretend an external party owns these items.
- **One naming pattern for future row authors.** Tier / backlog vocabulary applies uniformly. No second style to remember, no per-author drift.
- **Audit history preserved.** Hard Rule #16's carve-out for closed audit rows means we keep the record of *what the framing used to be* without perpetuating it forward. Readers of the closed rows see the obsolete terminology and can trace its retirement back to this ADR.

### Negative

- **A future fork of v2 that genuinely splits into a frontend team and backend team** will need to reintroduce some ownership notation. This ADR doesn't prevent that — it documents v2's current single-owner reality, not a universal v-next prohibition. A fork-time supersession ADR is the right mechanism.
- **The 9-edit cleanup of open rows is irreversible without a counter-edit pass.** Once shipped, the obsolete framing is gone from open rows; anyone reading PR history to understand "why was this called FE team" is routed to closed audit rows + this ADR.

### Neutral

- **Hard Rule #11 is not affected.** This is a documentation-naming decision, not a symbol-naming decision; no code identifiers change.
- **No file/folder structure change.** §0.2 stays as a §0.2 sub-section under §0; the only header text changes.

## Alternatives considered

1. **Capture as Hard Rule #18 in [`copilot-instructions.md`](../../.github/copilot-instructions.md) instead of an ADR.** Hard Rules govern continuous code-time enforcement; ADRs govern one-time decisions that are then immutable history. The single-owner framing is closer to a decision-with-history (the cleanup happened on a specific date; closed rows preserve the pre-decision state) than a continuous rule. Hard Rule path also requires the structural-change approval gate ([Hard Rule #10](../../.github/copilot-instructions.md)) and would put a process-governance rule alongside code-discipline rules that don't share its character. Rejected.
2. **Rewrite the closed audit rows so the whole file reads consistently.** Would violate [Hard Rule #16](../../.github/copilot-instructions.md) and destroy the historical record of how Phase 7 was actually framed and tracked at the time. The obsolescence of the closed-row terminology is itself useful information — it shows the framing was wrong and was corrected. Rejected.
3. **Do nothing; the open-row cleanup speaks for itself.** Rejected — leaves no machine-readable / human-readable record of *why* the cleanup happened. A future maintainer (or agent) seeing "Frontend debt" in §0.2 has no way to know it used to say "(separate team)" and was deliberately stripped, and could re-introduce ownership language under the misapprehension that the absence was an oversight.
4. **Permit "tier" *or* "team" framing, document only that team-framing is single-developer in v2.** Rejected — leaves the door open to per-row drift. A clean prohibition on team/owner language in row text is easier to enforce and easier to read.

## References

- [`development_plan.md`](../development_plan.md) §0 (status snapshot row 7), §0.2 (Frontend debt heading), §0.1 row `#35d`, §0.2 rows `DV1` and `#24`, §4 phase task tables — the surfaces edited under this decision.
- [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) Hard Rule #16 — closed audit rows / process narrative carve-out that protects the historical record.
- [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) Hard Rule #10 — structural-change approval gate (cited under Alternatives #1).
- [ADR 0008](0008-lazy-foundry-agent-bootstrap.md) — precedent for ADRs whose Pillar field carries a compound process/architecture label rather than a single code pillar.
- [ADR 0010](0010-chronological-debt-queue-drainage.md) — companion governance ADR drafted in the same turn for a related `development_plan.md` §0.1 drainage rule.
