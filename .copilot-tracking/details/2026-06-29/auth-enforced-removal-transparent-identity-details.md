<!-- markdownlint-disable-file -->
# Implementation Details: Remove `auth_enforced`, adopt transparent Easy-Auth-probe identity

## Context Reference

Sources:
* Primary research: .copilot-tracking/research/2026-06-29/auth-enforced-removal-transparent-identity-research.md
* Backend subagent research: .copilot-tracking/research/subagents/2026-06-29/backend-auth-enforced-userid-research.md
* Frontend subagent research: .copilot-tracking/research/subagents/2026-06-29/frontend-auth-enforced-identity-research.md
* Selected approach: Scenario A — delete the `auth_enforced` health signal + `AuthBlocked` screen; the SPA resolves identity purely from Easy Auth `/.auth/me` (principal → real userId, else `DEFAULT_USER_ID`); keep `require_admin_auth` as the orthogonal opt-in admin-write gate.

CWYD conventions in force: Hard Rule #1 (one unit/turn), #2 (test-first), #11 (StrEnum / no `__future__` / no `TYPE_CHECKING`), #12 (defect-vs-debt; the stale RED test is tracked, not "fixed"), #16 (no process narrative in `v2/src/**` — when rewriting docstrings, describe what the code IS), #19 (worklog + bugs.md). config-defaults-dev-first memory: never invert the `Environment.LOCAL` default; this removal deletes a derived UI signal, not a default.

## Implementation Phase 1: Backend — remove the `auth_enforced` health signal

<!-- parallelizable: true -->

