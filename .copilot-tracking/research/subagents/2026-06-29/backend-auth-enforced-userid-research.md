<!-- markdownlint-disable-file -->
# Research: Remove `auth_enforced`, adopt transparent principal-or-default identity rule (CWYD v2 backend)

Status: **Complete** (read-only; no code modified)
Date: 2026-06-29
Scope: `c:\workstation\Microsoft\github\cwyd-cdb\v2\src\backend\` + tests/infra/docs grep.

Design goal under evaluation: delete the `auth_enforced` signal entirely and replace it with a transparent rule — "if Azure Easy Auth identity is enabled, take the login + userId from the principal; otherwise use the default userId. No `auth_enforced` flag."

---

## 1. `v2/src/backend/services/health.py` — how `run_health_checks` produces `auth_enforced`

`run_health_checks` is the only producer of the live `auth_enforced` value.

- File: `v2/src/backend/services/health.py`
- `run_health_checks` body: lines 56-65.
- **Exact current line (line 61):**

  ```python
  auth_enforced=settings.require_admin_auth,
  ```

Full producer block (lines 56-65):

```python
def run_health_checks(settings: AppSettings) -> HealthResponse:
    """Run every dependency probe and assemble the aggregated response."""
    checks = [_check_foundry(settings), _check_database(settings), _check_search(settings)]
    return HealthResponse(
        status=_aggregate(checks),
        auth_enforced=settings.require_admin_auth,
        checks=checks,
    )
```

**Health payload fields** (every field returned by `run_health_checks`, via `HealthResponse`):

1. `status` — `OverallStatus` (`pass` | `degraded` | `fail`); from `_aggregate(checks)`.
2. `version` — `str`, default `"v2"` (model default; not set by `run_health_checks`).
3. `auth_enforced` — `bool`; set to `settings.require_admin_auth`. **← removal target.**
4. `checks` — `list[DependencyCheck]`; the three probes (`foundry_iq`, `database`, `search`).

Other (non-payload) helpers in the file: `_check_foundry` (lines 13-18), `_check_database` (21-31), `_check_search` (34-40), `_aggregate` (43-53). None of these touch `auth_enforced`.

---

## 2. `v2/src/backend/models/health.py` — `HealthResponse` model

File: `v2/src/backend/models/health.py` (entire file is 49 lines).

- `CheckStatus(StrEnum)` (lines 12-15): `PASS="pass"`, `FAIL="fail"`, `SKIP="skip"`.
- `OverallStatus(StrEnum)` (lines 18-21): `PASS="pass"`, `DEGRADED="degraded"`, `FAIL="fail"`.
- `DependencyCheck(BaseModel)` (lines 24-29): fields `name: str`, `status: CheckStatus`, `detail: str = ""`. (Note: the model is named `DependencyCheck`, not `CheckResult`.)
- `HealthResponse(BaseModel)` (lines 32-46) — every field:
  - `status: OverallStatus` (line 43)
  - `version: str = "v2"` (line 44)
  - `auth_enforced: bool = False` (**line 46**) ← removal target
  - `checks: list[DependencyCheck] = Field(default_factory=list[DependencyCheck])` (line 45)

  Note ordering in source: `status`, `version`, `checks`, `auth_enforced` (auth_enforced declared last).

- **`auth_enforced` default:** `False`.
- **`auth_enforced` docstring** (in the `HealthResponse` class docstring, lines 39-41):

  > `auth_enforced` reports whether the deployment requires a signed-in user (the admin wall is on), so the frontend can decide whether to demand an Easy Auth principal or fall back to the default user.

`__all__` (line 49) exports: `CheckStatus`, `DependencyCheck`, `HealthResponse`, `OverallStatus`.

---

## 3. `v2/src/backend/dependencies.py` — `get_user_id`, `requires_role`, helpers

File: `v2/src/backend/dependencies.py`.

### Constants (lines ~300-318)

- `_PRINCIPAL_ID_HEADER = "x-ms-client-principal-id"` (line ~301)
- `_PRINCIPAL_HEADER = "x-ms-client-principal"` (line ~302)
- `_LOCAL_DEV_USER = "local-dev"` (line ~303) — **the default/fallback user id value.**
- `_ROLE_TYP_SHORT = "roles"` (line ~304)
- `_ROLE_TYP_FULL = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"` (line ~305)
- `_PRINCIPAL_ID_PATTERN = re.compile(r"[A-Za-z0-9._@-]{1,128}")` (line ~314) — defensive well-formedness allowlist (admits Entra oid, all-zeros default id, and `local-dev`).

