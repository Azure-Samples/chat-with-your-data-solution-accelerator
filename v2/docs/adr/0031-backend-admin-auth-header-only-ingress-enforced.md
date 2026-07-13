# ADR 0031 — Backend admin auth is header-only; real enforcement is ingress-level

- **Status**: Accepted
- **Date**: 2026-07-02
- **Phase**: 5 (admin auth posture — `BUG-0090`)
- **Pillar**: Configuration Layer (the deployment auth posture) over Stable Core (the `get_user_id` dependency contract)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes / amends**: none (first ADR to record the admin auth posture)
- **Companion**: [BUG-0090](../bugs.md), [BUG-0091](../bugs.md); mirrors MACAE (`get_authenticated_user_details`)

## Context

The CWYD v2 backend previously carried two layers of identity handling in application code:

- `get_user_id` — the chat/history extractor. It read `x-ms-client-principal-id`, validated it against a broad non-GUID allowlist, and raised `401` on a malformed or (with the wall on) missing header.
- `requires_role("admin")` — an Easy Auth **role gate** on every `/api/admin/*` route. It required the base64 `x-ms-client-principal` **claims** blob, decoded it, extracted roles, and required the `admin` role. It fired only when `environment=production` **and** `require_admin_auth=true`.

The single-page app (SPA) forwards only the `x-ms-client-principal-id` header — never the base64 claims blob (a browser-forged claims blob would let any caller assert the `admin` role, so the SPA deliberately does not send one). In a deployment that set `AZURE_ENVIRONMENT=production` and `AZURE_REQUIRE_ADMIN_AUTH=true`, the claims check therefore failed for every caller and `GET /api/admin/status` returned `401` ([BUG-0090](../bugs.md)). The endpoint was correct; the gate it carried was the defect.

The product intent (owner directive, 2026-07-02) is simpler than the code that shipped:

- The frontend collects a real `user_id` (Entra `oid`) and initials when authentication is enabled, and a default GUID plus a `G` guest initial when it is not.
- The frontend always forwards `user_id` in a request header.
- The backend does **one** thing: check that the header is present and is a valid GUID. Nothing more.
- Real authentication, when wanted, is turned on at the **frontend / ingress** (the identity provider at the proxy) — not in application code.

This is exactly the [MACAE](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator) posture: its `get_authenticated_user_details` reads the header, falls back to an all-zeros sample principal, and **never raises** — enforcement is upstream at Easy Auth, not per-route in Python.

## Decision

1. **The backend no longer enforces admin authentication in application code.** The entire Easy Auth role gate is removed: `requires_role`, its checker, the claims-blob decode and role-extraction helpers, `REQUIRE_ADMIN_USER` / `AdminUserIdDep`, and the `require_admin_auth` setting. The `AZURE_REQUIRE_ADMIN_AUTH` Bicep env var on the backend Container App (`ca-backend-<SUFFIX>`) is dropped with it.

2. **One minimal `get_user_id` dependency serves chat, history, and admin alike.** It reads `x-ms-client-principal-id`; if the value is present **and** a valid GUID it is used, otherwise it falls back to the anonymous default GUID `00000000-0000-0000-0000-000000000000`. It **never raises** — so `/api/admin/status` (and every admin route) can no longer `401`. The returned value is always a non-empty string, preserving the Cosmos / Postgres partition-key contract.

3. **`user_id` arrives as a trusted, client-forgeable header.** The backend validates only that the header is a well-formed GUID. It is a partition key for chat history, not a secrets boundary. The backend makes no attempt to prove the caller is who the header claims.

4. **Real authentication, when enabled, is an ingress/frontend concern.** When an operator turns authentication on, the identity provider (for example Container Apps or App Service Easy Auth at the proxy) injects and overwrites `x-ms-client-principal-id` before the request reaches the backend, so the trusted header carries a real, proxy-attested identity. The durable protection for admin-write exposure is therefore network / ingress level — private backend ingress, or Easy Auth at the Container App ingress the operator opts into — not application-code role gates.

5. **The frontend is already compliant; no frontend change is made.** It forwards `x-ms-client-principal-id` on every request, defaults to the guest GUID `00000000-0000-0000-0000-000000000000` when no principal is resolved, and renders `G` for the guest badge. This matches decisions (2)–(4) as-is.

## Consequences

