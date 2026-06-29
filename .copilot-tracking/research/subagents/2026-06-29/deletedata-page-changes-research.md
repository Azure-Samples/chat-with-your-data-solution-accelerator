<!-- markdownlint-disable-file -->
# Research: DeleteData admin page — 5 requested changes

Status: Complete

Scope: RESEARCH ONLY. No production code modified. All line numbers verified against live files on 2026-06-29.

## Files in scope (verified to exist)

- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx  (page + reducer, 519 lines)
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css  (CSS module, ~196 lines)
- v2/src/frontend/src/pages/admin/AdminLayout.tsx  (admin sub-nav)
- v2/src/frontend/src/models/sections.tsx  (Section enum + route map)
- v2/src/frontend/src/models/admin.tsx  (SourceListing wire type)
- v2/src/frontend/src/App.tsx  (router; primary header nav)
- v2/src/frontend/src/pages/admin/Configuration/Configuration.tsx  (sibling page; has a non-formatting `formatTimestamp`)
- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx  (page suite)
- v2/tests/frontend/pages/admin/DeleteData/DeleteActionType.test.tsx  (reducer-enum suite)
- v2/tests/frontend/pages/admin/AdminLayout.test.tsx  (sub-nav suite)
- v2/tests/frontend/AppNavigation.test.tsx  (header regression guards)
- v2/tests/frontend/api/admin.test.tsx  (api client suite; SourceListing fixtures)

---

## Requirement 1 — TAB RENAME: "Delete data" -> "Data set"

### (a) Human-readable label string locations (rendered to UI)

There are exactly TWO places the string "Delete data" is rendered to the UI, plus one lowercase aria-label:

- v2/src/frontend/src/pages/admin/AdminLayout.tsx
  - Line 37: `label: "Delete data",` — this is the admin sub-nav link label (inside `ADMIN_NAV_ITEMS`, the `Section.AdminDelete` entry at lines 35-39). Rendered at AdminLayout.tsx line 78 (`{item.label}`).
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx
  - Line 284: `<h2 className={styles.pageTitle}>Delete data</h2>` — the page heading (h2).
  - Line 279: `aria-label="delete data"` — the outer `<section>` aria-label (lowercase). Optional to change; it is the accessible name of the page section, not a visible label.

Docstring/comment-only mentions (NOT rendered, no functional impact, change only if tidiness desired):
- DeleteData.tsx line 5: `* Admin "Delete Data" page.` (module docstring)
- DeleteData.module.css line 5: `* Page layout for the admin Delete Data view.`
- AdminLayout.tsx line 7: `* (Ingest data, Delete data, Configuration) — above an` (docstring)
- v2/src/frontend/src/api/admin.tsx line 211: `* Delete Data grid with one row per source.` (docstring)

### (b) Route path / Section enum key — does NOT embed a human label; KEEP AS-IS

The route + enum are wire/route identifiers, not labels. Confirmed structure in v2/src/frontend/src/models/sections.tsx:
- Line 16: `AdminDelete: "admin-delete",` (Section enum member; wire string)
- Line 25: `[Section.AdminDelete]: "/admin/delete",` (SectionPath route)

Router wiring in v2/src/frontend/src/App.tsx:
- Line 237: `path={adminChildPath(Section.AdminDelete)}` -> renders `<DeleteData />` (lines 236-239).

Sub-nav testid (NOT a label): AdminLayout.tsx line 38 `testId: "admin-subnav-delete"`.

Recommendation supported by code: change ONLY the display strings (AdminLayout.tsx:37 and, if the page heading should match, DeleteData.tsx:284). Leave `Section.AdminDelete`, the `/admin/delete` route, `data-testid="admin-subnav-delete"`, and `data-testid="delete-*"` selectors untouched — they are referenced by tests and the router by their existing wire/route names.

### (c) Tests asserting on the "Delete data" / "Delete Data" label

- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx line 70:
  `screen.getByRole("heading", { name: /delete data/i })` — asserts the page `<h2>` text. Breaks if DeleteData.tsx:284 heading changes to "Data set". (Sub-test "renders the page heading", lines 67-77.)
- v2/tests/frontend/pages/admin/AdminLayout.test.tsx line 49:
  `expect(screen.getByTestId("admin-subnav-delete")).toBeInTheDocument();` — asserts by TESTID, not by label text. Does NOT break on a label rename (only the `label` string changes; the testid stays `admin-subnav-delete`).
