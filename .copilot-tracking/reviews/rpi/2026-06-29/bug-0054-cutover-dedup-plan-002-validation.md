<!-- markdownlint-disable-file -->
# RPI Validation — BUG-0054 cutover-dedup — Phase 2

**Plan:** `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-dedup-plan.instructions.md`
**Phase:** 2 — Extract `parser_key_for_path` (structural — new module)
**Changes Log:** `.copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md`
**Details:** `.copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md` (Lines 38-108)
**Planning Log:** `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md` (DD-01, DE-02)
**Research:** `.copilot-tracking/research/subagents/2026-06-29/bug-0054-consolidation-design.md` (§"Secondary duplication — parser-key derivation", Lines 461-519)
**Validated:** 2026-06-29
**Status:** **Passed**

## Status summary

| Severity | Count |
| --- | --- |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Info | 3 |

Phase 2 is fully and faithfully implemented. The helper is defined once, all four prior derivation sites call it, every site's surrounding fallback/membership/urlparse/415-gate logic is preserved, the two Functions-side helpers are kept as delegators (justified by their own blueprint tests), the dead `PurePosixPath` imports are dropped everywhere they became unused, and the unit test covers the exact specified matrix. The single deviation (DE-02 Phase-header value) is recorded in both the Planning Log and the Changes Log, and resolves toward correctness. Targeted suites are green (62 passed locally).

## Per-step status

