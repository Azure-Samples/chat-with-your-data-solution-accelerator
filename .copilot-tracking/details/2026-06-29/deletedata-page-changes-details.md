<!-- markdownlint-disable-file -->
# Implementation Details: Delete Data (→ "Data set") page changes

## Context Reference

Sources:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (primary research; all line numbers verified 2026-06-29)
- .copilot-tracking/research/subagents/2026-06-29/deletedata-page-changes-research.md (subagent raw findings)

Decisions adopted (evidence-backed defaults from the research Open Questions):
- D1: The page `<h2>` heading is renamed to "Data set" alongside the sub-nav tab (internal consistency).
- D2: The Last-modified column is hidden when no currently-loaded row has a non-null value (per-load `state.rows.some(...)`).
- D3: `MM/DD/YY HH:MM` is rendered in UTC via zero-padded manual assembly (locale/TZ-independent, deterministic tests).
- D4: In a mixed set (column shown), individual null rows keep the "—" placeholder.

Scope guardrails:
- Frontend only. No backend, infra, or wire-shape change.
- KEEP unchanged: `Section.AdminDelete` (sections.tsx:16), `/admin/delete` route (sections.tsx:25), every `delete-*` / `admin-subnav-delete` / `row-*` / `source-table` test id, and the `SourceListing.last_modified` wire field (models/admin.tsx:145).
- Do NOT touch the dead `formatActor` / commented "Updated by" block in Configuration.tsx (out of scope).

## Implementation Phase 1: Tab + page heading rename (Requirement 1)

<!-- parallelizable: false -->

### Step 1.1: Rename the admin sub-nav tab label

Change the visible sub-nav label only; leave the section key and test id untouched.

Files:
- v2/src/frontend/src/pages/admin/AdminLayout.tsx - line 37 `label: "Delete data",` → `label: "Data set",` (inside the `Section.AdminDelete` entry of `ADMIN_NAV_ITEMS`, lines 35-39). Leave line 36 `section: Section.AdminDelete` and line 38 `testId: "admin-subnav-delete"` unchanged.

Discrepancy references:
- Implements DR-free requirement 1; no deviation.

Success criteria:
- The admin sub-nav renders a "Data set" link that still routes to `/admin/delete`.
- v2/tests/frontend/pages/admin/AdminLayout.test.tsx still passes unchanged (it asserts by test id `admin-subnav-delete`, not by label text — research §1(c)).

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Research Executed → AdminLayout.tsx; Scenario A) - tab label location + keep-list.

Dependencies:
- None.

### Step 1.2: Rename the page heading + section aria-label

Files:
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx - line 284 `<h2 className={styles.pageTitle}>Delete data</h2>` → `<h2 className={styles.pageTitle}>Data set</h2>`.
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx - line 279 `aria-label="delete data"` → `aria-label="data set"` (accessible name kept consistent with the heading). Leave line 280 `data-testid="delete-data"` unchanged.

Discrepancy references:
- Implements decision D1.

Success criteria:
- The page heading reads "Data set".
- `data-testid="delete-data"` and all other test ids unchanged.

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Research Executed → DeleteData.tsx lines 279, 284).

Dependencies:
- None (different file from Step 1.1; could be done in either order).

### Step 1.3: Update the heading test assertion

Files:
- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx - line 70 `screen.getByRole("heading", { name: /delete data/i })` → `{ name: /data set/i }` (sub-test "renders the page heading", lines 67-77).

Discrepancy references:
- Required by D1 (heading rename).

Success criteria:
- The "renders the page heading" test passes against the new heading text.

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Code Search Results → line 70).

Dependencies:
- Step 1.2.

### Step 1.4: Validate phase changes

Validation commands (run from v2/src/frontend):
- `npm test -- DeleteData AdminLayout` - the DeleteData + AdminLayout Vitest suites must pass.

## Implementation Phase 2: Unified confirm-delete dialog + wrap fix (Requirements 2, 3, 4)

<!-- parallelizable: false -->

### Step 2.1: Refactor the dialog body to one shared target string on its own line

Restructure the single confirm dialog (DeleteData.tsx lines 468-518) so both single- and multi-source prompts flow through one code path that computes a single `target` string and renders it on its own line. This removes the duplicated surrounding sentence (the only duplication today — research §4) and eliminates the mid-sentence break.

Replace the render expression that currently is:

```tsx
{state.pendingDeleteSources !== null ? (
  <div role="dialog" ... className={styles.dialogBackdrop}>
    <div className={styles.dialog}>
      <h3 className={styles.dialogTitle}>Confirm delete</h3>
      <p className={styles.dialogBody}>
        {state.pendingDeleteSources.length === 1 ? (
          <> ... {state.pendingDeleteSources[0]} ... </>
        ) : (
          <> ... {length} selected sources ... </>
        )}
      </p>
      <div className={styles.dialogActions}> ... </div>
    </div>
  </div>
) : null}
```

with an IIFE that computes the target once (mirrors the existing loaded-form IIFE pattern in this file and in Configuration.tsx):

```tsx
{state.pendingDeleteSources !== null
  ? (() => {
      const sources = state.pendingDeleteSources;
      const [firstSource] = sources;
      const target =
        sources.length === 1 && firstSource !== undefined
          ? firstSource
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
            <p className={styles.dialogBody}>The action cannot be undone.</p>
            <div className={styles.dialogActions}>
              {/* Cancel + Delete buttons UNCHANGED (data-testid delete-cancel / delete-confirm) */}
            </div>
          </div>
        </div>
      );
    })()
  : null}
```

Notes:
- `firstSource` destructure satisfies `noUncheckedIndexedAccess` without an empty-string fallback.
- The target strings stay exactly `<filename>` and `<N> selected sources`, so the existing `toHaveTextContent` dialog assertions (research §Code Search) keep passing.
- The Cancel / Delete buttons and their `onClick` handlers / test ids are copied across verbatim — only the body paragraphs change.

Files:
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx - replace lines 468-518 (the confirm-dialog render expression) as above. Preserve the original trailing sentence wording "The action cannot be undone." (no copy edit).

Discrepancy references:
- Implements requirements 2, 3, 4 (single path, target on its own line).

Success criteria:
- Single-source dialog shows the filename on its own line.
- Multi-source dialog shows "N selected sources" on its own line.
- One `target` computation drives both; the surrounding sentence is no longer duplicated.

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Key Discoveries → "Complete Example — unified dialog body"; Scenario B).

Dependencies:
- None within this file beyond Phase 1 (same file; sequential).

### Step 2.2: Fix the mid-word-break CSS

Files:
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css - `.dialogTarget` rule (lines 186-190). Replace `word-break: break-all;` (line 189) and add `margin: 0;` so the now-block paragraph sits cleanly in the dialog's flex-column gap:

```css
.dialogTarget {
  margin: 0;
  font-weight: var(--fontWeightSemibold);
  color: var(--colorNeutralForeground1);
  overflow-wrap: anywhere;
}
```

Do NOT change `.rowSource` (lines 131-135) — its `word-break: break-all` is correct for long filenames in the narrow table cell.

Discrepancy references:
- Root-cause fix for requirements 2 + 3 (research "CSS wrapping root cause").

Success criteria:
- "selected sources" never splits mid-word; a genuinely long filename wraps only at sane points (`overflow-wrap: anywhere`).

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Key Discoveries → "The wrapping bug is a single CSS rule").

Dependencies:
- Step 2.1 (paragraph becomes a direct flex child needing `margin: 0`).

### Step 2.3: Confirm/extend dialog tests

The existing dialog-text assertions survive unchanged (they use `toHaveTextContent` with the preserved target strings). Optionally add one assertion that the target renders in its own `.dialogTarget` paragraph for regression coverage.

Files:
- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx - no required change; OPTIONAL: in the bulk test (~lines 333-352) and the single-source test (~lines 218-231), assert the dialog still contains "2 selected sources" / "alpha.pdf" (already present) and, if adding coverage, that `screen.getByTestId("delete-confirm-dialog")` contains a paragraph with the target text.

Discrepancy references:
- Confirms requirement 4 did not regress the existing behavior.

Success criteria:
- All existing DeleteData dialog tests pass without modification.

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Code Search Results → dialog-text assertions at 230, 348-350, 400-402).

Dependencies:
- Steps 2.1, 2.2.

### Step 2.4: Validate phase changes

Validation commands (run from v2/src/frontend):
- `npm test -- DeleteData` - the DeleteData Vitest suite (dialog tests) must pass.

## Implementation Phase 3: Conditional + formatted Last-modified column (Requirement 5)

<!-- parallelizable: false -->

### Step 3.1: Rewrite formatLastModified to MM/DD/YY HH:MM (UTC)

Files:
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx - replace the helper body (lines 193-195):

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

Discrepancy references:
- Implements requirement 5 (format) + decisions D3 (UTC) and D4 ("—" for null).

Success criteria:
- `2026-05-01T12:00:00Z` → `05/01/26 12:00`; `null` and unparseable → "—".

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Key Discoveries → "Complete Example — formatLastModified"; Scenario C).

Dependencies:
- None within file beyond prior phases (same file; sequential).