> There is **no** separate "default user id" GUID constant in the backend. The backend's default identity is the synthetic string `"local-dev"` (`_LOCAL_DEV_USER`). The all-zeros GUID `00000000-0000-0000-0000-000000000000` is a **frontend** default (`DEFAULT_USER_ID` in `api/auth.tsx`, per `frontend-user-identity-plan.md` F3); the backend only *accepts* it via the principal-id allowlist, it never *emits* it.

### `_is_valid_principal_id(value)` (lines ~321-336)

Returns `_PRINCIPAL_ID_PATTERN.fullmatch(value) is not None`. Defensive well-formedness only (not a trust boundary; a browser-forwarded id is forgeable).

### `get_user_id(request, settings)` (lines ~339-389) — FULL logic

```python
def get_user_id(request: Request, settings: SettingsDep) -> str:
    value = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
    if value:
        if not _is_valid_principal_id(value):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed client principal id.",
            )
        return value
    allow_open_auth = (
        settings.environment is Environment.LOCAL
        or not settings.require_admin_auth
    )
    if allow_open_auth:
        return _LOCAL_DEV_USER
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing client principal; Easy Auth header required.",
    )
```

**Principal-vs-default decision (the rule the user wants):**

- If `x-ms-client-principal-id` header present + well-formed → return it (the Easy Auth principal). **This is the "take the login/userId from the principal" branch.**
- If header absent → fall back to `_LOCAL_DEV_USER` (`"local-dev"`) **only when `allow_open_auth`** = `environment is LOCAL` **OR** `not require_admin_auth`.
- If header absent **and** auth is REQUIRED (`production` AND `require_admin_auth=True`) → raise `401` (fail-closed).

`UserIdDep = Annotated[str, Depends(get_user_id)]` (line ~392).

### `_decode_easy_auth_principal(raw)` (lines ~395-412)

base64-decodes + JSON-parses the `x-ms-client-principal` claims blob; returns `dict | None` (None on any decode failure; never raises).

### `_extract_roles(principal)` (lines ~415-437)

Walks `principal["claims"]`, collects `val` where `typ in (_ROLE_TYP_SHORT, _ROLE_TYP_FULL)`. Returns `set[str]`.

### `requires_role(role)` factory (lines ~440-507) — FULL logic

Returns a fresh `_checker(request, settings)` callable each call. Logic:

```python
principal_id = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
claims_raw   = request.headers.get(_PRINCIPAL_HEADER, "").strip()

allow_open_admin = (
    settings.environment is Environment.LOCAL
    or not settings.require_admin_auth
)

if not claims_raw:                      # keyed on ABSENT CLAIMS blob, not both headers
    if allow_open_admin:
        return _LOCAL_DEV_USER
    raise HTTPException(401, "Missing client principal claims; ...")

principal = _decode_easy_auth_principal(claims_raw)
if principal is None:
    raise HTTPException(401, "Malformed client principal payload.")

roles = _extract_roles(principal)
if role not in roles:
    raise HTTPException(403, f"Role '{role}' required ...")

if principal_id:
    return principal_id
if allow_open_admin:
    return _LOCAL_DEV_USER
raise HTTPException(401, "Missing client principal id header.")
```

Key points:
- Open-admin bypass keys on the **absent claims blob** (the sole role authority), not on the forgeable principal-id.
- A present claims blob is **always** role-checked (403 on missing role) — the toggle relaxes the *auth wall*, never *role enforcement*.

### Cached admin gate (lines ~510-514)

- `REQUIRE_ADMIN_USER = requires_role("admin")` (line ~512)
- `AdminUserIdDep = Annotated[str, Depends(REQUIRE_ADMIN_USER)]` (line ~513)

> There is **no** `allow_open_auth` / `allow_open_admin` *function* — both are local boolean expressions computed inline inside `get_user_id` and `_checker` respectively, identical formula: `environment is LOCAL or not require_admin_auth`.

