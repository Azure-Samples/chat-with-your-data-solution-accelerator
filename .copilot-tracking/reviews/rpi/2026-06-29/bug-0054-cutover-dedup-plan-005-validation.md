<!-- markdownlint-disable-file -->
# RPI Validation: BUG-0054 cutover-dedup — Phase 5 (Validation)

**Validated**: 2026-06-29
**Plan**: `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-dedup-plan.instructions.md`
**Details**: `.copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md` (Phase 5 = Lines 300-322)
**Changes Log**: `.copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md`
**Planning Log**: `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md`
**Phase under validation**: Phase 5 — Validation (Steps 5.1, 5.2, 5.3)

## Status: PASSED

Both Phase 5 gates were independently re-run on this machine and reproduce the Changes Log
claims **exactly**. Step 5.3 made no source edits. Phase 4's operator cutover was not coupled
into the code phases. One Minor documentation-completeness discrepancy was surfaced (it does
not affect the Phase 5 gates).

## Phase 5 requirements (from plan + details Lines 300-322)

| Step | Requirement | Source |
| --- | --- | --- |
| 5.1 | Run full `pytest tests/backend tests/functions tests/infra tests/shared` | details L304-306 |
| 5.2 | Run pyright type gate on `src/backend/**` + `src/functions/core/**`; must stay `0 errors / 0 warnings / 0 information` (Hard Rule #11) | details L308-310 |
| 5.3 | Fix only minor/isolated issues (unused-import, fixture wiring); report blockers; no large refactor; do NOT couple Phase 4's operator cutover | details L312-322 |

Per Planning Log **DE-01**, `uv run pytest`/`uv run pyright` fail on this machine with
"failed to canonicalize script path" (uv trampoline shim quirk); the sanctioned fallback is the
venv interpreter (`.venv\Scripts\python.exe -m ...`). This validation used the same fallback.

## Step-by-step validation

### Step 5.1 — Full test suite — VERIFIED

**Claim** (changes log + plan checklist): `2514 passed, 1 skipped` (skip pre-existing, unrelated).

**Independent re-run** from `v2/`:

```text
> .venv\Scripts\python.exe -m pytest tests/backend tests/functions tests/infra tests/shared -q
...
2514 passed, 1 skipped, 31 warnings in 29.05s
```

**Measured**: `2514 passed, 1 skipped, 31 warnings`.
**Result**: Exact match on pass (2514) and skip (1). The 31 warnings are pre-existing and
unrelated (FastAPI `HTTP_422_UNPROCESSABLE_ENTITY` deprecation, `agent_framework`
ExperimentalWarning, langgraph `asyncio.iscoroutinefunction` DeprecationWarning) — the Changes
Log already characterizes these as "pre-existing and unrelated", which the warning summary
confirms (none originate in the BUG-0054 touched files). **Verified.**

### Step 5.2 — Type gate (pyright) — VERIFIED

**Claim**: `0 errors / 0 warnings / 0 information` on `src/backend` + `src/functions/core`.

**Independent re-run** from `v2/`:

```text
> .venv\Scripts\python.exe -m pyright src/backend src/functions/core
0 errors, 0 warnings, 0 informations
WARNING: there is a new pyright version available (v1.1.409 -> v1.1.411).
```

**Measured**: `0 errors, 0 warnings, 0 informations`.
**Result**: Exact match. The trailing line is an informational *version-availability* notice
from the pyright launcher (pinned v1.1.409 on this machine vs v1.1.411 available); it is not a
diagnostic and does not alter the `0/0/0` summary. **Verified.**

### Step 5.3 — Minor-fixes-only / no source edits / no Phase 4 coupling — VERIFIED

**Claim**: "no fixes needed; both gates green on first run."

**Evidence A — gates green with zero validator edits.** Steps 5.1 and 5.2 both passed on my
first run without my touching any source, reproducing the "green on first run" claim.

**Evidence B — no Step 5.3 source edits.** The working-tree source changes are all attributable
to Phases 3 and 4, not to Step 5.3. The plan landed across one commit + an uncommitted working
set:

```text
> git log --oneline -3
4c2bf280 Dedup parser key logic and guard Event Grid     <- Phase 1 (guard test) + Phase 2 (parser_key_for_path)
b965a04d BUG-0054 in-repo fix + WI-02 follow-up
e9509ffd Fix BUG-0054: add blob_event to Flex alwaysReady

> git status --short   (v2 paths)
 M v2/docs/bugs.md                                  <- Phase 4 Step 4.1 (doc reconcile only)
 M v2/src/functions/add_url/blueprint.py            <- Phase 3 (_execute -> resolve_search_provider)
 M v2/src/functions/batch_push/blueprint.py         <- Phase 3
 M v2/src/functions/blob_event/blueprint.py         <- Phase 3 (delete-branch repoint)
 M v2/tests/functions/add_url/test_blueprint.py     <- Phase 3 test adaptation (UNDOCUMENTED — see F3)
 M v2/tests/functions/batch_push/test_blueprint.py  <- Phase 3 test adaptation (UNDOCUMENTED — see F3)
 M v2/tests/functions/blob_event/test_blueprint.py  <- Phase 3 test adaptation (UNDOCUMENTED — see F3)
?? v2/src/functions/core/search_resolution.py       <- Phase 3 (new module)
?? v2/tests/functions/core/test_search_resolution.py<- Phase 3 (new test)
```

The Phase-1/2 files claimed in the Changes Log (`paths.py`, `test_paths.py`,
`test_main_bicep.py`, `ingestion.py`) are absent from the working tree because they are already
committed in `4c2bf280` — consistent with the Changes Log, not a gap.

The three `test_blueprint.py` diffs were inspected and are unambiguously Phase 3 refactor
adaptations, not Step 5.3 patches:

```text
+from functions.core import search_resolution
-    monkeypatch.setattr(bp_module.search_registry.registry, "get", ...)
+    monkeypatch.setattr(search_resolution.search_registry.registry, "get", ...)
-    class _StubSearch:
+    class _StubSearch(BaseSearch):
+        async def search(self, query: str, **_kwargs: object) -> Sequence[SearchResult]: ...
```

These edits exist *because* registry dispatch moved into the shared helper and the helper now
returns `BaseSearch`-typed providers (Step 3.2 + DE-03). They are required for the Phase 3
refactor to stay green — they are not Step-5.3 minor fixes.

**Evidence C — Phase 4 operator cutover NOT coupled.** The only Phase 4 change present is
`v2/docs/bugs.md` (Step 4.1, the docs reconciliation explicitly scoped to the in-repo portion).
There is no bicep edit, no `azd`/`az` invocation captured, and no `AZURE_ENV_INGESTION_TRIGGER`
flag flip in any tracked file. Plan Steps 4.2/4.3 remain `[ ]` (BLOCKED, operator-driven). The
code phases were not contaminated by the gated cloud cutover. **Verified.**

## Findings

### F1 — Step 5.1 pytest counts reproduce exactly — Info

Independent measurement `2514 passed, 1 skipped` matches the claim verbatim. No action.

### F2 — Step 5.2 pyright `0/0/0` reproduces exactly — Info

Independent measurement `0 errors, 0 warnings, 0 informations` matches the claim verbatim.
No action.

### F3 — Changes Log file inventory omits three Phase-3-modified test files — Minor

The Changes Log "Release Summary" states **"Files affected: 9 (4 added, 5 modified, 0 removed)"**
and enumerates the Modified set without listing the three function-blueprint test files that
Phase 3 actually modified:

* `v2/tests/functions/add_url/test_blueprint.py` (28 lines changed)
* `v2/tests/functions/batch_push/test_blueprint.py` (28 lines changed)
* `v2/tests/functions/blob_event/test_blueprint.py` (14 lines changed)

Two sub-issues:

1. **Omission** — these three test files are modified in the working tree (confirmed via
   `git status` + diff) but appear in neither the "Modified" bullet list nor the file count.
2. **Internal miscount** — even before the missing test files, the "Modified" bullet list
   enumerates six distinct files (`test_main_bicep.py`, `batch_push/blueprint.py`,
   `add_url/blueprint.py`, `ingestion.py`, `blob_event/blueprint.py`, `bugs.md`) while the
   summary labels it "(5 modified)".

**Severity rationale**: Minor, not Major. This is a documentation-completeness gap in the
Changes Log's inventory (a Phase 2/3 artifact), surfaced during Phase 5 validation. It does
**not** affect either Phase 5 gate — both reproduce green — and it does not represent a Step 5.3
source edit (the test edits are Phase 3, per Evidence B). A future reviewer reading only the
Changes Log would under-count the test surface touched by the dedup refactor.

**Recommended fix** (non-blocking): update the Changes Log "Modified" list to include the three
`test_blueprint.py` files and correct the affected-file tally (added 4 + modified 9 once the
committed Phase-1/2 files and the three test files are counted), or note that the count tracks
only the uncommitted working set.

### F4 — pyright launcher version-availability notice — Info

The pyright run prints `new pyright version available (v1.1.409 -> v1.1.411)`. This is a
launcher notice, not a diagnostic; the `0/0/0` summary is unaffected. No action.

## Coverage assessment

Phase 5 is **fully covered**. All three steps were independently exercised:

* Step 5.1 (test suite) — re-run, exact-match VERIFIED.
* Step 5.2 (type gate) — re-run, exact-match VERIFIED.
* Step 5.3 (no fixes / no source edits / no Phase 4 coupling) — VERIFIED via gate re-run +
  working-tree attribution + diff inspection.

The Phase 5 success criteria ("All existing seam + lifespan tests stay green; type gate stays
clean") are satisfied by the independent measurements above.

## Clarifying questions

None blocking. Optional: confirm whether the Changes Log "Files affected" tally is intended to
count only the uncommitted working set or the full plan span (commit `4c2bf280` + working set) —
this determines the exact correction for F3.

## Recommended next validations (not performed this session)

* [ ] Phase 1 — re-run `tests/infra/test_main_bicep.py` and confirm
  `test_blob_event_subscription_targets_blob_events_queue` fails when the Event Grid `queueName`
  is mutated off `blob-events` (regression-guard efficacy, DR-01).
* [ ] Phase 2 — verify all four parser-key call sites delegate to `parser_key_for_path` and the
  dead `PurePosixPath` imports are gone (Success Criteria + cleanup-before-next-step).
* [ ] Phase 3 — verify `backend/app.py` (Site 4) is unchanged and `resolve_search_provider`'s
  close-on-failure wrapper (DE-03) is exercised by a failing-resolution test.
* [ ] Phase 4 — operator-gated; validate only after the cloud cutover + BUG-0058 clean deploy
  (Steps 4.2/4.3 are BLOCKED and out of scope for repo validation).
* [ ] Cross-phase — apply the F3 Changes Log inventory correction, then re-confirm the file
  tally against `git status` + `git log`.
