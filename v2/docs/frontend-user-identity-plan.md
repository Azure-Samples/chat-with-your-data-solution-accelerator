---
title: CWYD v2 — Frontend user identity + per-user header forwarding (BUG-0046)
description: Implementation checklist for resolving the signed-in user in the v2 SPA, forwarding the x-ms-client-principal-id identity header on every API call, detecting whether login is enforced, blocking with an error screen when it is enforced but absent, and falling back to the all-zeros default user otherwise. Adapts the v1 getUserInfo pattern and the MACAE header-forward pattern.
author: CWYD Engineering
ms.date: 2026-06-15
topic: how-to
keywords: BUG-0046, user identity, x-ms-client-principal-id, getUserInfo, auth enforced, default user, easy auth, chat history isolation, MACAE, header forwarding, frontend, v2
estimated_reading_time: 7
---

## Purpose

This is the actionable, file-based checklist for **BUG-0046**. It tracks the work to give the v2 frontend a real per-user identity and to forward that identity to the backend on every API call, so chat history is isolated per user end-to-end.

Record progress by checking items off as each unit lands. The canonical defect record is [bugs.md](bugs.md) (`### BUG-0046`); the daily narrative is in [worklog/](worklog/). This file is the running task list that ties those together.

## Context — the backend is already user-scoped; the gap is the frontend

The backend already attributes every request to a user and enforces per-user ownership:

* The history routes (`list`, `get`, `delete`, `rename`, `add_message`, `feedback`) and the conversation route all consume the `UserIdDep` dependency, which reads the `x-ms-client-principal-id` header.
* `get_user_id` returns the header value when present; when the header is absent it falls back to the `local-dev` user in `local` mode and returns `401` in `production` mode.
* The Cosmos DB and PostgreSQL providers key every read and write on `user_id`, so a conversation that does not belong to the caller already resolves to `404` on get / delete / rename.

So the "query chat history by user" and "a deleted chat must belong to the same user" requirements are **already satisfied server-side**. The defect is entirely in the frontend: it never resolves the signed-in user, has no user-id store, and forwards **no** identity header on any of its four `fetch` clients. With the separate-origin topology (the SPA reaches the backend at an absolute `VITE_BACKEND_URL`), the platform-injected Easy Auth header on the frontend origin does not travel to the cross-origin backend call, so the identity must be forwarded manually — the MACAE pattern.

## Security constraint (binding)

A browser-forwarded `x-ms-client-principal-id` is **not** a trust boundary — any caller can set the header to any value. It is acceptable for **chat-history partitioning** (the requested behavior), but:

* Admin RBAC (`requires_role("admin")`) must stay anchored on the backend's own **server-injected** Easy Auth claims (`x-ms-client-principal`). The browser must never forward the claims blob to satisfy a role check.
* "Valid" (the backend check) can only mean **well-formed** (non-empty, sane length and character set) for a forwarded header — not authentic.

## Decisions

