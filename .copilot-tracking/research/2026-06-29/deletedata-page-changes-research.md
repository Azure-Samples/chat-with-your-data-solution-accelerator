<!-- markdownlint-disable-file -->
# Task Research: Delete Data admin page — 5 requested UI changes

The user requested five changes to the admin **Delete Data** page (the active editor file was `Configuration.tsx`, but every requirement and both attached screenshots are about the Delete Data page and its confirm-delete dialog). This is a frontend-only change set. All line numbers below were verified against the live files on 2026-06-29.

## Task Implementation Requests

1. Rename the admin tab/nav from "Delete data" to "Data set".
2. The single-source confirm-delete prompt must not break the file name at a random place — put the source name on its own (second) line.
3. The multi-source confirm-delete prompt must not break — say the number of files on its own (second) line.
4. Ensure the single-source and multi-source prompts are handled by the **same logic**, not duplicated in the code.
5. The "Last modified" column must be **removed when not available** (no row has a value); when available, format the value as `MM/DD/YY HH:MM`.

## Scope and Success Criteria

- Scope: Frontend only. Files under `v2/src/frontend/src/pages/admin/` and the mirrored test tree `v2/tests/frontend/pages/admin/`. No backend, no infra, no wire-shape change.
- Exclusions: The wire field `SourceListing.last_modified` and the backend route `DELETE /api/admin/documents/{source}` are unchanged. The `Section.AdminDelete` enum key, the `/admin/delete` route, and all `delete-*` / `admin-subnav-delete` / `row-*` test ids stay as-is (renaming them would break the router and the test suite for zero user benefit).
- Assumptions:
  - The page heading should match the new tab name ("Data set") for internal consistency — recommended, flagged as Open Question 1.
  - The Last-modified availability check is per-load: "does any row in the currently loaded data have a non-null `last_modified`" via `state.rows.some(...)`.
  - `MM/DD/YY HH:MM` is rendered in **UTC** (matching the stored ISO `Z` value) using zero-padded manual assembly so the format is locale- and timezone-independent and unit tests are deterministic.
- Success Criteria:
  - The admin sub-nav tab reads "Data set"; the page `<h2>` reads "Data set" (if Open Question 1 is yes).
  - Single-source confirm dialog shows the file name on its own line, never broken mid-word.
  - Multi-source confirm dialog shows "N selected sources" on its own line, never broken mid-word.
  - Both dialog variants are produced by one shared code path that computes a single target string — the surrounding sentence is not physically duplicated.
  - The "Last modified" column header + cells are absent when no loaded row has a value; present and formatted as `MM/DD/YY HH:MM` when at least one row has a value (null rows in a mixed set still show the "—" placeholder).
  - `npm run lint`, `npm run typecheck`, and the Vitest suite pass.

## Outline

- Requirement 1: rename the tab label (AdminLayout) and the page heading (DeleteData); keep route/enum/testids.
- Requirements 2–4: restructure the confirm-delete dialog body into one shared block that computes a single target string, places the target on its own line, and fixes the CSS that causes mid-word breaks.
- Requirement 5: conditionally render the column based on a `hasAnyLastModified` flag, and format the value in `formatLastModified`.

## Potential Next Research

- Confirm Vitest runner timezone before finalizing the date-format assertion. UTC-getter assembly sidesteps this entirely (no `toLocale*`/`Intl` locale dependency), so this is informational only.
  - Reasoning: A `toLocaleString`/`Intl.DateTimeFormat` approach would render in the runner's local TZ and make the BETA fixture (`2026-05-01T12:00:00Z`) assertion machine-dependent.
  - Reference: v2/src/frontend/vitest.config.ts and any test setup file.

## Research Executed

### File Analysis

