# ADR 0023 — Per-tenant `RuntimeConfig` storage keying (`#35g`)

> **Superseded by [ADR 0024](0024-withdraw-per-tenant-runtime-config-single-tenant.md) (2026-06-10).** The single-tenant deployment model makes per-tenant keying a functional no-op over the existing singleton, so `#35g` is withdrawn and the tenant-claim seam this ADR consumed is removed. The storage design below is retained as history should a genuine multi-org requirement ever be introduced — read ADR 0024 for the scope decision, the incident analysis, and the reopen criteria.

- **Status**: Superseded by [ADR 0024](0024-withdraw-per-tenant-runtime-config-single-tenant.md) (2026-06-10)
- **Date**: 2026-06-09
- **Phase**: 5 (`#35g` — per-tenant overrides; executed during the Phase 6 window)
- **Pillar**: Configuration Layer (per-tenant override resolution) over Stable Core (the tenant-keyed storage methods on `BaseDatabaseClient` + the Cosmos / Postgres providers)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes / amends**: amends the caching mechanism introduced for `#35e(a)` (process-global `app.state.runtime_overrides` preload + PATCH write-back) — see Decision 4
- **Companion**: the tenant-claim unblock (`get_tenant_id` + `TenantIdDep` in [dependencies.py](../../src/backend/dependencies.py), decoding the Easy Auth `tid` claim) that this ADR consumes; [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) (effective-config resolution choke point)
- **Superseded by**: [ADR 0024](0024-withdraw-per-tenant-runtime-config-single-tenant.md) — `#35g` withdrawn for the single-tenant deployment model; the tenant-claim seam is removed and the singleton is retained

## Context

`RuntimeConfig` is the admin-mutable override layer over `AppSettings` — orchestrator name, OpenAI temperature/max-tokens, search toggles, log level, content-safety flag, and the operator-editable prompts. It is persisted by `BaseDatabaseClient` and overlaid on the env / code defaults at request time by `resolve_effective_config(...)` in [services/admin.py](../../src/backend/services/admin.py).

Today it is a **single global override** (one document for the whole deployment):

- **Cosmos** — one item `id="runtime"` (`CosmosFixedItemId.RUNTIME_CONFIG`), `type="config"`, pinned to the synthetic `_system` partition (`CosmosSystemPartition.DEFAULT`); a 1-RU point-read in `get_runtime_config` ([cosmosdb.py](../../src/backend/core/providers/databases/cosmosdb.py)).
- **Postgres** — a `runtime_config` table keyed `id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1)`; the `CHECK` enforces the singleton at the DB layer ([postgres.py](../../src/backend/core/providers/databases/postgres.py)).
- **Contract** — `get_runtime_config() -> RuntimeConfig | None` / `upsert_runtime_config(config)` on [base.py](../../src/backend/core/providers/databases/base.py) take **no tenant argument**.
- **Caching (`#35e(a)`)** — the FastAPI lifespan loads the single override **once** at startup into `app.state.runtime_overrides`; `get_runtime_overrides` reads that attribute; the `PATCH /api/admin/config` route reassigns it after each successful upsert (same-replica live-reload).

`#35g` requires **per-tenant** config isolation: each Entra tenant sees and edits its own overrides. The prerequisite — extracting the tenant id from the Easy Auth `x-ms-client-principal` `tid` claim — shipped as `get_tenant_id` + `TenantIdDep` in [dependencies.py](../../src/backend/dependencies.py) (`#39` had surfaced role claims only).

**The obstacle is the caching model, not the schema.** The override is a process-global singleton loaded once at startup. Per-tenant means N override documents, so there is no single "the" override to preload — resolution must become tenant-keyed and on-demand, threading `TenantIdDep`. This is a structural change to storage schema, the Cosmos partition strategy, **and** the request-time resolution model, so it is gated by Hard Rule #10 (sign-off granted 2026-06-09).

## Decision

1. **Tenant is a storage *key*, threaded as `tenant_id: str`** on `get_runtime_config(tenant_id)` / `upsert_runtime_config(tenant_id, config)` (and on the read dependency). It is **not** a field on the `RuntimeConfig` payload model — the payload carries override values, the tenant identifies which document, exactly as the singleton key (`id="runtime"` / `id=1`) lives outside the payload today.

2. **Cosmos: keep the `_system` partition; namespace the item id `id=f"runtime::{tenant}"`.** The runtime-config rows stay co-located with the sibling `_system` rows (agent registry, admin audit), the point-read stays 1-RU, and no new partition is introduced. The existing `type == "config"` guard stays, so an id collision with a same-partition agent row degrades to `None` rather than mis-resolving. Cardinality is `# of tenants` (bounded, read-mostly), well under the 20 GB logical-partition cap. *(Rejected alternative A2: tenant as the partition key — see Alternatives.)*

