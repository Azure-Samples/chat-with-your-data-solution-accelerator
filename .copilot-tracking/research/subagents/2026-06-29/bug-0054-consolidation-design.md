# Research: BUG-0054 deploy reconciliation + search-provider/parser-key consolidation design

Status: Complete

## Research topics / questions

### TASK A — Reconcile cloud-deployment state of `blob_event` for BUG-0054
- Is `blob_event` deployed to the cloud function app today?
- Has `AZURE_INGESTION_TRIGGER` been flipped to `event_grid` in the azd env?
- Has the `doc-processing-poison` queue been drained?
- Exact remaining steps (ordered) to close BUG-0054.

### TASK B — Design consolidation of duplicated search-provider resolution block
- Quote all 4 sites in full.
- Pool lifecycle / `ensure_schema` / `aclose`/`__aexit__` contracts.
- Are the 4 sites identical or do they differ?
- Shared async helper design: signature, return type, home module, which sites it serves.
- Affected test files (`_execute` monkeypatch seams).
- Secondary duplication: `parser_key_for_path(...)` helper.

## Findings

### TASK A — Reconciling the BUG-0054 deploy-state contradiction

#### The contradiction, stated precisely

Two tracked records disagree about whether `blob_event` is in the cloud:

- BUG-0080 (fixed, 2026-06-24) + worklog 2026-06-24.md record `blob_event`
  as DEPLOYED and LIVE in the cloud function app.
- The BUG-0054 detail block in v2/docs/bugs.md + the WI-01 framing in
  worklog 2026-06-29.md still list "deploy `blob_event` to the cloud
  Function App" as PENDING / deferred work.

The reconciliation: **BUG-0080 is correct and current; the BUG-0054 detail
text is stale.** The BUG-0054 "deferred deploy" language was authored on
2026-06-20 (when the multi-day Flex remote-build block was still in force)
and was only lightly touched on 2026-06-29 (to add the `alwaysReady` bicep
note + "trim" the To-resume note). That 2026-06-29 edit never reconciled
against the 2026-06-24 BUG-0080 success — so it still lists "deploy
blob_event" as step 1 of the cutover even though that step completed
2026-06-24.

#### Q1 — Is `blob_event` deployed to the cloud function app today? → YES

Evidence (worklog 2026-06-24.md, BUG-0080):

- Root cause of the prior multi-day block was a dependency-resolution
  conflict, NOT a platform outage: the umbrella `agent-framework==1.7.0`
  pulled `agent-framework-hyperlight` →  unresolvable
  `hyperlight-sandbox-backend-wasm` on the Functions host's Python 3.11,
  so Oryx's remote `pip install` backtracked forever. Repinned to
  `agent-framework-core==1.7.0`.
- Deployed the pre-built package with Oryx skipped:
  `func azure functionapp publish func-<SUFFIX> --no-build --python`
  (logged `[Kudu-OryxBuildStep] Skipping oryx build (remotebuild=false)`,
  ~4.5 min).
- **Verified:** "`blob_event` now live (6 functions: add_url, batch_push,
  batch_start, **blob_event**, health, search_skill); `released-package.zip`
  advanced 2026-06-17 → 2026-06-24; host `Running`; `/api/health` →
  `{"status":"ok"}`." The app went 5 → 6 functions.

Durability check (did a later deploy remove it?):

- Worklog 2026-06-25.md gotcha 2: a `azd deploy function` from the
  workstation now FAILS with `403 InaccessibleStorageException /
  BlobUploadFailedException` because the function's package/documents
  storage account is `publicNetworkAccess=Disabled` and the package-zip
  upload comes over the public internet. So any post-06-24 function
  redeploy attempt would FAIL (not overwrite) — it cannot remove
  `blob_event`.
- `azd provision` (run 2026-06-25 for the KB-MCP seeder, 2026-06-29 for
  backend/frontend) re-applies bicep config but does NOT redeploy function
  *code*; the deployed package in the deployment container persists.

Conclusion: `blob_event` is deployed and remains live. The BUG-0054 detail
block must be updated to drop "deploy blob_event" from the remaining work.

NOTE (research-vs-live caveat): this is a documentation reconciliation. A
100%-definitive live confirmation would be a read-only
`az functionapp function list -g <RESOURCE_GROUP> -n func-<SUFFIX>` showing
6 functions incl. `blob_event`. The doc evidence is strong and internally
corroborated; no live `az` was run (research-only task).

