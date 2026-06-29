<!-- markdownlint-disable-file -->
# Release Changes: Remove `auth_enforced`, adopt transparent Easy-Auth-probe identity

**Related Plan**: auth-enforced-removal-transparent-identity-plan.instructions.md
**Implementation Date**: 2026-06-29

## Summary

Delete the `auth_enforced` health signal and the `AuthBlocked` "Authentication Not Configured" screen so the CWYD v2 frontend resolves identity purely from Azure Easy Auth `/.auth/me` (principal → real `userId`, else the default guest user). `require_admin_auth` is retained unchanged as the orthogonal opt-in server-side admin-write gate (PD-01 → Option A / Scenario A).

## Changes

### Added

* v2/docs/worklog/2026-06-29.md - New worklog for the day recording the transparent-identity behavior change, file inventory, PD-01 (Scenario A), green local gates, and pending cloud verification.

### Modified

* v2/src/backend/models/health.py - Removed the `auth_enforced` field and its docstring sentence from `HealthResponse`; the model now carries `status`, `version`, `checks`.
* v2/src/backend/services/health.py - Removed the `auth_enforced=settings.require_admin_auth` argument from the `HealthResponse(...)` construction in `run_health_checks`; signature unchanged (`settings` still used by the `_check_*` probes).
* v2/tests/backend/test_health.py - Dropped the `auth_enforced` assertion, deleted the two `*_auth_enforced_*` tests, and narrowed the wire-key lock to `{"status", "version", "checks"}`.
* v2/tests/backend/test_services_health.py - Deleted the `auth_enforced` section header and both `test_run_health_checks_auth_enforced_*` tests.
* v2/src/frontend/src/models/auth.tsx - Removed `AuthPhase.Blocked` (closed set now `Loading | Resolved`) and `AuthState.authEnforced`.
* v2/src/frontend/src/hooks/useAuth.tsx - `resolve` is now single-arg `resolve(userInfo)`; deleted the Blocked branch; dropped `authEnforced` from `INITIAL_AUTH_STATE` and the `setAuth` calls.
* v2/src/frontend/src/App.tsx - Removed the `readAuthEnforced` helper, the `AuthBlocked` import + render branch, and the `authEnforced` argument; the bootstrap effect now calls `resolve(userInfo)`.
* v2/tests/frontend/models/auth.test.tsx - Updated to the two-member `AuthPhase` set and dropped `authEnforced` from the `AuthState` shape assertions.
* v2/tests/frontend/hooks/useAuth.test.tsx - Switched `resolve(...)` calls to single-arg; removed the Blocked-branch and `authEnforced` cases.
* v2/tests/frontend/AppAuthBootstrap.test.tsx - Removed `authEnforced` from the fetch/health stubs and deleted the enforcement/blocked-screen cases; kept principal-resolved, default-fallback, and `/.auth/me`-origin cases.
* v2/docs/bugs.md - Appended BUG-0091 recording the removal of the `auth_enforced` signal + `AuthBlocked` screen (root cause: a frontend-only flag derived from `require_admin_auth` rendered a dead-end wall on open deploys).
* v2/docs/frontend-user-identity-plan.md - Added a supersession banner and "Retired 2026-06-29" notes on the rows describing the `auth_enforced` fold + `AuthBlocked` port (retired set D2/B1/F9/F10/F11); header-forwarding rows unchanged.
* v2/src/frontend/src/api/auth.tsx - Corrected four stale docstrings (the module header plus `getAuthMe`, `getUserInfo`, and the `DEFAULT_USER_ID` fallback) that still described the removed blocked-screen / enforcement behavior; now describe the transparent principal-or-default-guest resolution. Docstring-only — no behavior change (ESLint clean, `auth.tsx` type-checks).

### Removed

* v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx - Deleted the client-side "Authentication Not Configured" screen (only importer was `App.tsx`).
* v2/src/frontend/src/components/AuthBlocked/AuthBlocked.module.css - Deleted the component's styles; directory removed.
* v2/tests/frontend/components/AuthBlocked.test.tsx - Deleted the component's test.

## Additional or Deviating Changes

* PD-01 resolved as Option A (Scenario A): proceeding with implementation accepted the plan's default — `require_admin_auth` / `get_user_id` / `requires_role` are left unchanged.
* Phase 2 caught and removed an in-flight `readAuthEnforced` duplication while stripping `App.tsx` (clean-as-you-go); no residual dead code remains.
* v2/src/frontend/tsconfig.tsbuildinfo changed incidentally as a side effect of the Phase 2 `tsc` type-check gate (generated build artifact, not a source edit).

## Release Summary

All four phases complete; the `auth_enforced` health signal and the `AuthBlocked` "Authentication Not Configured" screen are fully removed, and the CWYD v2 SPA resolves identity transparently from Azure Easy Auth `/.auth/me` (principal → real `userId`, else the `DEFAULT_USER_ID` guest). `require_admin_auth` / `get_user_id` / `requires_role` are retained unchanged as the orthogonal opt-in admin-write gate (PD-01 → Scenario A).

**Files affected: 17** (1 added, 13 modified, 3 removed).

* **Added (1):** `v2/docs/worklog/2026-06-29.md`.
* **Modified (13):** backend — `models/health.py`, `services/health.py`, `tests/backend/test_health.py`, `tests/backend/test_services_health.py`; frontend — `src/models/auth.tsx`, `src/hooks/useAuth.tsx`, `src/App.tsx`, `src/api/auth.tsx`, `tests/frontend/models/auth.test.tsx`, `tests/frontend/hooks/useAuth.test.tsx`, `tests/frontend/AppAuthBootstrap.test.tsx`; docs — `docs/bugs.md`, `docs/frontend-user-identity-plan.md`.
* **Removed (3):** `src/frontend/src/components/AuthBlocked/AuthBlocked.tsx`, `AuthBlocked.module.css`, `tests/frontend/components/AuthBlocked.test.tsx`.

**Validation:** backend `pytest` + `pyright --strict` (0/0/0); frontend `vitest` (594/594) + `tsc` on the changed files green; shared AST gates green; ESLint clean on `auth.tsx`. Cloud deploy-and-test (binding directive) complete — live `/api/health` carries `{status, version, checks}` with no `auth_enforced`; the deployed SPA renders no blocking wall, resolves the Guest user by default, and returns a grounded answer with 7 citations over the SSE stream.

**Deployment notes:** no infrastructure or dependency changes; no OpenAPI regeneration (the health client is hand-written). Deployed via `azd deploy backend` + `azd deploy frontend` (frontend seed skipped to avoid index pollution).

**Out-of-scope observations (recorded, not fixed):** (1) BUG-0092 — the chat History panel uses the build-time `VITE_BACKEND_URL` instead of the runtime `getBackendUrl()` seam, so it 404s on the split-host cloud deploy; (2) a pre-existing, unrelated frontend `tsc -b` error (unused `formatActor` in the open #35d admin-merge `Configuration.tsx`, committed and untouched by this task).