3. **Postgres: replace the `id=1` singleton with `tenant_id TEXT PRIMARY KEY`.** Drop the `CHECK (id = 1)` constraint; read `WHERE tenant_id = $1`; upsert `ON CONFLICT (tenant_id) DO UPDATE`. The `tenant_id` is parameter-bound (never interpolated).

4. **Caching: drop the startup preload + the `app.state.runtime_overrides` single value; resolve per-request via `get_runtime_config(tenant_id)`.** `get_runtime_overrides` becomes tenant-aware (consumes `TenantIdDep` + the DB client). The lifespan no longer preloads, and the PATCH route no longer writes back to `app.state`. This **preserves the `#35e(a)` user-visible behavior** (an override applies on the very next request) while making it **strictly better**: every request reads the tenant's current row, so the result is cross-replica-consistent — it removes the same-replica-only staleness the `app.state` cache had under multi-replica Azure Container Apps. The cost is one cheap point-read per request that consumes overrides (1-RU Cosmos point-read / Postgres PK probe).

5. **Greenfield: no migration shim.** v2 is pre-GA; the legacy singleton row (`id="runtime"` / `id=1`) is simply never read again under the new keying. Operators re-apply overrides per tenant. The lazy `CREATE TABLE IF NOT EXISTS` will **not** alter an existing Postgres `runtime_config` table, so a pre-existing dev table must be dropped and re-created — acceptable pre-GA. *(Rejected alternative D2: backfill the legacy row to a sentinel tenant — see Alternatives.)*

6. **Audit-log tenant-scoping is deferred to a separate unit.** `AdminAuditEntry` + `write_admin_audit` stay global for now; the existing `actor` / `before` / `after` fields still capture *what* changed and *who* changed it. Adding a `tenant_id` dimension to the audit row is a clean follow-up unit, kept out of this change to bound the blast radius.

### Unit sequencing

The change lands test-first, one unit per turn, every step green (Hard Rule #1 / #8):

1. **Tenant-aware contract** — `tenant_id` on the read/write methods of `base.py` + both providers (Cosmos id-namespacing, Postgres `tenant_id` PK) + tests. One polymorphic method contract across its implementations (treated as a single logical unit, as the `requires_role` contract shipped).
2. **Thread the tenant** — `TenantIdDep` through `get_runtime_overrides` + the PATCH route + `resolve_effective_config`; drop the lifespan preload and PATCH write-back (Decision 4).
3. **Remove** the dead singleton methods + old schema remnants.
4. *(Deferred)* tenant-scope the admin audit log (Decision 6).

## Consequences

- **+** Per-tenant config isolation: each tenant's overrides resolve from its `tid` claim; one tenant's PATCH never affects another.
- **+** Cross-replica-consistent live-reload — strictly better than the `#35e(a)` same-replica `app.state` cache under multi-replica ACA.
- **+** Minimal Cosmos blast radius: id-namespacing only, same `_system` partition, same 1-RU point-read profile.
- **+** Simpler lifespan + PATCH route (the preload / write-back dance is removed, not extended).
- **−** One extra DB point-read per request that consumes overrides (cheap, but non-zero). A per-tenant in-process TTL/LRU cache can be reintroduced later if profiling demands it (YAGNI now) — the per-request read seam makes that an additive change.
- **−** Postgres schema change: the `runtime_config` primary key changes shape. Greenfield only (Decision 5); a pre-existing dev table must be dropped + re-created.
- **−** Audit rows are not yet tenant-filterable (deferred to the follow-up unit).
- **−** Removing the singleton methods + the `#35e` preload is a follow-up unit (sequencing), so the tree carries both the old and new read paths briefly between units 1 and 3.

## Alternatives considered

- **A2 — Tenant as the Cosmos partition key** (`partition_key=tenant`, `id="runtime"`). Rejected: it fragments the deliberate `_system` design (agents + audit + config share one synthetic partition) across N partitions for no benefit — the config row is tiny and read-mostly, so co-location and a stable 1-RU point-read win over partition "purity."
- **C2 / C3 — Per-tenant in-process cache** (a `dict[tenant_id, RuntimeConfig | None]` or a TTL/LRU). Rejected for now: it adds cache + invalidation code with **no correctness gain** over the per-request read, which is already cross-replica-correct. The per-request seam keeps this as a clean future optimization gated on profiling, not a guess.
- **D2 — Migrate the legacy global row to a sentinel / home tenant.** Rejected: there is no production override data to preserve pre-GA, so a backfill shim is needless code on a path that will be deleted.
- **E-inline — Tenant-scope the audit log in the same change.** Rejected: it widens the unit's blast radius; the audit tenant dimension is a self-contained follow-up unit.
- **Embedding `tenant_id` in the `RuntimeConfig` payload.** Rejected: the tenant is the document *key*, not an override *value*; keeping it out of the payload matches the singleton precedent and keeps the model clean.
