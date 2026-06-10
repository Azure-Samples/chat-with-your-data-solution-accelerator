# ADR 0024 — Withdraw per-tenant `RuntimeConfig` keying for the single-tenant deployment model (`#35g` scope correction)

- **Status**: Accepted
- **Date**: 2026-06-10
- **Phase**: 5 (`#35g` scope correction; recorded during the Phase 6 window)
- **Pillar**: Configuration Layer (the admin runtime-config surface this decision scopes) — a *withdrawal* decision, so it adds no new `v2/src/**` element
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes**: [ADR 0023](0023-per-tenant-runtime-config-keying.md) — withdraws its per-tenant storage-keying direction for the current single-tenant deployment model (ADR 0023 is retained as design history should multi-org ever be introduced)
- **Companion**: [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) (effective-config resolution choke point); `#35e(a)` `app.state.runtime_overrides` caching, which this ADR **retains unchanged** (ADR 0023's amendment to it is withdrawn along with the rest)

## Context

This ADR documents an incident: `#35g` ("per-tenant config overrides") was advanced — a speculative tenant-claim seam was shipped and a full implementation design was Accepted in [ADR 0023](0023-per-tenant-runtime-config-keying.md) — **before validating that the premise behind it (multiple Entra organizations served by one deployment) is an actual requirement of this product.** It is not.

`RuntimeConfig` is the admin-mutable override layer over `AppSettings` (orchestrator name, OpenAI temperature/max-tokens, search toggles, log level, content-safety flag, operator prompts). Today it is a **singleton** — one override document per deployment:

- **Cosmos** — one item `id="runtime"` pinned to the `_system` partition; a 1-RU point-read.
- **Postgres** — a `runtime_config` table keyed `id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1)`.
- **Caching (`#35e(a)`)** — the FastAPI lifespan loads the single override once at startup into `app.state.runtime_overrides`; the PATCH route reassigns it after each upsert.

`#35g` proposed re-keying this by the caller's Entra tenant id (`tid`). To enable that, a tenant-claim extraction seam (`get_tenant_id` + `TenantIdDep` + `_extract_tenant_id` in [dependencies.py](../../src/backend/dependencies.py), plus 9 unit tests) was shipped as an "unblock," and ADR 0023 locked the storage-keying design (Cosmos id-namespacing, Postgres `tenant_id` PK, per-request resolution).

**The premise does not hold for this product.**

## Decision

1. **Withdraw per-tenant `RuntimeConfig` keying for the current scope.** The singleton runtime config is **retained** — it is correct for a single-tenant deployment.
2. **Supersede [ADR 0023](0023-per-tenant-runtime-config-keying.md).** Its design is sound *for a genuine multi-org requirement* and is kept as history, but it is not implemented now.
3. **Retain `#35e(a)` `app.state.runtime_overrides` caching unchanged.** ADR 0023 proposed amending it (drop the preload, resolve per-request); that amendment is withdrawn — the existing startup-preload + PATCH-writeback channel stays.
4. **Remove the speculative tenant-claim seam.** `get_tenant_id`, `TenantIdDep`, `_extract_tenant_id`, the tenant-only constants, and the 9 tenant-claim unit tests are dead code (no router or service consumes them) and are removed.
5. **Correct all planning/status docs** that describe `#35g` as "designed / pending implementation" or "blocked on `#39`" to reflect the scope decision.

## Incident analysis

### Evidence the deployment model is single-tenant

- **Infrastructure** — [v2/infra/main.bicep](../../infra/main.bicep) states *"single-tenant deployments"* and binds every tenant reference to `subscription().tenantId` (a single constant: `AZURE_TENANT_ID = subscription().tenantId`). There is **no multi-tenant Entra app registration** (no `AzureADMultipleOrgs`, no per-org issuer config).
- **Data model is user-scoped, not tenant-scoped** — the Cosmos partition key is `/userId` (*"every conversation + every message for one user"*) and Postgres reads are `WHERE user_id = $1`. Identity is captured per **user** (`oid`) via Easy Auth, exactly the v1 / multi-agent model.
- **`tid` is constant for a single-tenant deployment.** Keying the runtime config by a value that never varies is **functionally identical to the singleton** it would replace — net behavioral change: zero.

### Root cause

A speculative "unblock" plus an Accepted design were produced ahead of validating the requirement. Hard Rule #10 sign-off *was* obtained for the storage change, but the sign-off covered the *mechanics* (partition/PK/caching) — the **premise** (multi-org-on-one-deployment) was never checked against the deployment model. Per-tenant config was also architecturally incoherent in isolation: if multi-org were real, chat history, documents, and the search index would all need tenant-scoping too — they are all user-scoped today. Re-keying one admin row would have been half-baked multi-tenancy.

## Remediation plan

Lands docs-first so the decision trail explains the code removal, one reviewable unit per turn, every step green (Hard Rule #1 / #8):

1. **Phase 1 — Documentation (this turn).** This ADR; supersede ADR 0023; ADR index row; correct `#35g` in [development_plan.md](../development_plan.md) (§0 Phase 5 row, §0.1 debt row, §4 task row); correct the stale `#35g` narrative in [admin_runtime_config.md](../admin_runtime_config.md), [mvp_status.md](../mvp_status.md), [project_status.md](../project_status.md), [qa_review_plan.md](../qa_review_plan.md).
2. **Phase 2 — Code removal (test-backed units).** (2a) drop the `TenantIdDep` / `get_tenant_id` exports + the tenant-claim test block; (2b) remove `_extract_tenant_id` / `get_tenant_id` and the tenant-only constants; (2c) reference sweep confirming zero remaining usages.
3. **Phase 3 — Validation.** Targeted backend tests, `pyright` strict, shared AST gates, and a doc text-search confirming no stale "blocked on `#39`" `#35g` phrasing remains.

## Consequences

- **+** Docs match the real architecture; no dead code; a smaller, honest auth surface (`get_user_id` + `requires_role` only).
- **+** The singleton `RuntimeConfig` — already correct for single-tenant — is preserved with no churn to storage or the `#35e(a)` cache.
- **−** The 9 tenant-claim tests + the extraction symbols are removed (sunk cost of the speculative unblock).
- **−** If multi-org is ever a real requirement, the work re-derives from ADR 0023 (kept as superseded history) **plus** a fresh requirements pass that also tenant-scopes chat history, documents, and the search index — not just the admin config row.

## Alternatives considered

- **Keep the tenant-claim seam "just in case."** Rejected: dead code rots and contradicts the clean / no-speculative-abstraction discipline; the seam is re-addable in an afternoon if a real requirement lands.
- **Implement `#35g` anyway.** Rejected: a no-op for single-tenant, and incoherent as isolated multi-tenancy while every other data axis stays user-scoped.
- **Leave the docs as "blocked on `#39`."** Rejected: stale and false — `#39` shipped 2026-05-06; the block was never the real constraint. The real finding is that the feature is out of scope.

## Reopen criteria

Reopen `#35g` (and revisit ADR 0023) only when **both** hold: (a) a concrete requirement to serve multiple Entra organizations from one deployment, and (b) a companion plan to tenant-scope chat history, documents, and the search index alongside the admin config row.
