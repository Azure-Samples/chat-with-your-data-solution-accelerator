<!-- markdownlint-disable-file -->
# Review Log: BUG-0054 cloud cutover + ingestion-wiring deduplication

## Metadata

* **Review date**: 2026-06-29
* **Reviewer mode**: Task Reviewer
* **Implementation plan**: .copilot-tracking/plans/2026-06-29/bug-0054-cutover-dedup-plan.instructions.md
* **Changes log**: .copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md
* **Planning log**: .copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md
* **Research**: .copilot-tracking/research/2026-06-29/bug-0054-research.md (+ 5 subagent docs under research/subagents/2026-06-29/)

## Scope

Review of the just-completed implementation of the BUG-0054 cutover-dedup plan (5 phases):

1. Phase 1 — Event Grid `blob-events` regression-guard test (non-structural).
2. Phase 2 — extract `parser_key_for_path` into `v2/src/backend/core/paths.py`; repoint 4 call sites.
3. Phase 3 — extract `resolve_search_provider` into `v2/src/functions/core/search_resolution.py`; repoint 3 blueprint `_execute` bodies.
4. Phase 4 — BUG-0054 docs reconcile (Step 4.1, in-repo); Steps 4.2/4.3 operator-driven + blocked.
5. Phase 5 — full validation sweep + type gate.

## Summary

The dedup refactor (Phases 2, 3) is **high quality, complete, and green** — both shared helpers are the single definition of their concern, all call sites repoint with no behavioral drift, type discipline is clean, and the resilience wrapper is leak-safe. Phase 5's gates were **independently reproduced** (2514 passed / 1 skipped; pyright 0/0/0). Phase 4's in-repo docs reconcile is verified; its cloud-cutover steps (4.2/4.3) are legitimately operator-blocked and BUG-0054 honestly stays `open`.

One **Major** finding sits in Phase 1: the new Event Grid regression-guard test uses whole-file substring assertions, so it catches a *total* regression (both subscriptions repointed) but **not** the *single-subscription* repoint that originally defined BUG-0054 — failing the plan's own "fails if **either** subscription regresses" success criterion. Plus a documentation-inventory inaccuracy in the Changes Log (file tally). Both are isolated, non-structural fixes.

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Major | 1 |
| Minor | 3 |
| Info | 20 |