`__all__` (lines ~517-540) exports `AdminUserIdDep`, `REQUIRE_ADMIN_USER`, `UserIdDep`, `get_user_id`, `requires_role`, plus the provider DI deps. **None of these export or reference `auth_enforced`** — `dependencies.py` does not touch the health signal at all.

---

## 4. `v2/src/backend/core/settings.py` — auth-related settings

File: `v2/src/backend/core/settings.py`.

### `Environment(StrEnum)` (lines 41-52)

```python
class Environment(StrEnum):
    LOCAL = "local"
    PRODUCTION = "production"
```

Docstring: `LOCAL` = developer machine, Easy-Auth-header-absent fallback to `local-dev` permitted; `PRODUCTION` = cloud, headers required, missing-header fails closed 401.

### `AppSettings` auth fields (root model, lines ~507-545)

- `environment: Environment = Environment.LOCAL` (line ~527) — env var `AZURE_ENVIRONMENT` (prefix `AZURE_`). Default `LOCAL`. Comment (lines ~519-526) explicitly: prod deployments set `AZURE_ENVIRONMENT=production` via `v2/infra/main.bicep`; "The admin auth wall is governed separately by `require_admin_auth` below, not by this field."
- `require_admin_auth: bool = False` (**line 544**) — env var `AZURE_REQUIRE_ADMIN_AUTH`. Default `False`. Comment (lines ~538-543): `False` = MACAE-faithful open posture (admin routes reachable without Easy Auth claims); `AZURE_REQUIRE_ADMIN_AUTH=true` makes `requires_role` fail closed in any non-`local` env; a present claims blob is always role-checked regardless.

`model_config` (lines ~512-517): `env_prefix="AZURE_"`, `env_file=".env"`, `extra="ignore"`.

No other auth-specific root fields. `IdentitySettings` (`identity:` sub-model, line ~546) holds UAMI client id etc., not auth-wall logic.

---

## 5. Every producer/consumer of `auth_enforced` and `require_admin_auth` across `v2/`

> Whole-tree literal grep timed out; results below are the union of subtree greps (`v2/src`, `v2/tests`, `v2/infra`, `v2/docs`). Compiled frontend bundles under `build-output/dist` and `dist` are generated artifacts (one match each) — listed once, not actionable.

### (a) Health/UI `auth_enforced` signal — producers & consumers

Backend producer:
- `v2/src/backend/services/health.py:61` — **PRODUCER.** `auth_enforced=settings.require_admin_auth` inside `run_health_checks`.
- `v2/src/backend/models/health.py:46` — model field `auth_enforced: bool = False` (declaration).
- `v2/src/backend/models/health.py:39` — docstring sentence describing `auth_enforced`.

Frontend consumers:
- `v2/src/frontend/src/App.tsx:104,107` — `readAuthEnforced(payload)` guard: narrows `auth_enforced` off the untyped health payload (`"auth_enforced" in payload`, `payload.auth_enforced === true`).
- `v2/src/frontend/src/App.tsx:145` — bootstrap effect: `const authEnforced = next.status === "ok" ? readAuthEnforced(next.payload) : false;` then `resolve(authEnforced, userInfo)`.
- `v2/src/frontend/src/App.tsx:19,95` — comments referencing the flag.
- `v2/src/frontend/build-output/dist/assets/index-klaMdg3d.js:94` — compiled bundle (generated; `vie()` = minified `readAuthEnforced`).
- `v2/src/frontend/dist/assets/index-klaMdg3d.js:94` — compiled bundle (generated; duplicate).

Backend tests asserting on `auth_enforced`:
- `v2/tests/backend/test_health.py:229` — `assert body["auth_enforced"] is False` (all-pass case, env unset → local).
- `v2/tests/backend/test_health.py:235-253` — `test_health_auth_enforced_false_when_open_in_production` (production + `AZURE_REQUIRE_ADMIN_AUTH=false` → `auth_enforced is False`).
- `v2/tests/backend/test_health.py:257-267` — `test_health_auth_enforced_true_when_admin_wall_on` (production + `AZURE_REQUIRE_ADMIN_AUTH=true` → `auth_enforced is True`).
- `v2/tests/backend/test_health.py:343` — `assert set(body.keys()) == {"status", "version", "auth_enforced", "checks"}` (wire-key lock).
- `v2/tests/backend/test_services_health.py:223-238` — section header + two tests `test_run_health_checks_auth_enforced_false_when_local` (passes) and `test_run_health_checks_auth_enforced_true_when_production` (**currently FAILING / stale** — see §7).