Files touched are backend-only (`v2/src/backend/services/**`, `v2/src/backend/models/**`, `v2/tests/backend/**`) and have no build dependency on the frontend phase. The `/api/health` payload is read by the SPA from an UNTYPED payload that treats a missing `auth_enforced` as `false`, so dropping the field does not break the frontend even if shipped independently. CWYD executes one unit per turn (Hard Rule #1), so in practice this phase runs as a single backend unit before or after Phase 2.

### Step 1.1: Drop `auth_enforced` from the health contract (model + producer) and update backend health tests

Remove the field from the Pydantic model, remove the one producer line, and align the backend health tests in the SAME turn (test-first contract, Hard Rule #2 — the assertions move with the code).

Files:
* v2/src/backend/models/health.py - delete the `auth_enforced: bool = False` field (line ~46) from `HealthResponse`; delete the docstring sentence describing `auth_enforced` (lines ~39-41). Leave `status`, `version="v2"`, `checks`. Per Hard Rule #16, the rewritten docstring describes only what the model carries — no removal narrative.
* v2/src/backend/services/health.py - delete the `auth_enforced=settings.require_admin_auth,` line (line ~61) from the `HealthResponse(...)` construction inside `run_health_checks`. `settings` is still consumed by the three `_check_*` probes, so the signature is unchanged.
* v2/tests/backend/test_health.py - delete the `assert body["auth_enforced"] is False` line in `test_health_returns_200_when_all_checks_pass` (line ~229); delete both signal tests `test_health_auth_enforced_false_when_open_in_production` and `test_health_auth_enforced_true_when_admin_wall_on` (lines ~235-267); update the wire-key lock in `test_health_response_model_shape` (line ~343) from `{"status", "version", "auth_enforced", "checks"}` to `{"status", "version", "checks"}`.
* v2/tests/backend/test_services_health.py - delete the `auth_enforced` section header + both tests `test_run_health_checks_auth_enforced_false_when_local` and `test_run_health_checks_auth_enforced_true_when_production` (lines ~223-238). The latter is already RED against current code (stale `environment is PRODUCTION` rule); it is removed intentionally with the signal, recorded as debt per Hard Rule #12 (see Planning Log DD-02).

Discrepancy references:
* Addresses the root-cause field behind the open-prod "Authentication Not Configured" regression (research Key Discoveries).
* DD-02 (Planning Log): the stale RED `..._true_when_production` test is deleted, not fixed.

Success criteria:
* `HealthResponse` exposes exactly `status`, `version`, `checks`; no `auth_enforced` anywhere in `v2/src/backend/**`.
* `GET /api/health` and `GET /api/health/ready` still return 200 / 503-on-fail with the slimmer model (no router change needed).
* `uv run python -m pytest v2/tests/backend/test_health.py v2/tests/backend/test_services_health.py -q` passes; the wire-key set assertion is green.
* `grep -rn "auth_enforced" v2/src/backend` returns no matches.

Context references:
* Backend subagent research §1, §2, §7, §8 - producer, model, tests, removal decision.

Dependencies:
* None (entry phase).

### Step 1.2: Validate backend phase changes

Run the backend gates scoped to the change. Skip the cross-tree `auth_enforced` grep until both code phases land if Phase 2 runs in parallel (the grep over `v2/src/frontend` belongs to Phase 2's validation).

Validation commands:
* `uv run python -m pytest v2/tests/backend/test_health.py v2/tests/backend/test_services_health.py -q` - backend health suites.
* `uv run python -m pytest v2/tests/shared/test_no_process_narrative_in_src.py -q` - Hard Rule #16 gate (docstring edits stay description-only).
* `grep -rn "auth_enforced" v2/src/backend` - expect zero matches.

## Implementation Phase 2: Frontend — delete the gate; resolve identity from `/.auth/me`

<!-- parallelizable: true -->

Files touched are frontend-only (`v2/src/frontend/**`, `v2/tests/frontend/**`); independent of Phase 1. Internally the steps are SEQUENTIAL by build dependency: `models/auth.tsx` → `hooks/useAuth.tsx` → `App.tsx` → component deletion. Each step lands with its test edits in the same turn (Hard Rule #2). The transparent rule is the behavior the code already produces when `authEnforced` is forced `false`, so this is deletion of a gate, not new logic.

### Step 2.1: Collapse the `AuthState` model — drop `AuthPhase.Blocked` and `AuthState.authEnforced`

Files:
* v2/src/frontend/src/models/auth.tsx - remove `Blocked: "blocked"` from the `AuthPhase` const (line ~52) so the closed set becomes `Loading | Resolved`; remove the `authEnforced: boolean;` field from `AuthState` (line ~60); update the surrounding docstrings (lines ~43-48, ~56) to describe the two-phase set and the principal-or-default state — no enforcement / Blocked narrative.
* v2/tests/frontend/models/auth.test.tsx - remove `Blocked` from the `AuthPhase` member + closed-set assertions and from the literal-union type test; remove `authEnforced` from the `AuthState` shape literal (line ~76) and its assertion (line ~81).

Success criteria:
* `AuthPhase` is exactly `{ Loading, Resolved }`; `AuthState` has no `authEnforced`.
* `npx vitest run tests/frontend/models/auth.test.tsx` passes.

Context references:
* Frontend subagent research §7 (models rows), §9 (files to change).

Dependencies:
* None within Phase 2 (first step).

### Step 2.2: Make `useAuth.resolve` single-arg (`resolve(userInfo)`) and delete the Blocked branch

Files:
* v2/src/frontend/src/hooks/useAuth.tsx - change the `resolve` interface + callback signature from `(authEnforced, userInfo)` to `(userInfo)` (lines ~38, ~50); delete the `if (authEnforced) { … Blocked … }` branch (lines ~62-74); drop `authEnforced` from `INITIAL_AUTH_STATE` (line ~31) and from both surviving `setAuth({...})` calls (lines ~57, ~79); rewrite the docstring (lines ~6-20) to the transparent rule (signed-in → real id; else default user) with no enforcement narrative (Hard Rule #16).
* v2/tests/frontend/hooks/useAuth.test.tsx - switch all `resolve(...)` calls to the single-arg signature; delete the "blocks when auth is enforced but no user resolved" test and the "resolves the signed-in user even when auth is enforced" variant (folds into the plain resolved-user case); drop every `authEnforced` field assertion (lines ~40, ~55, ~69, ~84, ~101).

Success criteria:
* `useAuth` exposes `resolve(userInfo: UserInfo | null)`; no `authEnforced`, no `Blocked` state is reachable.
* `npx vitest run tests/frontend/hooks/useAuth.test.tsx` passes.

Context references:
* Frontend subagent research §7 (useAuth rows), §8.3 (test names), §9.

Dependencies:
* Step 2.1 (model no longer has `Blocked` / `authEnforced`).

### Step 2.3: Strip the gate from `App.tsx` — remove `readAuthEnforced`, the `AuthBlocked` branch, and the `authEnforced` arg

Files:
* v2/src/frontend/src/App.tsx - delete the `AuthBlocked` import (line ~41); delete `readAuthEnforced` (lines ~95-109); in the bootstrap effect drop the `authEnforced` computation (lines ~148-149) and call `resolve(userInfo)` (line ~152); delete the `if (auth.phase === AuthPhase.Blocked) { … <AuthBlocked /> … }` branch (lines ~181-188); remove the now-unused `AuthPhase` import (line ~54) if nothing else references it; update the module docstring (lines ~17-25, ~95) to drop the `auth_enforced` / `AuthBlocked` narrative (Hard Rule #16).
* v2/tests/frontend/AppAuthBootstrap.test.tsx - remove `authEnforced` from the `stubFetch({ authEnforced, signedIn })` helper and the `/api/health` stub (line ~63); delete the two enforcement-blocked cases ("renders the blocked screen when auth is enforced …" and "forwards the default user when auth is enforced but no principal resolves" / "keeps the blocked screen hidden …" enforcement variants); KEEP the principal-resolved, default-fallback, and `/.auth/me`-origin cases — they become the transparent rule's full coverage.

Success criteria:
* `App.tsx` contains no `auth_enforced` / `AuthBlocked` / `AuthPhase.Blocked` reference; identity resolves from `getUserInfo()` alone.
* `npx vitest run tests/frontend/AppAuthBootstrap.test.tsx` passes; a not-signed-in bootstrap resolves to `DEFAULT_USER_ID` and renders the app shell (never a blocked screen).

Context references:
* Frontend subagent research §1 (bootstrap effect + Blocked branch), §8.2 (test names), §9.

Dependencies:
* Step 2.2 (single-arg `resolve`).

### Step 2.4: Delete the `AuthBlocked` component and its test

Files:
* v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx - delete (whole file).
* v2/src/frontend/src/components/AuthBlocked/AuthBlocked.module.css - delete (whole file; the `components/AuthBlocked/` directory has no other contents and no `index` barrel).
* v2/tests/frontend/components/AuthBlocked.test.tsx - delete (whole file; it is entirely AuthBlocked-specific).

Use `git rm` (or the terminal `Remove-Item`) for the deletions; do not leave empty directories.

Success criteria:
* `components/AuthBlocked/` no longer exists; no production importer remains (`App.tsx` import was removed in Step 2.3).
* `grep -rn "AuthBlocked\|auth-blocked\|Authentication Not Configured" v2/src/frontend v2/tests/frontend` returns no matches.

Context references:
* Frontend subagent research §2 (component is client-side, only importer was `App.tsx`), §8.1 (test to delete).

Dependencies:
* Step 2.3 (import already removed, so deletion breaks nothing).

### Step 2.5: Validate frontend phase changes

Validation commands:
* `npx vitest run tests/frontend/models/auth.test.tsx tests/frontend/hooks/useAuth.test.tsx tests/frontend/AppAuthBootstrap.test.tsx` - the three rewritten suites.
* `npm run build` (frontend) or `npx tsc --noEmit` - type-check the gate removal (no dangling `AuthPhase.Blocked` / `authEnforced` references).
* `grep -rn "auth_enforced\|authEnforced\|AuthBlocked\|auth-blocked\|Authentication Not Configured" v2/src/frontend v2/tests/frontend` - expect zero matches.

## Implementation Phase 3: Documentation & guidance sync (Hard Rule #0 / #19)

<!-- parallelizable: false -->

Records the behavior change and retires guidance that now contradicts the code. Runs after the code phases so the worklog / bugs entries describe the shipped result accurately. Writes are under `v2/docs/**` only.

### Step 3.1: Retire the `auth_enforced` design rows and log the behavior change

Files:
* v2/docs/frontend-user-identity-plan.md - mark the `auth_enforced` fold (D2) and the `AuthBlocked` port (F10) as superseded by the transparent Easy-Auth-probe rule; do not delete history, annotate it as retired with a pointer to the new behavior.
* v2/docs/bugs.md - add a `BUG-####` row (next sequential id) recording that the `auth_enforced` signal was removed (root cause: a frontend-only UI flag derived from `require_admin_auth` produced an "Authentication Not Configured" wall on open deploys); closed-set Area/Severity/Status per the registry convention.
* v2/docs/worklog/2026-06-29.md - append (do not open a second file for the date) the plan + outcome: the transparent identity rule, files removed, `require_admin_auth` retained as the orthogonal admin gate.

Discrepancy references:
* DR-01 (Planning Log): docs are out of scope for the code gates but required by Hard Rule #0/#19; flagged because Task Planner cannot edit `v2/docs/**` directly — the implementer performs this step.

Success criteria:
* No tracked guidance instructs the SPA to read `auth_enforced` or render `AuthBlocked`.
* `bugs.md` carries one new sequential row; `worklog/2026-06-29.md` carries the behavior-change entry.
* Hard Rule #18 placeholders only — no env-specific values.

Context references:
* Primary research "Potential Next Research" + "Project Conventions".

Dependencies:
* Phase 1 and Phase 2 complete (entries describe the shipped change).

## Implementation Phase 4: Validation

<!-- parallelizable: false -->

### Step 4.1: Run full project validation

* `uv run python -m pytest v2/tests/backend -q` - full backend suite (health contract + dependencies unaffected).
* `uv run python -m pytest v2/tests/shared -q` - the invariant gates (process-narrative, init-marker, imports-at-top, no-silent-excepts, etc.).
* `npx vitest run` (from `v2/src/frontend`) - full frontend suite.
* `npm run build` (frontend) - production build / type-check.
* `grep -rn "auth_enforced\|authEnforced\|AuthBlocked\|auth-blocked\|Authentication Not Configured" v2/src v2/tests` - expect zero matches across both tiers.

### Step 4.2: Fix minor validation issues

Iterate on type errors, dangling imports, or stale snapshots surfaced by the gates. Apply fixes directly when isolated (e.g., an orphaned `AuthPhase` import, a leftover `authEnforced` in an untouched test helper).

### Step 4.3: Cloud verification (binding project directive) and report blocking issues

Per the standing CWYD directive — "we deploy our new cwyd v2 code to the cloud and we test; any other approach is not valid" — after green local gates:
* `azd deploy backend` then `azd deploy frontend` (from `v2/`, after `Set-Location v2`).
* Verify live `/api/health` no longer carries `auth_enforced` (curl the backend health URL; body keys = `status`, `version`, `checks`).
* Reload the frontend; confirm NO "Authentication Not Configured" screen, the header shows "Guest", and a chat question returns a grounded answer.
* Clean up any test artifacts created during verification (cleanup-before-next-step memory).
Document any failure requiring more than a minor fix as a blocking issue with recommended follow-up planning rather than fixing inline.

## Dependencies

* `uv` (Python env), `npx vitest` / `npm` (frontend), `azd` (cloud verification).
* Easy Auth `/.auth/me` available on the frontend origin when identity is enabled (no change required by this work).

## Success Criteria

* `auth_enforced` / `authEnforced` / `AuthBlocked` / "Authentication Not Configured" appear nowhere in `v2/src` or `v2/tests`.
* The SPA resolves identity from `/.auth/me`: principal → real `userId`; no principal → `DEFAULT_USER_ID` ("Guest"); never a blocked screen.
* `require_admin_auth` (`AZURE_REQUIRE_ADMIN_AUTH`), `get_user_id`, and `requires_role` are unchanged; admin-write protection still engages when an operator opts in.
* All backend, shared, and frontend gates green; cloud `/api/health` returns `{status, version, checks}` and the deployed SPA loads guest-by-default with working chat.
