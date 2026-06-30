<!-- markdownlint-disable-file -->
# Review Log: BUG-0054 cutover fix (Event Grid ingestion trigger)

## Metadata

| Field | Value |
|---|---|
| **Review Date** | 2026-06-29 |
| **Implementation Plan** | .copilot-tracking/plans/2026-06-29/bug-0054-cutover-fix-plan.instructions.md |
| **Changes Log** | .copilot-tracking/changes/2026-06-29/bug-0054-cutover-fix-changes.md |
| **Research** | .copilot-tracking/research/2026-06-29/bug-0054-cutover-fix-research.md |
| **Planning Log** | .copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-fix-log.md |
| **Details** | .copilot-tracking/details/2026-06-29/bug-0054-cutover-fix-details.md |
| **RPI Validation (Phase 2)** | .copilot-tracking/reviews/rpi/2026-06-29/bug-0054-cutover-fix-plan-002-validation.md |
| **Impl Quality Validation** | .copilot-tracking/reviews/impl/2026-06-29/bug-0054-cutover-fix-impl-validation.md |

## Review Scope

The plan defines 5 phases. **Only Phase 2 (Durable Bicep idempotency hardening) was implemented this session** — it is the single repo-file-only, autonomous code unit. The other phases are intentionally out of autonomous scope:

- **Phase 1 (cutover)** + **Phase 3 (restore declarative provision)** are operator-run, confirmation-gated live-Azure mutations.
- **Phase 4 (close-out docs)** depends on Phase 1 validation.
- **Phase 5 (validation)** is partially satisfied — the infra-test + `az bicep build` portion that overlaps Phase 2.

Per-phase RPI validation therefore had substantive surface only for Phase 2. Phases 1/3/4/5 were reviewed for *correct deferral* (the Changes Log must not claim them as done) directly from the plan checkboxes + Changes Log.

## Summary

| Metric | Count |
|---|---|
| Critical findings | 0 |
| Major findings | 0 |
| Minor findings | 3 |
| Follow-up items | 4 |

Validation performed this turn:

- RPI Validator (Phase 2) — VALIDATED, 0 critical / 0 major / 2 minor; DD-02 deviation assessed SOUND.
- Implementation Validator (full-quality) — subagent Blocked (read-only tooling); findings produced by reviewer via direct file reads + test run: PASS, 0 critical / 0 major / 3 minor.
- Validation commands — infra test 36/36 green; `get_errors` clean; `az bicep build` EXIT=0 (confirmed by RPI Validator).

## Re-Review Addendum — 2026-06-29 (work since the initial review)

Since the initial review (the sections below), the implementer addressed all three minor findings (explicit user authorization ID-00) and the operator ran a full clean-slate `azd provision` (decision ID-01). **This addendum supersedes the historical "Overall Status" verdict at the bottom of this log.**

### Prior minor findings — all RESOLVED ✅

| Finding | Resolution | Evidence |
|---|---|---|
| M-1 (stale `main.json`) | Deleted + gitignored | `v2/infra/main.json` absent (file search: not found); ignore rule `infra/main.json` at `v2/.gitignore:20` |
| M-2 (`.id` vs `!.id`) | Normalized to `existingOpenAi!.id` | `v2/infra/main.bicep:1055` |
| M-3 (un-hoisted role GUID) | Hoisted to `var cognitiveServicesOpenAiUserRoleId` | declared `v2/infra/main.bicep:133`; referenced 7× (`:602,:704,:709,:1043,:1048,:1055,:1060`); only the declaration carries the literal |

Test coverage extended in lockstep — `v2/tests/infra/test_main_bicep.py` now pins the full deterministic `guid(...cognitiveServicesOpenAiUserRoleId))` expression on both names (`:688`,`:693`), asserts the `var` declaration (`:695-701`), keeps the negative pin on `'search-system-mi'` (`:721`), and pins the EG `queueName: blobEventsQueueName` invariant (`:233`). **36/36 infra tests pass; `az bicep build` EXIT=0 (no BCP120).** All three fixes are value-identical at compile time — no role-assignment `guid()` name changed, so no new orphan risk.

### Live re-provision (ID-01) — PARTIAL ⚠️ (one operational blocker, not a code defect)

The prior environment was entirely torn down (DR-06), so a full clean-slate `azd provision` ran against the hardened template. Outcome:

- **Provisioned green:** resource group, Log Analytics, Container Registry, App Insights, Container Apps Environment, Storage, Cosmos DB, both App Service plans, all three Cognitive Services accounts (Speech / Foundry AI Services / Content Safety) + 3 model deployments + Foundry project + project↔Search connection, **Search service, and the Function App**.
- **Phase 2 hardening proven in the wild:** on the clean slate the Search service's role assignments were created cleanly (`code=Created`) with **no `RoleAssignmentExists` conflict** — exactly the idempotency outcome Phase 2 targeted. The orphan `70d96d3a…` that blocked the pre-teardown run is gone with the old RG.
- **One failure — Container App `ca-backend-<SUFFIX>`:** `MANIFEST_UNKNOWN: manifest tagged by "latest" is not found` for `cr<SUFFIX>.azurecr.io/cwyd-backend:latest`. **Root cause: `azd provision` was run standalone, so no image has been built/pushed yet.** The backend image is produced by `azd deploy` (or `azd up`, which sequences package → provision → deploy). This is a deploy-sequencing gap, **not a Bicep defect and unrelated to the reviewed Phase 2 change.**

### Updated status of plan phases

- **Phase 2** — ✅ complete + clean (unchanged); the three follow-up minors are now resolved.
- **Phase 1 (live cutover validation), Phase 4 (close-out docs), Phase 5 (validation gate)** — still `[ ]`. The bug-closing live validation (Step 1.6 create/delete e2e) and the `bugs.md`/worklog close-out have **not** run.
- **BUG-0054 remains OPEN.** The durable intent (`AZURE_ENV_INGESTION_TRIGGER=event_grid`) is set and the template deploys the single `event_grid` path, but no live ingestion has been validated.

### Re-review severity counts

| Metric | Count |
|---|---|
| Critical findings | 0 |
| Major findings (code) | 0 |
| Minor findings (open) | 0 (all 3 prior minors resolved) |
| Operational blockers | 1 (backend image not pushed — run `azd deploy`/`azd up`) |

### Recommended next steps (operator)

1. `azd deploy` (or re-run `azd up`) to build+push the backend/frontend/functions images and complete the Container App revision.
2. Run Phase 1 Step 1.6 live validation — upload a doc → confirm single-path Event Grid ingestion + citation; delete → confirm de-index; **clean up the test doc** (cleanup-before-next-step).
3. Run Phase 4 close-out docs (flip BUG-0054 → `fixed` in `v2/docs/bugs.md` + add the discrete static-salt `BUG-####` row + append the worklog) and the Phase 5 validation gate.

## RPI Validation Findings (per phase)

### Phase 2 — Durable Bicep idempotency hardening — ✅ VALIDATED

All three steps trace to verified changes:

- **Step 2.1/2.2 (role-assignment names hardened)** — `searchOpenAiUserOnFoundry` name at `v2/infra/main.bicep:1039`; `searchOpenAiUserOnReusedOpenAi` name at `v2/infra/main.bicep:1051`. Both now `guid(<scope>.id, 'srch-${solutionSuffix}', subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-...'))`. The literal `'search-system-mi'` is absent from `main.bicep`.
- **Step 2.3 (EG queue invariant)** — both blob subscriptions pinned to `blob-events` via `queueName: blobEventsQueueName` (`main.bicep:2421`, `:2487`).
- **Test-first** — guards land with the code in `v2/tests/infra/test_main_bicep.py`; 36/36 green.

**DD-02 deviation — verdict: SOUND.** The plan/details specified salting the `guid()` on the deploy-time `systemAssignedMIPrincipalId`. A `roleAssignments` `name` must resolve at template start-time, so that output triggers **BCP120**. The implementation salts on the start-time `'srch-${solutionSuffix}'` (the suffix-derived Search service name) instead, while still binding the real principal via `properties.principalId`. The deviation is (a) forced by the compiler, (b) dual-logged (Changes Log DD-02 + Planning Log DD-02), (c) idempotency-preserving (deterministic, collision-safe, re-run-stable, `'search-system-mi'`-free), and (d) mirrors the existing `existingOpenAiUamiRole` `guid(scope.id, uami.name, role)` precedent at `main.bicep:699-708`. Does not undermine the phase objective.

### Phases 1, 3, 4, 5 — deferral check — ✅ CORRECTLY DEFERRED (no deviation)

- Plan checkboxes for Phases 1/3/4/5 remain `[ ]`; only Phase 2 steps are `[x]`.
- The Changes Log explicitly records Phases 1/3 as operator-gated, Phase 4 as deferred, and marks Added/Removed/Release Summary as "(pending)".
- No phase is falsely claimed complete. The deferral is honest and matches the plan's `parallelizable`/operator-run markers and the Planning Log. **This is correct project hygiene, not a missing-work defect** — the work is genuinely outside the autonomous-execution boundary.

## Implementation Quality Findings

PASS (reviewer-produced; subagent Blocked on tooling). By category:

| Category | Result | Evidence |
|---|---|---|
| Bicep correctness | PASS | `.id` resolves under the same `if(...)` guard as each `existing` symbol (`main.bicep:1034`/`1038`; `existingOpenAi`/`1050`); no BCP318/unresolved-ref risk |
| Idempotency objective | PASS | `guid()` byte-stable per `(scope, suffix, roleDef)`; principal bound via `properties.principalId` (`:1043`, `:1055`) |
| Naming-convention drift (HR #11) | PASS | Only `name:` guid args changed; symbols/scope/role/principal untouched |
| Test quality | PASS | Exact full-expression positive pins + negative pin on `'search-system-mi'`; `count(...)==2` on EG queue; bidirectional regression coverage, not brittle |
| Security / least-privilege | PASS | Role/scope/principal unchanged; no broadening |
| Hard Rule #18 (no env content) | PASS | Only literal is the built-in role GUID (carve-out) |

## Validation Command Outputs

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/infra/test_main_bicep.py -q` (from `v2/`) | **36 passed in 0.06s** |
| `get_errors` on `main.bicep` | Only a benign "file missing from workspace" context warning (not a compile error) |
| `get_errors` on `test_main_bicep.py` | No errors found |
| `az bicep build --file v2/infra/main.bicep` | EXIT=0, no BCP120 (confirmed by RPI Validator this session) |

## Missing Work and Deviations

**Deviations (both recorded, both sound):**

- **DD-01** — Bicep hardening bundled into the cutover plan (rather than a separate change). Documented; low impact.
- **DD-02** — BCP120-forced salt swap (`'srch-${solutionSuffix}'` for `systemAssignedMIPrincipalId`). Documented; low impact; idempotency preserved (see Phase 2 finding above).

**Missing work (out of autonomous scope, correctly deferred — not defects):**

- **Phase 1** — operator cutover: `az containerapp update` flip of `AZURE_INGESTION_TRIGGER` → `event_grid` on the backend Container App, re-validate ingestion, drain poison queue. **This is the action that actually closes BUG-0054.**
- **Phase 3** — operator `azd provision` to restore declarative provisioning (now unblocked by the Phase 2 hardening once the orphan `<ORPHAN_ROLE_ASSIGNMENT_GUID>` is removed).
- **Phase 4** — close-out docs (flip BUG-0054 → fixed in `bugs.md`, add a discrete static-salt BUG row, worklog entry) — gated on Phase 1 validation.

## Follow-Up Work

**Deferred from scope (in the plan, not yet executed — operator action):**

1. Run Phase 1 cutover (single env-var flip) — **closes BUG-0054**.
2. Run Phase 3 `azd provision` restore (delete orphan role assignment `<ORPHAN_ROLE_ASSIGNMENT_GUID>`, then provision to confirm idempotency).
3. Run Phase 4 close-out docs after Phase 1 validates.

**Discovered during review (repo hygiene, out of Phase 2 scope):**

4. **M-1 — `v2/infra/main.json` is stale.** The git-tracked pre-compiled ARM still contains `'search-system-mi'` (`main.json:571`, `:586`). No runtime impact (`azure.yaml` uses `provider: bicep` / `module: main`, so `azd` compiles `main.bicep` directly and never reads `main.json`). Decide: regenerate to stay salt-free, or remove + gitignore. *(Open question raised by the RPI Validator — operator/maintainer decision.)*

**Minor, no action required:**

- **M-2 (cosmetic)** — `existingOpenAi.id` (`:1051`) vs `existingOpenAi!.id` (`:702`) null-assertion inconsistency; both compile clean.
- **M-3 (pre-existing)** — the role-def GUID `5e0bd9bd-...` is not hoisted to a Bicep `var` despite repeated use; pre-existing, not worsened by this change; do not back-fill inline (HR #12).

## Overall Status

> **Superseded by the Re-Review Addendum (2026-06-29) above** — the three minor findings are now resolved and a full clean-slate `azd provision` has run (all resources green except the backend Container App, which needs `azd deploy`/`azd up` to push its image). BUG-0054 remains OPEN pending live validation. The verdict below is the historical initial-review record.

🚫 **Blocked** (plan-level / BUG-0054 closure) — **with the implemented Phase 2 scope ✅ Complete and clean.**

- **Implemented scope (Phase 2):** ✅ Complete — 0 critical, 0 major, 3 minor (all out-of-scope follow-ups). Validated by RPI Validator + reviewer quality pass + 36/36 infra tests + clean `bicep build`. The one deviation (DD-02) is sound and dual-logged.
- **Plan primary objective (close BUG-0054):** 🚫 Blocked on **operator-gated cloud execution** — the bug-closing Phase 1 cutover (`az containerapp update` env-var flip) and the Phase 3 provision restore are confirmation-gated live-Azure mutations that cannot be performed in an autonomous review/implement context. This is an external dependency, **not a code defect**: the implemented hardening is correct, and the runbook to close the bug is documented in the plan/research.

**Reviewer note:** No rework is required on the implemented code. To complete the plan and close BUG-0054, an operator must run the documented Phase 1 cutover (and, to restore declarative provisioning, Phase 3). Do not interpret the green Phase 2 review as "BUG-0054 closed" — the trigger flip has not been applied to the cloud.
