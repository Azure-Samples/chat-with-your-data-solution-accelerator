# CWYD v2 — Admin Runtime Configuration

> Pillar: **Stable Core** · Phase: **5** (Admin + Frontend Merge)
> Source files: [v2/src/backend/routers/admin.py](../src/backend/routers/admin.py), [v2/src/backend/models/admin.py](../src/backend/models/admin.py), [v2/src/backend/core/types.py](../src/backend/core/types.py), [v2/src/backend/core/providers/databases/](../src/backend/core/providers/databases/), [v2/src/backend/dependencies.py](../src/backend/dependencies.py)

This document explains the v2 backend's **admin surface** — the five HTTP routes under `/api/admin/`, the runtime-override store behind them, and the live-reload contract that lets an admin change behavior without redeploying or restarting the container.

The frontend integration of this surface lives in [`v2/src/frontend/src/api/admin.ts`](../src/frontend/src/api/admin.ts) and is tracked as Phase 5-FE in [development_plan.md](development_plan.md) §0.1. **The backend half of every route below is shipped and tested.** The FE form / page that consumes it is FE-team work and is not a backend blocker.

---

## 1. Design principles

1. **Sanitize at the boundary.** `/api/admin/status` is a read-only allow-list snapshot — secrets, tenant IDs, UAMI IDs, connection strings, and API version pins never leave the process. The allow-list is locked by `test_status_does_not_leak_sensitive_settings`. Adding a field to `AdminStatus` is a deliberate, test-gated act, not an accident of `AppSettings` growth.
2. **Two layers, one effective view.** Operator overrides do not replace env defaults — they overlay them. `AppSettings` defines the baked-in baseline (from `.env` / Bicep outputs / Container App env vars); `RuntimeConfig` stores the operator's deltas; `EffectiveAdminConfig` is the merged result with per-field provenance so the UI can show "this value came from env" vs "this value was set by `<admin>` at `<time>`".
3. **RFC 7396 JSON Merge Patch.** `PATCH /api/admin/config` accepts a sparse JSON body. Each key is one of three states: present-with-value (set override), present-as-`null` (clear override → fall back to env), absent (leave untouched). Unknown keys are rejected with 422 — the writable surface is an explicit `WRITABLE_FIELDS` allow-list, not "anything Pydantic accepts".
4. **Live-reload, no restart.** A successful PATCH writes the new `RuntimeConfig` row through the database client and immediately reassigns `request.app.state.runtime_overrides`. The very next request sees the new value. No container recycle, no SIGHUP, no eventual-consistency window beyond a single round-trip to the database.
5. **Audit-on-success, fire-and-forget.** Every successful PATCH writes one row to the `admin_audit` log (Cosmos `type="audit"` item, or Postgres `admin_audit` table) capturing actor, action, before-state, after-state, and timestamp. Audit-write failure logs an error but does **not** roll back the PATCH — the override is authoritative; the audit trail is best-effort.
6. **Both database modes.** All persistence flows through the abstract database provider Protocol. `databaseType=cosmosdb` and `databaseType=postgresql` both implement the full `(get_runtime_config, upsert_runtime_config, write_admin_audit)` triplet. See [infrastructure.md](infrastructure.md) §2.2.1 for the one-shot nature of that choice.
7. **Header user-id resolved.** Every route under `/api/admin/` declares `UserIdDep` ([v2/src/backend/dependencies.py](../src/backend/dependencies.py)) — the dependency reads the `x-ms-client-principal-id` header, validates it is a GUID, returns it as the caller's user id, and otherwise falls back to the anonymous default GUID. There is no application-layer role gate; identity enforcement, when enabled, is an ingress/proxy concern (see [ADR 0031](adr/0031-backend-admin-auth-header-only-ingress-enforced.md)).

---

## 2. Routes

All routes are mounted under `/api/admin/`. All resolve the caller's user id from the `x-ms-client-principal-id` header. All return JSON.

### 2.1 `GET /api/admin/status` → `AdminStatus`

Sanitized snapshot of running backend configuration. Used by the FE to display "what backend am I talking to and what is it configured for" without exposing anything secret. Already consumed by [`v2/src/frontend/src/api/admin.ts`](../src/frontend/src/api/admin.ts) (`getAdminStatus()`).

Status codes: `200` on success.

**Response fields** ([v2/src/backend/models/admin.py](../src/backend/models/admin.py) — 12 fields, `extra="forbid"`):

