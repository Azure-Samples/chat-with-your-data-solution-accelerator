<!-- markdownlint-disable-file -->
# Task Research: Remove `auth_enforced` in favor of a transparent Easy-Auth-probe identity model

Investigate whether the `auth_enforced` signal (backend `GET /api/health` field + frontend
`AuthBlocked` gate) can be removed entirely and replaced with a self-evident rule:

> If the user enabled identity (Azure Easy Auth) in the frontend, probe `/.auth/me`, take the
> login + `userId` from the principal. If identity is not enabled (no principal), use the default
> `userId`. Period. No `auth_enforced` variable, no "Authentication Not Configured" screen.

## Task Implementation Requests

* Determine every backend and frontend consumer of `auth_enforced` / `authEnforced` so removal is complete.
* Determine how the frontend already resolves a user from Easy Auth (`/.auth/me`) and where the default user comes from.
* Determine how the backend resolves `userId` (`get_user_id`) and whether the open fallback already implements the "principal-or-default" rule.
* Decide whether `auth_enforced` (and `AuthBlocked`, `require_admin_auth` as a *health/UI* signal) can be deleted without breaking admin-route protection.
* Produce the transparent design: what to delete, what to keep, what tests change.

## Scope and Success Criteria

* Scope: v2 only (`v2/src/backend/**`, `v2/src/frontend/**`, `v2/tests/**`, `v2/infra/**`, `v2/docs/**`). v1 (`code/`) is provenance reference only.
* Assumptions:
  * Deployment is single-tenant and currently open (guest-by-default), per repo config-defaults-dev-first.
  * `require_admin_auth` / `AZURE_REQUIRE_ADMIN_AUTH` still legitimately gates **admin write routes** (upload/config) server-side — that is a separate concern from the frontend `auth_enforced` UI signal.
  * Easy Auth, when enabled, injects `/.auth/me` (frontend) and `X-MS-CLIENT-PRINCIPAL-*` headers (backend).
* Success Criteria:
  * Complete inventory of `auth_enforced` producers/consumers with file:line references.
  * Clear separation between (a) the frontend `auth_enforced` UI gate (candidate for deletion) and (b) backend admin-route enforcement (must remain).
  * A selected transparent approach with exact edit list + test impact, plus rejected alternatives with rationale.

## Outline

1. Backend: where `auth_enforced` is produced (`services/health.py`, `models/health.py`) and how `get_user_id` / `requires_role` resolve identity.
2. Frontend: where `auth_enforced` is consumed (`App.tsx`), the `AuthBlocked` component, the `/.auth/me` probe (`getUserInfo`), and the default-user fallback.
3. The design intent in `v2/docs/frontend-user-identity-plan.md` (D2 + F10) that introduced the flag.
4. Removal impact: tests, infra env vars, OpenAPI/health contract.
5. Transparent design + alternatives.

## Potential Next Research

* Hard Rule #0 sync-guidance: check `.github/instructions/v2-frontend.instructions.md`, `v2/docs/frontend-user-identity-plan.md` (D2/F10), and `v2/docs/bugs.md` for auth/identity policy text that must be updated alongside the code removal.
  * Reasoning: the plan + bugs log document the v1→v2 port of `auth_enforced`; removing it should retire those design rows so guidance does not contradict code.
  * Reference: `v2/docs/frontend-user-identity-plan.md:39,54,61,74`; `v2/docs/bugs.md:105,109,148,857`.
* Confirm no v2 e2e / Playwright spec outside `v2/tests/frontend/` asserts the `auth-blocked` testid before deleting the component.
  * Reasoning: deleting `AuthBlocked` breaks any out-of-tree spec referencing `data-testid="auth-blocked"`.
  * Reference: `v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx` testid.
* Whether the stale already-failing `test_run_health_checks_auth_enforced_true_when_production` should be tracked as a §0.1 debt row or simply deleted with the signal.
  * Reasoning: it is RED against current code (encodes the old `environment is PRODUCTION` rule); it disappears with the signal but should be acknowledged per Hard Rule #12/#19.
  * Reference: `v2/tests/backend/test_services_health.py:235-238`.

## Resolved (no longer open)

* **Is the health client generated?** No. The v2 frontend has **no OpenAPI client** (`api/admin.tsx:7`, `api/speech.tsx:6` both note "no OpenAPI generator wired in v2 yet"). Health is the inline `fetchHealth()` in `App.tsx`; `auth_enforced` is narrowed ad hoc from an `unknown` payload. **No codegen to regenerate** — removal is pure deletion.
* **Is `require_admin_auth` still needed?** Yes — it is the **orthogonal** server-side admin-write gate (`requires_role` → `AdminUserIdDep`). Its only coupling to `auth_enforced` is the single line `services/health.py:61`. Removing the signal does not weaken admin protection.

