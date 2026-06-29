<!-- markdownlint-disable-file -->
# BUG-0093 — Remove empty "Last modified" column from admin Delete Data table

Research for a **frontend-only** bug fix in CWYD v2. **Read-only** investigation; no source files were edited.

- **Bug:** BUG-0093 (frontend, low). In the admin **Delete Data** tab, the indexed-files table has a **Last modified** column that is ALWAYS empty for the deployed Azure AI Search index store.
- **Root cause (confirmed):** the Azure AI Search `list_sources` facet path emits `last_modified=None` for every source (BUG-0075 populated `last_modified` only for the pgvector path and explicitly left Azure Search null).
- **Agreed resolution:** remove the "Last modified" column from the Delete Data table. Keep the wire/model `last_modified` field intact (pgvector still populates it).

---

## Scope

- **Frontend-only change.** No backend change is required.
- **Keep the wire model field.** `SourceListing.last_modified` stays in both the frontend type (`v2/src/frontend/src/models/admin.tsx`) and the backend model (`v2/src/backend/core/providers/search/base.py`). The pgvector path keeps populating it.
- The only production change is to stop rendering the column (header + body cell) and delete the now-dead `formatLastModified` helper that exists solely for that column.

---

## Findings (with exact paths + line numbers)

### 1. Delete Data page component — `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx`

#### 1a. Table head — the "Last modified" header cell

The full `<thead>` column set (`v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` Lines 383-390):

```tsx
                </th>
                <th scope="col">Source</th>
                <th scope="col">Chunks</th>
                <th scope="col">Last modified</th>
                <th scope="col" className={styles.rowActions}>
                  Actions
                </th>
              </tr>
```

- The **"Last modified" header cell** is exactly one line: `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` (Line 386) — `<th scope="col">Last modified</th>`.
- Columns are positional (no per-column `data-testid`). Header order is: Select (Line 372 region), Source (Line 384), Chunks (Line 385), **Last modified (Line 386)**, Actions (Lines 387-389).

#### 1b. Table body — the "Last modified" body cell

The per-row cells (`v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` Lines 424-431):

```tsx
                  </td>
                  <td className={styles.rowMeta}>
                    {row.listing.chunk_count.toString()}
                  </td>
                  <td className={styles.rowMeta}>
                    {formatLastModified(row.listing.last_modified)}
                  </td>
                  <td className={styles.rowActions}>
```

- The **"Last modified" body cell** is `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` (Lines 428-430):
  ```tsx
                  <td className={styles.rowMeta}>
                    {formatLastModified(row.listing.last_modified)}
                  </td>
  ```
- It reuses the shared `styles.rowMeta` class, which the immediately-preceding **Chunks** cell (Lines 425-427) also uses. So `.rowMeta` is **not** dead after removal.

#### 1c. The `formatLastModified` helper (becomes dead code)

`v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` (Lines 193-195):

```tsx
function formatLastModified(value: string | null): string {
  return value ?? "—";
}
```

- This helper is referenced in exactly ONE place — the body cell at Line 429 (confirmed by grep across the whole `v2/src/frontend/src` tree: the only `formatLastModified` hits are its definition at Line 193 and its single call at Line 429). Removing the column makes it **dead code** that must be deleted in the same change to keep the tree clean.

#### 1d. `data-testid` attributes tied to the column

- **None.** The Last modified header and body cells carry NO `data-testid`. The only row-level testid is `data-testid={`source-row-${row.listing.source}`}` (Line ~404), applied to the whole `<tr>`, not to the Last modified cell. Tests assert the rendered value via `toHaveTextContent(...)` on the row, not via a column testid (see §4).

#### 1e. Stale docstring reference (optional cleanup)

The module docstring describes the "Loaded" state and mentions the timestamp — `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` (Lines 20-22):

```text
 * 4. **Loaded** -- one row per source with the chunk count, last
 *    modified timestamp (when available), and a per-row Delete
 *    button that opens a confirmation dialog.
```