- v2/tests/frontend/AppNavigation.test.tsx line 150:
  `expect(screen.queryByTestId("nav-admin-delete")).not.toBeInTheDocument();` — regression guard asserting the (removed) primary-header nav item is ABSENT. Unaffected by the sub-nav label rename.

No test asserts the AdminLayout sub-nav by its visible "Delete data" text, so renaming AdminLayout.tsx:37 alone needs NO test change. Only DeleteData.test.tsx:70 must change if the page heading is renamed.

### Confirmed: NO primary-header nav label exists

v2/src/frontend/src/App.tsx renders a single gated "Admin" entry (header-admin) that navigates to `Section.AdminIngest` (App.tsx line 188). There is no per-page "Delete data" button in the header — AppNavigation.test.tsx lines 141-153 is a regression guard confirming the old four header nav buttons (`nav-admin-*`) are gone. So the ONLY nav-style "Delete data" label is the AdminLayout sub-nav.

---

## Requirement 2 — Confirm-delete dialog, SINGLE source

The dialog body is ONE `<p className={styles.dialogBody}>` whose content branches inline on `state.pendingDeleteSources.length`. Full JSX (DeleteData.tsx):

- Line 468: `{state.pendingDeleteSources !== null ? (` — render guard for the whole dialog.
- Line 470: `role="dialog"` ... `className={styles.dialogBackdrop}` (hand-rolled backdrop; see "Fluent UI" note below).
- Line 476: `<div className={styles.dialog}>`
- Line 477: `<h3 className={styles.dialogTitle}>Confirm delete</h3>`
- Line 478: `<p className={styles.dialogBody}>`
- Line 479: `{state.pendingDeleteSources.length === 1 ? (` — branch point.
- Lines 480-486 (single-source arm):
  ```
  <>
    This permanently removes every indexed chunk attached to{" "}
    <span className={styles.dialogTarget}>
      {state.pendingDeleteSources[0]}
    </span>
    . The action cannot be undone.
  </>
  ```
  - Line 481: leading text `This permanently removes every indexed chunk attached to{" "}`
  - Line 482: `<span className={styles.dialogTarget}>`
  - Line 483: `{state.pendingDeleteSources[0]}` — the bold filename (e.g. `Benefit_Options.pdf`).
  - Line 485: `. The action cannot be undone.`

CSS classes applied:
- Dialog body paragraph: `.dialogBody` (DeleteData.module.css lines 181-184) — only `margin: 0; color: ...`. No wrapping rule here.
- Bold source span: `.dialogTarget` (DeleteData.module.css lines 186-190) — includes `word-break: break-all;` (line 189). THIS is the mid-word wrap root cause (see "CSS wrapping root cause" below).

Source interpolation: the filename is the raw `pendingDeleteSources[0]` string (a `SourceListing.source`, i.e. the title/filename at ingestion). No transformation.

---

## Requirement 3 — Confirm-delete dialog, MULTIPLE sources

Same single `<p className={styles.dialogBody}>`; the `else` arm of the `length === 1` ternary. DeleteData.tsx lines 487-495:

- Line 487: `) : (` — multi-source arm.
- Lines 488-495:
  ```
  <>
    This permanently removes every indexed chunk attached to{" "}
    <span className={styles.dialogTarget}>
      {state.pendingDeleteSources.length.toString()} selected
      sources
    </span>
    . The action cannot be undone.
  </>
  ```
  - Line 489: leading text `This permanently removes every indexed chunk attached to{" "}`
  - Line 490: `<span className={styles.dialogTarget}>` (SAME `.dialogTarget` class as single).
  - Lines 491-492: `{state.pendingDeleteSources.length.toString()} selected sources` — the count phrase. Note JSX source-formatting splits "selected" (491) and "sources" (492) across two lines, but they render as one phrase "<N> selected sources".
  - Line 494: `. The action cannot be undone.`

Count computation: `state.pendingDeleteSources.length` — the length of the `pendingDeleteSources: string[] | null` array set when the confirm dialog opened (via `ConfirmOpen`, reducer lines 153-160). The bold span wraps the WHOLE phrase "6 selected sources" in `.dialogTarget` (word-break:break-all), which is why "sources" splits to "sourc\nes".

---

## Requirement 4 — SHARED-LOGIC / duplication check (CRITICAL)

