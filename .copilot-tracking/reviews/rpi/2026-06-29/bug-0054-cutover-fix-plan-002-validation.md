<!-- markdownlint-disable-file -->
# RPI Validation — BUG-0054 Cutover-Fix Plan, Phase 2 (Durable Bicep idempotency hardening)

- **Plan through-line (phase):** Phase 2 — Durable Bicep idempotency hardening (Steps 2.1, 2.2, 2.3)
- **Plan file:** `.copilot-tracking/plans/bug-0054-cutover-fix-plan.instructions.md`
- **Planning Log / DD entries:** same plan file (Planning Log section, DD-01 / DD-02)
- **Changes Log:** `.copilot-tracking/changes/bug-0054-cutover-fix-changes.md`
- **Research doc:** `.copilot-tracking/research/bug-0054-cutover-fix-research.md`
- **Validated artifacts:** `v2/infra/main.bicep`, `v2/tests/infra/test_main_bicep.py`
- **Date:** 2026-06-29
- **Mode:** read + analysis only (no implementation/plan/research files modified)

## Phase status: **VALIDATED** — one deviation (DD-02), assessed **SOUND** and fully documented

Phase 2 is implemented faithfully. Every plan item maps to a verified change with
file:line evidence. The single departure from the literal plan text (DD-02, the
role-assignment name salt) is forced by a Bicep constraint, recorded in both the
Changes Log and the Planning Log, mirrors an established in-repo precedent, and
still satisfies the idempotency objective. No Critical or Major findings. Two
Minor findings (one tracked-artifact drift, one cosmetic style nit), neither
blocking Phase 2 closure.

## Independently verified (this validation, non-mutating)

| Check | Method | Result |
| --- | --- | --- |
| Infra guards execute green | `python -m pytest tests/infra/test_main_bicep.py` | **36 passed** (matches Changes Log "36/36") |
| `main.bicep` compiles | `az bicep build --file main.bicep --stdout` | **EXIT=0** (only benign BCP081 type-cache warnings; **no BCP120**, no null-safety error) |
| Static salt removed from source | `grep 'search-system-mi' v2/infra/**` | absent from `main.bicep`; present only in `main.json` (see M-1) |
| Both EG subs pinned to `blob-events` | `grep 'queueName: blobEventsQueueName' main.bicep` | exactly **2** sites (L2421, L2487) — grounds the `count == 2` guard |
| DD-02 precedent is real | read `main.bicep:699-708` | `existingOpenAiUamiRole` uses `guid(existingOpenAi!.id, userAssignedIdentity.name, '<roleId>')` |

## Plan-item → change traceability

### Step 2.1 — Harden search-system-MI → OpenAI role-assignment names (idempotency)

- **PASS (with DD-02).** Both assignments now key their `name:` on the full scope
  resource id + the start-time Search service name + the role-definition id:
  - `searchOpenAiUserOnFoundry` — `main.bicep:1039`: `name: guid(aiServicesAccount.id, 'srch-${solutionSuffix}', subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'))`, `scope: aiServicesAccount` (`existing` resource declared `main.bicep:1034`).
  - `searchOpenAiUserOnReusedOpenAi` — `main.bicep:1051`: `name: guid(existingOpenAi.id, 'srch-${solutionSuffix}', subscriptionResourceId(...))`, `scope: existingOpenAi` (`existing` resource declared `main.bicep:656`).
  - Deploy-time principal (`aiSearch!.outputs.systemAssignedMIPrincipalId!`) is used **only** in `properties.principalId` — correct; never in `name`.
- **Departure from literal plan text:** plan/details specified the salt as
  `systemAssignedMIPrincipalId`; the implementation uses `'srch-${solutionSuffix}'`.
  This is **DD-02** — see verdict below.

### Step 2.2 — Guard the Event Grid blob subscription destination (`blob-events`, never `doc-processing`)

- **PASS.** `test_blob_event_subscription_targets_blob_events_queue`
  (`test_main_bicep.py:220-262`) asserts:
  - `bicep_text.count("queueName: blobEventsQueueName") == 2` (L233-249) — both the
    new-topic and existing-topic-reuse subscriptions must land on `blob-events`.
  - `"queueName: docProcessingQueueName" not in bicep_text` (L250-256) — forbids the
    exact BUG-0054 double-ingest repoint.
  - `BlobCreated` + `BlobDeleted` included-event-types present (L257-262).
- Grounded in real code: the two `queueName: blobEventsQueueName` bindings exist at
  `main.bicep:2421` and `main.bicep:2487`.

### Step 2.3 — Test-first regression guards

- **PASS.** `test_search_openai_role_assignments_use_idempotent_name`
  (`test_main_bicep.py:672-720`) lands with the implementation and executes
  (36/36 green). Pillar/Phase header present on the test module (`test_main_bicep.py:1-16`).

## DD-02 verdict: **SOUND** — justified, correctly documented, objective still met

The deviation (salt = `'srch-${solutionSuffix}'` instead of the plan's
`systemAssignedMIPrincipalId`) is validated on four independent grounds:

1. **Forced by a Bicep constraint.** A role-assignment `name` must be evaluable at
   the **start** of deployment. `systemAssignedMIPrincipalId` is a deploy-time
   module output; putting it in `name` raises **BCP120**. Independently confirmed:
   `az bicep build` returns EXIT=0 with the suffix-based salt and raises **no**
   BCP120 — the constraint the plan's original approach would have hit is real and
   is resolved by the start-time salt.
2. **Documented in both required logs.** Recorded in the Changes Log
   ("Additional or Deviating Changes" → DD-02) and the Planning Log (DD-02 entry),
   each carrying the BCP120 rationale. No silent deviation.
