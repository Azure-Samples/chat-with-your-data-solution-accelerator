<!-- markdownlint-disable-file -->
# Implementation Details: BUG-0054 cloud cutover + ingestion-wiring deduplication

## Context Reference

Sources: .copilot-tracking/research/2026-06-29/bug-0054-research.md (consolidated deliverable); subagent docs under .copilot-tracking/research/subagents/2026-06-29/ (history-adr, code-analysis, infra-wiring, consolidation-design). Hard Rule #10 structural sign-off for the two new modules recorded in the Planning Log (.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md).

## Implementation Phase 1: Infra regression-guard test (non-structural)

<!-- parallelizable: true -->

### Step 1.1: Add `test_blob_event_subscription_targets_blob_events_queue` to the bicep test

Add one grep-style guard test to `v2/tests/infra/test_main_bicep.py`, next to `test_function_app_keeps_blob_event_always_ready` (line 202). The test asserts the Event Grid subscription destination is pinned to the `blob-events` queue (via the `blobEventsQueueName` var) and never regresses to `doc-processing` — the exact regression that defined BUG-0054. Use the existing module-scoped `bicep_text` fixture (raw `main.bicep` text). Assert on the substrings present in the committed bicep so the test is implementation-honest:

* `queueName: blobEventsQueueName` appears in the bicep (the subscription destination references the `'blob-events'` var, not a raw `'doc-processing'` literal).
* `'Microsoft.Storage.BlobCreated'` and `'Microsoft.Storage.BlobDeleted'` appear in the `includedEventTypes` filter.