- **+** `/api/admin/status` (and every admin route) can no longer `401`; the admin panel loads without a backend identity source.
- **+** One identity contract across chat, history, and admin — a single `get_user_id` seam, no role-gate cluster, no broad non-GUID allowlist, no environment-based auth branching. The backend matches the MACAE mental model the owner asked for.
- **+** The removed code (the claims-blob decode, role extraction, the `require_admin_auth` flag, the `AZURE_REQUIRE_ADMIN_AUTH` env var) is dead-code debt retired in the same change, not left tested-but-unused.
- **−** **Security tradeoff (stated explicitly):** `x-ms-client-principal-id` is a client-set, forgeable header. After this change, any caller who can reach the backend FQDN can present any GUID and call admin routes — reads **and** writes — unless ingress-level authentication is enabled. This is accepted only because (a) it matches MACAE's posture; (b) `user_id` is a history-partition key, not a secrets boundary; and (c) the owner's model is that real auth is turned on at the frontend / ingress, where the proxy injects and overwrites the header. Operators who expose the backend FQDN publicly without ingress auth accept open admin writes.
- **−** The backend alone cannot distinguish an authenticated admin from an anonymous caller; that distinction now depends entirely on the ingress configuration. There is no in-app fail-closed default.

## Security tradeoff and mitigations

The forgeable-header trust is deliberate, but it must be paired with a deployment-level control whenever admin writes matter:

- **Ingress authentication** — enable Easy Auth on the backend Container App ingress (or front the backend behind a proxy that authenticates and injects the header). The proxy overwrites any client-supplied `x-ms-client-principal-id`, so a forged value cannot survive.
- **Network restriction** — restrict backend ingress to the frontend origin / a private network so the backend FQDN is not reachable by arbitrary callers.

Absent either control, admin routes are open on the backend FQDN. The registry entry for [BUG-0090](../bugs.md) records the same tradeoff.

## Revert path

If the deployment must re-enforce admin authentication in application code (rather than at ingress), the change is reversible:

1. Re-add the Easy Auth role gate (`requires_role("admin")` and its claims-blob decode + role-extraction helpers) and re-attach it to the `/api/admin/*` routes in place of `get_user_id`.
2. Re-add the `require_admin_auth` setting and gate the role check on `environment=production` **and** `require_admin_auth=true`.
3. Re-add the `AZURE_REQUIRE_ADMIN_AUTH` env var on the backend Container App (`ca-backend-<SUFFIX>`) in the Bicep, and provision the identity source the gate depends on (an Entra app registration defining the `admin` app role, plus the ingress that injects the claims blob).

The `get_user_id` contract stays valid for chat and history in either posture; the revert only re-adds the admin-specific gate on top.

## Alternatives considered

- **A — Wire Container Apps Easy Auth on the backend behind an Entra app registration with an `admin` app role, and keep the role gate.** Rejected: contradicts the owner directive ("any extra safety is unnecessary"; the `401` "shouldn't even exist"), adds structural infra + Entra provisioning, and keeps the heavy role gate. It also diverges from MACAE, which enforces at the proxy, not per route.
- **B — Reverse-proxy `/api/*` through the frontend and reuse the frontend's Easy Auth + `admin` role.** Rejected: same objections as A, plus new proxy plumbing in `frontend_app.py`. The frontend is a Container App, so this option is also topology-stale.
- **C — Keep both extractors; relax only `/api/admin/status` to the header extractor.** Rejected as insufficient: it leaves the role gate on admin **write** routes and the broad non-GUID allowlist, so the backend still does "extra safety" the owner asked to remove and still `401`s on writes. The owner's rule is a general contract, so it applies to every route uniformly.
- **D — On a present-but-invalid GUID, return `400` (strict) instead of falling back to the default.** A purer reading of "check it is a valid GUID", but it introduces an error path MACAE does not have, and the frontend guarantees a valid GUID so it never triggers in practice. Not selected; the never-raise fallback keeps the contract identical to MACAE.

## Follow-ups

- **Live verification (Phase 6).** The delivered fix is verified by the backend + infra test suites; live confirmation that `GET /api/admin/status` returns `200` on the deployed backend without a claims header is a Phase 6 step. The [BUG-0090](../bugs.md) registry status stays `open` until then.
- **Stale frontend docstring.** The `api/auth.tsx` header docstring still reads "admin RBAC stays anchored on the backend's own server-injected Easy Auth claims", which is stale after this decision (the backend no longer has an admin RBAC gate). Correcting it is a frontend edit deliberately out of scope for the BUG-0090 documentation step; it is noted here as a follow-up.