Verdict: ONE shared code path with an inline `count === 1 ? single : multi` ternary. NOT duplicated string builders.

- Single dialog component: a hand-rolled `role="dialog"` block, rendered once (DeleteData.tsx lines 468-518), gated solely on `state.pendingDeleteSources !== null`.
- Single state field drives BOTH variants: `pendingDeleteSources: string[] | null` (declared DeleteData.tsx line 54; initial `null` line 89).
- Single dialog body: one `<p className={styles.dialogBody}>` (line 478) whose children are the `length === 1 ? <single/> : <multi/>` ternary (lines 479-495). The leading sentence ("This permanently removes every indexed chunk attached to ") and trailing sentence (". The action cannot be undone.") are DUPLICATED inside each ternary arm (lines 481 vs 489, and 485 vs 494) — they are NOT factored into a shared prefix/suffix. The only true difference between arms is the `<span>` content: `pendingDeleteSources[0]` vs `<N> selected sources`.

All four delete triggers funnel into this ONE dialog/state via the SAME `ConfirmOpen` action (`handleConfirmOpen` -> `dispatch ConfirmOpen` -> sets `pendingDeleteSources`):
- Per-row Delete button: DeleteData.tsx line 451 `handleConfirmOpen([row.listing.source])` (onClick body; single-element array -> single arm); button `data-testid` at line 453.
- Per-row Retry button (after a failed delete): onClick body line 437 calls `handleRetryDelete(row.listing.source)` (`handleRetryDelete` defined lines 265-267) which dispatches `ConfirmOpen` with `[source]` (line 266) -> single arm.
- Bulk "Delete selected": onClick body line 312 `handleConfirmOpen(state.selectedSources)` -> multi arm when >1.
- Bulk "Retry selected failed": onClick body line 302 `handleConfirmOpen(selectedFailedSources)` -> single or multi by count.

`handleConfirmOpen` definition: DeleteData.tsx lines 228-230. Reducer `ConfirmOpen` case: lines 153-160 (stores `sources` if non-empty, else `null`). The shared confirm handler `handleConfirmDelete` (lines 236-263) iterates `state.pendingDeleteSources` for both single and bulk — there is one delete loop, not two.

Implication for the user's "same logic, not duplicated" intent: the branch already lives in one place. To unify the wrapping fix in one spot, the simplest path is to compute the dialog target STRING once (e.g. a single `const dialogTarget = count === 1 ? sources[0] : `${count} selected sources`` plus a single shared sentence template) so both prompts share identical surrounding text and identical CSS. Today the surrounding sentence is physically duplicated in the two ternary arms even though it is byte-identical.

---

## Requirement 5 — "Last modified" column

### (a) Header cell `<th>`
- DeleteData.tsx line 386: `<th scope="col">Last modified</th>`
- Full header row order (DeleteData.tsx `<thead>`, lines 369-389):
  - Line 371: `<th scope="col" className={styles.selectColumn}>` — Select (checkbox + "Select" label, lines 372-383).
  - Line 384: `<th scope="col">Source</th>`
  - Line 385: `<th scope="col">Chunks</th>`
  - Line 386: `<th scope="col">Last modified</th>`
  - Line 387-389: `<th scope="col" className={styles.rowActions}>Actions</th>`

### (b) Body cell `<td>` for Last modified
- DeleteData.tsx lines 428-430:
  ```
  <td className={styles.rowMeta}>
    {formatLastModified(row.listing.last_modified)}
  </td>
  ```
  - Line 428: `<td className={styles.rowMeta}>`
  - Line 429: `{formatLastModified(row.listing.last_modified)}`

### (c) Current `formatLastModified` helper
- DeleteData.tsx lines 193-195 (exact body):
  ```
  function formatLastModified(value: string | null): string {
    return value ?? "—";
  }
  ```
  It does NO date formatting — it returns the raw ISO string verbatim when present, or the em-dash "—" placeholder when `null`. (The page docstring at lines 17-20 still claims "last modified timestamp (when available)".)

### (d) `SourceListing.last_modified` type
- v2/src/frontend/src/models/admin.tsx line 145: `last_modified: string | null;` (inside `interface SourceListing`, lines 142-146; field is `source: string` (143), `chunk_count: number` (144), `last_modified: string | null` (145)).
- Docstring (admin.tsx lines 130-141) states pgvector always returns `null` (no timestamp column), Azure AI Search can produce one. NOTE the user prompt says the opposite polarity ("blank on Azure AI Search, populated on pgvector") — the code docstring is the authoritative wire contract: `null` is possible on at least one backend, non-null on the other. Either way the rule "hide column when no row has a non-null value" is backend-agnostic.