- v2/src/frontend/src/pages/admin/AdminLayout.tsx
  - Line 33-39: `ADMIN_NAV_ITEMS` `Section.AdminDelete` entry; line 37 `label: "Delete data"`, line 38 `testId: "admin-subnav-delete"`. Label rendered at line ~78 (`{item.label}`).
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx (519 lines)
  - Line 5: module docstring `Admin "Delete Data" page.` (not rendered).
  - Lines 193-195: `function formatLastModified(value: string | null): string { return value ?? "—"; }` — no date formatting; sole caller is the body cell.
  - Lines 196-209: component body computes `selectedSet` (197), `selectedFailedSources` (198-205), `isAllSelected` (206-209). This is the natural place for a new `hasAnyLastModified` flag.
  - Line 279: `aria-label="delete data"`, line 280 `data-testid="delete-data"`.
  - Line 284: `<h2 className={styles.pageTitle}>Delete data</h2>` — page heading.
  - Lines 369-389 `<thead>`: column order Select | Source | Chunks | Last modified | Actions. Header cell `<th scope="col">Last modified</th>` at line 386.
  - Line 393: `{state.rows.map((row) => (` — table body map.
  - Lines 424-426: Chunks `<td className={styles.rowMeta}>{row.listing.chunk_count.toString()}</td>`.
  - Lines 427-430: Last modified `<td className={styles.rowMeta}>{formatLastModified(row.listing.last_modified)}</td>` (shares `.rowMeta` with Chunks).
  - Lines 467-475: hand-rolled confirm dialog `<div role="dialog" aria-modal="true" aria-label="Confirm delete" data-testid="delete-confirm-dialog" className={styles.dialogBackdrop}>`, gated on `state.pendingDeleteSources !== null` (line 467).
  - Line 477: `<h3 className={styles.dialogTitle}>Confirm delete</h3>`.
  - Line 478: `<p className={styles.dialogBody}>` — single paragraph for both variants.
  - Lines 479-495: inline `state.pendingDeleteSources.length === 1 ? <single/> : <multi/>` ternary. Single arm (480-486) renders `<span className={styles.dialogTarget}>{state.pendingDeleteSources[0]}</span>`; multi arm (488-495) renders `<span className={styles.dialogTarget}>{length.toString()} selected sources</span>`. The leading sentence and `. The action cannot be undone.` are byte-identical in both arms (physically duplicated).
  - Confirm triggers (all funnel through `handleConfirmOpen` → `ConfirmOpen` → `pendingDeleteSources`): per-row Delete `handleConfirmOpen([row.listing.source])`; per-row Retry `handleRetryDelete(source)` → `ConfirmOpen [source]`; bulk Delete `handleConfirmOpen(state.selectedSources)`; bulk Retry `handleConfirmOpen(selectedFailedSources)`.
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css (~196 lines)
  - Lines 131-135: `.rowSource { font-weight: ...; word-break: break-all; }` — keep (long filenames in a narrow cell).
  - Lines 137-140: `.rowMeta { color: ...; white-space: nowrap; }` — SHARED by Chunks + Last modified cells.
  - Lines 181-184: `.dialogBody { margin: 0; color: ... }` — no wrap rule.
  - Lines 186-190: `.dialogTarget { font-weight: ...; color: ...; word-break: break-all; }` — line 189 `word-break: break-all` is the mid-word-break ROOT CAUSE for both prompts (both spans use this class).
  - `.dialog` max-width 520px (lines ~163-172).
- v2/src/frontend/src/models/admin.tsx
  - Lines 142-146: `interface SourceListing { source: string; chunk_count: number; last_modified: string | null; }` (last_modified at line 145). KEEP — wire contract unchanged.
- v2/src/frontend/src/models/sections.tsx
  - Line 16: `AdminDelete: "admin-delete"`; line 25: `[Section.AdminDelete]: "/admin/delete"`. KEEP.

### Code Search Results

