# ADR 0014 — Frontend CI workflow (lint + typecheck + vitest)

- **Status**: Accepted
- **Date**: 2026-06-02
- **Phase**: Phase 7 close-out (FE conventions refactor — follow-up CI wiring after `U-P7-FE-REFAC-5`)
- **Pillar**: Stable Core (frontend type-safety enforcement surface)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR wires the CI gate that [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) §"Decision/2" promised but deferred (the `U-P7-FE-REFAC` debt row in `development_plan.md` §0.1 closed locally-green with the CI step left as a follow-up).

## Context

[ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) ratified three coordinated FE policies in one block: extra strict `tsconfig.json` flags, ESLint `strict-type-checked` + `stylistic-type-checked`, and `.tsx` everywhere. The ADR's Decision §2 stated:

> `npm run lint` is CI-gated; the FE lint step fails the build on any error.

At the time `U-P7-FE-REFAC` shipped (2026-06-02), the repository had two v2-scoped CI workflows:

- `.github/workflows/v2-typecheck.yml` — `pyright --strict` over `v2/src/**/*.py`.
- `.github/workflows/v2-backend-only-smoke.yml` — Path A router smoke against the backend-only docker compose profile.

**No v2 FE workflow existed.** The v1 workflow `.github/workflows/tests.yml` ran `make unittest-frontend` and `make lint` against `code/frontend/`, but its path scope and Makefile targets were v1-only. Creating a new top-level workflow file is a structural change governed by Hard Rule #10 in [`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md) ("ask before changing structure"), so `U-P7-FE-REFAC-4` and `U-P7-FE-REFAC-5` closed with the local gate green (`tsc --noEmit` 0 errors, `npm run lint` 0 errors, `vitest run` 147/147) and the CI workflow itself left as an explicit user-confirmed follow-up — documented in the `U-P7-FE-REFAC` row tail and in §0 status row 7.

The user confirmed the follow-up on 2026-06-02. This ADR records the resulting CI wiring.

## Decision

The repository ships a new GitHub Actions workflow at [`.github/workflows/v2-frontend-checks.yml`](../../../.github/workflows/v2-frontend-checks.yml) that runs three sequential hard-gated checks against the `v2/src/frontend` package on every push to `main` and on every PR targeting `main`.

### 1. Path-scoped triggers

The workflow fires only when one of these globs matches a changed file:

- `v2/src/frontend/**`
- `.github/workflows/v2-frontend-checks.yml`

Edits outside the FE tree pay zero CI cost. Same path-scope discipline as `v2-typecheck.yml` and `v2-backend-only-smoke.yml`.

### 2. Three sequential checks (all hard-gated, no `continue-on-error`)