## Research Executed

Delegated to two parallel Researcher Subagents (backend + frontend). Full outputs:

* `.copilot-tracking/research/subagents/2026-06-29/backend-auth-enforced-userid-research.md`
* `.copilot-tracking/research/subagents/2026-06-29/frontend-auth-enforced-identity-research.md`

### File Analysis

Backend:

* `v2/src/backend/services/health.py:56-65` — `run_health_checks` is the **only** producer of the live `auth_enforced` value; line 61 is `auth_enforced=settings.require_admin_auth,`. The three checks need `settings`, so removing the field does not change the signature.
* `v2/src/backend/models/health.py:32-46` — `HealthResponse` fields: `status: OverallStatus`, `version: str = "v2"`, `checks: list[DependencyCheck]`, `auth_enforced: bool = False` (line 46, declared last). Docstring sentence at lines 39-41 describes the field.
* `v2/src/backend/routers/health.py:34-50` — `GET /api/health` and `GET /api/health/ready` both return `run_health_checks(settings)`; neither names `auth_enforced` (it rides inside the model).
* `v2/src/backend/dependencies.py:339-389` — `get_user_id`: principal header present + well-formed → return it; absent → `_LOCAL_DEV_USER` (`"local-dev"`) only when `allow_open_auth = environment is LOCAL or not require_admin_auth`; absent + wall on in prod → `401`. Does **not** reference `auth_enforced`.
* `v2/src/backend/dependencies.py:440-514` — `requires_role("admin")` → `REQUIRE_ADMIN_USER` → `AdminUserIdDep`: open-admin bypass keys on the **absent claims blob**; a present claims blob is **always** role-checked (403). Independent of `auth_enforced`.
* `v2/src/backend/core/settings.py:507-545` — `environment: Environment = Environment.LOCAL` (`AZURE_ENVIRONMENT`), `require_admin_auth: bool = False` (`AZURE_REQUIRE_ADMIN_AUTH`). Settings comment already states the admin wall is governed by `require_admin_auth`, separate from `environment`.

Frontend:

* `v2/src/frontend/src/App.tsx:95-109` — `readAuthEnforced(payload)` narrows `auth_enforced` off an untyped `unknown` health payload.
* `v2/src/frontend/src/App.tsx:137-167` — bootstrap effect: `loadRuntimeConfig()` → `fetchHealth()` → `readAuthEnforced` → `getUserInfo()` (`/.auth/me`) → `resolve(authEnforced, userInfo)`.
* `v2/src/frontend/src/App.tsx:181-188` — the **only** `AuthBlocked` render branch: `if (auth.phase === AuthPhase.Blocked) { return <CoralShellColumn><AuthBlocked /></CoralShellColumn>; }`.
* `v2/src/frontend/src/hooks/useAuth.tsx:50-83` — `resolve(authEnforced, userInfo)`: signed-in → `Resolved(real id)`; no user + enforced → `Blocked`; no user + not enforced → `Resolved(default)`. The last branch IS the desired transparent fallback.
* `v2/src/frontend/src/models/auth.tsx:52,60` — `AuthPhase.Blocked = "blocked"` and `AuthState.authEnforced: boolean` — both gate-only.
* `v2/src/frontend/src/api/auth.tsx:40,60-82` — `DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"`; `getUserInfo()` probes `/.auth/me`, returns `UserInfo | null` (null when no IdP / not signed in / no `oid` claim / fetch error — never throws).
* `v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx` — client-side Fluent v9 component (port of the v1 "Authentication Not Configured" screen); only production importer is `App.tsx:41`; no `index` barrel.
* `v2/src/frontend/src/components/Header/userIdentity.tsx:15` — `GUEST_NAME = "Guest"` (initials "G"); identity-display only; **no change needed**.

### Code Search Results

* `auth_enforced` / `authEnforced` producers + consumers: backend `services/health.py:61` (producer), `models/health.py:39,46`; frontend `App.tsx:19,95,100,104,107,145,148-149,152`, `hooks/useAuth.tsx:6,7,31,38,50,57,62,69,79`, `models/auth.tsx:60`; plus `AuthPhase.Blocked` at `models/auth.tsx:52` consumed by `App.tsx:181`, set by `useAuth.tsx:71`.
* `require_admin_auth` (orthogonal admin gate, **keep**): `settings.py:529,538,544`; `dependencies.py:353,356,376,452,460`; `services/health.py:61` (the one coupling to cut); `main.bicep:1852,1854,1861` + `main.json:48375` set `AZURE_REQUIRE_ADMIN_AUTH='false'`.
* Infra has **no** `auth_enforced` reference — the signal is purely in-process.
* Compiled bundles (`build-output/dist`, `dist`) carry one minified match each — generated artifacts, not actionable.

