<!-- markdownlint-disable-file -->
# RPI Validation — BUG-0054 cutover-dedup Plan, Phase 3

**Phase under validation:** Phase 3 — Extract `resolve_search_provider` (structural — new module)
**Validation date:** 2026-06-29
**Validator mode:** RPI Validator (read-only analysis)

## Inputs validated

* Plan: `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-dedup-plan.instructions.md` (Phase 3 checklist)
* Details: `.copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md` (Lines 109-222)
* Changes Log: `.copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md`
* Planning Log: `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md` (DD-02, IP-01, DE-03)
* Research: `.copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md`

## Executive Summary

**Status: PASSED.**

Phase 3 is fully and faithfully implemented. The shared `resolve_search_provider` helper is defined once with a frozen `ResolvedSearch` Pydantic struct, all three blueprint `_execute` bodies call it with caller-owned teardown in the preserved order, `backend/app.py` (Site 4) is untouched, and the `blob_event` CREATE branch is untouched while only the DELETE branch was repointed. Every monkeypatch seam is intact and both `index_store` paths are tested (plus two extra failure-cleanup tests that directly back DE-03). All applicable Hard Rules (#3, #11, #14, #15, #16, #17) are satisfied. The DE-03 close-on-failure wrapper is behavior-preserving, leak-safe, re-raising (non-silent), and recorded in both the Planning Log and Changes Log.

**Findings by severity:** Critical 0 · Major 0 · Minor 1 · Info 3

| Severity | Count | Area |
| --- | --- | --- |
| Critical | 0 | — |
| Major | 0 | — |
| Minor | 1 | Changes Log Release Summary file-count miscount (whole-plan summary; not a Phase 3 defect) |
| Info | 3 | Helper test exceeds required coverage; `except BaseException` breadth; green-gate claims not re-executed (read-only mode) |

## Per-Step Status

| Step | Description | Status | Evidence |
| --- | --- | --- | --- |
| 3.1 | Create `search_resolution.py` (`ResolvedSearch` + `resolve_search_provider`) + test (both paths) | **Verified** | `v2/src/functions/core/search_resolution.py` L46-98; `v2/tests/functions/core/test_search_resolution.py` (4 tests) |
| 3.2 | Repoint the three blueprint `_execute` bodies to the helper (caller-owned teardown; CREATE branch untouched) | **Verified** | batch_push L118-139; add_url L119-134; blob_event L116-124 (CREATE L106-111 untouched) |
| 3.3 | Validate phase changes (helper + 3 blueprint suites) | **Verified (claim)** | Changes Log + Planning Log report green; not re-executed in read-only mode (Info-3) |
| DE-03 | Close-on-failure `try/except` wrapper (deviation from verbatim snippet) | **Deviation — accepted** | search_resolution L86-97; Planning Log DE-03; Changes Log "Additional or Deviating Changes" |

## Detailed Findings

### Step 3.1 — Helper module + test (Verified)

* **`ResolvedSearch` is the typed struct (Hard Rule #15).** `v2/src/functions/core/search_resolution.py` L46-60: `class ResolvedSearch(BaseModel)` with `model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)` (L55-58) and typed fields `provider: BaseSearch` / `pool_helper: PgVectorPool | None` (L59-60). No anonymous dict return — matches the baked-in decision exactly.
* **Signature matches the plan.** L63-65: `async def resolve_search_provider(*, settings: AppSettings, credential: AsyncTokenCredential) -> ResolvedSearch`. Keyword-only, returns the struct.
* **`ensure_schema` folded into the helper.** L91 `await provider.ensure_schema()` runs inside the helper before return; the three blueprints no longer call it (grep for `ensure_schema()` across the three blueprints returns empty). Matches the "ensure_schema moves INTO the helper" decision (details Lines 152-156).
* **Registry-first dispatch (Hard Rule #4).** L90 `provider = search_registry.registry.get(search_key)(**search_kwargs)`, keyed on `settings.database.index_store` (L74). No `if/elif` provider dispatch.
* **pgvector pool wiring.** L87-89: on `IndexStore.PGVECTOR`, constructs `PgVectorPool` and wires the acquired pool into `search_kwargs["pool"]`. AzureSearch path skips the pool (`pool_helper` stays `None`).
* **Test covers both paths + cleanup.** `v2/tests/functions/core/test_search_resolution.py`:
  * `test_azure_search_path_skips_pool_and_runs_ensure_schema` — `pool_helper is None`, no `pool` kwarg, `ensure_schema` once.
  * `test_pgvector_path_builds_pool_and_wires_pool_kwarg` — pool constructed + acquired, `pool` kwarg is the sentinel, `pool_helper` returned.
  * `test_ensure_schema_failure_closes_provider_and_pool_and_reraises` — provider closed before pool, `AzureError` propagates.
  * `test_ensure_schema_failure_on_azure_search_closes_provider_only` — only provider closed, error propagates.
  * Stubs subclass the real `BaseSearch` / `PgVectorPool` (required because `ResolvedSearch` validates field types via `isinstance` under `arbitrary_types_allowed`).

### Step 3.2 — Three blueprint repoints (Verified)

* **Helper defined once; all three `_execute` call it.**
  * batch_push: import L76; call `resolved = await resolve_search_provider(settings=settings, credential=credential)` L118.
  * add_url: import L63; call L119; `add_url_handler(request, parser, embedder, resolved.provider)` L127.
  * blob_event (DELETE branch only): import L61; call L116; `handle_blob_deleted(event.ref, resolved.provider)` L120.
* **No inline duplication remains.** Grep across the three blueprints for `search_kwargs | PgVectorPool( | IndexStore.PGVECTOR | ensure_schema() | search_registry` returns **empty** — every inline search/pgvector/ensure_schema/finally block was removed.
* **Dead imports dropped.** None of `IndexStore`, `PgVectorPool`, `Any`, `search_registry`, or `PurePosixPath` remain imported in the three blueprints (confirmed by the empty grep + reading each import block).
* **Teardown order preserved (provider before pool; embedder in its own outer finally).**
  * batch_push L135-139: inner `finally` → `resolved.provider.aclose()` (L135) → `resolved.pool_helper.aclose()` (L137); outer `finally` → `embedder.aclose()` (L139). Order: provider → pool → embedder, matching the original Site 1.
  * add_url L130-134: provider (L130) → pool (L132) → embedder (L134). Matches original Site 2.
  * blob_event L122-124: provider (L122) → pool (L124); **no embedder** (delete path has none) — matches the baked-in "embedder NOT folded; Site 3 has no embedder" decision (details Lines 158-160, 208-216).
* **`blob_event` CREATE branch untouched.** L106-111: `async with QueueClient(...)` → `handle_blob_created(event.ref, queue_client)`. The CREATE branch does **not** call `resolve_search_provider` and still uses `resolve_storage_endpoints` (still imported). Only the DELETE branch (L116-124) was repointed. Matches details Lines 210-213 ("the CREATE branch ... is untouched — it must NOT call the helper").
* **`backend/app.py` (Site 4) UNCHANGED.** Grep confirms the inline block is intact: `search_registry` import (L35), `IndexStore.AZURE_SEARCH` gate (L151), `search_kwargs: dict[str, Any]` (L159), `IndexStore.PGVECTOR` (L163), `search_registry.registry.get(...)` (L175), `ensure_schema()` (L182). The bespoke disabled-search gate + `database_client.ensure_pool()` pool source were not folded in — matches the 3+1 split (plan Success Criteria; Planning Log structural sign-off item 1).
* **`_execute` monkeypatch seams intact.** All three route-level test files patch `bp_module._execute`: batch_push test L83, add_url test L77, blob_event test L128. The helper sits **below** `_execute`, so route-level seam tests are unaffected — matches the Derived Objective "preserve seams".
* **Repointed bodies are exercised end-to-end.** Beyond the seam tests, integration tests drive the real `_execute` through the helper:
  * add_url `test_execute_calls_ensure_schema_before_handler_and_aclose_after` patches `search_resolution.search_registry.registry` and asserts `ensure_schema` runs before the handler.
  * blob_event `test_execute_enqueues_translated_envelope_to_doc_processing` exercises the untouched CREATE branch (QueueClient enqueue); `test_execute_deindexes_on_blob_deleted` exercises the repointed DELETE branch (`resolve_search_provider` → `delete_by_source`), explicitly noting the doc-processing queue client is never opened and the pgvector branch is skipped on AzureSearch.

### Step 3.3 — Phase validation (Verified by claim)

* The Planning Log (DE-03) reports "pyright 0/0/0; 38 blueprint+helper tests pass"; the Changes Log Release Summary reports "2514 passed, 1 skipped" and "pyright 0 errors / 0 warnings / 0 information". These are consistent with the static structure verified above. **Not re-executed in read-only validation mode** (see Info-3); listed as a recommended next validation.

### DE-03 Deviation — close-on-failure wrapper (Accepted)

The implementer wrapped pool-acquire + provider-construct + `ensure_schema` in a `try/except BaseException` that closes any already-opened resource before re-raising (search_resolution L86-97), instead of the verbatim bare resolve-then-return snippet in details Lines 130-150.

* **(a) Preserves behavior.** On the success path the helper returns the struct and the caller still owns teardown (unchanged). The `except` arm only fires on a mid-resolution failure and performs cleanup that the original per-site `try/finally` blocks performed implicitly. Behavior-preserving.
* **(b) Hard Rule #14 satisfied.** On failure it closes the provider first (L93-94) then the pool (L95-96) — no asyncpg pool / SDK client leak — and re-raises with a bare `raise` (L97), preserving `__cause__`. It never silently swallows (re-raises unconditionally), so `test_no_silent_excepts.py` is satisfied. Logging is intentionally **not** duplicated here: per Hard Rule #14, cleanup paths own resource release, not error reporting; the trigger decorators (`log_queue_errors` for queue triggers, `map_function_exceptions` for HTTP) own the observability ladder, as the module docstring states (L27-34).
* **(c) Recorded.** Planning Log "Implementation Deviations (execution)" → DE-03; Changes Log "Additional or Deviating Changes" → "Phase 3 reconciliation". Both describe the wrapper accurately.

### Hard Rule compliance (Verified)

* **#3 (Pillar/Phase header).** search_resolution.py L1-2: `Pillar: Stable Core` / `Phase: 6 (Functions blueprints / modular RAG indexing pipeline)`. Note DE-02 (Phase 6 vs Phase 7) concerns `paths.py` (Phase 2), not this module; the details file already specified `Phase: 6` for `search_resolution.py`, so there is no deviation here.
* **#11 (StrEnum / no `Any` in plumbing / types-at-runtime).** The only `Any` is `search_kwargs: dict[str, Any]` (L81), the explicit Hard Rule #11(a) boundary carve-out (heterogeneous registry-callable kwargs), with an inline justification comment (L77-80). No `if TYPE_CHECKING:` and no `from __future__ import annotations`. All annotations resolve to real imported symbols.
* **#15 (typed-model dict/struct returns).** `ResolvedSearch` (frozen, `extra="forbid"`) is the typed return — no anonymous dict.
* **#16 (no process narrative in src).** Docstrings describe what the code *is*. Comments cite only standing policy ("Hard Rule #11 boundary carve-out") and a live architectural anchor ("Same pattern as backend/app.py:lifespan") — both permitted carve-outs. No unit IDs, no phase narrative, no date stamps, no dev_plan section citations.
* **#17 (imports-at-top).** All imports are at module top (L35-43); the only prelude is the docstring header.

### Changes Log accuracy (Verified, with one Minor)

* Phase 3 "Added" entries (search_resolution.py, test_search_resolution.py) and "Modified" entries (the three blueprint `_execute` repoints; blob_event DELETE-only with CREATE untouched) accurately describe the implementation. The close-on-failure description ("closes any partially-opened resources before re-raising on failure (Hard Rule #14)") is backed by L86-97.
* **Minor-1 — Release Summary file-count miscount (cross-phase, not a Phase 3 defect).** The Release Summary states "Files affected: 9 (4 added, 5 modified, 0 removed)", but the enumerated "Modified (5)" list contains **6 distinct files**: `test_main_bicep.py`, `batch_push/blueprint.py`, `add_url/blueprint.py`, `services/ingestion.py`, `blob_event/blueprint.py`, `docs/bugs.md`. Actual total = 4 added + 6 modified = **10**. This is a whole-plan summary tally error spanning Phases 1-4; the Phase 3 scope itself (2 added + 3 modified blueprints) is fully and correctly enumerated. Recommend correcting the summary to "10 (4 added, 6 modified, 0 removed)".

## Info-level Notes

* **Info-1 — Helper test exceeds required coverage (positive).** The plan required the test to cover "both paths"; the implementer added two extra failure-cleanup tests (pgvector + AzureSearch `ensure_schema` failure) that directly back the DE-03 close-on-failure contract test-first. Strengthens the deviation's safety argument.
* **Info-2 — `except BaseException` breadth (intentional).** The wrapper catches `BaseException` (broader than the SDK umbrella). Because it *always* re-raises, this is a deliberate, safe choice for a cleanup-on-error wrapper: resources are released even on `CancelledError` / `KeyboardInterrupt`. It does not swallow and does not trip the silent-except gate. No action required; noted for completeness.
* **Info-3 — Green-gate claims not re-executed (read-only mode).** The "2514 passed / 1 skipped", "38 blueprint+helper tests", and "pyright 0/0/0" claims were validated by static structure only, not by re-running. They are consistent with everything inspected. Re-execution is listed below as a recommended next validation.

## Recommended Next Validations (not performed this session)

- [ ] Re-run the Phase 3 command: `uv run pytest v2/tests/functions/core/test_search_resolution.py v2/tests/functions/batch_push/test_blueprint.py v2/tests/functions/add_url/test_blueprint.py v2/tests/functions/blob_event/test_blueprint.py` (local fallback `.venv\Scripts\python.exe -m pytest ...` per DE-01) to confirm the green claim.
- [ ] Re-run `uv run pyright` on `v2/src/functions/core/**` to confirm `0/0/0` for the new module.
- [ ] Run the structural gates that pin these invariants: `test_no_silent_excepts.py`, `test_no_anonymous_dict_returns.py`, `test_no_process_narrative_in_src.py`, `test_imports_at_top_only.py`, `test_no_type_checking_or_future_annotations.py`.
- [ ] (Changes Log hygiene) Correct the Release Summary "Files affected" tally to 10 (4 added, 6 modified).

## Clarifying Questions

None — all Phase 3 items were resolvable from the available artifacts and source. The only follow-ups are the optional re-execution checks above.