### (e) CSS class `.rowMeta` — SHARED with the Chunks column
- DeleteData.module.css lines 137-140:
  ```
  .rowMeta {
    color: var(--colorNeutralForeground3);
    white-space: nowrap;
  }
  ```
- SHARED: both the Chunks `<td>` (DeleteData.tsx line 425) and the Last modified `<td>` (line 428) use `className={styles.rowMeta}`. There is no Last-modified-specific class. If a date-specific style is needed, add a new class; do not mutate `.rowMeta` (it would also restyle Chunks).

### (f) Row/state sourcing — where to compute "any row has non-null last_modified"
- Table rows come from `state.rows: RowState[]` (state shape DeleteData.tsx lines 49-56; `RowState` lines 39-43: `{ listing: SourceListing; deleteStatus; deleteError? }`).
- `state.rows` is built from the wire response in reducer `ListSucceeded` (lines 119-128): `rows: action.listings.map((listing) => ({ listing, deleteStatus: Idle }))`, where `action.listings = response.documents` (refresh callback lines 209-219, `response.documents` is `SourceListing[]`).
- The table body maps `state.rows.map((row) => ...)` at DeleteData.tsx line 393.
- Compute the availability flag in the component body (alongside `selectedSet` line 199 / `selectedFailedSources` lines 200-206 / `isAllSelected` lines 207-209), e.g.:
  `const hasAnyLastModified = state.rows.some((row) => row.listing.last_modified !== null);`
  Then conditionally render the `<th>` (line 386) and the `<td>` (lines 428-430) only when `hasAnyLastModified` is true. Both header and every body cell must be guarded together to keep the column count consistent.

### (g) Tests asserting the column header / last_modified cell value
- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx, sub-test "surfaces chunk_count and last_modified per row" (lines 95-113):
  - Fixtures: `ALPHA` (lines 31-35) `last_modified: null`; `BETA` (lines 37-41) `last_modified: "2026-05-01T12:00:00Z"`; `LIST_FIXTURE = [ALPHA, BETA]` (lines 43-46).
  - Line ~105-106: `// null last_modified renders as the em-dash placeholder.` then `expect(alphaRow).toHaveTextContent("—");`
  - Line ~111: `expect(betaRow).toHaveTextContent("2026-05-01T12:00:00Z");` — asserts the RAW ISO string is shown. This WILL BREAK once the value is formatted to `MM/DD/YY HH:MM` (e.g. expected `05/01/26 12:00`).
  - Because `LIST_FIXTURE` always contains BETA (non-null), the column would always render under existing fixtures. To test the "hidden when none available" branch, a NEW all-null fixture is required (none exists today).
- No test asserts the literal header text "Last modified". AdminLayout/AppNavigation tests assert by testid only. `api/admin.test.tsx` lines 78-79 only build `SourceListing` fixtures with `last_modified: null` (api-client shape test, no UI rendering).

---

## Also report

### Overall DeleteData table structure
- Columns (in order): Select (checkbox + select-all) | Source | Chunks | Last modified | Actions.
- `<td>` contents per column:
  - Select (line 399 `.selectColumn`): per-row checkbox `data-testid={`row-select-${source}`}` (testid line 409); disabled while `deleteStatus === Deleting`.
  - Source (line 413 `.rowSource`): `{row.listing.source}` plus an inline error `<div ... data-testid={`row-error-${source}`}>` when `deleteStatus === Failed` (error testid line 419).
  - Chunks (line 425 `.rowMeta`): `{row.listing.chunk_count.toString()}` (line 426).
  - Last modified (line 428 `.rowMeta`): `{formatLastModified(row.listing.last_modified)}` (line 429).
  - Actions (line 431 `.rowActions`): per-row Retry button when Failed (retry onClick line 437, testid line 439) else Delete button (delete onClick line 451, testid line 453; label "Deleting…" while deleting, "Delete" otherwise).
  - Table body map: `{state.rows.map((row) => (` at line 393 (inside `<tbody>` line 392).