- Dialog-text test assertions in v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx
  - Line 230: `expect(dialog).toHaveTextContent(/alpha\.pdf/)` (single source).
  - Lines 348-350: `expect(...).toHaveTextContent("2 selected sources")` (bulk).
  - Lines 400-402: `expect(...).toHaveTextContent("alpha.pdf")` (bulk-retry single).
  - All three use `toHaveTextContent`, which normalizes whitespace and concatenates across child nodes. The restructure survives unchanged as long as the target strings remain `<filename>` and `<N> selected sources`.
- Page-heading + column test assertions
  - Line 70: `screen.getByRole("heading", { name: /delete data/i })` — breaks if the page heading is renamed (must become `/data set/i`).
  - Lines 95-113: sub-test "surfaces chunk_count and last_modified per row"; ALPHA (`last_modified: null`, fixture lines 31-35) asserts "—" (~line 106); BETA (`last_modified: "2026-05-01T12:00:00Z"`, fixture lines 37-41) asserts the RAW ISO string (~line 111) — this WILL BREAK once formatted to `05/01/26 12:00`.
- Date-format utilities
  - None exist. `Configuration.tsx` line 621 `formatTimestamp` is a pass-through (returns the raw string or "—"), not reusable. A new local helper is required.

### Project Conventions

- Standards referenced: v2-frontend.instructions.md (services/models layering, enums as `as const`, CSS Modules, strict TS with `noUncheckedIndexedAccess`/`exactOptionalPropertyTypes`, tests under `v2/tests/frontend/**`, `@/*` alias).
- Hard rules: one-unit-per-turn + test-first contract (planning splits these into discrete units); pillar header already present on DeleteData.tsx (`Stable Core / Phase 7`).

## Key Discoveries

### The dialog is already one component and one state field

A single hand-rolled `role="dialog"` block (DeleteData.tsx 467-518) driven by one state field `pendingDeleteSources: string[] | null` serves every delete path (per-row, per-row retry, bulk, bulk retry). The only duplication is textual: the leading sentence and trailing sentence are repeated inside both ternary arms. "Same logic, not duplicated" (Requirement 4) is therefore a small, contained refactor — compute one `target` string, render one block.

### The wrapping bug is a single CSS rule

`.dialogTarget { word-break: break-all }` (CSS line 189) breaks at any character. `Benefit_Options.pdf` → `Benefit_Options.` / `pdf`; `6 selected sources` → `6 selected sourc` / `es`. Both spans share the class, so one CSS change fixes both prompts. Putting the target on its own line additionally guarantees no mid-sentence break.

### The Last-modified column is conditional, not a hard removal

This supersedes the earlier "always remove the column" framing (the old BUG-0093 resolution). The column is data-dependent: hide it when no loaded row has a value; show it formatted when at least one does. The availability flag is `state.rows.some((row) => row.listing.last_modified !== null)`.

### Strict-TS note for the unified target string

With `noUncheckedIndexedAccess: true`, `state.pendingDeleteSources[0]` is `string | undefined`. Building a `const target` requires a guard: `const target = sources.length === 1 ? (sources[0] ?? "") : `${sources.length} selected sources``.

### Complete Example — unified dialog body (Requirements 2–4)

```tsx
{state.pendingDeleteSources !== null
  ? (() => {
      const sources = state.pendingDeleteSources;
      const target =
        sources.length === 1
          ? (sources[0] ?? "")
          : `${sources.length.toString()} selected sources`;
      return (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete"
          data-testid="delete-confirm-dialog"
          className={styles.dialogBackdrop}
        >
          <div className={styles.dialog}>
            <h3 className={styles.dialogTitle}>Confirm delete</h3>
            <p className={styles.dialogBody}>
              This permanently removes every indexed chunk attached to:
            </p>
            <p className={styles.dialogTarget}>{target}</p>
            <p className={styles.dialogBody}>This action cannot be undone.</p>
            <div className={styles.dialogActions}>
              {/* Cancel + Delete buttons unchanged */}
            </div>
          </div>
        </div>
      );
    })()
  : null}
```