| Field | Type | Source |
|---|---|---|
| `orchestrator_name` | `str` | `settings.orchestrator.name` |
| `db_type` | `str` | `settings.database.type` |
| `index_store` | `str` | `settings.database.index_store` |
| `environment` | `str` | `"local"` or `"production"` |
| `foundry_project_endpoint_host` | `str` | hostname of `settings.foundry.project_endpoint`, path stripped |
| `gpt_deployment` | `str` | `settings.llm.gpt_deployment` |
| `embedding_deployment` | `str` | `settings.embedder.deployment_name` |
| `search_enabled` | `bool` | true iff `settings.search.service_endpoint` is set |
| `app_insights_enabled` | `bool` | true iff `settings.observability.application_insights_connection_string` is set |
| `cors_origins` | `list[str]` | `settings.cors.allow_origins` |
| `version` | `str` | `APP_VERSION` constant (currently `"2.0.0"`) |

**Excluded by design** (locked by `test_status_does_not_leak_sensitive_settings`): tenant ID, UAMI client/principal IDs, every `*_connection_string`, every `*_key`, API version pins. Any future field must opt-in explicitly.

### 2.2 `GET /api/admin/config` → `AdminConfig`

Read-only view of the **mutable runtime-toggle subset** of `AppSettings`. This is the field set that `PATCH /api/admin/config` is allowed to override. The two models are deliberately one-to-one so the UI can render the same form for read and write.

Status codes: `200`.

**Response fields** ([v2/src/backend/models/admin.py](../src/backend/models/admin.py) — 7 fields, `extra="forbid"`):

| Field | Type | Source default |
|---|---|---|
| `orchestrator_name` | `str` | `settings.orchestrator.name` |
| `openai_temperature` | `float` | `settings.llm.openai_temperature` |
| `openai_max_tokens` | `int` | `settings.llm.openai_max_tokens` |
| `search_use_semantic_search` | `bool` | `settings.search.use_semantic_search` |
| `search_top_k` | `int` | `settings.search.top_k` |
| `log_level` | `str` | `settings.observability.log_level` |
| `content_safety_enabled` | `bool` | `settings.content_safety.enabled` |

Sensitive fields (UAMI / tenant / connection strings / API version) are excluded by the same allow-list discipline as `AdminStatus`, locked by `test_config_does_not_leak_sensitive_settings`.

### 2.3 `PATCH /api/admin/config` → `RuntimeConfig`

Apply a JSON Merge Patch (RFC 7396) over the same 7-field surface as `GET /api/admin/config`. The patch payload is sparse: only the keys you want to change need to appear.

Status codes: `200` on success · `422` unknown field or wrong type · `500`/`503` storage failure.

**Body semantics:**

| Key state | Meaning |
|---|---|
| Present, with a value | Set the override to that value |
| Present, with `null` | Clear the override → fall back to env default |
| Absent | Leave the current override (or absence) untouched |

The full set of writable keys is the `WRITABLE_FIELDS` allow-list in the route — any key outside it produces `422 Unprocessable Entity`. There is no "passthrough" path.

**Server-assigned audit fields** on every successful PATCH:

- `updated_at` — ISO-8601 UTC timestamp of the upsert
- `updated_by` — the caller's user id (from the `x-ms-client-principal-id` header via `get_user_id`)

**Live-reload:** after the storage upsert succeeds, the route reassigns `request.app.state.runtime_overrides = merged`. This is a single Python attribute write — atomic from the perspective of the next request, no IPC, no message bus.

**Audit:** the route fires `write_admin_audit(...)` asynchronously after the PATCH succeeds. Audit-write failure is logged via `logger.exception(...)` with structured `extra={"operation": "admin_audit_write", ...}` and **does not** roll back the PATCH. The override is the source of truth; the audit trail is the operator's receipt.

### 2.4 `GET /api/admin/config/effective` → `EffectiveAdminConfig`

The merged view that powers the admin UI's "current effective config" panel. Combines env defaults with persisted overrides and tells the caller, per field, where each value came from.

Status codes: `200`.

**Response shape** ([v2/src/backend/models/admin.py](../src/backend/models/admin.py)):

```json
{
  "values": { /* full AdminConfig — every field resolved */ },
  "sources": { "orchestrator_name": "env", "openai_temperature": "override", ... },
  "updated_at": "2026-06-01T14:23:11.482Z",
  "updated_by": "00000000-0000-0000-0000-000000000000"
}
```