#### Q2 — Has `AZURE_INGESTION_TRIGGER` been flipped to `event_grid`? → NO

Evidence:

- BUG-0054 detail (v2/docs/bugs.md): "The env flag was deliberately not
  flipped to `event_grid`" — backend stays on the default `direct_enqueue`.
- Worklog 2026-06-29.md (most recent), BUG-0054 section: "The cloud cutover
  (deploy `blob_event` + flip `AZURE_ENV_INGESTION_TRIGGER` → `event_grid`)
  stays deferred as WI-01 ... BUG-0054 remains `open`."
- Worklog 2026-06-29.md PD-01: the `ingestion_job_id` drop "stays gated on
  the cloud cutover (WI-01), when `EVENT_GRID` becomes live" — i.e.
  EVENT_GRID is framed as a future state, not yet live.
- Worklog 2026-06-29.md live `/api/health` shows `database pass (cosmosdb)`,
  `search pass (AzureSearch)` and admin uploads working via the current
  `DIRECT_ENQUEUE` path.

Conclusion: the trigger flag is NOT flipped. Backend is still
`direct_enqueue`.

Env-var naming wrinkle to flag: the codebase setting is
`StorageSettings.ingestion_trigger`, env name `AZURE_INGESTION_TRIGGER`
(ADR 0028); bicep param `ingestionTrigger`. The worklogs/bugs use the
`azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` form (the azd
env-key with the `AZURE_ENV_` prefix that azd maps into the bicep param).
The cutover command pair is `azd env set <azd key> event_grid` +
`azd provision` so the deployed `AZURE_INGESTION_TRIGGER` becomes
`event_grid`. Confirm the exact azd→bicep key mapping at cutover time
(read-only `azd env get-values`).

#### Q3 — Has the `doc-processing-poison` queue been drained? → NO (not confirmed; 4 historical messages outstanding)

Evidence:

- Worklog 2026-06-23.md lines 78–79: "The 4 remaining `doc-processing-poison`
  messages are historical, pre-repoint noise." Line 101 lists "Drain the 4
  `doc-processing-poison` messages" as a planned (not-yet-done) cutover step.
- No worklog AFTER 2026-06-23 (i.e. 06-24, 06-25, 06-29) records draining
  `doc-processing-poison`. (An earlier, UNRELATED drain on 2026-06-16 under
  BUG-0034 cleared `doc-processing-poison` 22→0 and
  `doc-processing-local-poison` 10→0 — but that predates the Event-Grid
  repoint and the 4 historical messages noted on 06-23.)

Conclusion: the 4 historical `doc-processing-poison` messages are still
outstanding as of the doc trail. They are "pre-repoint noise" (harmless to
runtime behavior — Event Grid no longer targets `doc-processing`), but the
BUG-0054 close-out checklist includes draining them.

Live caveat: definitive confirmation = read-only
`az storage message peek --queue-name doc-processing-poison --account-name st<SUFFIX> --num-messages 32 --auth-mode login`.

#### Ordered remaining steps to close BUG-0054

State today: `blob_event` deployed (since 06-24); Event Grid subscription
points at `blob-events` per committed `infra/main.bicep` (so new events no
longer poison `doc-processing`); backend still `direct_enqueue`; 4 historical
`doc-processing-poison` messages outstanding; the `alwaysReady` bicep entry
for `function:blob_event` is committed (2026-06-29).

1. **Reconcile the stale record (in-repo, no cloud).** Update the BUG-0054
   detail block in v2/docs/bugs.md to drop "deploy `blob_event`" from the
   remaining work and note the 2026-06-24 deploy (BUG-0080). Without this,
   the next operator re-attempts an already-done (and now 403-blocked)
   function deploy.
2. **Flip the trigger.** `azd env set <ingestion-trigger azd key>
   event_grid` then `azd provision`, so the backend's
   `AZURE_INGESTION_TRIGGER` becomes `event_grid` and the backend STOPS
   direct-enqueuing to `doc-processing` (eliminating the current
   blob_event-vs-backend double path under `direct_enqueue`).
3. **Verify the Event Grid subscription target.** Read-only confirm the
   live system-topic subscription delivers to the `blob-events` queue
   (not `doc-processing`), matching committed `infra/main.bicep`
   (`az eventgrid system-topic event-subscription show ...`).