### Step 3.2: Hide the column when no loaded row has a value

Files:
- v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx - add, alongside the existing derived values in the component body (near `selectedSet` / `selectedFailedSources` / `isAllSelected`, lines ~199-209):

```ts
const hasAnyLastModified = state.rows.some(
  (row) => row.listing.last_modified !== null,
);
```

- Guard the header cell (currently line 386):

```tsx
{hasAnyLastModified ? <th scope="col">Last modified</th> : null}
```

- Guard the body cell (currently lines 428-430):

```tsx
{hasAnyLastModified ? (
  <td className={styles.rowMeta}>
    {formatLastModified(row.listing.last_modified)}
  </td>
) : null}
```

Both guards use the SAME `hasAnyLastModified` flag so the header and every body row stay column-count consistent.

Discrepancy references:
- Implements requirement 5 (hide-when-unavailable) + decision D2.

Success criteria:
- All-null data → no "Last modified" header and no corresponding cells.
- Any non-null row → header + cells present; null rows in a mixed set show "—".

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Scenario C; Research Executed → header 386, body 427-430, derived values 197-209).

Dependencies:
- Step 3.1 (cell calls `formatLastModified`).

### Step 3.3: Update + add the column tests

Files:
- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx - sub-test "surfaces chunk_count and last_modified per row" (lines 95-113):
  - Change the BETA assertion (~line 111) from `toHaveTextContent("2026-05-01T12:00:00Z")` to `toHaveTextContent("05/01/26 12:00")`.
  - Keep the ALPHA "—" assertion (~line 106): BETA is non-null so the column renders and ALPHA's null cell shows "—".
  - Optionally rename the test to "surfaces chunk_count and formatted last_modified per row".
- v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx - ADD a new test with an all-null fixture asserting the column is hidden:

```tsx
it("hides the Last modified column when no row has a value", async () => {
  const allNull = {
    documents: [
      { source: "alpha.pdf", chunk_count: 3, last_modified: null },
      { source: "beta.pdf", chunk_count: 5, last_modified: null },
    ],
    total: 2,
  };
  listMock.mockResolvedValueOnce(allNull);
  render(<DeleteData />);
  await waitFor(() => {
    expect(screen.getByTestId("source-table")).toBeInTheDocument();
  });
  expect(
    screen.queryByRole("columnheader", { name: /last modified/i }),
  ).not.toBeInTheDocument();
});
```

(Use the suite's existing `listMock` mock shape — confirm the exact fixture wrapper `{ documents, total }` matches the `listDocuments` return used by the other tests, e.g. `LIST_FIXTURE` lines 43-46.)

Discrepancy references:
- Covers requirement 5 both branches (formatted value + hidden column).

Success criteria:
- The formatted-value assertion passes (`05/01/26 12:00`).
- The all-null hidden-column test passes.

Context references:
- .copilot-tracking/research/2026-06-29/deletedata-page-changes-research.md (Scenario C → tests; Code Search Results → fixtures lines 31-46, assertions 95-113).

Dependencies:
- Steps 3.1, 3.2.

### Step 3.4: Validate phase changes

Validation commands (run from v2/src/frontend):
- `npm test -- DeleteData` - the DeleteData Vitest suite (column tests) must pass.

## Implementation Phase 4: Final validation

<!-- parallelizable: false -->

### Step 4.1: Run full frontend validation

Execute from v2/src/frontend:
- `npm run lint`
- `npm run typecheck`
- `npm test -- DeleteData AdminLayout`

### Step 4.2: Fix minor validation issues

Iterate on lint/typecheck/test failures that are straightforward and isolated (e.g. an unused import after the dialog refactor, a `padStart` radix lint nit, a stray fixture type mismatch).

### Step 4.3: Report blocking issues

If a failure needs more than a minor fix (e.g. a strict-TS error that implies a model change, or a Vitest timezone surprise despite UTC getters), stop and report to the user with the affected file + next steps rather than reworking inline.

## Dependencies

- Node + the frontend toolchain installed (`npm install` under v2/src/frontend).
- Vitest, Testing Library, ESLint, TypeScript (already in `package.json`).

## Success Criteria

- Sub-nav tab and page heading read "Data set"; route/enum/test ids unchanged.
- Both confirm-delete prompts render the target (filename or "N selected sources") on its own line with no mid-word break, from one shared code path.
- The Last-modified column is hidden when no loaded row has a value, and formats available values as `MM/DD/YY HH:MM` (UTC) otherwise.
- `npm run lint`, `npm run typecheck`, and the DeleteData + AdminLayout Vitest suites pass.
