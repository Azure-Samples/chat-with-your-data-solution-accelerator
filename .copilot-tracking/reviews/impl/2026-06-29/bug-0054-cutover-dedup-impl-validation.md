<!-- markdownlint-disable-file -->
# Implementation Quality Validation: BUG-0054 cutover-dedup

**Validated**: 2026-06-29
**Scope**: full-quality (behavior-preserving dedup refactor)
**Method**: direct source read + `get_errors` diagnostics + grep dedup-completeness sweep. (The `Implementation Validator` subagent self-reported Blocked — its session had no file-read/write tools — so the reviewer performed the quality pass directly.)

## Files reviewed

* `v2/src/backend/core/paths.py` (added), `v2/tests/backend/core/test_paths.py` (added)
* `v2/src/functions/core/search_resolution.py` (added), `v2/tests/functions/core/test_search_resolution.py` (added)
* `v2/src/functions/batch_push/blueprint.py`, `v2/src/functions/add_url/blueprint.py`, `v2/src/functions/blob_event/blueprint.py` (modified)
* `v2/src/backend/services/ingestion.py` (modified)

## Diagnostics

`get_errors` over all 8 source/test files: **No errors found** (clean on every file).

## Findings by category

### DRY / dedup quality — Info (clean)

* **IQ-1 (Info) — `parser_key_for_path` is the single definition; dedup complete.** Grep confirms one definition (`paths.py:11`) and four delegating call sites: `ingestion.py:94` (`_blob_name_for_url`), `ingestion.py:217` (`validate_upload`), `batch_push/blueprint.py:89` (via `_parser_key_for_filename`), `add_url/blueprint.py:90` (via `_parser_key_for_url`). No residual inline `.suffix.lstrip(".").lower()` survives anywhere in `v2/src/**`. Evidence: grep `parser_key_for_path|_parser_key_for_filename|_parser_key_for_url`.
* **IQ-2 (Info) — the two kept delegators are justified, not dead weight.** `_parser_key_for_url` (`add_url/blueprint.py:74-90`) preserves the URL-specific `urlparse(url).path` preprocessing *before* delegating to the shared helper — that preprocessing correctly stays at the call site, not in the generic helper. `_parser_key_for_filename` (`batch_push/blueprint.py:82-89`) is a 1-line delegator retained as the documented seam its blueprint test monkeypatches. Both are referenced by their suites, so neither is orphaned.
* **IQ-3 (Info) — `resolve_search_provider` is the single registry-dispatch + schema-bootstrap point in the functions tree.** The only `search_registry.registry.get(...)` call and the only `ensure_schema()` call under `v2/src/functions/**` now live inside the helper (`search_resolution.py:90-91`). All three blueprints call `resolve_search_provider` (`batch_push:118`, `add_url:119`, `blob_event:116`). `backend/app.py` Site 4 is outside the functions tree and intentionally left bespoke (consistent with Phase 3 scoping).

### Behavior preservation — Info (clean)

* **IQ-4 (Info) — no behavioral drift in extension derivation.** `parser_key_for_path` uses `PurePosixPath(...).suffix.lstrip(".").lower()` — identical semantics to the pre-refactor inline logic, with `PurePosixPath` (not `Path`) keeping separator handling stable across Windows dev / Linux Functions hosts. The test matrix pins the edge cases (`report.PDF`→`pdf`, `a/b/file.txt`→`txt`, `article`→`""`, `name.`→`""`, `archive.tar.gz`→`gz`).
* **IQ-5 (Info) — teardown ownership + order preserved.** `ResolvedSearch` returns `(provider, pool_helper)` and the docstring + field contract make the caller close `provider` first then `pool_helper` (SDK client released before the pool it layered over). The `blob_event` CREATE branch (QueueClient enqueue) is untouched; only the DELETE branch was repointed (Phase 3 scope confirmed by the Phase 3 RPI validator, grep-clean here).

### Resilience (Hard Rule #14) — Info (clean)