3. **Idempotency objective preserved.** `guid(scope.id, 'srch-${solutionSuffix}', roleDefId)`
   is deterministic, unique per deployment (suffix), collision-safe (real scope id +
   role-def id), and stable across re-runs — exactly the re-run-safe property Phase 2
   set out to guarantee. The hand-coded `'search-system-mi'` token is gone from source.
4. **Mirrors an established precedent.** `existingOpenAiUamiRole` (`main.bicep:699-708`)
   already uses `guid(existingOpenAi!.id, userAssignedIdentity.name, '<roleId>')` —
   the identical `guid(scope.id, identityName, roleDefId)` shape, where the resource
   **name** stands in for a deploy-time principal. The Phase 2 change adopts the same,
   proven pattern.

## Findings by severity

### Critical
- None.

### Major
- None.

### Minor

- **M-1 — Stale compiled ARM artifact (`main.json`) still carries the removed salt.**
  `v2/infra/main.json` is git-tracked (`git ls-files` returns it; not gitignored) and
  was **not** regenerated after the Phase 2 `main.bicep` edit (`git status --short`
  shows no `M` on `main.json`, only on `main.bicep` + the test). It still contains
  `guid(..., 'search-system-mi', '5e0bd9bd-...')` at `main.json:571` and `main.json:586`.
  - **No runtime impact:** `azure.yaml:30-33` declares `infra.provider: bicep` /
    `module: main`, so `azd up` / `azd provision` compile `main.bicep` directly and
    never consume `main.json`. The deployed role-assignment names will use the
    hardened suffix salt.
  - **Why it is still worth a note:** the very token Phase 2 set out to eliminate
    survives in a tracked sibling file, `main.json` is now divergent from `main.bicep`,
    and the regression guard (`'search-system-mi' not in bicep_text`) only covers
    `main.bicep`. Out of the literal Phase 2 plan scope (plan/details/research touch
    only `main.bicep` + the test), so informational rather than a defect — but a
    regenerate-or-remove follow-up would close the repo-wide "salt-free" claim.
  - Evidence: `main.json:571`, `main.json:586`; `azure.yaml:30-33`.

- **M-2 — Cosmetic null-assert inconsistency between sibling role assignments.**
  `searchOpenAiUserOnReusedOpenAi` (`main.bicep:1051`) writes `guid(existingOpenAi.id, ...)`
  while its cited precedent `existingOpenAiUamiRole` (`main.bicep:702`) writes
  `guid(existingOpenAi!.id, ...)` on the same conditional `existing` symbol. Compiles
  clean (independently confirmed, EXIT=0, no BCP error — the resource's own `if`
  condition narrows the symbol as non-null), so purely stylistic. No action required
  for Phase 2 closure; aligning the two for consistency is optional.

### Informational
- The `"queueName: docProcessingQueueName" not in bicep_text` negative (Step 2.2) is
  partly redundant with the `count(...) == 2` positive — a repoint to a raw
  `'doc-processing'` literal would still be caught because the `blob-events` count
  drops below 2. The pair is strictly stronger than either alone; this is a strength,
  not a gap.

## Five-dimension assessment (as requested)

| # | Dimension | Verdict | Notes |
| --- | --- | --- | --- |
| 1 | Fidelity to plan/details | **PASS** (one sound deviation) | Steps 2.1/2.2/2.3 all implemented in `main.bicep` + `test_main_bicep.py`; only departure is DD-02. |
| 2 | DD-02 deviation soundness | **SOUND** | BCP120-forced, dual-logged, idempotency preserved, mirrors `existingOpenAiUamiRole` precedent. |
| 3 | Test coverage adequacy | **ROBUST** | Exact-string name pins + static-salt negative; `count == 2` EG pin grounded in 2 real sites; no loose substring that passes while the invariant breaks; 36/36 green. |
| 4 | Success-criteria traceability | **PASS** | "no static-salt names" (source clean), "infra test green" (36/36), "bicep compiles" (EXIT=0) all independently confirmed; checklist `[x]`, `parallelizable: true`, "NOT required to close BUG-0054" consistent with DD-01. |
| 5 | Hard-rule compliance (#2, #18) | **PASS** | #2 test-first guards execute green; #18 only literal is the built-in role-def GUID `5e0bd9bd-...` (allowed carve-out), salt uses the `${solutionSuffix}` expression (not a hard-coded suffix), no sub/tenant/RG/UAMI ids introduced. |

## Coverage assessment

Phase 2 is **fully covered**. All three steps are implemented, test-first, and green;
both the role-assignment idempotency invariant and the BUG-0054 double-ingest
invariant are guarded by assertions that fail on regression. The phase ends in a
compilable, green state. Residual items (M-1 stale `main.json`, M-2 style nit) are
outside the phase's plan scope and do not affect the deployed surface.

## Recommended next validations (not performed this session)

- [ ] Phase 1 through-line (cutover backend/functions changes) vs Changes Log.
- [ ] Phase 3+ through-lines per the plan checklist.
- [ ] Repo-hygiene follow-up: confirm whether `v2/infra/main.json` should be
      regenerated or removed (M-1) — tracked compiled artifact divergence is a
      cross-phase concern, not Phase 2 scope.
- [ ] End-to-end `azd provision` dry-run / what-if to confirm the new role-assignment
      names apply idempotently on a real re-run (runtime confirmation beyond static guards).

## Clarifying questions

- Is `v2/infra/main.json` intended to be a committed pre-compiled artifact, or a
  leftover `az bicep build` output? If committed-by-design, it should be regenerated
  as part of Phase 2 to stay salt-free; if leftover, it can be removed and gitignored.
  Either way the decision is out of Phase 2's read-only plan scope and is raised here
  for the user, not actioned.