Frontend test asserting on `auth_enforced`:
- `v2/tests/frontend/AppAuthBootstrap.test.tsx:9,63` — drives the bootstrap with a mocked health payload carrying `auth_enforced: authEnforced`.

Docs referencing the signal (non-code; update for accuracy, not blocking):
- `v2/docs/bugs.md:105,109,148,857` (+1 more) — BUG history describing the `auth_enforced` fold and an open-prod regression.
- `v2/docs/frontend-user-identity-plan.md:39,54,61,74` — design plan D2/B1/F3/F9 describing the fold.
- `v2/docs/worklog/2026-06-15.md:722,731,743,744,774,816,820,821,860` — implementation worklog.
- `v2/docs/worklog/2026-06-16.md:128` — open-prod behavior note.
- `v2/docs/worklog/2026-06-22.md:156` — the revert that re-tied the signal to `require_admin_auth` (away from `environment`).
- `v2/docs/worklog/2026-06-25.md:118` — BUG-0089 acceptance referencing `auth_enforced:true`.

### (b) Backend admin-route ENFORCEMENT via `require_admin_auth` — independent of the signal

Producers/consumers of the *enforcement* toggle (these are **separate** from the health signal):
- `v2/src/backend/core/settings.py:529,538,544` — the `require_admin_auth: bool = False` field + its explanatory comments.
- `v2/src/backend/dependencies.py:353,356,376` — `get_user_id` open-auth fold (`not settings.require_admin_auth`).
- `v2/src/backend/dependencies.py:452,460` — `requires_role._checker` open-admin fold (`not settings.require_admin_auth`).
- `v2/src/backend/services/health.py:61` — the **only** place the enforcement toggle feeds the *signal* (the coupling the user wants to cut).

Tests of the enforcement toggle (must STAY — they test server-side gating, not the UI signal):
- `v2/tests/backend/core/test_settings.py:131-145` — `test_require_admin_auth_defaults_to_false`, `test_require_admin_auth_env_override_enables_wall`.
- `v2/tests/backend/test_admin.py:75,103` — admin-router test harness passes `require_admin_auth=True/...` to exercise the gate.
- `v2/tests/backend/test_dependencies.py:171,179-189,335,345,359,374,575,609` (+2 more) — `get_user_id` and `requires_role` behavior under wall on/off.
- `v2/tests/backend/test_health.py:241,248,262` — set `AZURE_REQUIRE_ADMIN_AUTH` to drive the *signal* tests (these specific health tests would be deleted with the signal; the env var itself stays meaningful for admin gating).

Infra (sets the env var that drives the enforcement toggle — keep):
- `v2/infra/main.bicep:1852,1854,1861` — `{ name: 'AZURE_REQUIRE_ADMIN_AUTH', value: 'false' }` on the backend Container App env-vars (comment notes it is separate from `AZURE_ENVIRONMENT`).
- `v2/infra/main.json:48375` — compiled ARM (generated from the bicep; same `AZURE_REQUIRE_ADMIN_AUTH=false`).

> Infra has **no** `auth_enforced` reference — the signal is purely derived in-process; nothing in Bicep/ARM emits it.

---

## 6. Health endpoint router — where `GET /api/health` returns `HealthResponse`

File: `v2/src/backend/routers/health.py`.

- Router: `router = APIRouter(prefix="/api", tags=["health"])` (line ~31).
- `GET /api/health` handler (lines 34-40):

  ```python
  @router.get("/health", response_model=HealthResponse, summary="Diagnostic health snapshot (always 200)")
  async def health(settings: SettingsDep) -> HealthResponse:
      return run_health_checks(settings)
  ```

- `GET /api/health/ready` handler (lines 43-50) — also calls `run_health_checks`; flips to `503` on `OverallStatus.FAIL`. Returns the same `HealthResponse` (so it also carries `auth_enforced` today).