| ID | Decision | Choice |
|---|---|---|
| D1 | Header injection mechanism | One `userIdHeaders()` helper, spread into each existing `fetch` call (four clients). |
| D2 | Auth-enforced signal source | Fold `auth_enforced: bool` into the existing `GET /api/health` payload (`auth_enforced = settings.environment is Environment.PRODUCTION`); no new route. |
| D3 | Default user when login not enforced | The frontend sends `00000000-0000-0000-0000-000000000000`; the backend keeps its `local-dev` fallback for header-absent direct calls. |
| D4 | Tracking | `BUG-0046` in [bugs.md](bugs.md) + a worklog entry + this checklist doc. |
| D5 | New modules (Hard Rule #10) | New `api/auth.tsx` (existing folder); auth context location to be confirmed before F8 (fold into `AppShell` state, or a new context module). No new backend module (D2 folds into health). |

## Checklist

### Phase 0 — Tracking

* [x] T0a — `BUG-0046` row + `### BUG-0046` detail in [bugs.md](bugs.md).
* [x] T0b — worklog entry in [worklog/2026-06-15.md](worklog/2026-06-15.md).
* [x] T0c — this checklist doc.

### Phase 1 — Backend (small)

* [x] B1 — add `auth_enforced` to the `GET /api/health` response (`HealthResponse` field + `run_health_checks` sets it from `settings.environment`); pytest.
* [x] B2 (optional) — light principal-id well-formedness check in `get_user_id` (non-empty, bounded length / character set; accept the all-zeros default and `local-dev`); malformed → `401` in production; pytest.

### Phase 2 — Frontend identity module (`api/auth.tsx`)

* [ ] F1 — auth models: `UserInfo` / `AuthStatus` types + `DEFAULT_USER_ID` constant; vitest.
* [ ] F2 — `getUserInfo()` → `fetch("/.auth/me")`, parse the principal, extract the `objectidentifier` claim, degrade gracefully on failure; vitest.
* [ ] F3 — module-level resolved id + `getUserId()` (resolved id or default), `setUserId()`, and `userIdHeaders()`; vitest.

### Phase 3 — Inject the header into every client (one file per unit)

* [ ] F4 — `streamChat.tsx` spreads `userIdHeaders()`; test.
* [ ] F5 — `conversationHistory.tsx` spreads `userIdHeaders()`; test.
* [ ] F6 — `admin.tsx` spreads `userIdHeaders()` on every call; test.
* [ ] F7 — `speech.tsx` spreads `userIdHeaders()`; test.

### Phase 4 — Bootstrap + UI

* [ ] F8 — auth context / provider (`userId`, `userInfo`, `authEnforced`) or `AppShell` state; vitest.
* [ ] F9 — bootstrap effect in `App.tsx` `AppShell`: read `auth_enforced`, call `getUserInfo()`, set the resolved or default user, mark blocked when enforced but absent; vitest.
* [ ] F10 — blocked-screen component (Fluent v9 adaptation of the v1 "Authentication Not Configured" screen); vitest.
* [ ] F11 — render the blocked screen in the shell when `authEnforced && !userId`; vitest.

### Phase 5 — Verify

* [ ] Frontend: `vitest run`; `tsc -b` in both `v2/src/frontend` and `v2/src/tests/frontend`; `eslint` on touched files.
* [ ] Backend: `pytest` (health + dependencies); `pyright --strict`; shared AST gates.
* [ ] Live (`5273` / `8000`): two users get distinct histories; delete only own (cross-user `404`); local uses the default user; every request carries `x-ms-client-principal-id`; auth enforced + no `/.auth/me` → blocked screen.

## Relevant files

* Backend (reference — already user-scoped): [routers/history.py](../src/backend/routers/history.py), [routers/conversation.py](../src/backend/routers/conversation.py), [dependencies.py](../src/backend/dependencies.py), [core/providers/databases/cosmosdb.py](../src/backend/core/providers/databases/cosmosdb.py), [core/providers/databases/postgres.py](../src/backend/core/providers/databases/postgres.py).
* Backend (change): [models/health.py](../src/backend/models/health.py), [services/health.py](../src/backend/services/health.py), [routers/health.py](../src/backend/routers/health.py); optionally [dependencies.py](../src/backend/dependencies.py).
* Frontend (new): `v2/src/frontend/src/api/auth.tsx`; the auth models module; optionally an auth context module.
* Frontend (change): the four `api/*.tsx` clients and `App.tsx`.
* Patterns (read-only): v1 `code/frontend/src/api/api.ts` + `code/frontend/src/pages/layout/Layout.tsx`; MACAE `data/sample_code/macae/src/frontend/src/api/`.

## Out of scope

* Forwarding the admin claims blob from the browser (admin RBAC stays backend-trusted).
* Frontend / backend Easy Auth infrastructure (Bicep) — this plan is code-only.
* MSAL / JWT bearer flows (explicitly not the chosen pattern).
* BUG-0045 (chat double scroll — operator-owned).

## References

* [bugs.md](bugs.md) — `BUG-0046`.
* [worklog/2026-06-15.md](worklog/2026-06-15.md).
* [development_plan.md](development_plan.md).