* **IQ-6 (Info) — DE-03 close-on-failure wrapper is leak-safe and non-silent.** `search_resolution.py:86-97`: the `try/except BaseException` closes whatever was already opened (`provider` then `pool_helper`) and **re-raises** unconditionally — no silent swallow, `__cause__` preserved. This satisfies Hard Rule #14: no asyncpg pool / SDK client leak on a mid-resolution failure (pool acquire, provider construction, or `ensure_schema`). Observability is correctly delegated to the trigger-level decorators (`log_queue_errors` / `map_function_exceptions`), as the module docstring states. The `BaseException` (vs `Exception`) breadth is appropriate for a cleanup-on-failure guard that must also release on cancellation.

### Type discipline (Hard Rules #11, #15) — Info (clean)

* **IQ-7 (Info) — `Any` confined to the documented boundary.** The only `Any` is `search_kwargs: dict[str, Any]` (`search_resolution.py:81`), carrying an inline comment that cites the Hard Rule #11(a) boundary carve-out and the parallel `backend/app.py:lifespan` precedent (registry callable takes heterogeneous kwargs across provider concretes). No `Any` in internal plumbing.
* **IQ-8 (Info) — `ResolvedSearch` is a proper typed struct (Hard Rule #15).** Frozen, `extra="forbid"`, `arbitrary_types_allowed=True` (required because `provider: BaseSearch` / `pool_helper: PgVectorPool | None` are validated by `isinstance`). No anonymous `dict` return — the closed-set 2-field result is a model, exactly as Hard Rule #15 requires.
* **IQ-9 (Info) — no `TYPE_CHECKING` / `__future__`; all imports at top.** `paths.py` and `search_resolution.py` both keep every import in the top block (Hard Rule #17), no lazy/in-function imports, no annotation guards (Hard Rule #11). The `index_store` discriminator is referenced as the `IndexStore.PGVECTOR` StrEnum member, not a bare string (Hard Rule #11).

### Dead-code / cleanup — Info (clean)

* **IQ-10 (Info) — repoint-orphaned imports dropped.** The Phase 3 RPI validator confirmed per-file removal of the now-dead `IndexStore` / `PgVectorPool` / `Any` / `PurePosixPath` imports from the repointed blueprints; `get_errors` shows no unused-import diagnostics on any reviewed file. (Per the user's standing "reduce code debt as you go" directive, the dead-but-tested-symbol check is satisfied — both kept delegators retain live test callers.)

### Comment / docstring hygiene (Hard Rule #16) — Info (clean)

* **IQ-11 (Info) — no process narrative in the new src.** Both new modules carry only the mandated `Pillar:` / `Phase: 6 (…)` header (standing descriptive phase name, **no** `, U#` task tag) plus structural/architectural docstrings. Policy anchors present (`Hard Rule #4`, `#11`, `#14`) are the permitted standing-policy carve-out, not transient process. No unit IDs, no `BUG-0054` reference, no dev_plan `task #N`, no date stamps, no "added in this turn" narrative. (Test-file docstrings are exempt — Hard Rule #16 scopes to `v2/src/**`.)

### Test quality — Info (clean)

* **IQ-12 (Info) — new tests assert real behavior, including the DE-03 failure path.** `test_paths.py` is a 5-case parametrized matrix on the real helper. `test_search_resolution.py` exercises **both** registry-keyed paths (AzureSearch builds no pool + calls factory without a `pool` kwarg; pgvector builds `PgVectorPool`, awaits `acquire`, wires the pool, returns the helper) **plus** the `ensure_schema`-failure cleanup contract (provider + pool closed, exception propagates) — directly backing DE-03. Stubs subclass the real `BaseSearch` / `PgVectorPool` because `ResolvedSearch`'s `arbitrary_types_allowed` validates fields by `isinstance`, so loose doubles would be rejected — a correct, non-brittle seam.

## Severity tally

| Severity | Count |
| --- | --- |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Info | 12 |

## Verdict

**High quality.** The refactor is a genuine, complete deduplication with no behavioral drift, clean type discipline, a leak-safe resilience wrapper, justified kept-delegators, and tests that cover both dispatch paths plus the failure-cleanup contract. Zero blocking findings; zero diagnostics. The only review-wide issues are documentation-inventory inaccuracies in the **Changes Log** (file tally), surfaced by the Phase 3 + Phase 5 RPI validators — not implementation defects.