> **Post-rework (2026-06-29):** the 1 Major + 3 Minor are **resolved and independently re-verified** by the reviewer (not accepted on the implementer's self-marked status) — residual **0 Critical / 0 Major / 0 Minor**. See the [Re-review](#re-review-rework-verification-2026-06-29) section.

## RPI Validation Findings (per plan phase)

| Phase | Status | Critical | Major | Minor | Info | Validation file |
|-------|--------|----------|-------|-------|------|-----------------|
| 1 — infra guard test | ⚠️ Partial → ✅ Verified (rework RR-01) | 0 | 1→**0** | 2→**0** | 2 | reviews/rpi/2026-06-29/bug-0054-cutover-dedup-plan-001-validation.md |
| 2 — `parser_key_for_path` | ✅ Verified | 0 | 0 | 0 | 0 | reviews/rpi/2026-06-29/bug-0054-cutover-dedup-plan-002-validation.md |
| 3 — `resolve_search_provider` | ✅ Verified | 0 | 0 | 1* | 3 | reviews/rpi/2026-06-29/bug-0054-cutover-dedup-plan-003-validation.md |
| 4 — docs reconcile | ✅ Verified | 0 | 0 | 0 | 3 | reviews/rpi/2026-06-29/bug-0054-cutover-dedup-plan-004-validation.md |
| 5 — validation sweep | ✅ Verified | 0 | 0 | 1* | 3 | reviews/rpi/2026-06-29/bug-0054-cutover-dedup-plan-005-validation.md |

\* The Phase 3 and Phase 5 Minors are the **same** underlying issue (Changes Log file-inventory inaccuracy), counted once in the aggregate tally above.

### Phase 1 — Partial (1 Major, 2 Minor, 2 Info)

* **DR-A (Major)** — Regression guard does not satisfy the plan's "**either** subscription regresses" success criterion. `v2/infra/main.bicep` has **two** mutually-exclusive subscription resources both carrying `queueName: blobEventsQueueName` (new-topic `blobCreatedSubscription` L2421 under `if (!useExistingEventGridTopic)`; existing-topic `existingEventGridSubscription` L2487 under `if (useExistingEventGridTopic)`). The test (`test_main_bicep.py:233`) asserts whole-file substring membership `"queueName: blobEventsQueueName" in bicep_text`. Because the literal occurs twice, the guard passes if **at least one** survives — so repointing the **new-topic** subscription (the common new-storage deploy path, the exact original BUG-0054 shape) back to `doc-processing` is **not** caught. Read-only simulation confirmed: mutate one → still passes; mutate both → fails. Catches a total regression, not a single-path one.
* **DR-B (Minor)** — Changes Log claim that the test "fails if either Event Grid subscription regresses off the `blob-events` queue" overstates coverage given DR-A; should be scoped to "adds a total-regression guard."
* **DR-C (Minor)** — No negative / per-subscription-scoped assertion (e.g. `"queueName: docProcessingQueueName" not in <subscription slice>`); a scoped negative is what would close DR-A.
* **DR-D, DR-E (Info)** — `subjectBeginsWith` left unguarded (consistent with narrowed plan scope); `uv run` trampoline fallback (DE-01) accurately recorded.
* Verified positives: test added next to its sibling, uses the module-scoped `bicep_text` fixture, covers both `BlobCreated`/`BlobDeleted` event types, actionable sibling-voice messages, correctly no per-function `Pillar:` header, passes (35/35).

### Phase 2 — Verified (0 findings)

* `parser_key_for_path` extracted to `v2/src/backend/core/paths.py`, defined once, all four call sites repoint (`ingestion.py:94`, `ingestion.py:217`, plus the `batch_push` / `add_url` delegators). Behavior-preserving (each site's fallback / urlparse / 415-gate logic intact). Two Functions-side delegators correctly kept (their blueprint tests reference them). Dead `PurePosixPath` imports dropped. Test matrix covers all specified cases. Hard Rules #3/#15/#16/#17 satisfied. DE-02 (`Phase: 6` header vs details' `Phase: 7`) is the only deviation and is recorded.

### Phase 3 — Verified (1 Minor*, 3 Info)

* `resolve_search_provider` + frozen `ResolvedSearch` struct extracted to `v2/src/functions/core/search_resolution.py`; all three blueprint `_execute` bodies call it (`batch_push:118`, `add_url:119`, `blob_event:116`); no inline search/pgvector/`ensure_schema` duplication remains. The three scoping invariants hold: `backend/app.py` Site 4 unchanged; `blob_event` CREATE branch (QueueClient enqueue) untouched, only DELETE branch repointed; teardown order preserved (provider → pool; embedder in its own outer finally). Monkeypatch seams intact; both index_store paths + two failure-cleanup tests covered. **DE-03** (`try/except BaseException` close-on-failure wrapper) accepted: behavior-preserving, leak-safe, re-raising (non-silent), recorded in Planning + Changes logs. Hard Rules #3/#11/#14/#15/#16/#17 all satisfied.
* **Minor*** — Changes Log Release Summary tally inaccuracy (see aggregate CL-INVENTORY below); not a Phase 3 code defect.

### Phase 4 — Verified (3 Info, Steps 4.2/4.3 correctly Blocked)

* **Step 4.1 Verified** — both the BUG-0054 detail block (`v2/docs/bugs.md` ~L973-991) and the summary row (~L113) reconciled: 2026-06-24 deploy (BUG-0080, 5→6 functions) recorded, four operator close-out steps listed, BUG-0054 stays `open`, closed-set `infra | medium | open` fields intact, placeholders only (Hard Rule #18 clean). The summary-row fix beyond the literal details file is a traced extension recorded in Planning Log DR-02.
* **Steps 4.2 / 4.3 Blocked (correctly)** — marked `[ ]` / BLOCKED; no artifact claims the trigger flip or cloud E2E happened; no premature "BUG-0054 fixed" assertion anywhere. DR-03 / WI-01 live confirmations correctly deferred to operator close-out.

### Phase 5 — Verified (1 Minor*, 3 Info) — gates independently reproduced

* **Step 5.1** — independent re-run `.venv\Scripts\python.exe -m pytest tests/backend tests/functions tests/infra tests/shared -q` → **2514 passed, 1 skipped, 31 warnings** (exact match; 31 warnings pre-existing/unrelated — FastAPI 422 deprecation, agent_framework ExperimentalWarning, langgraph asyncio DeprecationWarning).
* **Step 5.2** — independent re-run `.venv\Scripts\python.exe -m pyright src/backend src/functions/core` → **0 errors, 0 warnings, 0 informations** (exact match; trailing line is a launcher version-availability notice, not a diagnostic).
* **Step 5.3 Verified** — gates green on first run with zero validator source edits; the three `test_blueprint.py` diffs are Phase 3 refactor adaptations (registry dispatch moved into the helper; stubs now subclass `BaseSearch`), not Step 5.3 patches; Phase 4 operator cutover NOT coupled (only `bugs.md` doc change present, no bicep edit / `azd` / flag flip).
* **F3 (Minor*)** — see aggregate CL-INVENTORY below.

## Implementation Quality Findings

Full log: reviews/impl/2026-06-29/bug-0054-cutover-dedup-impl-validation.md. (The `Implementation Validator` subagent self-reported Blocked — no file tools in its session — so the reviewer performed the quality pass directly via source read + `get_errors` + grep.)

* **Verdict: High quality** — 0 Critical / 0 Major / 0 Minor / 12 Info. `get_errors` clean on all 8 reviewed source/test files.
* **DRY/dedup** — genuine, complete: `parser_key_for_path` is the sole extension-derivation point (no residual inline `.suffix.lstrip(".").lower()`); `resolve_search_provider` is the sole `search_registry.registry.get` + `ensure_schema()` caller under `v2/src/functions/**`. Kept delegators justified (`_parser_key_for_url` preserves URL-specific `urlparse` preprocessing at the call site; both have live test callers).
* **Behavior preservation** — no drift; `PurePosixPath` keeps separator handling stable cross-platform; teardown order + `blob_event` CREATE-branch isolation preserved.
* **Resilience (#14)** — DE-03 wrapper closes provider→pool and re-raises unconditionally; observability delegated to trigger decorators.
* **Type discipline (#11/#15)** — only `Any` is the documented `dict[str, Any]` registry-kwargs boundary (inline-justified); `ResolvedSearch` frozen + `extra="forbid"`; no `TYPE_CHECKING`/`__future__`; `IndexStore.PGVECTOR` StrEnum member used, not a bare string.
* **Comment hygiene (#16)** — clean; only `Pillar:`/`Phase: 6 (…)` headers + standing-policy anchors (`Hard Rule #4/#11/#14`); no unit IDs, no BUG ref, no task numbers, no date stamps.
* **Test quality** — both registry paths + the DE-03 `ensure_schema`-failure cleanup contract covered; stubs subclass real `BaseSearch`/`PgVectorPool` to satisfy `arbitrary_types_allowed` `isinstance` validation.

## Validation Command Outputs

| Command | Result | Source |
|---------|--------|--------|
| `get_errors` (8 changed src/test files) | No errors found (clean) | Reviewer (direct) |
| `pytest tests/backend tests/functions tests/infra tests/shared -q` | 2514 passed, 1 skipped, 31 warnings | Phase 5 RPI validator (independent re-run) — matches claim |
| `pyright src/backend src/functions/core` | 0 errors, 0 warnings, 0 informations | Phase 5 RPI validator (independent re-run) — matches claim |

## Missing Work and Deviations

* **Phase 4 Steps 4.2 / 4.3 (operator-blocked, not missing)** — cloud cutover (flip `AZURE_ENV_INGESTION_TRIGGER`/provision) + cloud E2E + poison-queue drain + BUG-0054 close are operator-driven and intentionally deferred. BUG-0054 remains `open`. This is by design, not a gap in the agent-doable scope.
* ✅ **RESOLVED (RR-01)** — **DR-A (Major) — substantive gap** — the Phase 1 regression guard did not meet its own stated success criterion for the single-subscription regression vector (the original BUG-0054 shape). Closed by the `count == 2` + scoped negative `doc-processing` tightening; the reviewer independently executed the real guard against a single-subscription mutation and confirmed it now raises (see Re-review). No structural impact.
* ✅ **RESOLVED (RR-02)** — **CL-INVENTORY (Minor) — Changes Log file tally inaccurate** — the Release Summary now reads "Files affected: 12 (4 added, 8 modified, 0 removed)" and the three Phase-3-modified test files (`tests/functions/add_url/test_blueprint.py`, `tests/functions/batch_push/test_blueprint.py`, `tests/functions/blob_event/test_blueprint.py`) are listed in the Modified set — reconciled against `git show --stat` + `git status --short` and confirmed on disk by the reviewer. Documentation-completeness only; did not affect either gate.

## Re-review (rework verification, 2026-06-29)

The `/task-implement` rework (RR-01, RR-02 in the planning log) was **independently re-validated** by the reviewer — not accepted on the implementer's self-marked status. Verification imported the **actual** Phase 1 guard function (`test_blob_event_subscription_targets_blob_events_queue`) live from `tests/infra/test_main_bicep.py` and exercised it against the real `v2/infra/main.bicep` plus two mutated copies:

| Check | Evidence | Result |
|-------|----------|--------|
| Pinned-literal count | `bicep_text.count("queueName: blobEventsQueueName")` | **2** — both subscriptions pinned, so `count == 2` is exact |
| Negative-literal safety | `bicep_text.count("queueName: docProcessingQueueName")` | **0** — the scoped negative cannot false-positive on the correct bicep |
| Baseline (correct bicep) | `fn(bicep_text)` | PASS — no raise |
| **Single-subscription regression** (original BUG-0054 shape) | repoint one subscription → `doc-processing` | **AssertionError raised** ✅ — the vector the original whole-file membership assert silently missed (DR-A) is now caught |
| Total regression | repoint both subscriptions → `doc-processing` | **AssertionError raised** ✅ |
| Official gate | `pytest tests/infra/test_main_bicep.py -q` | **35 passed** |
| Static | `get_errors` on the test file | clean |

**Outcome — all four review findings closed, independently confirmed:**

* **DR-A (Major) → closed** by RR-01. The `count == 2` assertion fails the moment *either* subscription regresses; the live single-subscription mutation proves it. Meets the plan's "fails if **either** subscription regresses" success criterion.
* **DR-C (Minor) → closed** by RR-01 — the scoped negative `"queueName: docProcessingQueueName" not in bicep_text` is present and provably safe (literal count 0 on correct bicep).
* **DR-B (Minor) → closed** by RR-01 — the Changes Log guard-coverage claim is scoped to "*either* subscription" and backed by the tightened assertions.
* **CL-INVENTORY (Minor) → closed** by RR-02 — the Changes Log Release Summary reconciles to **12 files (4 added, 8 modified, 0 removed)** with the three Phase-3 `test_blueprint.py` files now enumerated (confirmed on disk).

The rework is **test-only + doc-only** — no production source or structural change. Phases 2–5 are untouched by the rework and retain their prior ✅ Verified status.

| Severity | Found | Resolved | Residual |
|----------|-------|----------|----------|
| Critical | 0 | — | 0 |
| Major | 1 | 1 (RR-01) | **0** |
| Minor | 3 | 3 (RR-01 ×2, RR-02) | **0** |
| Info | 20 | — | 20 |

## Follow-Up Work

### Deferred from scope (operator-gated / planned)

* Phase 4 Steps 4.2 / 4.3 — cloud cutover, cloud E2E, poison-queue drain, then close BUG-0054 (gated on operator + BUG-0058 clean deploy).
* WI-01 — three read-only live `az`/`azd` confirmations (deferred to operator close-out per DR-03).
* WI-03 — bicep literal hoist; WI-04 — (per Planning Log follow-on list). (WI-02 double-enqueue guard already landed in commit `b965a04d` per the Phase 5 git-log inspection.)

### Discovered during review

* ✅ **RESOLVED (2026-06-29 `/task-implement`)** — **Tighten the Phase 1 Event Grid guard (DR-A / DR-B / DR-C).** `test_blob_event_subscription_targets_blob_events_queue` now asserts `bicep_text.count("queueName: blobEventsQueueName") == 2` (both subscriptions pinned) plus the scoped negative `"queueName: docProcessingQueueName" not in bicep_text`. Verified safe by grep (the pinned literal occurs exactly twice; `docProcessingQueueName` is never a `queueName:` destination) and by an in-memory single-subscription mutation that confirms both asserts fire (count→1, negative→present). `tests/infra/test_main_bicep.py` 35 passed. The Changes Log coverage claim (DR-B) was scoped to match. Recorded as RR-01 in the planning log.
* ✅ **RESOLVED (2026-06-29 `/task-implement`)** — **Correct the Changes Log file inventory (CL-INVENTORY).** The three `test_blueprint.py` files were added to the Modified list and the tally reconciled against `git show --stat 4c2bf280` + `git status --short` to **12 files (4 added, 8 modified, 0 removed)**, with an explicit note that the span covers the commit plus the working tree. Recorded as RR-02 in the planning log.

## Overall Status

✅ **Complete** — *review rework resolved 2026-06-29 (`/task-implement`).*

> **Original verdict (retained for history):** ⚠️ Needs Rework — narrow, non-blocking. The single **Major** (DR-A) was an isolated test-efficacy gap in the Phase 1 regression guard, paired with the Minor Changes Log inventory inaccuracy (CL-INVENTORY).

Both discovered-during-review findings are now closed (RR-01, RR-02 in the planning log) with **test-only and doc-only** changes — no production-code or structural change. The Phase 1 guard now fails on the single-subscription regression vector (the original BUG-0054 shape), validated by an in-memory mutation; the Changes Log inventory is reconciled to 12 files. The dedup refactor (Phases 2, 3) remains complete, behavior-preserving, high-quality, and green; Phase 4's in-repo docs reconcile and Phase 5's gates are verified and independently reproduced. The operator-gated Phase 4 cloud cutover (Steps 4.2/4.3) is correctly out of agent scope and not counted against this status — it stays the only open work and keeps BUG-0054 `open`.

### Reviewer notes

* No production source defect was found; the Major lives entirely in test coverage of `v2/infra/main.bicep`.
* The Phase 3 + Phase 5 RPI validators independently surfaced the same Changes Log tally issue — deduped to one Minor here.
* The `Implementation Validator` subagent was Blocked (no file tools in its session); the reviewer performed that pass directly — findings in the impl validation log.
* **Re-review (2026-06-29):** the `/task-implement` turn pre-marked this log ✅ Complete; the reviewer did **not** rubber-stamp that self-report. The rework was independently re-validated by importing and executing the **actual** Phase 1 guard function against the live bicep plus single-/both-subscription mutations (see [Re-review](#re-review-rework-verification-2026-06-29)) — the single-subscription regression now raises, closing DR-A at the source level. RR-02 was confirmed by reading the reconciled Changes Log inventory on disk.
* No files outside `.copilot-tracking/` were modified during this review.