Imports `HealthResponse`, `OverallStatus`, `run_health_checks`. No direct `auth_enforced` reference in the router (it rides inside the model).

---

## 7. Backend tests asserting on `auth_enforced` — names + assertions

`v2/tests/backend/test_health.py`:
- `test_health_returns_200_when_all_checks_pass` (line ~219) — asserts `body["auth_enforced"] is False` (line 229), `AZURE_ENVIRONMENT` deleted (defaults local), `require_admin_auth` default false.
- `test_health_auth_enforced_false_when_open_in_production` (lines 235-253) — `AZURE_ENVIRONMENT=production` + `AZURE_REQUIRE_ADMIN_AUTH=false` → `r.json()["auth_enforced"] is False`. Docstring records the BUG it guards: open prod must not block on missing principal ("Authentication Not Configured" regression when the flag was tied to `environment`).
- `test_health_auth_enforced_true_when_admin_wall_on` (lines 257-267) — `AZURE_ENVIRONMENT=production` + `AZURE_REQUIRE_ADMIN_AUTH=true` → `auth_enforced is True`.
- `test_health_response_model_shape` (line ~338) — `assert set(body.keys()) == {"status", "version", "auth_enforced", "checks"}` (line 343).

`v2/tests/backend/test_services_health.py`:
- `test_run_health_checks_auth_enforced_false_when_local` (lines 227-232) — `AZURE_ENVIRONMENT` deleted → `result.auth_enforced is False`. **Passes** (default `require_admin_auth=False` also yields False).
- `test_run_health_checks_auth_enforced_true_when_production` (lines 235-238) — sets only `AZURE_ENVIRONMENT=production`, asserts `result.auth_enforced is True`. **CURRENTLY FAILS** — verified by running the test:

  ```
  FAILED tests/backend/test_services_health.py::test_run_health_checks_auth_enforced_true_when_production
  AssertionError: assert False is True  (auth_enforced=False)
  1 failed, 1 passed, 15 deselected
  ```

  Root cause: the test still encodes the **old** rule (`auth_enforced = environment is PRODUCTION`) but the code now derives `auth_enforced = settings.require_admin_auth` (default `False`), and the test never sets `AZURE_REQUIRE_ADMIN_AUTH`. This is stale test debt that predates this research — it gets deleted along with the signal regardless.

Frontend (out of backend scope but relevant to the full removal):
- `v2/tests/frontend/AppAuthBootstrap.test.tsx` — `auth_enforced` (lines 9, 63) drives the AuthBlocked-screen bootstrap test.

---

## 8. Decision — deleting `auth_enforced` from `HealthResponse`

### What backend code must change

1. `v2/src/backend/models/health.py:46` — delete the `auth_enforced: bool = False` field; delete the docstring sentence at lines 39-41.
2. `v2/src/backend/services/health.py:61` — delete `auth_enforced=settings.require_admin_auth,` from the `HealthResponse(...)` construction in `run_health_checks`. (`settings` is still needed for the three checks, so the signature is unchanged.)
3. No change to `v2/src/backend/routers/health.py` — it never names `auth_enforced`; it just returns the model.
4. No change to `v2/src/backend/dependencies.py` — it does not reference `auth_enforced`.

### What backend tests must change

- Delete the four signal assertions/tests in `test_health.py`: the `auth_enforced is False` line in `test_health_returns_200_when_all_checks_pass` (line 229); both `test_health_auth_enforced_*` tests (lines 235-267); and update the wire-key set in `test_health_response_model_shape` (line 343) to `{"status", "version", "checks"}`.
- Delete the two `auth_enforced` tests + section header in `test_services_health.py` (lines 223-238) — including the already-failing `..._true_when_production`.
- Frontend: remove `readAuthEnforced` + its use in `App.tsx` and the `AppAuthBootstrap.test.tsx` payload field (out of backend scope, but required for a clean end-to-end removal; the SPA bootstrap must then resolve identity from `getUserInfo()`/principal-or-default alone).

### Does `get_user_id` already implement the "principal-or-default" rule the user wants?

**Partially — yes for the happy path, no for the production-wall edge.**