Keep the assertion messages actionable (mirror the existing tests' "Add ... to main.bicep so ..." voice). No `Pillar:` header is needed — the file is a test module, not `v2/src/**`.

Files:
* v2/tests/infra/test_main_bicep.py - add the new test function after line ~222 (end of `test_function_app_keeps_blob_event_always_ready`).

Discrepancy references:
* Addresses DR-01 (the missing Event Grid `queueName` guard) from the Planning Log.

Success criteria:
* `uv run pytest v2/tests/infra/test_main_bicep.py` passes including the new test.
* Mutating the bicep subscription `queueName` to `docProcessingQueueName` makes the new test fail (verify mentally / by a scratch edit, do not commit the mutation).

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md (§1 "New-topic subscription", §5 "Coverage GAP") - subscription line ~2402/2421; the gap.
* v2/tests/infra/test_main_bicep.py (Lines 202-222) - the sibling always-ready guard to mirror.

Dependencies:
* None (test-only; isolated file).

## Implementation Phase 2: Extract `parser_key_for_path` (structural — new module)

<!-- parallelizable: false -->

### Step 2.1: Create `v2/src/backend/core/paths.py` with `parser_key_for_path` + its unit test

Create the new leaf module `v2/src/backend/core/paths.py` (Hard Rule #10 sign-off recorded in the Planning Log). It homes a single pure function:

```python
from pathlib import PurePosixPath


def parser_key_for_path(name: str) -> str:
    """Lowercase extension (no dot) of a POSIX-style path / filename."""
    return PurePosixPath(name).suffix.lstrip(".").lower()
```

Open the module with the mandatory `Pillar: Stable Core` / `Phase: 7 (...)` docstring header (Hard Rule #3). Keep imports at top (Hard Rule #17). No `Any`, no process narrative (Hard Rule #16). The function returns a bare `str` (a scalar, not a closed-set dict), so Hard Rule #15 does not apply.

Home-module rationale: the helper is consumed by BOTH `functions/*` and `backend/services/ingestion.py`. `functions/` imports `backend.core.*` one-way, so a `backend.core` leaf lets both sides import it without inverting the dependency. `backend/core/paths.py` is chosen over `backend/core/parsers/paths.py` to avoid conceptual collision with the existing `backend/core/providers/parsers/` package (the provider registry).

Add the test-first unit test `v2/tests/backend/core/test_paths.py` covering: a plain filename (`report.PDF` -> `pdf`), a POSIX path (`a/b/file.txt` -> `txt`), no-extension (`article` -> `""`), a trailing-dot edge (`name.` -> `""`), and a multi-dot name (`archive.tar.gz` -> `gz`).

Files:
* v2/src/backend/core/paths.py - new module (the helper).
* v2/tests/backend/core/test_paths.py - new unit test.

Discrepancy references:
* Addresses the parser-key duplication (DD-01 selected path) from the Planning Log.

Success criteria:
* `uv run pytest v2/tests/backend/core/test_paths.py` passes.
* `uv run pyright` reports no new errors for `v2/src/backend/core/paths.py`.

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md ("Secondary duplication — parser-key derivation") - helper shape + home-module decision.

Dependencies:
* None.

### Step 2.2: Repoint the four parser-key call sites to the shared helper

Replace each of the four `PurePosixPath(...).suffix.lstrip(".").lower()` derivations with a call to `parser_key_for_path`, preserving each site's surrounding fallback / membership / urlparse logic exactly. Add `from backend.core.paths import parser_key_for_path` to each file's top import block (Hard Rule #17) and drop the now-unused `from pathlib import PurePosixPath` import where it becomes dead.

1. `v2/src/functions/batch_push/blueprint.py` `_parser_key_for_filename` (lines ~72-81): body becomes `return parser_key_for_path(filename)`. Keep the function (the `_execute` call site and its test reference it) — it becomes a thin alias, or inline it at the single call site if no test references the name directly (verify first).
2. `v2/src/functions/add_url/blueprint.py` `_parser_key_for_url` (lines ~71-92): becomes `suffix = parser_key_for_path(urlparse(url).path)` then the existing `return suffix or _DEFAULT_PARSER_KEY`.
3. `v2/src/backend/services/ingestion.py` `_blob_name_for_url` (line ~94): `suffix = parser_key_for_path(parsed.path)` then the existing membership check against `ingestion_parsers_registry.registry`.
4. `v2/src/backend/services/ingestion.py` `validate_upload` (line ~217): `extension = parser_key_for_path(filename)` then the existing 415 gate.

Before deleting/aliasing `_parser_key_for_filename` / `_parser_key_for_url`, grep their names across `v2/tests/` — the existing unit tests `test_parser_key_for_filename_*` (batch_push) and `_parser_key_for_url` tests (add_url) reference them; keep the names as 1-line delegators so those tests stay green (per the cleanup-before-next-step memory: only remove a symbol when zero non-test callers AND the behavior is covered elsewhere — here the helper's own test covers the core).

Files:
* v2/src/functions/batch_push/blueprint.py - parser-key Site 1.
* v2/src/functions/add_url/blueprint.py - parser-key Site 2.
* v2/src/backend/services/ingestion.py - parser-key Sites 3 + 4.

Success criteria:
* All four sites import and call `parser_key_for_path`; no remaining `PurePosixPath(...).suffix.lstrip(".").lower()` in these files.
* `uv run pytest v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/backend/test_services_ingestion.py` stays green.

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md ("Call-site shapes after consolidation").

Dependencies:
* Step 2.1 completion (the helper must exist).

### Step 2.3: Validate phase changes

Validation commands:
* `uv run pytest v2/tests/backend/core/test_paths.py v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/backend/test_services_ingestion.py` - parser-key helper + all four affected call-site suites.

## Implementation Phase 3: Extract `resolve_search_provider` (structural — new module)

<!-- parallelizable: false -->

### Step 3.1: Create `v2/src/functions/core/search_resolution.py` (`ResolvedSearch` + `resolve_search_provider`) + its unit test

Create the new module `v2/src/functions/core/search_resolution.py` (Hard Rule #10 sign-off recorded in the Planning Log). It homes a frozen Pydantic return struct (Hard Rule #15 — the helper hands back a struct) and one async resolver serving the THREE function blueprints (Sites 1, 2, 3). It does NOT serve `backend/app.py` (Site 4 — different pool source + lifespan scope + disabled-search gate, correctly bespoke).

```python
# Pillar: Stable Core
# Phase: 6 (Functions blueprints / modular RAG indexing pipeline)
from typing import Any

from azure.core.credentials_async import AsyncTokenCredential
from pydantic import BaseModel, ConfigDict

from backend.core.providers.search import registry as search_registry
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, IndexStore
from functions.core.pgvector_pool import PgVectorPool


class ResolvedSearch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
    provider: BaseSearch
    pool_helper: PgVectorPool | None


async def resolve_search_provider(
    *, settings: AppSettings, credential: AsyncTokenCredential
) -> ResolvedSearch:
    """Resolve the registry-first search provider (+ pgvector pool on the
    pgvector path), run ensure_schema, and return both so the caller owns teardown."""
    search_key = settings.database.index_store
    pool_helper: PgVectorPool | None = None
    search_kwargs: dict[str, Any] = {"settings": settings, "credential": credential}
    if search_key == IndexStore.PGVECTOR:
        pool_helper = PgVectorPool(settings=settings, credential=credential)
        search_kwargs["pool"] = await pool_helper.acquire()
    provider = search_registry.registry.get(search_key)(**search_kwargs)
    await provider.ensure_schema()
    return ResolvedSearch(provider=provider, pool_helper=pool_helper)
```

Decisions baked in (from the consolidation design):
* `ensure_schema()` moves INTO the helper (idempotent, provider-agnostic; raising aborts before any handler work — preserves current behavior).
* Teardown stays with the CALLER (the provider must remain open across the handler; Site 1 wraps a `ContainerClient` around the call). The helper returns the struct; the caller's `finally` closes `provider.aclose()` then `pool_helper.aclose()`.
* The embedder is NOT folded in — Site 3 (delete) has no embedder; it stays at each call site.
* The `dict[str, Any]` `search_kwargs` is the Hard Rule #11(a) boundary carve-out (heterogeneous registry-callable kwargs across provider concretes), exactly as the current blueprints annotate it.

Add the test-first unit test `v2/tests/functions/core/test_search_resolution.py` covering both paths via monkeypatched registries / a fake `PgVectorPool`:
* AzureSearch path: `index_store=AzureSearch` -> `pool_helper is None`, `ensure_schema` called once, `provider` is the registered concrete.
* pgvector path: `index_store=pgvector` -> `PgVectorPool` constructed, `acquire()` awaited, `pool` passed into the provider kwargs, `ensure_schema` called once, `pool_helper` is the helper instance.

Files:
* v2/src/functions/core/search_resolution.py - new module (`ResolvedSearch` + `resolve_search_provider`).
* v2/tests/functions/core/test_search_resolution.py - new unit test (both paths).

Discrepancy references:
* Addresses the search-block duplication (DD-02 selected path) from the Planning Log.

Success criteria:
* `uv run pytest v2/tests/functions/core/test_search_resolution.py` passes (both paths).
* `uv run pyright` reports no new errors for the new module.

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md ("Shared helper design", "Collaborator contracts", "Import-boundary + Hard Rule #10").
* v2/src/functions/core/pgvector_pool.py - `acquire()` / `aclose()` contract.
* v2/src/backend/core/providers/search/base.py - `ensure_schema()` / `aclose()` contract.

Dependencies:
* None (composes existing `PgVectorPool` + registries).

### Step 3.2: Repoint the three function-blueprint `_execute` bodies to the shared helper

Replace each blueprint's inline search/pgvector/ensure_schema/finally block with a `resolve_search_provider(...)` call, keeping each `_execute`'s signature and seam unchanged (route-level tests monkeypatch `_execute`, which sits ABOVE the helper, so they stay green). Add `from functions.core.search_resolution import resolve_search_provider` to each file's top import block; drop the now-dead `IndexStore` / `PgVectorPool` / `Any` imports where they become unused (verify per file).

Each call site collapses to:

```python
resolved = await resolve_search_provider(settings=settings, credential=credential)
try:
    # site-specific handler work using resolved.provider ...
finally:
    await resolved.provider.aclose()
    if resolved.pool_helper is not None:
        await resolved.pool_helper.aclose()
```

1. `v2/src/functions/batch_push/blueprint.py` `_execute` (search block ~114-150): the embedder construction + its `finally: await embedder.aclose()` stay; the `ContainerClient` async-with wraps the `batch_push_handler` call, now using `resolved.provider`.
2. `v2/src/functions/add_url/blueprint.py` `_execute` (search block ~113-145): the embedder stays; the `add_url_handler(request, parser, embedder, resolved.provider)` call replaces the inline provider.
3. `v2/src/functions/blob_event/blueprint.py` `_execute` DELETE branch (block ~120-148): no embedder; `handle_blob_deleted(event.ref, resolved.provider)` uses the resolved provider; the CREATE branch (QueueClient enqueue) is untouched — it must NOT call the helper.

Preserve the exact teardown ORDER each site has today (provider before pool; embedder closed in the outer `finally` where present).

Files:
* v2/src/functions/batch_push/blueprint.py - Site 1.
* v2/src/functions/add_url/blueprint.py - Site 2.
* v2/src/functions/blob_event/blueprint.py - Site 3 (delete branch only).

Success criteria:
* No inline `search_kwargs` / `PgVectorPool(...)` / `ensure_schema()` block remains in the three blueprints; each calls `resolve_search_provider`.
* `uv run pytest v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/functions/blob_event/test_blueprint.py` stays green (seams unchanged).

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md ("Caller shape at each of Sites 1/2/3").
* v2/src/functions/blob_event/blueprint.py (Lines 120-148) - the delete-branch block to replace; CREATE branch stays.

Dependencies:
* Step 3.1 completion (the helper must exist).

### Step 3.3: Validate phase changes

Validation commands:
* `uv run pytest v2/tests/functions/core/test_search_resolution.py v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/functions/blob_event/test_blueprint.py` - helper + all three affected blueprint suites.

## Implementation Phase 4: BUG-0054 cloud cutover + docs reconcile (ops, gated on BUG-0058)

<!-- parallelizable: false -->

### Step 4.1: Reconcile the stale BUG-0054 detail block in `v2/docs/bugs.md`

Update the BUG-0054 detail block (lines ~973-1003) so it no longer lists "deploy `blob_event`" as remaining work. State that `blob_event` was deployed to the cloud Function App on 2026-06-24 (BUG-0080; the app went 5 -> 6 functions via `func ... publish --no-build --python` after the `agent-framework-core` repin), and that the remaining close-out is: (1) flip `AZURE_ENV_INGESTION_TRIGGER` -> `event_grid` + `azd provision`; (2) verify the Event Grid subscription target; (3) cloud E2E re-validation (create + delete) — the BUG-0058 gate; (4) drain the 4 historical `doc-processing-poison` messages. Use placeholder tokens (`<RESOURCE_GROUP>`, `<SUFFIX>`) per Hard Rule #18 — no real env IDs.

Use the long-row table-edit discipline (anchor on the row's unique tail; read the full byte range first) per the markdown-table-edits memory. This is the only in-repo edit of Phase 4; the rest is operator-driven.

Files:
* v2/docs/bugs.md - BUG-0054 detail block reconciliation.

Discrepancy references:
* Addresses DR-02 (the stale "deploy blob_event" note vs. the 2026-06-24 BUG-0080 deploy) from the Planning Log.

Success criteria:
* The BUG-0054 detail block reflects the 2026-06-24 deploy and the 4 remaining cutover steps; BUG-0054 stays `open`.

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md (Task A "Reconciling the BUG-0054 deploy-state contradiction", "Ordered remaining steps").

Dependencies:
* None (in-repo doc edit).

### Step 4.2: Flip the trigger flag and re-provision (operator-driven)

Operator (not the agent) runs the cutover. Steps:

1. Confirm the exact azd -> bicep key with a read-only `azd env get-values` (the codebase setting is `AZURE_INGESTION_TRIGGER`; azd env key is `AZURE_ENV_INGESTION_TRIGGER`; bicep param `ingestionTrigger`).
2. `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid`.
3. `azd provision` (re-applies bicep config so the backend Container App's `AZURE_INGESTION_TRIGGER` becomes `event_grid`; does NOT redeploy function code — `blob_event` stays deployed).
4. Read-only verify the live Event Grid system-topic subscription delivers to `blob-events` (not `doc-processing`): `az eventgrid system-topic event-subscription show ...` against `<RESOURCE_GROUP>` / `evgt-<SUFFIX>`.

No function code redeploy is required (`blob_event` already live since 2026-06-24). If a redeploy IS ever needed, use the 2026-06-24 `func ... publish --no-build` path or the 2026-06-25 temporarily-enable-storage-public-access-then-relock workaround — the plain `azd deploy function` 403s against the locked storage account.

Files:
* None (operator azd/az commands; no tracked-file change).

Success criteria:
* `azd env get-values` shows `AZURE_INGESTION_TRIGGER="event_grid"`; the backend container app's app setting reflects it after provision.
* The live Event Grid subscription `queueName` is `blob-events`.

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md (§2 "Wiring through IaC").
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md (Task A Q2 + "Ordered remaining steps" 2-3).

Dependencies:
* Step 4.1 (reconcile first so the operator doesn't re-attempt the already-done deploy).
* A clean BUG-0058 deploy state.

### Step 4.3: Cloud end-to-end re-validation (the BUG-0058 gate) + poison drain + close

Operator-driven close-out:

1. Drop a blob into the documents container -> Event Grid `BlobCreated` -> `blob-events` -> cloud `blob_event` -> enqueue to `doc-processing` -> `batch_push` -> parse/embed -> index write -> source appears in `GET /api/admin/documents`.
2. Delete the blob -> `BlobDeleted` -> `blob_event` -> `delete_by_source` drops the chunks (BUG-0077 path). Confirm no double-ingestion / no new poison (BUG-0058 clean).
3. Drain the 4 historical `doc-processing-poison` messages (peek first: `az storage message peek --queue-name doc-processing-poison --account-name st<SUFFIX> --num-messages 32 --auth-mode login`).
4. Per the cleanup-before-next-step memory: delete the validation blob + its ingested index source after the E2E passes.
5. Set BUG-0054 `open` -> `fixed` in `v2/docs/bugs.md` and write the worklog entry (Hard Rule #19).

Files:
* v2/docs/bugs.md - BUG-0054 status -> `fixed` (after validation passes).
* v2/docs/worklog/2026-06-29.md (or the real current-date worklog) - close-out entry.

Success criteria:
* Create + delete E2E both pass against the cloud; no new poison; the 4 historical poison messages drained; validation artifacts cleaned up; BUG-0054 `fixed`.

Context references:
* .copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md (Task A "Ordered remaining steps" 4-6).
* v2/docs/bugs.md - BUG-0058 (the cloud-verify gate), BUG-0077 (delete path).

Dependencies:
* Step 4.2 completion (trigger flipped + provisioned).

## Implementation Phase 5: Validation

<!-- parallelizable: false -->

### Step 5.1: Run full backend + functions + infra + shared test suites

* `uv run pytest v2/tests/backend v2/tests/functions v2/tests/infra v2/tests/shared`

### Step 5.2: Run the type gate on touched trees

* `uv run pyright` for `v2/src/backend/**` + `v2/src/functions/core/**` — must stay `0 errors / 0 warnings / 0 information` (Hard Rule #11).

### Step 5.3: Fix minor validation issues; report blocking issues

Iterate on lint / type / test failures introduced by Phases 1-3 when fixes are straightforward and isolated (unused-import removal after the extractions, fixture wiring). When a failure needs more than a minor fix:
* Document the issue and affected files.
* Provide the user with next steps and recommend a follow-up planning pass.
* Do NOT attempt large-scale refactoring inline (dont-restructure-working-code memory).
* Do NOT couple Phase 4's operator cutover into the code phases.

## Dependencies

* `uv` (v2 Python toolchain).
* `azd` + `az` CLI with an authenticated session (Phase 4 only).
* A clean BUG-0058 function deploy state (Phase 4 gate).

## Success Criteria

* New bicep guard test pins the Event Grid subscription to `blob-events`.
* `parser_key_for_path` (one definition) replaces all four derivation sites.
* `resolve_search_provider` (one definition) replaces all three function-blueprint search blocks; `backend/app.py` unchanged.
* All existing seam + lifespan tests stay green; type gate stays clean.
* BUG-0054 detail block reconciled; status reaches `fixed` only after the gated cloud E2E + poison drain.