- This becomes inaccurate once the column is removed. Recommend trimming "last modified timestamp (when available), and" → "and" so the docstring reads "one row per source with the chunk count and a per-row Delete button…". (Descriptive, not process narrative — safe to edit; keeps Hard Rule #16 clean.)

### 2. Domain/wire model — `v2/src/frontend/src/models/admin.tsx`

- Type name: **`SourceListing`** (`v2/src/frontend/src/models/admin.tsx` Lines 146-150):
  ```tsx
  export interface SourceListing {
    source: string;
    chunk_count: number;
    last_modified: string | null;
  }
  ```
- Field: `last_modified: string | null` (`v2/src/frontend/src/models/admin.tsx` Line 149). The doc comment above it (Lines 142-145) already states the pgvector schema has no timestamp column for the always-`null` backend.
- **Other consumers of `last_modified` in the SPA: NONE.** A grep for `last_modified` / `formatLastModified` / `Last modified` across `v2/src/frontend/src/**` returns hits in only two files:
  - `v2/src/frontend/src/models/admin.tsx` (Lines 142, 149) — the type + its doc comment.
  - `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` (Lines 193, 386, 429) — the helper, header, body cell.
  No chat page, IngestData page, or any other admin page reads `last_modified`. **Keep the type field** (the wire shape mirrors the backend, which still returns it for pgvector).

### 3. CSS module — `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css`

- **No Last-modified-specific class exists.** The body cell uses `.rowMeta` (`v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css` Lines 152-155), which is **shared** with the Chunks cell. There is **no dead CSS class** to remove. Header cells use the generic `.table th` rule (Lines 121-125). No CSS edit is required.

### 4. Existing tests — `v2/tests/frontend/pages/admin/DeleteData/`

Two test files exist:

- `v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx` — the component suite (references the column).
- `v2/tests/frontend/pages/admin/DeleteData/DeleteActionType.test.tsx` — reducer/action-type unit tests. Grep for `modified` / `last_modified` / `—` returns **no matches**; this file needs **no change**.

References in `DeleteData.test.tsx` that touch the Last modified column:

- **Fixtures** (`v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx` Lines 30-40) set `last_modified` on both `SourceListing` fixtures:
  ```tsx
  const ALPHA: SourceListing = {
    source: "alpha.pdf",
    chunk_count: 3,
    last_modified: null,
  };
  const BETA: SourceListing = {
    source: "beta.pdf",
    chunk_count: 7,
    last_modified: "2026-05-01T12:00:00Z",
  };
  ```
  These fields are **still required by the `SourceListing` type** (the wire field stays), so the fixtures keep `last_modified`. No fixture change is strictly required, but the assertions on the rendered values must go (below).

- **The per-row test** `it("surfaces chunk_count and last_modified per row", ...)` (`v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx` Lines 95-112):
  ```tsx
  it("surfaces chunk_count and last_modified per row", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    const alphaRow = screen.getByTestId("source-row-alpha.pdf");
    expect(alphaRow).toHaveTextContent("alpha.pdf");
    expect(alphaRow).toHaveTextContent("3");
    // null last_modified renders as the em-dash placeholder.
    expect(alphaRow).toHaveTextContent("—");

    const betaRow = screen.getByTestId("source-row-beta.pdf");
    expect(betaRow).toHaveTextContent("beta.pdf");
    expect(betaRow).toHaveTextContent("7");
    expect(betaRow).toHaveTextContent("2026-05-01T12:00:00Z");
  });
  ```
  Lines that must be **removed/updated** once the column is gone:
  - Line 105 comment + Line 106: `expect(alphaRow).toHaveTextContent("—");` — the em-dash placeholder assertion (placeholder no longer renders).
  - Line 112: `expect(betaRow).toHaveTextContent("2026-05-01T12:00:00Z");` — the timestamp assertion (value no longer renders).
  - Rename the test to `"surfaces chunk_count per row"` and keep the remaining `source` + `chunk_count` assertions (Lines 102-104, 110-111).

> Note: a bare `expect(...).toHaveTextContent("—")` is a substring match against the **whole row**; with the column removed there is no em-dash anywhere in the row, so leaving Line 106 in place would fail. It must be deleted, not just left "harmless."

### 5. Backend cross-check (confirms FE-only)

- **Route:** `GET /api/admin/documents` → `list_documents_endpoint` in `v2/src/backend/routers/admin.py` (Lines 412-448). It is a pure pass-through: `listings = await search.list_sources()` then `return ListDocumentsResponse(documents=list(listings), total=len(listings))` (`v2/src/backend/routers/admin.py` Lines 444-447). The router never touches `last_modified`.
- **Model:** `SourceListing.last_modified: str | None = None` in `v2/src/backend/core/providers/search/base.py` (Lines 51-62).
- **Azure Search path returns null:** `v2/src/backend/core/providers/search/azure_search.py` (Lines 291-293):
  ```python
        return [
            SourceListing(source=source, chunk_count=count, last_modified=None)
            for source, count in sorted(counts.items())
        ]
  ```
- **pgvector path populates it:** `v2/src/backend/core/providers/search/pgvector.py` (Lines 197, 221-223) — `MAX(last_modified)` per source, ISO-formatted when non-null.

**Conclusion:** the wire field is correct as-is. The empty column is purely a presentation artifact of the Azure Search deployment. **No backend change is needed** — remove only the frontend column.

### 6. No other consumers in the SPA

Confirmed by grep across `v2/src/frontend/src/**`: only `models/admin.tsx` (the type) and `DeleteData/DeleteData.tsx` (the column) reference the field. Chat pages and all other admin pages do not render `last_modified`. Removing the Delete Data column has zero blast radius elsewhere.

---

## Files to change (exact paths + line ranges)

| # | File | Lines | Change |
|---|------|-------|--------|
| (a) | `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` | 386 | Remove the header cell `<th scope="col">Last modified</th>`. |
| (b) | `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` | 428-430 | Remove the body cell `<td className={styles.rowMeta}>{formatLastModified(row.listing.last_modified)}</td>`. |
| (c) | `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` | 193-195 | Delete the now-dead `formatLastModified` helper (only caller was line 429). |
| (d) | `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx` | 20-22 | (Optional, recommended) Trim the docstring "Loaded" bullet so it no longer mentions "last modified timestamp (when available)". |
| (e) | `v2/src/frontend/src/pages/admin/DeleteData/DeleteData.module.css` | — | **No change.** `.rowMeta` is shared with the Chunks cell; no dead class. |
| (f) | `v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx` | 95-112 | Update the per-row test (rename + drop the em-dash and timestamp assertions). Add a regression assertion (below). |

> No change to `v2/src/frontend/src/models/admin.tsx` (`SourceListing.last_modified` stays). No change to `v2/tests/frontend/pages/admin/DeleteData/DeleteActionType.test.tsx`. No backend change.

---

## Tests to update / add

**File:** `v2/tests/frontend/pages/admin/DeleteData/DeleteData.test.tsx`

1. **Update** the test at Lines 95-112 (`"surfaces chunk_count and last_modified per row"`):
   - Rename to `"surfaces chunk_count per row"`.
   - Delete Line 105 comment + Line 106 `expect(alphaRow).toHaveTextContent("—");`.
   - Delete Line 112 `expect(betaRow).toHaveTextContent("2026-05-01T12:00:00Z");`.
   - Keep the `source` + `chunk_count` assertions (Lines 102-104, 110-111).
   - Fixtures at Lines 30-40 keep `last_modified` (required by the `SourceListing` type).

2. **Add** a regression test asserting the column is gone, e.g.:
   - Render with `LIST_FIXTURE`, wait for `source-table`, then assert the table has no "Last modified" header. Recommended assertion:
     ```tsx
     expect(
       screen.queryByRole("columnheader", { name: /last modified/i }),
     ).not.toBeInTheDocument();
     ```
   - Optionally also assert the BETA timestamp string is absent from the row:
     ```tsx
     expect(
       screen.getByTestId("source-row-beta.pdf"),
     ).not.toHaveTextContent("2026-05-01T12:00:00Z");
     ```
   - This locks in the fix and prevents column re-introduction.

---

## Out of scope / keep

- **Keep** the wire model field `SourceListing.last_modified` in `v2/src/frontend/src/models/admin.tsx` (Line 149) and its doc comment (Lines 142-145). The frontend type must continue to mirror the backend wire shape.
- **No backend change.** `v2/src/backend/routers/admin.py`, `v2/src/backend/core/providers/search/base.py`, `azure_search.py`, and `pgvector.py` are unchanged. The Azure Search path keeps returning `last_modified=None`; the pgvector path keeps populating it.
- **pgvector path unaffected** — it still computes `MAX(last_modified)`; the value simply stops being displayed in this one admin table.
- **No CSS edit** — `.rowMeta` stays (shared with the Chunks cell).
- `DeleteActionType.test.tsx` unchanged.

---

## Status

**Complete.** All requested items located with exact paths and line numbers. No source files edited.

### Recommended next research (none blocking)

- [ ] (Optional) Confirm the frontend OpenAPI client / generated types do not separately re-declare `SourceListing` outside `models/admin.tsx` if the project regenerates a client (grep found only the hand-authored `models/admin.tsx`; the page imports `SourceListing` from `@/models/admin`). Not required for this FE-only change.

### Clarifying questions

- None. The resolution (remove the column, keep the wire field, no backend change) is fully supported by the code.