CSS change (DeleteData.module.css 186-190): `.dialogTarget` becomes a block on its own line with sane wrapping:

```css
.dialogTarget {
  display: block;
  font-weight: var(--fontWeightSemibold);
  color: var(--colorNeutralForeground1);
  overflow-wrap: anywhere;
}
```

### Complete Example — formatLastModified + conditional column (Requirement 5)

```ts
function formatLastModified(value: string | null): string {
  if (value === null) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const yy = String(date.getUTCFullYear() % 100).padStart(2, "0");
  const hh = String(date.getUTCHours()).padStart(2, "0");
  const min = String(date.getUTCMinutes()).padStart(2, "0");
  return `${mm}/${dd}/${yy} ${hh}:${min}`;
}
```

Component body (near lines 196-209):

```ts
const hasAnyLastModified = state.rows.some(
  (row) => row.listing.last_modified !== null,
);
```

Header guard (replace line 386) and body-cell guard (replace lines 427-430):

```tsx
{hasAnyLastModified ? <th scope="col">Last modified</th> : null}
```

```tsx
{hasAnyLastModified ? (
  <td className={styles.rowMeta}>
    {formatLastModified(row.listing.last_modified)}
  </td>
) : null}
```

The BETA fixture `2026-05-01T12:00:00Z` formats to `05/01/26 12:00` (UTC, deterministic).

## Technical Scenarios

### Scenario A — Tab + heading rename (Requirement 1)

**Requirements:** Sub-nav tab "Delete data" → "Data set"; page heading to match.

**Preferred Approach:** Change only the visible label strings.

- AdminLayout.tsx line 37: `label: "Delete data"` → `label: "Data set"`.
- DeleteData.tsx line 284: `<h2 ...>Delete data</h2>` → `<h2 ...>Data set</h2>` (recommended; Open Question 1).
- DeleteData.tsx line 279: `aria-label="delete data"` → `aria-label="data set"` (recommended for a11y consistency; harmless).
- Keep `Section.AdminDelete`, `/admin/delete`, and every `delete-*` / `admin-subnav-delete` test id.
- Test: DeleteData.test.tsx line 70 `/delete data/i` → `/data set/i` (only if the heading changes). AdminLayout.test.tsx asserts by test id only — no change.

**Implementation Details:** Pure string edits + one test regex. Zero blast radius beyond the heading test.

#### Considered Alternatives

