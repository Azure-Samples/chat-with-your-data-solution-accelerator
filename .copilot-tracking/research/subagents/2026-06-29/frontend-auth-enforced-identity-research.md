<!-- markdownlint-disable-file -->
# Frontend research — remove `auth_enforced` / `AuthBlocked`, keep the transparent identity rule

## Research topic / questions

The team wants to REMOVE the `auth_enforced` / `authEnforced` signal and the `AuthBlocked`
"Authentication Not Configured" screen from the CWYD v2 frontend, replacing the gate with a
transparent rule: probe Azure Easy Auth `/.auth/me`; if a logged-in principal exists use that
login + its userId; otherwise use the default user. No `auth_enforced`, no `AuthBlocked`.

Read-only research only. Document the current flow with exact file paths + line numbers, list
every reference, list the tests, and determine precisely which files/tests must change or be
deleted.

Status: **Complete**

---

## 1. `App.tsx` — the identity-resolution effect and the AuthBlocked branch

File: `v2/src/frontend/src/App.tsx`

### Imports that wire the gate

- Line 41 — `import { AuthBlocked } from "./components/AuthBlocked/AuthBlocked";`
- Line 52 — `import { getUserInfo } from "./api/auth";`
- Line 53 — `import { useAuth } from "./hooks/useAuth";`
- Line 54 — `import { AuthPhase } from "./models/auth";`

### `fetchHealth` (lines 72–92)

Hand-written `fetch` of `/api/health` against the runtime backend origin. Returns a discriminated
`HealthState` whose `ok` arm carries `payload: unknown` (no typed health model):

```tsx
async function fetchHealth(signal: AbortSignal): Promise<HealthState> {
  const url = `${getBackendUrl().replace(/\/$/, "")}/api/health`;
  try {
    const response = await fetch(url, { signal });
    if (!response.ok) {
      return { status: "error", message: `HTTP ${response.status}` };
    }
    const payload: unknown = await response.json();
    return { status: "ok", payload };
  } catch (err) {
    ...
  }
}
```

### `readAuthEnforced` (lines 95–109)

Narrows the `auth_enforced` flag out of the untyped health payload; anything that is not literal
`true` is treated as "not enforced":

```tsx
function readAuthEnforced(payload: unknown): boolean {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }
  if (!("auth_enforced" in payload)) {
    return false;
  }
  const value: unknown = payload.auth_enforced;
  return value === true;
}
```

### The bootstrap effect (lines 137–167)

Calls the health endpoint, reads `auth_enforced`, probes `/.auth/me`, then settles the state machine
via `resolve(authEnforced, userInfo)`:

```tsx
useEffect(() => {
  const controller = new AbortController();
  let cancelled = false;
  void loadRuntimeConfig()
    .then(() => fetchHealth(controller.signal))
    .then(async (next) => {
      if (!cancelled) {
        setHealth(next);
      }
      // auth_enforced rides the health payload (no separate auth route);
      // pair it with the Easy Auth /.auth/me lookup to resolve the
      // signed-in user, or fall back to the default when not enforced.
      const authEnforced =
        next.status === "ok" ? readAuthEnforced(next.payload) : false;
      const userInfo = await getUserInfo();
      if (!cancelled) {
        resolve(authEnforced, userInfo);
      }
    });
  return () => {
    cancelled = true;
    controller.abort();
  };
}, [resolve]);
```

Key call sites inside the effect:

- Lines 148–149 — `const authEnforced = next.status === "ok" ? readAuthEnforced(next.payload) : false;`
- Line 150 — `const userInfo = await getUserInfo();` (the `/.auth/me` probe)
- Line 152 — `resolve(authEnforced, userInfo);`

### The exact branch that renders `<AuthBlocked>` (lines 181–188)

```tsx
// Auth is enforced but no signed-in user resolved: replace the whole
// shell with the blocked screen so no user-scoped API call can fire.
if (auth.phase === AuthPhase.Blocked) {
  return (
    <CoralShellColumn>
      <AuthBlocked />
    </CoralShellColumn>
  );
}
```

Note: there is **no** `Loading`-phase branch in `App.tsx` — despite docstrings mentioning a
"spinner while Loading", the shell renders the full app during `Loading` and only special-cases
`Blocked`. The header receives `userInfo={auth.userInfo}` (line ~213), which is `null` for the
default user.

