---
applyTo: '.copilot-tracking/changes/2026-06-29/deletedata-page-changes-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: Delete Data (→ "Data set") page changes

## Overview

Apply five frontend-only changes to the CWYD v2 admin Delete Data page: rename the tab/heading to "Data set", restructure the confirm-delete dialog into one shared code path that places the target on its own line, and make the "Last modified" column conditional and formatted as `MM/DD/YY HH:MM`.

## Objectives

### User Requirements

* Rename the admin tab from "Delete data" to "Data set" — Source: user request 2026-06-29 ("the name, of the tab will change from delete data to data set").
* Single-source confirm prompt must not break the file name; put the source on the second line — Source: user request ("confirm delete prompt shouldn't cut the name of the file. We should put the name of the source in the second line not break in random place").
* Multi-source confirm prompt must not break; put the file count on the second line — Source: user request ("confirm delete prompt for multiple sources shouldn't break it should say the number of the files in the second line").
* The two prompts must share one logic, not be duplicated — Source: user request ("review that those two prompt are handle with the same logic and it is not duplicated in the code").
* Remove the Last-modified column when unavailable; otherwise format as `MM/DD/YY HH:MM` — Source: user request ("the last modified column should be removed if it is not available. If it is available MM/DD/YY HH:MM should be the format").

### Derived Objectives

* Rename the page `<h2>` heading and section aria-label to match the new tab — Derived from: internal consistency (research Open Question 1, default yes).
* Keep route/enum/test ids stable (`Section.AdminDelete`, `/admin/delete`, `delete-*` / `row-*` / `admin-subnav-delete`) — Derived from: naming-stability Hard Rule #11 (renaming wire/route identifiers breaks the router + test suite for zero user benefit).
* Format dates in UTC via zero-padded manual assembly — Derived from: deterministic, locale/TZ-independent unit tests (research Open Question 3, default UTC).

## Context Summary

### Project Files

* v2/src/frontend/src/pages/admin/AdminLayout.tsx - admin sub-nav; line 37 holds the "Delete data" tab label.
* v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx - the page: heading (284), aria-label (279), `formatLastModified` (193-195), derived values (199-209), Last-modified header `<th>` (386) + body `<td>` (428-430), confirm-delete dialog (468-518).
* v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css - `.dialogTarget` (186-190, the `word-break: break-all` wrap bug), `.rowMeta` (137-140, shared with Chunks — do not mutate).
* v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx - heading test (70), last_modified test (95-113), dialog-text assertions (230, 348-350, 400-402), fixtures (31-46).
* v2/src/frontend/src/models/admin.tsx - `SourceListing.last_modified: string | null` (145); KEEP.
* v2/src/frontend/src/models/sections.tsx - `Section.AdminDelete` (16) + `/admin/delete` (25); KEEP.

### References

* .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md - primary research; all line numbers verified 2026-06-29; selected approach + alternatives.
* .copilot-tracking/research/subagents/2026-06-29/deletedata-page-changes-research.md - subagent raw findings.

### Standards References

* .github/instructions/v2-frontend.instructions.md - CSS Modules, strict TS (`noUncheckedIndexedAccess`), tests under v2/tests/frontend/**, enums as `as const`, no `any`.
* .github/copilot-instructions.md - Hard Rule #1 (one unit per turn), #2 (test-first), #11 (naming stability).

### Decisions Adopted (evidence-backed defaults)

* D1: Rename the page heading to "Data set" alongside the tab.
* D2: Hide the Last-modified column when no currently-loaded row has a non-null value (`state.rows.some(...)`, per-load).
* D3: Format `MM/DD/YY HH:MM` in UTC (zero-padded manual assembly).
* D4: Keep the "—" placeholder for individual null rows in a mixed set.

## Implementation Checklist

### [x] Implementation Phase 1: Tab + page heading rename (Requirement 1)

<!-- parallelizable: false -->

* [x] Step 1.1: Rename the admin sub-nav tab label (AdminLayout.tsx:37)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 28-48)
* [x] Step 1.2: Rename the page heading + section aria-label (DeleteData.tsx:284, 279)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 50-72)
* [x] Step 1.3: Update the heading test assertion (DeleteData.test.tsx:70)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 74-91)
* [x] Step 1.4: Validate — DeleteData + AdminLayout Vitest suites (30/30 green)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 93-97)

### [x] Implementation Phase 2: Unified confirm-delete dialog + wrap fix (Requirements 2, 3, 4)

<!-- parallelizable: false -->

* [x] Step 2.1: Refactor the dialog body to one shared `target` string on its own line (DeleteData.tsx:468-518)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 105-185)
* [x] Step 2.2: Fix the mid-word-break CSS (DeleteData.module.css:186-190)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 187-213)
* [x] Step 2.3: Confirm/extend dialog tests (DeleteData.test.tsx)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 215-233)
* [x] Step 2.4: Validate — DeleteData Vitest suite (24/24 green)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 235-239)

### [x] Implementation Phase 3: Conditional + formatted Last-modified column (Requirement 5)

<!-- parallelizable: false -->

* [x] Step 3.1: Rewrite `formatLastModified` to `MM/DD/YY HH:MM` UTC (DeleteData.tsx:193-195)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 243-270)
* [x] Step 3.2: Hide the column when no loaded row has a value (DeleteData.tsx:199-209, 386, 428-430)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 272-310)
* [x] Step 3.3: Update the formatted-value test + add the all-null hidden-column test (DeleteData.test.tsx:95-113)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 312-355)
* [x] Step 3.4: Validate — DeleteData Vitest suite (25/25 green, +1 hidden-column test)
  * Details: .copilot-tracking/details/2026-06-29/deletedata-page-changes-details.md (Lines 357-361)

### [x] Implementation Phase 4: Final validation

<!-- parallelizable: false -->

* [x] Step 4.1: Run `npm run lint`, `tsc -b` (typecheck), `npm test --workspace cwyd-frontend-tests -- DeleteData AdminLayout`
* [x] Step 4.2: Fix minor validation issues — removed the stray gitignored `build-output/` build artifact that crashed ESLint typed-linting; no nits in changed files
* [x] Step 4.3: Report blocking issues that exceed minor fixes — repo-wide lint + typecheck blocked solely by the pre-existing out-of-scope `Configuration.tsx` unused `formatActor` (WI-02); surfaced, not reworked inline

## Planning Log

See .copilot-tracking/plans/logs/2026-06-29/deletedata-page-changes-log.md for discrepancy tracking, implementation paths considered, and suggested follow-on work.

## Dependencies

* Node + the frontend toolchain (`npm install` under v2/src/frontend).
* Vitest, Testing Library, ESLint, TypeScript (already in package.json).

## Success Criteria

* Sub-nav tab and page heading read "Data set"; route/enum/test ids unchanged — Traces to: user requirement 1 + D1.
* Both confirm-delete prompts render the target on its own line with no mid-word break, from one shared code path — Traces to: user requirements 2, 3, 4.
* The Last-modified column is hidden when no loaded row has a value and formats available values as `MM/DD/YY HH:MM` (UTC) — Traces to: user requirement 5 + D2/D3/D4.
* `npm run lint`, `npm run typecheck`, and the DeleteData + AdminLayout Vitest suites pass — Traces to: v2-frontend CI gate.