- Renaming the `Section.AdminDelete` enum / `/admin/delete` route to "data-set": rejected — breaks the router, deep links, and every `admin-subnav-delete` / `delete-*` test id for no user benefit. The route is a wire identifier (naming-stability Hard Rule #11), the label is the only thing the user sees.

### Scenario B — Unified confirm-delete dialog with clean wrapping (Requirements 2, 3, 4)

**Requirements:** No mid-word break; target (file name or count) on its own line; one shared code path.

**Preferred Approach:** Compute a single `target` string from `pendingDeleteSources`, render one dialog body (intro sentence + target-on-its-own-line + "This action cannot be undone."), and replace `.dialogTarget`'s `word-break: break-all` with `display: block` + `overflow-wrap: anywhere`. See "Complete Example — unified dialog body" above.

- This removes the duplicated sentence (one render path, one target computation), satisfying Requirement 4.
- The target on its own block line satisfies Requirements 2 and 3 (the name/count is on the second line and cannot break mid-sentence; `overflow-wrap: anywhere` only breaks a genuinely over-long single filename token, never the words "selected sources").
- Tests survive unchanged: the existing assertions match `/alpha\.pdf/`, `"2 selected sources"`, and `"alpha.pdf"` via `toHaveTextContent`, all preserved by the unchanged target strings.

**Implementation Details:** One IIFE in the JSX (mirrors the existing `state.formValues` IIFE pattern in Configuration.tsx and the loaded-state IIFE in DeleteData) to host the `const target`. One CSS rule edit. No reducer/state change. No new test required, though adding a "renders the target on its own line" assertion is optional hardening.

#### Considered Alternatives

- Keep two ternary arms but only change CSS: rejected — fixes wrapping but leaves the duplicated sentence, failing Requirement 4 ("same logic, not duplicated").
- Extract a separate `<ConfirmDeleteDialog>` component: rejected for now — over-engineering for a single in-file dialog; the IIFE + single target string is the minimal change. Revisit only if a second caller appears.
- `word-break: keep-all` or `white-space: nowrap` on the target: rejected — would overflow the 520px dialog for long filenames. `overflow-wrap: anywhere` degrades gracefully.

### Scenario C — Conditional, formatted Last-modified column (Requirement 5)

**Requirements:** Hide the column when no row has a value; format available values as `MM/DD/YY HH:MM`.

**Preferred Approach:** Add `hasAnyLastModified` to the component body; guard the `<th>` (line 386) and the `<td>` (lines 427-430) on it; rewrite `formatLastModified` (lines 193-195) to UTC `MM/DD/YY HH:MM` with a null/NaN → "—" fallback. See "Complete Example — formatLastModified" above.

**Implementation Details:**

- The flag is recomputed every render from `state.rows`, so a refresh that returns all-null rows hides the column and one with any value shows it — per-load semantics (Open Question 2).
- Mixed sets (some rows null, some not): column shows; null rows render "—" (Open Question 4 — recommended to keep "—").
- UTC formatting keeps the unit test deterministic (Open Question 3 — recommended UTC).
- Tests to update in DeleteData.test.tsx:
  - "surfaces chunk_count and last_modified per row" (~95-113): change the BETA assertion from the raw ISO string to `05/01/26 12:00`; keep the ALPHA "—" assertion (BETA is non-null so the column renders and ALPHA's null cell shows "—"); optionally rename to "surfaces chunk_count and formatted last_modified per row".
  - Add a NEW test with an all-null fixture asserting `expect(screen.queryByRole("columnheader", { name: /last modified/i })).not.toBeInTheDocument();` (no all-null fixture exists today).

#### Considered Alternatives

- A backend capability flag ("does this store support last_modified"): rejected — no such flag exists on the wire and the per-load `some(...)` check is sufficient and backend-agnostic.
- `Intl.DateTimeFormat` / `toLocaleString`: rejected for the value formatting — renders in the runner's local timezone, making the BETA assertion machine-dependent. Manual UTC-getter assembly is deterministic.
- Mutating `.rowMeta` for date styling: rejected — `.rowMeta` is shared with the Chunks cell; add a new class only if date-specific styling is ever needed (not needed now).

## Open Questions (recommend a default; confirm before/at planning)

1. Should the page `<h2>` heading also change to "Data set" (recommended: yes, for consistency), or only the sub-nav tab? If only the tab, DeleteData.test.tsx line 70 needs no change.
2. Hidden Last-modified column trigger = "no row in the currently loaded data has a value" (recommended: yes, `state.rows.some(...)`, recomputed each refresh).
3. `MM/DD/YY HH:MM` rendered in UTC (recommended: yes — matches the stored `Z` value, deterministic tests) or browser-local time?
4. In a mixed set (column shown), keep the "—" placeholder for individual null rows (recommended: yes) or render blank?
5. Should the multi-source target stay emphasized like the filename (recommended: yes — both share `.dialogTarget`, the unified approach keeps them visually identical)?

## Relationship to BUG-0093

The originally-drafted BUG-0093 ("remove the always-blank Last modified column") is **superseded** by Requirement 5: the column is now conditional + formatted rather than removed outright. The drafted `bugs.md` row text should be reworded from "remove the column" to "make the Last modified column conditional (hidden when no row has a value) and format available values as MM/DD/YY HH:MM" before it is appended to `v2/docs/bugs.md` (an implement-mode action — Planner/Researcher mode cannot edit `bugs.md`).