### External Research

* None required — entirely internal codebase analysis.

### Project Conventions

* Standards referenced: `.github/copilot-instructions.md` Hard Rules #1 (one-unit/turn), #2 (test-first), #3 (pillar header), #11 (`StrEnum`, no `__future__`/`TYPE_CHECKING`), #12 (no mid-phase back-fills / defect-vs-debt), #16 (no process narrative in `v2/src/**`), #19 (worklog + bugs.md).
* config-defaults-dev-first memory: `Environment.LOCAL` default is never inverted; prod is flipped only by IaC `AZURE_ENVIRONMENT=production`. The transparent removal honors this — it deletes a *derived UI signal*, not a default.
* Instructions to sync (Hard Rule #0): `.github/instructions/v2-frontend.instructions.md`, `v2/docs/frontend-user-identity-plan.md`, `v2/docs/bugs.md`.

## Key Discoveries

### The transparent rule is already the code's behavior when `auth_enforced` is forced false

Both tiers already implement principal-or-default; `auth_enforced` + `AuthBlocked` are the *only* thing layered on top:

* **Backend** `get_user_id` already returns the principal when the Easy Auth header is present, else the default user (`local-dev`) in the open posture. **Frontend** `useAuth.resolve` already returns `Resolved(real id)` for a principal and `Resolved(default)` for no-principal-not-enforced. The `Blocked` outcome is the lone extra branch.
* Therefore removal is **deletion of a gate**, not new logic. Forcing `authEnforced=false` everywhere = the desired transparent behavior, so the cleanest implementation is to delete the flag and the `Blocked` branch entirely.

### `auth_enforced` (UI signal) and `require_admin_auth` (server admin gate) are orthogonal

* `auth_enforced` is a **frontend-only UI signal**: its sole job is to tell the SPA whether to show the `AuthBlocked` wall. It is derived from `require_admin_auth` at exactly one line (`services/health.py:61`).
* `require_admin_auth` is a **server-side admin-write gate** consumed by `requires_role` → `AdminUserIdDep`. With the wall on in a non-local env, admin routes fail closed (`401`/`403`). This is test-proven in `test_dependencies.py` + `test_admin.py` and is **independent** of the health signal.
* **Cutting the one coupling line removes the UI signal while leaving admin protection fully intact.** A deployment that opts into `AZURE_REQUIRE_ADMIN_AUTH=true` still gets server-side admin gating; it simply no longer drives a frontend wall.

### The health client is hand-written — no OpenAPI regen

`auth_enforced` is read from an `unknown` payload via an ad-hoc narrowing function. Deleting the field needs no client codegen and breaks no typed model (there is none).

### A stale test is already RED against current code

`test_run_health_checks_auth_enforced_true_when_production` (`test_services_health.py:235-238`) still encodes the **old** `auth_enforced = environment is PRODUCTION` rule and fails against the current `require_admin_auth`-derived code. It disappears with the signal; flag per Hard Rule #12/#19 so it is deleted intentionally, not "fixed."

### Default identity values (for reference)

* Frontend default user id: `DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"` (`api/auth.tsx:40`); display name `"Guest"` / initials `"G"` (`userIdentity.tsx:15`).
* Backend default user id: `_LOCAL_DEV_USER = "local-dev"` (`dependencies.py`). The backend only *accepts* the all-zeros GUID via its principal-id allowlist; it never emits it.

## Technical Scenarios

### Scenario A (SELECTED) — Delete the `auth_enforced` signal + `AuthBlocked`; resolve identity purely from `/.auth/me`

Make the SPA's identity entirely self-evident from the Easy Auth probe, with no backend flag and no client-side wall. Keep `require_admin_auth` as the orthogonal, opt-in, server-side admin-write gate (default `False` = open). This is exactly the user's rule: *identity enabled → principal login + userId; identity not enabled → default user, period.*

**Requirements:**

* Backend stops emitting `auth_enforced`; `HealthResponse` carries only `status`, `version`, `checks`.
* Frontend resolves identity from `getUserInfo()` (`/.auth/me`) alone: principal → real id; no principal → `DEFAULT_USER_ID`. No `AuthBlocked`, no `AuthPhase.Blocked`, no `authEnforced` state field.
* `get_user_id` / `requires_role` / `require_admin_auth` unchanged — admin-write protection preserved for deployments that opt in.

**Preferred Approach:**

* Severs the single coupling line and deletes a shallow gate the code already bypasses in the open default. Satisfies the user's intent literally while keeping a real, orthogonal security control (admin-write gating) intact. No OpenAPI regen. Removes a known footgun (the field was the root cause of the open-prod "Authentication Not Configured" regression).

```text
v2/src/backend/models/health.py        (edit: drop auth_enforced field + docstring line)
v2/src/backend/services/health.py      (edit: drop auth_enforced=... line)
v2/src/frontend/src/App.tsx            (edit: drop readAuthEnforced, AuthBlocked import+branch, authEnforced arg)
v2/src/frontend/src/hooks/useAuth.tsx  (edit: resolve(userInfo) single-arg, drop Blocked branch + authEnforced)
v2/src/frontend/src/models/auth.tsx    (edit: drop AuthPhase.Blocked + AuthState.authEnforced)
v2/src/frontend/src/components/AuthBlocked/  (delete: AuthBlocked.tsx + AuthBlocked.module.css)

v2/tests/backend/test_health.py              (edit: drop signal assertions; key set -> {status,version,checks})
v2/tests/backend/test_services_health.py     (edit: delete the two auth_enforced tests incl. the stale RED one)
v2/tests/frontend/AppAuthBootstrap.test.tsx  (edit: drop authEnforced; delete 2 enforcement-blocked cases)
v2/tests/frontend/hooks/useAuth.test.tsx     (edit: single-arg resolve; delete "blocks when enforced")
v2/tests/frontend/models/auth.test.tsx       (edit: drop Blocked + authEnforced)
v2/tests/frontend/components/AuthBlocked.test.tsx  (delete: whole file)
```

**Implementation Details:**

Recommended unit decomposition (Hard Rule #1, test-first per Hard Rule #2 — final ordering is the planner's call):

* **Unit 1 (backend):** remove `auth_enforced` from `HealthResponse` + `run_health_checks`; update `test_health.py` (key set + assertions) and delete the two `test_services_health.py` signal tests. Backend ends green.
* **Unit 2 (frontend):** collapse `useAuth.resolve` to single-arg, drop `AuthPhase.Blocked` + `AuthState.authEnforced` from `models/auth.tsx`, strip `readAuthEnforced` + the `AuthBlocked` branch from `App.tsx`, delete the `AuthBlocked` component dir; rewrite/delete the four affected frontend tests. Frontend ends green.
* **Unit 3 (docs/guidance, Hard Rule #0/#19):** retire the `auth_enforced` rows in `frontend-user-identity-plan.md` (D2/F10), add a `bugs.md`/worklog note that the signal was removed in favor of the transparent rule.

`AuthPhase` keeps its two surviving members (`Loading | Resolved`) — minimum-deletion path, preserves the "still loading" semantics existing tests assert.

#### Sub-decision — does "default userId, period" also drop `get_user_id`'s prod fail-closed branch?

`get_user_id` currently raises `401` when `environment=production` AND `require_admin_auth=True` AND no principal. This branch **only fires when an operator explicitly opts into the wall** in a non-local env; in the default open deployment (`require_admin_auth=False`) it never fires, so the transparent rule already holds.

* **Recommended:** keep the branch. It is a deliberate opt-in security control, orthogonal to the UI signal, and removing it would silently weaken admin-write protection for deployments that turned the wall on. The user's "period" describes the *default* identity UX (guest-by-default, no wall), which Scenario A delivers without touching this branch.
* **If the user wants zero auth enforcement anywhere** (truly unconditional default), that is Scenario C below — a larger, security-relevant change requiring explicit confirmation.

### Scenario B — Keep `auth_enforced` in the payload but make the frontend ignore it

Leave the backend untouched; only delete the frontend `readAuthEnforced` + `AuthBlocked`.

#### Considered Alternatives

Rejected: leaves a dead, misleading field on the shipped `/api/health` contract (the field whose mis-derivation caused the open-prod regression), and leaves the stale RED backend test in place. Half-removal violates clean-as-you-go (cleanup-before-next-step memory) and keeps a footgun. Scenario A's backend deletion is cheap (two lines + a few test edits) and removes the root-cause field outright.

### Scenario C — Remove ALL auth enforcement (drop `require_admin_auth` + `get_user_id` fail-closed)

Unconditional principal-or-default everywhere; delete the admin wall entirely.

#### Considered Alternatives

Rejected as the default recommendation: this deletes a real, test-proven server-side admin-write security control, not just a UI signal. It exceeds the user's stated intent (which targets the `auth_enforced` *variable* / login UX, not admin-write protection) and is a security-relevant change that must be explicitly confirmed (Hard Rule operational-safety). Available on request, but Scenario A is the faithful reading of "we shouldn't need this variable."