- `values` is a full `AdminConfig` (every field non-null) — for each field, the override wins if present, else the env default.
- `sources` is a per-field `ConfigSource` discriminator — `"env"` if the value came from `AppSettings`, `"override"` if the value came from the persisted `RuntimeConfig` row. `ConfigSource` is a `StrEnum` (per Hard Rule #11).
- `updated_at` / `updated_by` are populated iff a `RuntimeConfig` row exists in the database — even if every field on that row is `None` (the row is the receipt that an operator interacted with the surface).

**Performance:** the override read happens once at startup (`app.lifespan` calls `database_client.get_runtime_config()` and stashes the result on `app.state.runtime_overrides`). The effective-config endpoint reads from `app.state`, not the database — no DB round-trip per request.

### 2.5 `DELETE /api/admin/documents/{source:path}` → `DeleteDocumentResponse`

Delete every indexed chunk whose `source` field (filename for uploaded files, URL for URL-ingested pages) matches the path segment.

Status codes: `200` with `{"deleted": N}` when N≥1 chunks removed · `404` no matching chunks · `503` search backend not configured (backend-only dev profile).

**Dispatch** through `SearchProviderDep` → `await search.delete_by_source(source)`:

- **Azure Search** ([v2/src/backend/core/providers/search/azure_search.py](../src/backend/core/providers/search/azure_search.py)) — `title eq '<escaped_source>'` OData filter (single-quote escaping `'` → `''` per Azure spec), batch deletes through `SearchClient.delete_documents()` (1000-doc per-batch ceiling), aggregates count across batches. `AzureError` wrapped per Hard Rule #14.
- **pgvector** ([v2/src/backend/core/providers/search/pgvector.py](../src/backend/core/providers/search/pgvector.py)) — parameterized `DELETE FROM <table> WHERE source = $1 RETURNING id`, returns `len(rows)`. `asyncpg.PostgresError` wrapped per Hard Rule #14.

Both backends are wired today. This route works in both `databaseType` modes (it does not share the `B2-INGEST-PGVECTOR` defect — that one is on the Functions ingest blueprints, not the backend admin surface).

---

## 3. Persistence layer

The store sits behind the abstract database provider Protocol — three async methods on every concrete implementation:

```text
async def get_runtime_config(self) -> RuntimeConfig | None
async def upsert_runtime_config(self, config: RuntimeConfig) -> None
async def write_admin_audit(self, entry: AdminAuditEntry) -> None
```

Source: [v2/src/backend/core/providers/databases/base.py](../src/backend/core/providers/databases/base.py).

### 3.1 Cosmos DB layout

Source: [v2/src/backend/core/providers/databases/cosmosdb.py](../src/backend/core/providers/databases/cosmosdb.py).

- **Runtime config item.** Singleton in the conversation container under the synthetic system partition.
  - `id = "runtime"` (fixed, not operator-controlled)
  - `partition_key = "_system"`
  - `type = "config"` (`CosmosItemType.CONFIG` per Hard Rule #11)
  - `payload = <RuntimeConfig dict>`
  - Read: `container.read_item(item="runtime", partition_key="_system")` — single-RU point read
  - Write: `container.upsert_item(body=...)` — atomic CREATE-or-REPLACE
- **Audit items.** Append-only, per-event.
  - `id = uuid4()` (app-generated)
  - `partition_key = "_system"`
  - `type = "audit"`
  - Write via `container.create_item(...)` (raises 409 on UUID collision rather than silently overwriting)

### 3.2 PostgreSQL layout

Source: [v2/src/backend/core/providers/databases/postgres.py](../src/backend/core/providers/databases/postgres.py).

- **`runtime_config` table** — singleton enforced by CHECK constraint:
  ```sql
  CREATE TABLE runtime_config (
      id         INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
      payload    JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```
  Upsert: `INSERT INTO runtime_config (id, payload) VALUES (1, $1) ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()`.
- **`admin_audit` table** — append-only:
  ```sql
  CREATE TABLE admin_audit (
      id         TEXT PRIMARY KEY,
      actor      TEXT NOT NULL,
      action     TEXT NOT NULL,
      before     JSONB,
      after      JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```
  `id` is an app-generated UUID4 string (deliberately avoids the `pgcrypto` extension dependency); `created_at` is filled by the DB default.

### 3.3 Live-reload channel

1. `app.lifespan` (in [v2/src/backend/app.py](../src/backend/app.py)) calls `await database_client.get_runtime_config()` once at startup.
2. The result (a `RuntimeConfig | None`) is stored on `app.state.runtime_overrides`.
3. `GET /api/admin/config/effective` and the chat pipelines read from `app.state.runtime_overrides` via the `get_runtime_overrides(request)` dependency — no per-request DB read.
4. `PATCH /api/admin/config` writes to the database, then reassigns `request.app.state.runtime_overrides = merged`. The next request — including the next chat request — sees the new effective config.

This is the live-reload contract: **a successful PATCH is visible to every other request within one network round-trip, with no container restart.**

---

## 4. What is and isn't admin-mutable

The split between **build-time / deploy-time settings** and **runtime-mutable settings** is deliberate. Operators flipping the wrong knob from the admin UI must not be able to break the deployment.

**Admin-mutable** (the 7 `AdminConfig` fields above) — chosen because they are pure runtime behavior toggles that take effect on the next chat request without needing new credentials, new endpoints, or new provisioned resources.

**Not admin-mutable — change via `azd env set` + redeploy:**

- Anything under `settings.identity.*` — tenant ID, UAMI client/principal IDs. Changing identity at runtime would break every outgoing token request.
- Anything under `settings.foundry.*` (endpoint, project, model deployment names) — these correspond to provisioned Azure resources; flipping the string does not move the resource.
- Anything under `settings.database.*` (`type`, connection details, container/table names) — see [infrastructure.md](infrastructure.md) §2.2.1; `databaseType` is a one-shot provisioning-time choice.
- API version pins (`api_version` on the LLM client, etc.) — these are SDK contracts, not toggles. Bumping them is a code-and-test change, not an operator action.
- Anything under `settings.search.service_endpoint` / `settings.embedder.endpoint` — same logic as Foundry: the string is bound to a provisioned resource.
- Anything secret. There are no secrets in `AppSettings` to begin with (AAD-only, no Key Vault per [infrastructure.md](infrastructure.md) §1) — but the rule is reaffirmed here so future field additions don't drift.

---

## 5. Per-tenant overrides (#35g) — withdrawn (out of scope)

**Status: withdrawn. The singleton is the final design for this product. See [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md).**

`#35g` proposed keying `RuntimeConfig` by the caller's Entra tenant id so that one deployment could serve multiple Entra organizations with independent config. **That premise does not hold for CWYD.** The deployment is single-tenant (`v2/infra/main.bicep` binds every tenant reference to `subscription().tenantId`; there is no multi-org Entra app registration), and all data is **user-scoped** (the Cosmos partition key is `/userId`; Postgres reads are `WHERE user_id = $1`). Because the tenant id (`tid`) is constant for a single-tenant deployment, keying the config by it would be a **functional no-op** over the existing singleton — and re-keying one admin row while chat history, documents, and the search index stay user-scoped would be incoherent half-multi-tenancy.

The speculative tenant-claim seam that was shipped for this (`get_tenant_id` / `TenantIdDep` in [dependencies.py](../src/backend/dependencies.py)) is therefore dead code and has been removed. The incident and the full reasoning are recorded in [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md), which supersedes [ADR 0023](adr/0023-per-tenant-runtime-config-keying.md).

**The `RuntimeConfig` singleton is correct and final:** every admin caller with the `admin` role sees and mutates the same one override document per deployment. Reopen `#35g` only if a real requirement to serve multiple Entra organizations from one deployment is introduced — together with a plan to tenant-scope chat history, documents, and the search index too, not just the admin config row.

---

## 6. Test coverage

Source: [v2/tests/backend/test_admin.py](../tests/backend/test_admin.py) — 49 test functions covering the full surface:

| Area | Count | What it locks |
|---|---|---|
| `GET /api/admin/status` | 11 | Field set, value mapping, host extraction, search/AppInsights truthiness, CORS pass-through, leak guard, 200 status |
| `GET /api/admin/config` | 11 | Field set, value mapping for each writable field, leak guard, production auth |
| `PATCH /api/admin/config` | 17 | Single-field persist, unknown-field 422, wrong-type 422, null clears override, sparse merge preserves siblings, audit timestamp + caller capture, response = persisted state, app-state live-reload, audit-on-success + best-effort failure handling |
| `GET /api/admin/config/effective` | 6 | Env-only cold start, partial overlay, full override, content-safety override, explicit-None treated as env |
| Models / `ConfigSource` enum | 7 | StrEnum subclass + member set + wire serialization round-trip |
| `DELETE /api/admin/documents/{source}` | 4 | 200 + count on success, 404 on no match, 503 when search disabled, auth |
| Pillar/phase header | 1 | Hard Rule #3 enforcement |

Database-side audit + runtime-config tests live under [v2/tests/backend/core/providers/databases/](../tests/backend/core/providers/databases/) and assert: canonical row shape, `before=None` on first patch, distinct UUIDs across audit rows, SDK error logged-and-re-raised on both backends.

Current full-suite baseline: **1879 passed / 1 skipped / 3 deselected / 4 warnings** (Phase 7 backend-tier drained; see [development_plan.md](development_plan.md) §0).