4. **Cloud end-to-end re-validation (the BUG-0058 gate).** Drop a blob into
   the documents container → Event Grid `BlobCreated` → `blob-events` queue
   → cloud `blob_event` → enqueue to `doc-processing` → `batch_push` →
   parse/embed → write to the index store → source appears in
   `GET /api/admin/documents`. Also exercise the delete path (BUG-0077): a
   blob delete → `BlobDeleted` → `blob_event` → `delete_by_source` drops
   the chunks. Confirm no double-ingestion / no new poison (BUG-0058 clean).
5. **Drain the 4 historical `doc-processing-poison` messages** (operator-
   confirmed clear), so the poison queue reflects only post-cutover reality.
6. **Close BUG-0054** (status open → fixed) and write the worklog.

Gating note: WI-01 was "gated on BUG-0058 cloud verification + the Flex
remote-build timeout." The remote-build timeout is resolved (BUG-0080's
`--no-build` path); the remaining gate is the BUG-0058 cloud re-validation
in step 4. Because `blob_event` is already deployed, NO function code
redeploy is required to close BUG-0054 — only the env flip (provision) +
validate + drain. If a future function redeploy IS ever needed, it must use
either the 06-24 `func ... publish --no-build` path or the 06-25
temporarily-enable-storage-public-access-then-relock workaround (the plain
`azd deploy function` 403s against the locked storage account).

---

### TASK B — Consolidating the duplicated search-provider resolution block

#### The four sites, quoted

**Site 1 — v2/src/functions/batch_push/blueprint.py `_execute` (queue trigger, blob ingest).**
After resolving credential + parser + embedder, the search/pgvector block:

```python
search_key = settings.database.index_store
async with await cred_provider.get_credential() as credential:
    parser = parser_cls(settings=settings, credential=credential)
    embedder_cls = embedders_registry.registry.get("azure_openai")
    embedder = embedder_cls(settings=settings, credential=credential)
    pool_helper: PgVectorPool | None = None
    try:
        search_kwargs: dict[str, Any] = {
            "settings": settings,
            "credential": credential,
        }
        if search_key == IndexStore.PGVECTOR:
            pool_helper = PgVectorPool(settings=settings, credential=credential)
            search_kwargs["pool"] = await pool_helper.acquire()
        search_provider = search_registry.registry.get(search_key)(**search_kwargs)
        try:
            await search_provider.ensure_schema()
            async with ContainerClient(...) as container_client:
                return await batch_push_handler(message=..., container_client=..., parser=parser, embedder=embedder, search_provider=search_provider)
        finally:
            await search_provider.aclose()
    finally:
        if pool_helper is not None:
            await pool_helper.aclose()
        await embedder.aclose()
```

**Site 2 — v2/src/functions/add_url/blueprint.py `_execute` (HTTP trigger, URL ingest).**
Structurally identical to Site 1 minus the blob `ContainerClient` / endpoint
resolution; dispatches to `add_url_handler(request, parser, embedder, search_provider)`:

```python
search_key = settings.database.index_store
async with await cred_provider.get_credential() as credential:
    parser = parser_cls(settings=settings, credential=credential)
    embedder_cls = embedders_registry.registry.get("azure_openai")
    embedder = embedder_cls(settings=settings, credential=credential)
    pool_helper: PgVectorPool | None = None
    try:
        search_kwargs: dict[str, Any] = {"settings": settings, "credential": credential}
        if search_key == IndexStore.PGVECTOR:
            pool_helper = PgVectorPool(settings=settings, credential=credential)
            search_kwargs["pool"] = await pool_helper.acquire()
        search_provider = search_registry.registry.get(search_key)(**search_kwargs)
        try:
            await search_provider.ensure_schema()
            return await add_url_handler(request, parser, embedder, search_provider)
        finally:
            await search_provider.aclose()
    finally:
        if pool_helper is not None:
            await pool_helper.aclose()
        await embedder.aclose()
```