| Step | Command | Gates |
|---|---|---|
| 1. Lint | `npm run lint` | ESLint 9.39.4 flat config, `tseslint.configs.strictTypeChecked` + `stylisticTypeChecked`, scoped to `src/**` + `tests/**`. Build fails on any error. |
| 2. Typecheck | `npx tsc -p .` | tsc 5.7 strict mode + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` (per ADR 0013); `noEmit: true` in `tsconfig.json`, so the step is pure type-check. |
| 3. Tests | `npm test` (`vitest run`) | 147 vitests across 18 suites at time of wiring. Build fails on any failed test. |

Steps run in order; a failing step short-circuits the rest. Lint runs first because it's the cheapest gate and the most common failure mode after the strict-type-checked rollout.

### 3. Toolchain pins

- `actions/checkout@v6` — same version as `v2-typecheck.yml` and `v2-backend-only-smoke.yml`.
- `actions/setup-node@v6` with `node-version: 20` and `cache: "npm"`, cache key derived from `v2/src/frontend/package-lock.json`. Node 20 matches the v1 FE workflow in `tests.yml` and the active LTS line at workflow-creation time.
- `npm ci` for install — frozen lockfile, zero install drift.
- Working dir `v2/src/frontend` set once via `defaults.run.working-directory`.

## Consequences

### Positive

- **ADR 0013 promise is now enforced.** A regression on any of the three strict-type-checked gates (lint, tsc strict, vitest) fails the PR build instead of relying on local developer discipline. The two pain points cited in ADR 0013 §Context (`noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` catching real bugs) now have CI teeth.
- **Symmetric with backend CI surface.** Backend has `pyright --strict` hard-gated via `v2-typecheck.yml`. Frontend now has `lint + tsc + vitest` hard-gated via `v2-frontend-checks.yml`. One CI story per side.
- **Cheap incremental cost.** Path-scoped triggers + `setup-node` cache keep the marginal cost near-zero for unrelated PRs.
- **Closes a tracked debt-style follow-up.** The `U-P7-FE-REFAC` row in `development_plan.md` §0.1 explicitly named "creating a `v2-frontend-checks.yml` is structural per Hard Rule #10 and is left as a separate user-confirmed follow-up." This ADR + the workflow file together close that follow-up.

### Negative

- **PR build cost on FE-touching PRs grows by ~1 job (Node 20 + npm ci + lint + tsc + vitest).** Bounded by the FE LOC and the test suite size; acceptable for the regression-catching benefit.
- **Lint failures are now blocking.** Before this workflow, a contributor could land FE changes that introduced new lint errors as long as `tsc --noEmit` was clean locally. After this workflow, any new lint error fails the PR. This is the intended behavior — the cost is a one-time recalibration of contributor habit.

### Neutral

- **No `coverage` artifact upload.** The backend `pyright` workflow uploads `pyright-report.json` for reviewer triage. The FE workflow does not upload coverage today because the dev_plan does not call for an FE coverage gate. If a future ADR proposes one (e.g. minimum line/branch coverage), the workflow can grow an `actions/upload-artifact@v6` step at that time.
- **`npm test` is `vitest run`, not `vitest --coverage`.** Coverage instrumentation is off by default; turning it on is a separate decision.

## Alternatives considered

1. **Add the FE steps to the existing `v2-typecheck.yml` workflow.** Rejected — `v2-typecheck.yml` is path-scoped to `v2/src/**/*.py` and runs `uv sync` for pyright. Mixing FE + BE in one workflow couples their lifecycles (Node setup pays even on Python-only PRs and vice versa, unless we split jobs) and conflates "what failed?" attribution. A dedicated workflow keeps the surface clean.
2. **Extend the v1 `tests.yml` workflow to also run v2 FE checks.** Rejected — `tests.yml` is the v1 surface (root `code/`, root `tests/`, `make` targets). Extending it back-pressures v2 onto a v1-shaped harness. v2 has its own workflow naming pattern (`v2-*.yml`).
3. **Drop the typecheck step (rely on ESLint type-aware rules).** Rejected — ESLint `strict-type-checked` uses the TypeScript program internally but does not run every tsc diagnostic. tsc strict mode + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` catch a strictly larger set of errors than the ESLint rules do; running both is the cheapest way to get full coverage.
4. **Add a `typecheck` script to `package.json`** (e.g. `"typecheck": "tsc -p ."`). Acceptable but not required for this ADR. Calling `npx tsc -p .` directly from the workflow keeps `package.json` minimal; the same command is what a developer would run locally to reproduce the failure. A `typecheck` script can be added later without changing the CI contract.
5. **Run `npm run build` instead of `tsc -p .`.** Rejected — `npm run build` is `tsc -b && vite build`. The `vite build` half produces production bundles, which CI doesn't ship anywhere; paying for it is waste.
6. **Run `npm install` instead of `npm ci`.** Rejected — `npm install` mutates `package-lock.json` if drift is detected, producing non-deterministic CI runs. `npm ci` errors on drift, which is the correct CI behavior.

## References

- [`.github/workflows/v2-frontend-checks.yml`](../../../.github/workflows/v2-frontend-checks.yml) — the workflow this ADR wires.
- [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) — the prior ADR whose Decision §2 ("`npm run lint` is CI-gated") this ADR fulfills.
- [`.github/workflows/v2-typecheck.yml`](../../../.github/workflows/v2-typecheck.yml) — backend pyright workflow; the structural template this FE workflow mirrors.
- [`.github/workflows/v2-backend-only-smoke.yml`](../../../.github/workflows/v2-backend-only-smoke.yml) — backend smoke workflow; same path-scope + hard-gate discipline.
- [`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md) Hard Rule #10 — "ask before changing structure" — the rule that gated this workflow creation on explicit user confirmation.
- [`v2/src/frontend/package.json`](../../src/frontend/package.json) — `scripts.lint` (`eslint .`) and `scripts.test` (`vitest run`).
- [`v2/src/frontend/tsconfig.json`](../../src/frontend/tsconfig.json) — strict flag set + `noEmit: true` (so `tsc -p .` is type-check only).
- [`development_plan.md`](../development_plan.md) `U-P7-FE-REFAC` row — the FE conventions refactor row whose deferred CI follow-up this ADR closes.