---

## 2. `AuthBlocked` component — client-side React, not an Easy Auth page

Directory `v2/src/frontend/src/components/AuthBlocked/` contains exactly two files (no `index.tsx`
barrel):

- `AuthBlocked.tsx`
- `AuthBlocked.module.css`

File: `v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx` (lines 1–53)

It is a **client-side Fluent UI v9 React component** (a port of the v1 "Authentication Not
Configured" screen), NOT an Azure Easy Auth platform page. It renders:

- a `<section role="alert" data-testid="auth-blocked">`
- a decorative `<ShieldLockRegular aria-hidden="true">` icon (`@fluentui/react-icons`)
- `<h1>Authentication Not Configured</h1>` (line 30)
- operator guidance text with two external `<Link>`s:
  - `AZURE_PORTAL_URL = "https://portal.azure.com/"` (line 18)
  - `APP_SERVICE_AUTH_DOCS_URL = "https://learn.microsoft.com/azure/app-service/scenario-secure-app-authentication-app-service#3-configure-authentication-and-authorization"` (lines 19–20)
- a propagation note ("takes a few minutes to apply").

It is rendered by `App.tsx` only when `auth.phase === AuthPhase.Blocked`. The component itself does
no fetching and reads no `auth_enforced` value — it is pure presentation gated upstream.

The component is imported directly via `./components/AuthBlocked/AuthBlocked` (App.tsx line 41) and
`@/components/AuthBlocked/AuthBlocked` (test). No other production file imports it (the only other
reference is its own test).

---

## 3. The Easy Auth probe — `getUserInfo` / `/.auth/me` and the principal model

File: `v2/src/frontend/src/api/auth.tsx`

- `OBJECT_ID_CLAIM` (lines 24–25) — `"http://schemas.microsoft.com/identity/claims/objectidentifier"`,
  the Entra `oid` claim URI used as the per-user partition key.
- `getUserInfo()` (lines 60–82):

```tsx
export async function getUserInfo(): Promise<UserInfo | null> {
  try {
    const response = await fetch("/.auth/me");
    if (!response.ok) {
      return null;
    }
    const principals = (await response.json()) as AuthMeResponse[];
    const principal = principals[0];
    if (!principal) {
      return null;
    }
    const userId = principal.user_claims.find(
      (claim) => claim.typ === OBJECT_ID_CLAIM,
    )?.val;
    if (!userId) {
      return null;
    }
    return { userId, claims: principal.user_claims };
  } catch {
    return null;
  }
}
```

How "no principal" / empty result is detected — `getUserInfo()` returns `null` when **any** of:
non-2xx `/.auth/me` response (no IdP configured / not signed in), empty principals array
(`principals[0]` undefined), no `objectidentifier` claim present, or a thrown fetch/parse error.
The probe **never throws** — an absent IdP is the normal local-dev state.

The wire + domain models live in `v2/src/frontend/src/models/auth.tsx`:

- `UserClaim` (lines 21–24) — `{ typ: string; val: string }` (external Easy Auth claim).
- `AuthMeResponse` (lines 30–34) — `{ user_id: string; user_claims: UserClaim[]; provider_name: string }`
  (external Easy Auth `/.auth/me` wire shape, snake_case, platform-owned).
- `UserInfo` (lines 37–40) — FE-owned `{ userId: string; claims: UserClaim[] }`.

The probe targets `/.auth/me` on the **SPA's own origin** (never prefixed with the backend URL).

---

## 4. The DEFAULT user — id and display name

### Default user id

File: `v2/src/frontend/src/api/auth.tsx`, line 40:

```tsx
export const DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000";
```

All-zeros GUID; the backend treats it as a single shared partition for local / unauthenticated use.
`getUserId()` (lines 89–91) returns the resolved singleton `currentUserId ?? DEFAULT_USER_ID`;
`setUserId(null)` (lines 99–101) clears back to the default; `userIdHeaders()` (lines 108–110)
builds `{ "x-ms-client-principal-id": getUserId() }`.

### Default display name

File: `v2/src/frontend/src/components/Header/userIdentity.tsx`, line 15:

```tsx
const GUEST_NAME = "Guest";
```

`resolveDisplayName(userInfo)` (lines 32–47) returns `"Guest"` when `userInfo` is `null`/`undefined`
or carries no name-bearing claim; `userInitials("")` returns `"G"` (line ~56). This is the only
default-display-name source in the FE. The default user has `userInfo === null` (no claims), so the
header badge shows "Guest" / "G". **This file is identity-display only and does NOT reference
`auth_enforced` / `AuthBlocked`; it needs NO change for this work.**

---

## 5. The health client — generated or hand-written?

**Hand-written, NOT generated.** There is no OpenAPI client in the v2 frontend at all:

- `v2/src/frontend/src/api/admin.tsx`, line 7 — comment: "…per endpoint, no OpenAPI generator
  wired in v2 yet."
- `v2/src/frontend/src/api/speech.tsx`, line 6 — same note: "no OpenAPI generator wired in v2 yet".

The health request is the inline `fetchHealth()` in `App.tsx` (lines 72–92). There is **no typed
health model file** and **no generated model**; `auth_enforced` is narrowed ad hoc from an
`unknown` payload via `readAuthEnforced` (App.tsx lines 95–109). Removing `auth_enforced` therefore
requires no codegen/regeneration — it is purely deleting the inline narrowing + its caller.

---

## 6. Runtime config loader + `VITE_BACKEND_URL` (health-fetch wiring)

File: `v2/src/frontend/src/api/runtimeConfig.tsx`

- `loadRuntimeConfig()` (lines 46–73) — fetches `GET /config` once (idempotent, shares an in-flight
  promise) and caches `backendUrl`. On any failure it leaves the cache unset.
- `getBackendUrl()` (lines 31–38) — returns the cached `/config` value once loaded, else the
  build-time `import.meta.env.VITE_BACKEND_URL` (empty when unset).
- `resetRuntimeConfig()` (lines 76–79) — test-only reset seam.

`App.tsx`'s bootstrap effect chains `loadRuntimeConfig().then(() => fetchHealth(...))`, so the health
probe targets the resolved backend origin (Container App in the deployed split-host topology, or the
Vite proxy in local dev). This wiring is unaffected by removing `auth_enforced` — only the payload
field read changes.

---

## 7. Full reference inventory (`auth_enforced` | `authEnforced` | `AuthBlocked` | "Authentication Not Configured")

### Production code (`v2/src/frontend/`)

| File:line | Token | Description |
| --- | --- | --- |
| `App.tsx:19` | auth_enforced | Docstring: "The same health response carries `auth_enforced`". |
| `App.tsx:24` | AuthBlocked | Docstring: shell renders `<AuthBlocked>` in place of routed view. |
| `App.tsx:41` | AuthBlocked | `import { AuthBlocked } from "./components/AuthBlocked/AuthBlocked";` |
| `App.tsx:95` | auth_enforced | Docstring above `readAuthEnforced`. |
| `App.tsx:100` | auth_enforced | `function readAuthEnforced(payload: unknown): boolean {` |
| `App.tsx:104` | auth_enforced | `if (!("auth_enforced" in payload))` guard. |
| `App.tsx:107` | auth_enforced | `const value: unknown = payload.auth_enforced;` |
| `App.tsx:145` | auth_enforced | Effect comment: "auth_enforced rides the health payload". |
| `App.tsx:148–149` | authEnforced | `const authEnforced = … readAuthEnforced(next.payload) : false;` |
| `App.tsx:152` | authEnforced | `resolve(authEnforced, userInfo);` |
| `App.tsx:185` | AuthBlocked | `<AuthBlocked />` render inside the `Blocked` branch (branch at line 181). |
| `components/AuthBlocked/AuthBlocked.tsx:8` | Authentication Not Configured | Docstring referencing v1 layout. |
| `components/AuthBlocked/AuthBlocked.tsx:16` | AuthBlocked | `import styles from "./AuthBlocked.module.css";` |
| `components/AuthBlocked/AuthBlocked.tsx:22` | AuthBlocked | `export function AuthBlocked(): JSX.Element {` |
| `components/AuthBlocked/AuthBlocked.tsx:30` | Authentication Not Configured | `<h1 …>Authentication Not Configured</h1>` |
| `hooks/useAuth.tsx:6` | authEnforced | Docstring: state fields list. |
| `hooks/useAuth.tsx:7` | authEnforced | Docstring: `resolve(authEnforced, userInfo)` action. |
| `hooks/useAuth.tsx:31` | authEnforced | `INITIAL_AUTH_STATE.authEnforced: false`. |
| `hooks/useAuth.tsx:38` | authEnforced | `resolve: (authEnforced: boolean, userInfo: …) => void` (interface). |
| `hooks/useAuth.tsx:50` | authEnforced | `resolve` callback param. |
| `hooks/useAuth.tsx:57` | authEnforced | sets `authEnforced` in the resolved-user state. |
| `hooks/useAuth.tsx:62` | authEnforced | `if (authEnforced) {` — the Blocked branch guard (branch 62–74). |
| `hooks/useAuth.tsx:69` | authEnforced | sets `authEnforced: true` in the Blocked state. |
| `hooks/useAuth.tsx:79` | authEnforced | sets `authEnforced: false` in the default-user state. |
| `models/auth.tsx:60` | authEnforced | `authEnforced: boolean;` field on `AuthState`. |

Additional gate-coupled symbol (not matched by the four tokens but part of the same removal):
`AuthPhase.Blocked` member at `models/auth.tsx:52` (`Blocked: "blocked"`), consumed by `App.tsx:181`
and set by `useAuth.tsx:71`.

### Tests (`v2/tests/frontend/`)

| File:line | Token | Description |
| --- | --- | --- |
| `AppAuthBootstrap.test.tsx:9` | auth_enforced | Suite docstring. |
| `AppAuthBootstrap.test.tsx:11` | AuthBlocked | Docstring: renders `<AuthBlocked>` when enforced + no principal. |
| `AppAuthBootstrap.test.tsx:41` | authEnforced | `stubFetch` doc. |
| `AppAuthBootstrap.test.tsx:46` | authEnforced | `stubFetch` destructured param. |
| `AppAuthBootstrap.test.tsx:49` | authEnforced | `stubFetch` param type. |
| `AppAuthBootstrap.test.tsx:63` | auth_enforced | health stub: `auth_enforced: authEnforced`. |
| `AppAuthBootstrap.test.tsx:90,98,106,116,127,144,150,159` | authEnforced | `stubFetch({ authEnforced, signedIn })` across 8 cases. |
| `components/AuthBlocked.test.tsx:5` | AuthBlocked | Suite docstring. |
| `components/AuthBlocked.test.tsx:12` | AuthBlocked | `import { AuthBlocked } from "@/components/AuthBlocked/AuthBlocked";` |
| `components/AuthBlocked.test.tsx:20` | AuthBlocked | `<AuthBlocked />` render in helper. |
| `components/AuthBlocked.test.tsx:26` | AuthBlocked | `describe("AuthBlocked", …)`. |
| `components/AuthBlocked.test.tsx:34` | Authentication Not Configured | heading assertion `/authentication not configured/i`. |
| `hooks/useAuth.test.tsx:40` | authEnforced | initial-state assertion. |
| `hooks/useAuth.test.tsx:55` | authEnforced | resolved-user assertion. |
| `hooks/useAuth.test.tsx:69` | authEnforced | `expect(result.current.auth.authEnforced).toBe(true)`. |
| `hooks/useAuth.test.tsx:84` | authEnforced | Blocked-state assertion (`authEnforced: true`). |
| `hooks/useAuth.test.tsx:101` | authEnforced | default-user assertion (`authEnforced: false`). |
| `models/auth.test.tsx:76` | authEnforced | `AuthState` literal in shape test. |
| `models/auth.test.tsx:81` | authEnforced | `expect(state.authEnforced).toBe(false)`. |

Plus `AuthPhase.Blocked` coverage in `models/auth.test.tsx` (lines ~20–32 assert the closed set
includes `"blocked"`) and `useAuth.test.tsx:76–88` ("blocks when auth is enforced but no user
resolved").

---

## 8. Frontend vitest tests that exercise `auth_enforced` / `AuthBlocked`

1. **`v2/tests/frontend/components/AuthBlocked.test.tsx`** — pure component tests. Test names:
   - "renders an alert region with the auth-blocked heading"
   - "explains that the app requires sign-in but no user was found"
   - "links to the Azure Portal, opened safely in a new tab"
   - "links to the App Service authentication setup instructions"
   - "shows the configuration-propagation note"
   - "renders a decorative shield icon hidden from assistive tech"

   Asserts the `auth-blocked` testid, the alert role, the "Authentication Not Configured" heading,
   the two external links (`href`/`target`/`rel`), the propagation note, and the aria-hidden shield.
   → **Delete entirely with the component.**

2. **`v2/tests/frontend/AppAuthBootstrap.test.tsx`** — full-shell bootstrap via URL-routed `fetch`
   mock. `stubFetch({ authEnforced, signedIn })` injects `auth_enforced` on the `/api/health` stub
   (line 63) and toggles `/.auth/me` 200 vs 401. Test names:
   - "forwards the resolved object id once /.auth/me returns a principal" (`authEnforced:false, signedIn:true`)
   - "forwards the resolved object id even when auth is enforced" (`true, true`)
   - "falls back to the default user when not signed in and auth is not enforced" (`false, false`)
   - "forwards the default user when auth is enforced but no principal resolves" (`true, false`)
   - "queries the Easy Auth /.auth/me endpoint on the SPA origin" (`false, true`)
   - "renders the blocked screen when auth is enforced but no principal resolves" (`true, false`) →
     asserts `findByTestId("auth-blocked")`.
   - "keeps the blocked screen hidden once a principal resolves under enforcement" (`true, true`)
   - "keeps the blocked screen hidden when auth is not enforced and no principal resolves" (`false, false`)

   → **Rewrite:** drop `authEnforced` from `stubFetch`, delete the two enforcement-specific blocked
   cases, keep principal-resolved + default-fallback + `/.auth/me`-origin cases (they become the
   transparent rule's full coverage).

3. **`v2/tests/frontend/hooks/useAuth.test.tsx`** — state-machine tests. Test names:
   - "starts in the loading phase on the default user"
   - "resolves to the signed-in user and forwards their id"
   - "resolves the signed-in user even when auth is enforced"
   - "blocks when auth is enforced but no user resolved" → asserts `AuthPhase.Blocked`.
   - "falls back to the default user when auth is not enforced"
   - "keeps a stable resolve identity across renders"

   → **Rewrite:** `resolve(userInfo)` single-arg signature; delete the "blocks when enforced" test
   and the "even when auth is enforced" variant (collapses into the resolved-user case); drop every
   `authEnforced` field assertion.

4. **`v2/tests/frontend/models/auth.test.tsx`** — model shape/enum tests.
   - "maps every member to its canonical string" + "exposes the full closed phase set" assert
     `AuthPhase.Blocked === "blocked"` and `["blocked","loading","resolved"]`.
   - "produces a literal-union type covering every phase string" → `"loading" | "resolved" | "blocked"`.
   - "models the auth store state with a closed-set phase" includes `authEnforced: false` (line 76)
     and asserts `state.authEnforced` (line 81).

   → **Edit:** remove `Blocked` from the `AuthPhase` assertions + union; remove `authEnforced` from
   the `AuthState` literal + assertion.

Tests that touch identity but do **NOT** need changes (they use `getUserInfo`/`DEFAULT_USER_ID`
without `auth_enforced`/`AuthBlocked`): `tests/frontend/api/auth.test.tsx` (the `/.auth/me` seam
itself), `tests/frontend/api/admin.test.tsx`, `tests/frontend/api/conversationHistory.test.tsx`,
`tests/frontend/api/streamChat.test.tsx`, `tests/frontend/pages/chat/components/HistoryPanel.test.tsx`,
`tests/frontend/App.test.tsx` (health reporting only), `tests/frontend/AppHistoryToggle.test.tsx`,
`tests/frontend/AppNavigation.test.tsx`.

---

## 9. Implementation impact — does `App.tsx` already have all the pieces?

**Yes.** The transparent rule is already the behavior the code produces when `authEnforced` is
always `false`: `App.tsx` already calls `/.auth/me` (`getUserInfo`, line 150) and already has a
default user (`DEFAULT_USER_ID`, `api/auth.tsx:40`). Removal is mostly **DELETION of the gate**, not
new logic. The `useAuth.resolve` "no user + not enforced → Resolved(default)" branch
(`useAuth.tsx:76–83`) IS the desired fallback — it just needs to become the only no-user branch.

### Files to CHANGE (edit)

1. `v2/src/frontend/src/App.tsx`
   - Delete the `AuthBlocked` import (line 41) and the `AuthPhase` import (line 54) if `AuthPhase` is
     no longer referenced after the `Blocked` branch goes (it is only used in the `Blocked` check).
   - Delete `readAuthEnforced` (lines 95–109).
   - In the bootstrap effect, drop the `authEnforced` computation (lines 148–149) and change
     `resolve(authEnforced, userInfo)` → `resolve(userInfo)` (line 152).
   - Delete the `if (auth.phase === AuthPhase.Blocked) { … <AuthBlocked /> … }` branch (lines 181–188).
   - Update the module docstring (lines 17–25, 95) to drop the `auth_enforced` / `AuthBlocked`
     narrative.

2. `v2/src/frontend/src/hooks/useAuth.tsx`
   - Change `resolve` signature to `resolve(userInfo: UserInfo | null)` (interface line 38; callback
     line 50).
   - Remove the `if (authEnforced) { … Blocked … }` branch (lines 62–74).
   - Drop `authEnforced` from `INITIAL_AUTH_STATE` (line 31) and from both remaining
     `setAuth({...})` calls (lines 57, 79).
   - Update docstring (lines 6–20) to the transparent rule.

3. `v2/src/frontend/src/models/auth.tsx`
   - Remove `authEnforced: boolean;` from `AuthState` (line 60).
   - Remove `Blocked: "blocked"` from the `AuthPhase` const (line 52) — closed set becomes
     `Loading | Resolved`.
   - Update docstrings referencing `Blocked`/enforcement (lines ~43–48, ~56).

### Files to DELETE

4. `v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx`
5. `v2/src/frontend/src/components/AuthBlocked/AuthBlocked.module.css`
   (the entire `components/AuthBlocked/` directory)

### Tests to CHANGE

6. `v2/tests/frontend/AppAuthBootstrap.test.tsx` — drop `authEnforced` from `stubFetch` + the two
   enforcement-blocked cases; keep principal-resolved / default-fallback / `/.auth/me`-origin cases.
7. `v2/tests/frontend/hooks/useAuth.test.tsx` — single-arg `resolve(userInfo)`; delete the
   "blocks when enforced" + "even when enforced" tests; drop `authEnforced` assertions.
8. `v2/tests/frontend/models/auth.test.tsx` — remove `Blocked` from `AuthPhase` assertions/union and
   `authEnforced` from the `AuthState` shape test.

### Tests to DELETE

9. `v2/tests/frontend/components/AuthBlocked.test.tsx` (whole file).

No generated client to regenerate (Section 5). No backend FE-client coupling — `auth_enforced` is
read inline from an untyped payload. `userIdentity.tsx` ("Guest"/"G") is untouched.

---

## Clarifying questions

1. **Loading phase / spinner.** `AuthPhase.Loading` survives in the transparent rule (it marks the
   pre-`/.auth/me` window), but `App.tsx` never renders a distinct `Loading` view today — it renders
   the full shell while loading. Should the removal also collapse `AuthPhase` to a boolean
   `resolved` flag, or keep the `Loading | Resolved` two-member enum as-is? (Recommendation: keep the
   two-member enum; it is the minimum-deletion path and preserves the existing "still loading"
   semantics the tests assert.)
2. **Backend `auth_enforced`.** This research is FE-scoped. The backend `/api/health` payload still
   emits `auth_enforced`; the FE will simply ignore it after removal. Confirm whether a companion
   backend change to stop emitting `auth_enforced` is in scope (separate unit), or whether the FE
   ignoring the field is sufficient for this turn.

---

## Recommended next research (not completed here)

- [ ] Backend: locate where `/api/health` sets `auth_enforced` and the settings flag behind it, to
      scope an optional backend removal companion unit.
- [ ] Confirm no v2 frontend e2e / Playwright spec (outside `v2/tests/frontend/`) asserts the
      `auth-blocked` testid before deleting the component.
- [ ] Check `v2/.github/instructions/v2-frontend.instructions.md` (root `.github/instructions/`) for
      any auth/identity policy that must be updated alongside the code (Hard Rule #0 sync-guidance).