**Site 3 — v2/src/functions/blob_event/blueprint.py `_execute` (queue trigger, DELETE branch only).**
The same search/pgvector block, but inside the `BlobEventType.DELETED`
branch, with NO embedder (delete path doesn't embed) and dispatching to
`handle_blob_deleted(event.ref, search_provider)`:

```python
search_key = settings.database.index_store
pool_helper: PgVectorPool | None = None
try:
    search_kwargs: dict[str, Any] = {"settings": settings, "credential": credential}
    if search_key == IndexStore.PGVECTOR:
        pool_helper = PgVectorPool(settings=settings, credential=credential)
        search_kwargs["pool"] = await pool_helper.acquire()
    search_provider = search_registry.registry.get(search_key)(**search_kwargs)
    try:
        await search_provider.ensure_schema()
        return await handle_blob_deleted(event.ref, search_provider)
    finally:
        await search_provider.aclose()
finally:
    if pool_helper is not None:
        await pool_helper.aclose()
```

(The CREATED branch of blob_event opens a `QueueClient` instead and does
NOT resolve a search provider — it just enqueues to `doc-processing`.)

**Site 4 — v2/src/backend/app.py lifespan (read side, app-scoped).**
Structurally DIFFERENT:

```python
search_key = settings.database.index_store
search_provider = None
needs_endpoint = search_key == IndexStore.AZURE_SEARCH
if needs_endpoint and not settings.search.endpoint:
    logger.info("Search disabled ...; orchestrator will run in pass-through mode.")
else:
    search_kwargs: dict[str, Any] = {"settings": settings, "credential": credential}
    if search_key == IndexStore.PGVECTOR:
        search_kwargs["pool"] = await database_client.ensure_pool()  # pyright: ignore[...]
    search_provider = search_registry.registry.get(search_key)(**search_kwargs)
    await search_provider.ensure_schema()
app.state.search_provider = search_provider
# ... aclose happens in the lifespan `finally:` at shutdown, in reverse order.
```

#### Collaborator contracts

**PgVectorPool (v2/src/functions/core/pgvector_pool.py):**

- `__init__(self, settings, credential, *, pool: asyncpg.Pool | None = None)`.
- `async acquire() -> asyncpg.Pool` — single-flight + idempotent lazy
  construction under `asyncio.Lock`; fast-path returns an already-built
  pool. Raises `RuntimeError` if `AZURE_POSTGRES_ENDPOINT` /
  `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` unset; wraps
  `asyncpg.PostgresError | OSError` (log-loud + re-raise) per Hard Rule #14.
- `async aclose() -> None` — best-effort, idempotent (None-guarded; resets
  `self._pool = None`); WARNING (not exception) on close failure.
- It is NOT an async context manager — lifecycle is explicit
  `acquire()` … `aclose()`. The function blueprints construct it
  per-invocation, `acquire()` it, and `aclose()` it in `finally`.

**BaseSearch (v2/src/backend/core/providers/search/base.py):**

- `async ensure_schema() -> None` — default NO-OP; pgvector overrides
  (creates `documents` + HNSW index once-per-process under an
  `asyncio.Lock` + `_schema_ready` flag); AzureSearch inherits the no-op
  (index owned by Bicep). Idempotent on the concrete side. Docstring
  states it is "called once per process by the lifespan wiring ... and
  once per blueprint invocation by the Functions ingestion path."
- `async aclose() -> None` — default NO-OP; concretes override to release
  owned SDK clients.
- BaseSearch defines NO `__aenter__` / `__aexit__` — there is no
  async-context-manager protocol on the provider. Lifecycle is explicit
  `ensure_schema()` then `aclose()`. (The blob/queue SDK clients
  `ContainerClient` / `QueueClient` ARE `async with` context managers, but
  those are separate from the search provider.)

#### Are the four sites identical? — NO (3 + 1)

- **Sites 1, 2, 3 (the three function blueprints) share an identical
  search-provider-resolution + pgvector-pool + ensure_schema + aclose
  lifecycle**, differing only in (a) whether an embedder is also resolved
  (Sites 1, 2 yes; Site 3 no), and (b) the handler they ultimately call
  while the provider is open. The per-invocation `PgVectorPool` create +
  `acquire()` + `finally: aclose()` is byte-for-byte the same.
- **Site 4 (backend/app.py) is structurally different** and CANNOT share
  the function helper:
  1. **Pool source.** Functions construct a fresh per-invocation
     `PgVectorPool(...).acquire()`. The backend injects the single
     per-process pool owned by the database client
     (`await database_client.ensure_pool()`), and does NOT use
     `PgVectorPool` at all. (`PgVectorPool` even lives under
     `functions/core/` — see import boundary below.)
  2. **Lifecycle scope.** Functions resolve + `aclose()` within one
     invocation (`try/finally`). The backend resolves once at lifespan
     startup, stashes on `app.state.search_provider`, and `aclose()`s at
     shutdown in the lifespan `finally` (reverse construction order, AFTER
     content-safety, BEFORE the database client whose pool it borrows).
  3. **Disabled-search gate.** The backend has a `needs_endpoint` branch:
     `AzureSearch` with no endpoint → `search_provider = None` (pass-through
     retrieval) so the backend-only dev profile still boots. The functions
     have no such gate — ingestion always resolves a concrete provider.

#### Shared helper design (serves the three function blueprints only)

Proposed signature + return type (Hard Rule #15 — the helper hands back a
struct, so it's a frozen Pydantic model, not a bare tuple/dict):

```python
# Home: v2/src/functions/core/search_resolution.py  (NEW module)

class ResolvedSearch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
    provider: BaseSearch
    pool_helper: PgVectorPool | None  # non-None only on the pgvector path

async def resolve_search_provider(
    *,
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> ResolvedSearch:
    """Resolve the registry-first search provider + (pgvector) pool,
    run ensure_schema, and return both so the caller owns teardown."""
```

Caller shape at each of Sites 1/2/3 collapses to:

```python
resolved = await resolve_search_provider(settings=settings, credential=credential)
try:
    # ... open ContainerClient (Site 1) / call handler (Sites 2,3) ...
finally:
    await resolved.provider.aclose()
    if resolved.pool_helper is not None:
        await resolved.pool_helper.aclose()
```

Design notes / decisions to surface:

- **`ensure_schema()` placement.** Move the `ensure_schema()` call INTO the
  helper (after construction, before return). It is idempotent + provider-
  agnostic, so this is safe and removes one more duplicated line. (If a
  caller wanted to assert ensure_schema failure aborts before any handler
  work — they already get that, since the helper raises before returning.)
- **Teardown ownership stays with the caller.** The helper does NOT own
  `aclose()` because the provider must stay open across the caller's
  handler work (and Site 1 additionally opens a `ContainerClient` around
  the call). Returning `(provider, pool_helper)` and letting the caller's
  `finally` close both preserves the exact current lifecycle. An
  alternative — an `@asynccontextmanager` yielding `ResolvedSearch` — is
  cleaner at the call site but: (a) the codebase's BaseSearch lifecycle is
  deliberately explicit-`aclose`, not context-manager (consistency); (b)
  blob_event's CREATE branch must NOT enter it at all. The plain
  resolve-returns-struct form maps 1:1 onto today's code and is the safer
  consolidation. Flag both options for the implementer/user.
- **Embedder stays at the call site.** The embedder is NOT part of this
  helper — Site 3 (delete) has no embedder, and the embedder's `aclose()`
  is in the caller's outer `finally`. Folding it in would force a
  None-embedder special case onto blob_event. Keep embedder resolution +
  teardown where it is.
- **`arbitrary_types_allowed=True`** is required because `BaseSearch` /
  `PgVectorPool` are not Pydantic types. This is a legitimate boundary use
  (the model is a typed return struct over SDK-ish objects), consistent
  with Hard Rule #15's "closed-set dict/struct returns get a model."

#### Import-boundary + Hard Rule #10 (home-module decision)

- The three function blueprints already import `PgVectorPool` from
  `functions.core.pgvector_pool` and import `backend.core...` registries
  freely (functions depend on backend.core; backend does NOT depend on
  functions). So a helper under **`v2/src/functions/core/search_resolution.py`**
  is the correct home — it can import both `PgVectorPool` (sibling) and the
  `backend.core` registries, and it serves exactly the three function
  blueprints.
- It must NOT live under `backend/core/` — that would (a) make
  backend.core import `PgVectorPool` from `functions/core/`, inverting the
  dependency direction, and (b) be useless to the backend lifespan anyway
  (Site 4 needs a different pool source + the disabled-search gate).
- **Hard Rule #10 sign-off required:** creating
  `functions/core/search_resolution.py` is a NEW shared module/symbol — a
  structural change. The implementer/planner must get explicit user
  approval before landing it. (Per repo workflow, the `cwyd-planner` Work
  Order should call this out.)
- **Verdict on scope:** the helper serves the THREE function blueprints
  (Sites 1, 2, 3). It does NOT and should not serve backend/app.py (Site 4)
  — Site 4's pool-from-database-client + lifespan scope + disabled-search
  gate are intrinsically different and correctly stay bespoke.

#### Affected test files + can the consolidation stay green?

The blueprints are tested through the private `_execute` monkeypatch seam,
NOT through the internal search block — so swapping the inner block for a
helper call leaves the route-level tests untouched:

- v2/tests/functions/batch_push/test_blueprint.py — monkeypatches
  `_execute`; also unit-tests `_parser_key_for_filename`.
- v2/tests/functions/add_url/test_blueprint.py — monkeypatches `_execute`;
  also unit-tests `_parser_key_for_url`.
- v2/tests/functions/blob_event/test_blueprint.py — monkeypatches
  `_execute` (delete-branch path included).
- v2/tests/functions/core/test_pgvector_pool.py — PgVectorPool unit tests
  (unchanged; the helper composes PgVectorPool, doesn't replace it).
- v2/tests/backend/test_app_lifespan.py — backend lifespan search wiring
  (`test_lifespan_constructs_search_provider_when_endpoint_set`, etc.).
  UNCHANGED, because Site 4 is intentionally left out of the consolidation.

New test to add (per the test-first contract): a unit test for the new
`resolve_search_provider` helper + `ResolvedSearch` model under
v2/tests/functions/core/ (e.g. `test_search_resolution.py`) covering both
the AzureSearch path (pool_helper is None) and the pgvector path
(PgVectorPool acquired, ensure_schema called). The existing `_execute`
tests stay green because `_execute` keeps its signature + seam; only its
body delegates.

Consolidation can stay green: YES — the seam tests are above the helper,
and the helper is independently unit-tested.

#### Secondary duplication — parser-key derivation

The token `PurePosixPath(<name>).suffix.lstrip(".").lower()` appears at 4
sites (slightly different wrappers, identical core):

- v2/src/functions/batch_push/blueprint.py `_parser_key_for_filename`
  (filename; bare derivation, no fallback).
- v2/src/functions/add_url/blueprint.py `_parser_key_for_url`
  (URL: `urlparse(url).path` first, then derivation, then
  `or _DEFAULT_PARSER_KEY` fallback).
- v2/src/backend/services/ingestion.py `_blob_name_for_url` (~line 94)
  (URL: `urlparse(url).path` first, then derivation; used as a
  registry-membership check → falls back to `_DEFAULT_URL_BLOB_EXT`).
- v2/src/backend/services/ingestion.py `validate_upload` (~line 217)
  (filename; bare derivation; used as the 415 gate).

Proposed helper (low-level, returns the bare key; callers keep their
differing fallback / membership / urlparse logic):

```python
# Home: v2/src/backend/core/... leaf — see boundary note below.
def parser_key_for_path(name: str) -> str:
    """Lowercase extension (no dot) of a POSIX-style path/filename.

    The core parser-registry key derivation shared by the blob-filename
    and (post-urlparse) URL-path call sites. PurePosixPath keeps
    separator handling stable across Windows dev hosts and Linux
    Functions runtimes (blob paths + URL paths are both POSIX-style).
    """
    return PurePosixPath(name).suffix.lstrip(".").lower()
```

Call-site shapes after consolidation:

- batch_push: `_parser_key_for_filename(fn)` → `parser_key_for_path(fn)`
  (drop the local helper, or keep it as a 1-line alias).
- add_url: `suffix = parser_key_for_path(urlparse(url).path); return suffix or _DEFAULT_PARSER_KEY`.
- ingestion `_blob_name_for_url`: `suffix = parser_key_for_path(urlparse(url).path)` then the existing membership check.
- ingestion `validate_upload`: `extension = parser_key_for_path(filename)` then the existing 415 gate.

Home-module decision (Hard Rule #10 — also a new shared symbol):

- This helper is used by BOTH `functions/*` AND `backend/services/ingestion.py`.
  Since `functions/` already imports `backend.core.*` (one-way), the correct
  home is a **`backend.core`** leaf so both sides can import it without
  inverting the dependency. Candidate: an existing low-level module under
  `v2/src/backend/core/` (e.g. alongside the parser registry helpers) or a
  small new `v2/src/backend/core/parsers/paths.py`. Creating a new module is
  a Hard Rule #10 structural change → user sign-off. If a suitable existing
  leaf already houses path/extension helpers, prefer adding the function
  there to avoid a new module.
- Affected tests: `test_parser_key_for_filename_*` in
  v2/tests/functions/batch_push/test_blueprint.py and the
  `_parser_key_for_url` tests in v2/tests/functions/add_url/test_blueprint.py;
  the `_blob_name_for_url` / `validate_upload` tests in
  v2/tests/backend/test_services_ingestion.py. Add a focused unit test for
  `parser_key_for_path` itself in the backend.core test tree. Existing tests
  stay green if the local helpers keep their names + behavior and just
  delegate (or are inlined to the shared call).

This secondary consolidation is independent of the search-provider one and
can be a separate one-unit turn.

## References / evidence

- v2/docs/bugs.md — BUG-0054 (open, detail block stale), BUG-0080 (fixed,
  2026-06-24 deploy), BUG-0058 (cloud-verify gate), BUG-0077 (delete path),
  BUG-0053 (alwaysReady precedent), BUG-0056 (host.json messageEncoding).
- v2/docs/worklog/2026-06-20.md — deploy deferred; Event Grid → blob-events
  repoint; blob_event "not yet deployed" at that date; env flag not flipped.
- v2/docs/worklog/2026-06-23.md — 4 historical doc-processing-poison
  messages (pre-repoint noise); cutover step list incl. "drain the 4".
- v2/docs/worklog/2026-06-24.md — BUG-0080 root cause + `--no-build`
  publish; "blob_event now live (6 functions)"; verified.
- v2/docs/worklog/2026-06-25.md — azd deploy function 403 (storage
  publicNetworkAccess=Disabled) workaround; provision for KB-MCP seeder.
- v2/docs/worklog/2026-06-29.md — BUG-0054 alwaysReady bicep add; WI-01
  cutover still deferred; PD-01 "EVENT_GRID becomes live" framed as future.
- v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md — trigger
  model, AZURE_INGESTION_TRIGGER, blob-events queue, ingestion_job_id.
- v2/src/functions/batch_push/blueprint.py — Site 1 + `_parser_key_for_filename`.
- v2/src/functions/add_url/blueprint.py — Site 2 + `_parser_key_for_url`.
- v2/src/functions/blob_event/blueprint.py — Site 3 (delete branch).
- v2/src/backend/app.py — Site 4 (lifespan, app-scoped, pool-from-db-client).
- v2/src/backend/services/ingestion.py — parser-key derivations (~94, ~217).
- v2/src/functions/core/pgvector_pool.py — PgVectorPool lifecycle contract.
- v2/src/backend/core/providers/search/base.py — ensure_schema / aclose /
  (no __aexit__) contract.
- Test seams: v2/tests/functions/{batch_push,add_url,blob_event,search_skill}/test_blueprint.py;
  v2/tests/functions/core/test_pgvector_pool.py;
  v2/tests/backend/test_app_lifespan.py;
  v2/tests/backend/test_services_ingestion.py.

## Clarifying questions

1. TASK A is reconciled from the doc trail (research-only; no live `az`
   was run). Do you want a follow-up turn to run the three read-only live
   confirmations (`az functionapp function list`, `azd env get-values`,
   `az storage message peek doc-processing-poison`) to make the deploy /
   flag / poison answers 100% live-definitive before closing BUG-0054?
2. For the search-resolution helper, do you prefer the
   resolve-returns-`ResolvedSearch`-struct form (1:1 with today's explicit
   `aclose` lifecycle, recommended) or an `@asynccontextmanager` form
   (cleaner call site, but diverges from the codebase's explicit-aclose
   convention and needs blob_event's CREATE branch to opt out)?
3. For `parser_key_for_path`, is there an existing `backend.core` leaf you
   want it added to, or should the planner propose a new
   `backend/core/parsers/paths.py` (new module → Hard Rule #10 sign-off)?
4. Both consolidations create NEW shared symbols (Hard Rule #10). Confirm
   you want the `cwyd-planner` to emit Work Orders for them (one unit per
   turn: search-resolution helper first, parser-key helper second), or
   whether either is out of scope right now.