- Principal present → returns the principal id (✓ matches "take login/userId from the principal").
- Principal absent → returns `_LOCAL_DEV_USER` **only when `allow_open_auth`** (`LOCAL` or `not require_admin_auth`). In `production` **with** `require_admin_auth=True`, an absent principal raises `401` instead of falling back to the default.

So `get_user_id` is **not** an unconditional "principal-or-default" — it retains a fail-closed branch gated by `require_admin_auth`. If the user's "no flags at all" intent extends to chat identity, `get_user_id` would need its `require_admin_auth` branch removed too (always fall back to default on missing header). That is a behavioral decision beyond just deleting the health field — see clarifying questions.

### Does `require_admin_auth` still have a legitimate job? — **YES.**

Evidence:
- `require_admin_auth` is the **server-side admin-write gate**, consumed by `requires_role._checker` (`dependencies.py:452,460`) via `REQUIRE_ADMIN_USER = requires_role("admin")` → `AdminUserIdDep`. With the wall on in a non-local env, an admin route with no/insufficient claims fails closed (`401`/`403`); test-proven in `test_dependencies.py` (`test_requires_role_wall_on_raises_401_without_claims_in_prod`, lines ~340-345) and `test_admin.py`.
- This gating is **completely independent** of the health/UI `auth_enforced` signal. The *only* coupling between the two is the single line `services/health.py:61`. Deleting `auth_enforced` severs that one coupling and leaves the enforcement path (settings field, `dependencies.py` folds, `main.bicep` env var, `test_settings.py`/`test_admin.py`/`test_dependencies.py`) fully intact.

Conclusion: `auth_enforced` (UI signal) and `require_admin_auth` (server enforcement) are **orthogonal**. Removing the former does **not** weaken admin protection; `require_admin_auth` must stay.

---

## Clarifying questions

1. **Scope of "no flags":** Does removing `auth_enforced` also mean `get_user_id` should become unconditional principal-or-default (drop the `require_admin_auth`/`production` 401 fail-closed branch so a missing principal *always* yields the default user)? Or keep the fail-closed branch (chat identity still respects the admin wall) and only delete the health *signal*? The user's phrasing ("otherwise use the default userId") reads as unconditional, which would also change `requires_role`'s fail-closed posture by extension — please confirm whether the auth *wall* (`require_admin_auth` 401/403 on admin writes) is being kept or also dropped.
2. **`require_admin_auth` retention:** Confirm `require_admin_auth` (env `AZURE_REQUIRE_ADMIN_AUTH`, `main.bicep:1861`) stays as the admin-write gate. Evidence says it must; the user's note only targets the `auth_enforced` *signal*, but "No auth_enforced flag" should be confirmed to mean "no health signal," not "no admin wall."
3. **Frontend coordination:** The SPA currently blocks (`AuthBlocked`) when `auth_enforced === true` and no principal resolves. Removing the field makes `readAuthEnforced` always-false, so the SPA would never block — it would always fall back to the default user. Confirm that is the desired transparent behavior (the frontend is out of this backend research's edit scope but is part of the same contract).
4. **Pre-existing failing test:** `test_run_health_checks_auth_enforced_true_when_production` is already failing against current code (stale). It will be deleted with the signal — flag only to confirm it should not be "fixed" first under a separate bug id.

---

## Recommended next research (not done this session)

- [ ] Frontend `App.tsx` + `api/auth.tsx` full identity bootstrap (`getUserId`, `DEFAULT_USER_ID`, `getUserInfo`, `resolve`, `AuthBlocked`) to spec the SPA-side removal and confirm the all-zeros default GUID flow.
- [ ] `AppAuthBootstrap.test.tsx` full test to enumerate frontend assertions to drop/rewrite.
- [ ] Generated OpenAPI client (`v2/src/frontend/.../api` models for `HealthResponse`) — does a typed `HealthResponse` model exist client-side that also carries `auth_enforced`? (App.tsx narrows from an *untyped* payload, suggesting maybe not, but worth confirming so the client regen is clean.)
- [ ] `v2/docs/development_plan.md` §0.1 / §0.2 — whether a debt row should track the stale `test_services_health.py` failure and the planned signal removal (per Hard Rule #12/#19).