- Row/state types: `DeleteDataState` (lines 49-56), `RowState` (lines 39-43), `RowDeleteStatus` (imported from @/models/status), `LoadStatus` (imported), `SourceListing` (@/models/admin).
- Action buttons / controls:
  - Select-all checkbox: header, `data-testid="select-all"` at line 379, `checked={isAllSelected}` (isAllSelected computed lines 207-209).
  - Bulk "Retry selected failed (N)": `data-testid="bulk-retry-failed-button"` (line 305), onClick `handleConfirmOpen(selectedFailedSources)` (line 302), disabled when `selectedFailedSources.length === 0` (line 304; selectedFailedSources computed lines 200-206), label line 307.
  - Bulk "Delete selected (N)": `data-testid="bulk-delete-button"` (line 315), onClick `handleConfirmOpen(state.selectedSources)` (line 312).
  - Refresh: `data-testid="refresh-button"` (line 325), disabled while Loading.
  - Per-row Delete: `data-testid={`row-delete-${source}`}` (line 453), opens confirm via `handleConfirmOpen([row.listing.source])` (onClick line 451).
  - Per-row Retry (post-failure): `data-testid={`row-retry-${source}`}` (line 439), re-opens confirm via `handleRetryDelete(row.listing.source)` (onClick line 437; `handleRetryDelete` definition lines 265-267, dispatches `ConfirmOpen` at line 266).