| Step | Description | Status | Evidence |
| --- | --- | --- | --- |
| 2.1 | Create `paths.py` + test-first unit test | **Verified** | [v2/src/backend/core/paths.py](../../../../../v2/src/backend/core/paths.py#L1-L19), [v2/tests/backend/core/test_paths.py](../../../../../v2/tests/backend/core/test_paths.py#L1-L20) |
| 2.2 | Repoint the four parser-key call sites | **Verified** | batch_push [L73-L81](../../../../../v2/src/functions/batch_push/blueprint.py#L73-L81); add_url [L75-L94](../../../../../v2/src/functions/add_url/blueprint.py#L75-L94); ingestion [L94](../../../../../v2/src/backend/services/ingestion.py#L94), [L217](../../../../../v2/src/backend/services/ingestion.py#L217) |
| 2.3 | Validate phase changes | **Verified** | `pytest` 62 passed (paths + batch_push + add_url + ingestion suites) |

## Step 2.1 — `paths.py` helper + unit test (Verified)

### Helper body matches research + details verbatim core

* The function body is byte-for-byte the research-proposed and details-specified expression: `return PurePosixPath(name).suffix.lstrip(".").lower()` — see [v2/src/backend/core/paths.py](../../../../../v2/src/backend/core/paths.py#L19) vs details Lines 50-53 and research Lines 481-490.
* The import `from pathlib import PurePosixPath` is at module top (Hard Rule #17) — [paths.py L8](../../../../../v2/src/backend/core/paths.py#L8).
* Signature `parser_key_for_path(name: str) -> str` — a bare scalar `str` return, so Hard Rule #15 (typed-model dict returns) does not apply. No anonymous dict return is introduced. **Verified.**

### Pillar/Phase header present (Hard Rule #3)

* [paths.py L1-L6](../../../../../v2/src/backend/core/paths.py#L1-L6): `Pillar: Stable Core` / `Phase: 6 (Functions blueprints / modular RAG indexing pipeline)` plus a `Purpose:` line describing what the module *is*. The `Phase:` line is the permitted carve-out (a) of Hard Rule #16. **Verified.**

### Test covers the exact specified matrix

* [test_paths.py L8-L20](../../../../../v2/tests/backend/core/test_paths.py#L8-L20) parametrizes exactly the five required cases: `report.PDF`→`pdf`, `a/b/file.txt`→`txt`, `article`→`""`, `name.`→`""`, `archive.tar.gz`→`gz`. No case missing, none added. **Verified.**

## Step 2.2 — Repoint the four call sites (Verified)

### Helper defined once; all four sites call it

* Definition exists only in `paths.py`. The three touched source files import `parser_key_for_path` from `backend.core.paths` and contain zero `PurePosixPath` references (grep returned empty in all three).
* **Site 1 — batch_push `_parser_key_for_filename`** ([blueprint.py L73-L81](../../../../../v2/src/functions/batch_push/blueprint.py#L73-L81)): reduced to `return parser_key_for_path(filename)`; top import added [L62](../../../../../v2/src/functions/batch_push/blueprint.py#L62). Matches research "drop the local helper, or keep it as a 1-line alias".
* **Site 2 — add_url `_parser_key_for_url`** ([blueprint.py L75-L94](../../../../../v2/src/functions/add_url/blueprint.py#L75-L94)): `suffix = parser_key_for_path(urlparse(url).path)` then `return suffix or _DEFAULT_PARSER_KEY` — fallback preserved exactly; top import added [L61](../../../../../v2/src/functions/add_url/blueprint.py#L61). Matches research call-site shape.
* **Site 3 — ingestion `_blob_name_for_url`** ([ingestion.py L94](../../../../../v2/src/backend/services/ingestion.py#L94)): `suffix = parser_key_for_path(parsed.path)` (where `parsed = urlparse(url)`), then the existing `suffix in ingestion_parsers_registry.registry` membership check and the `if suffix:` stem-trim — preserved exactly; top import [L41](../../../../../v2/src/backend/services/ingestion.py#L41). Behavior-preserving.
* **Site 4 — ingestion `validate_upload`** ([ingestion.py L217](../../../../../v2/src/backend/services/ingestion.py#L217)): `extension = parser_key_for_path(filename)` then the unchanged 415 `UNSUPPORTED_MEDIA_TYPE` gate against the registry — preserved exactly. **Verified.**

### Delegators kept (justified) — not deleted

* Both Functions-side helpers are referenced by their own blueprint tests, so deleting them would break test contracts:
  * `_parser_key_for_filename` — imported + asserted at [v2/tests/functions/batch_push/test_blueprint.py L28, L96-L105](../../../../../v2/tests/functions/batch_push/test_blueprint.py#L96-L105).
  * `_parser_key_for_url` — imported + asserted at [v2/tests/functions/add_url/test_blueprint.py L22, L273-L274](../../../../../v2/tests/functions/add_url/test_blueprint.py#L273-L274).
* This exactly satisfies the details' "keep the names as 1-line delegators so those tests stay green" instruction and the `cleanup-before-next-step` memory (remove only with zero non-test callers). **Verified — claim is backed.**

### Dead `PurePosixPath` imports dropped

* Grep for `PurePosixPath` in all three touched source files returned empty, confirming the Changes Log "dropped now-dead `from pathlib import PurePosixPath`" claim for batch_push, add_url, and ingestion. **Verified by absence.**

## Step 2.3 — Validation (Verified)

* Ran `python -m pytest tests/backend/core/test_paths.py tests/functions/batch_push/test_blueprint.py tests/functions/add_url/test_blueprint.py tests/backend/test_services_ingestion.py` → **62 passed in 2.85s**. This backs the Changes Log "stays green" claim for the Phase 2 call-site suites.
* Note: the plan's command form is `uv run pytest`; the implementor's recorded fallback (DE-01, trampoline quirk) is `.venv\Scripts\python.exe -m pytest`. Validation used the same fallback interpreter/env. No discrepancy.

## Hard Rule compliance

| Rule | Result | Evidence |
| --- | --- | --- |
| #3 Pillar/Phase header | Pass | [paths.py L1-L6](../../../../../v2/src/backend/core/paths.py#L1-L6) |
| #10 structural sign-off (new module) | Pass | Planning Log "Structural Sign-off" + DD-01 record the user's "Approve both new modules" |
| #15 typed-model dict return | N/A (exempt) | bare `str` scalar return — [paths.py L11](../../../../../v2/src/backend/core/paths.py#L11) |
| #16 no process narrative in src | Pass | `paths.py` docstrings describe what the code *is*; only the carve-out `Phase:` header present; no unit IDs / dates / "lands next" |
| #17 imports at top | Pass | [paths.py L8](../../../../../v2/src/backend/core/paths.py#L8); blueprint top-import blocks at [batch_push L62](../../../../../v2/src/functions/batch_push/blueprint.py#L62), [add_url L61](../../../../../v2/src/functions/add_url/blueprint.py#L61), [ingestion L41](../../../../../v2/src/backend/services/ingestion.py#L41) |

## Findings (all Info)

* **INFO-1 — DE-02 Phase-header value deviation (recorded, toward correctness).** The details (Step 2.1, Line 50) specified `Phase: 7` for `paths.py`; the implementation uses `Phase: 6`. This is the only header deviation, is recorded in the Planning Log (DE-02) and the Changes Log ("Additional or Deviating Changes"), and is the *more* correct value — it matches the active dev_plan phase (Phase 6) and the sibling Phase-3 module `functions/core/search_resolution.py`. Both forms pass `test_no_process_narrative_in_src.py`. No action needed.
* **INFO-2 — helper docstring expanded beyond the verbatim details snippet.** `paths.py` adds a behavioral rationale paragraph (`PurePosixPath` vs `Path` separator stability) and a module-level `Purpose:` line not present in the details' bare snippet. Content is descriptive ("what the code is"), Hard-Rule-#16-compliant, and mirrors the research docstring (Lines 484-489). Enhancement, not a behavior deviation. No action needed.
* **INFO-3 — DD-01 home-module deviation from research (recorded).** Research recommended a `backend.core` leaf "either an existing leaf or a new `v2/src/backend/core/parsers/paths.py`"; the plan/implementation use `v2/src/backend/core/paths.py` to avoid conceptual collision with the existing `backend/core/providers/parsers/` registry package. Both are one-way-importable `backend.core` leaves, so the dependency-direction requirement is honored. Recorded as DD-01 in the Planning Log and covered by the #10 sign-off. No action needed.

## Coverage assessment

**Complete.** All three Phase 2 steps are implemented exactly as specified, with each call site behavior-preserved and traceable to the research design (Lines 461-519). The Changes Log "Added"/"Modified" entries for Phase 2 are accurate, and no Changes Log claim is unbacked by code (delegators-kept, dead-import-dropped, and stays-green claims were each independently verified). No missing implementations, no incorrect functionality, no specification deviations beyond the three recorded Info-level items.

## Clarifying questions

None — all Phase 2 items were resolvable from the plan, details, research, code, and a green targeted test run.

## Recommended next validations (not performed this session)

- [ ] Phase 1 — `test_blob_event_subscription_targets_blob_events_queue` infra guard (`-001` validation).
- [ ] Phase 3 — `resolve_search_provider` + `ResolvedSearch` extraction and the three `_execute` repoints, including the DE-03 close-on-failure wrapper (`-003` validation).
- [ ] Phase 4 Step 4.1 — `v2/docs/bugs.md` BUG-0054 reconciliation (detail block L973-991 + summary row L113); Steps 4.2/4.3 remain operator-blocked.
- [ ] Phase 5 — full-sweep + pyright gate claims (`2514 passed, 1 skipped`; `0/0/0`).