### Existing date/time formatting utility?
- NONE exists in the frontend. Searches for `toLocaleString` / `toLocaleDateString` / `Intl.DateTimeFormat` / `formatTimestamp` / `formatDate` / `new Date(` returned only:
  - Built bundle artifacts (v2/src/frontend/dist/**, build-output/**) — ignore (vendor/minified).
  - v2/src/frontend/src/pages/admin/Configuration/Configuration.tsx line 621 `function formatTimestamp(value: string): string` (lines 621-626) — a PASS-THROUGH that returns the raw string or "—"; it does NOT parse/format dates. Not reusable for `MM/DD/YY HH:MM`.
- Conclusion: add a NEW local helper (e.g. replace `formatLastModified` body with `new Date(value)` + manual `MM/DD/YY HH:MM` assembly, or a fixed `Intl.DateTimeFormat("en-US", { year:"2-digit", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", hour12:false })`). Watch the test-locale/timezone sensitivity: BETA's fixture is `2026-05-01T12:00:00Z` (UTC) — a `toLocale*`/`Intl` formatter renders in the test runner's local TZ, so a deterministic test should either pin the expected output to UTC via explicit `timeZone: "UTC"` in the formatter, or assert a regex. For exact `MM/DD/YY HH:MM` with no locale ambiguity, manual zero-padded assembly from `Date` getters (UTC getters if UTC is intended) is the most test-stable.

### Fluent UI components in the dialog
- The confirm dialog is HAND-ROLLED, not a Fluent `Dialog`/`DialogSurface`. It is a `<div role="dialog" aria-modal="true" className={styles.dialogBackdrop}>` (DeleteData.tsx lines 469-475) wrapping `<div className={styles.dialog}>` (line 476). This matches the Configuration reset-dialog pattern the user referenced.
- Only Fluent component used on the page: `Button` — `import { Button } from "@fluentui/react-components";` (DeleteData.tsx line 33). Buttons used for bulk actions, refresh, per-row delete/retry, and dialog Cancel/Delete. No Fluent Dialog/Surface/Overlay imports.

### CSS wrapping root cause (mid-word break)
- ROOT CAUSE: `.dialogTarget { ... word-break: break-all; }` — DeleteData.module.css line 189 (rule lines 186-190). `word-break: break-all` breaks at ANY character boundary, so:
  - Single: `Benefit_Options.pdf` -> `Benefit_Options.` / `pdf`.
  - Multi: `6 selected sources` -> `6 selected sourc` / `es`.
  Both variants share this one class (single span at DeleteData.tsx line 482, multi span at line 490), so a single CSS change fixes both prompts.
- The dialog body wrapper `.dialogBody` (lines 181-184) has NO wrapping rule — it is not the cause.
- Sibling reference: `.rowSource` (lines 132-135) ALSO uses `word-break: break-all` (line 134) — appropriate for long filenames in a narrow table cell, so do NOT change that one unless asked.
- Fix options for the planner (not implemented):
  - For the multi-source phrase, `word-break: break-all` is semantically wrong (it is words, not an unbreakable token). Switching `.dialogTarget` to `overflow-wrap: anywhere` (a.k.a. `overflow-wrap: break-word`) breaks only when needed and prefers word boundaries — fixes "sourc\nes" while still allowing a very long filename to wrap.
  - Alternatively split into two classes: a filename class keeping aggressive breaking and a phrase class with normal wrapping. But since the user wants ONE shared path, a single `.dialogTarget` using `overflow-wrap: anywhere` (drop `word-break: break-all`) is the minimal unified fix; the `.dialog` max-width is 520px (CSS lines 163-172) so the filename still has room.

---

## Exact files + lines to touch per requirement (summary for the plan)

1. Tab rename "Delete data" -> "Data set":
   - v2/src/frontend/src/pages/admin/AdminLayout.tsx line 37 (sub-nav label) — required.
   - v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx line 284 (page h2) — required if heading must match.
   - Optional: DeleteData.tsx line 279 aria-label; docstrings (DeleteData.tsx:5, AdminLayout.tsx:7, css:5, api/admin.tsx:211).
   - Test to update IF page heading changes: v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx line 70 (`/delete data/i` -> `/data set/i`).
   - KEEP untouched: Section.AdminDelete (sections.tsx:16), route /admin/delete (sections.tsx:25), all `delete-*` / `admin-subnav-delete` testids.

2. Single-source dialog text: DeleteData.tsx lines 480-486 (span at 482-483).
3. Multi-source dialog text: DeleteData.tsx lines 488-495 (span at 490-492). Both share `.dialogBody` (478) and `.dialogTarget` (CSS 186-190).
4. Unify single+multi logic: already one path (DeleteData.tsx 478-495); de-duplicate the surrounding sentence by computing a single target string. Confirm trigger funnels: handleConfirmOpen (225-227) from row-delete (453), row-retry (281), bulk-delete (311-313), bulk-retry (300-302).
5. Last modified column:
   - Hide-when-none: add `hasAnyLastModified` flag near DeleteData.tsx lines 199-208; guard `<th>` line 386 and `<td>` lines 428-430.
   - Format value: rewrite `formatLastModified` body (DeleteData.tsx 193-195) to `MM/DD/YY HH:MM`.
   - Type ref: models/admin.tsx line 145 (`last_modified: string | null`).
   - CSS: `.rowMeta` (css 137-140) is SHARED with Chunks — add a new class if date-specific styling is needed; do not mutate `.rowMeta`.
   - Tests to update: DeleteData.test.tsx lines 95-113 (assertion at ~111 expects raw ISO; ~105-106 expects "—"); add an all-null fixture to cover the hidden-column branch.

---

## Open questions for the user / planner

1. Should the PAGE HEADING (DeleteData.tsx:284 `<h2>Delete data</h2>`) also change to "Data set", or only the sub-nav tab (AdminLayout.tsx:37)? The user said "tab/nav label" but also asked us to find the page heading. If the heading changes, DeleteData.test.tsx:70 must change too.
2. For the hidden Last-modified column: should the trigger be "no row in the CURRENT loaded data has a non-null last_modified" (per-load, recomputed each refresh)? The code naturally supports `state.rows.some(...)`. Confirm this per-load semantics is intended (vs a backend capability flag).
3. `MM/DD/YY HH:MM` timezone: render in UTC (matches the stored ISO `Z`) or in the browser's local time? This determines whether the formatter pins `timeZone: "UTC"` and what BETA's test expectation becomes (`05/01/26 12:00` for UTC vs a local-offset value).
4. The em-dash placeholder "—" for null cells (DeleteData.tsx:194) — once the column is hidden when NO row has a value, individual null rows can still coexist with non-null rows (mixed backend). Keep "—" for the per-row null case, or render blank? Current code shows "—".
5. Multi-source bold styling: should "6 selected sources" remain bold (`.dialogTarget`) at all, or should only the count be bold? Current code bolds the whole phrase. (Affects requirement 2/3 unification choice.)

## Recommended next research (not done this session)
- [ ] Confirm the Configuration reset dialog markup to mirror its exact wrapping/styling conventions if the planner wants visual parity (Configuration.tsx, search `role="dialog"`).
- [ ] Verify vitest runner timezone config (v2/src/frontend/vitest.config.* / setup) before choosing a date-format assertion strategy.
