<!-- markdownlint-disable-file -->
# Task Research: New bug additions + numerically-ordered open-bug list (v1 release)

Operator-directed (2026-06-29): promote two deferred MVP gaps to tracked bugs and add one new
defect, then re-list all open bugs in numerical order for one-by-one fixing.

## Task Implementation Requests

- Add a bug: **public file-serve route** missing (v1 `GET /api/files/<filename>`) — needed for v1.
- Add a bug: **bulk history delete** missing (v1 `DELETE /history/delete_all`) — needed for v1.
- Add a bug: **Delete Data tab "Last modified" column is always empty** — resolution is to remove
  the column when no last-modified date is available.
- All other project-status gaps (Explore Data page, page-number restitching) are **not** needed for
  this v1 release — do not file them.
- Re-list every open bug in numerical order.

## Scope and Success Criteria

- Scope: defect-registry additions + ordered listing only. No code edits in this mode.
- Assumptions: next free id is **BUG-0093** (current max is BUG-0092). Deployed index store is
  **Azure AI Search** (`cwyd-index`), so `last_modified` is null for every source.
- Success Criteria:
  - Three new bug rows drafted in exact `v2/docs/bugs.md` row format, ready to paste.
  - Full numerically-ordered open-bug list (12 open after additions).

## Proposed new rows (paste into v2/docs/bugs.md, after BUG-0092)

```text
| BUG-0093 | 2026-06-29 |  | frontend | low | open | The admin **Delete Data** tab's indexed-files table has a **Last modified** column that is always blank. The deployed index store is **Azure AI Search** (`cwyd-index`), whose facet-based `list_sources` path has no per-source timestamp field, so `GET /api/admin/documents` returns `last_modified: null` for every source. BUG-0075 added a `last_modified` column for the **pgvector** path but explicitly left Azure Search as `None` (out of scope there), so on this Azure Search deployment the column can never populate. **Resolution (operator-directed 2026-06-29):** since the deployment cannot supply a last-modified date, **remove the Last modified column** from the Delete Data table ([DeleteData.tsx](../src/frontend/src/pages/admin/DeleteData/DeleteData.tsx)) rather than render a permanently empty column. Fix direction: drop the column header + cell from the DeleteData table (and any now-dead `last_modified` formatting helper), keeping the wire field intact for the pgvector path. **Status: open.** |
| BUG-0094 | 2026-06-29 |  | backend | medium | open | v2 has **no user-facing file-serve route** equivalent to v1's `GET /api/files/<filename>` (Blob SAS-backed); it is logged as a deferred gap in [project_status.md](project_status.md) §M. For the v1 release a cited source document must be openable from chat citations, but with no serve route citations cannot link to the underlying blob. **Promoted to a tracked bug (operator-directed 2026-06-29)** — needed for v1. Fix direction: add a backend route (e.g. `GET /api/files/{filename}`) that returns the indexed document's blob (SAS redirect or streamed) under the same `_validate_filename` guard used by the admin delete path, and wire citation rendering to it. **Status: open.** |
| BUG-0095 | 2026-06-29 |  | backend | low | open | v2 chat history exposes per-conversation `DELETE /api/history/conversations/{id}` only; v1's bulk `DELETE /history/delete_all` (clear **all** of a user's conversations) was not ported — logged as a deferred gap in [project_status.md](project_status.md) §M. **Promoted to a tracked bug (operator-directed 2026-06-29)** — needed for v1. Fix direction: add a bulk-delete route under `/api/history/*` that deletes every conversation for the caller's `user_id` (idempotent, 204) across **both** the Cosmos and Postgres history providers, and add a guarded "Delete all" control to the History panel ([HistoryPanel.tsx](../src/frontend/src/pages/chat/components/HistoryPanel.tsx)). **Status: open.** |
```

Row-format notes: columns are `| id | found | fixed | area | severity | status | detail |`; open
bugs leave the `fixed` column blank (two spaces), matching BUG-0077/0081/0088/0090/0092. Area ∈
{backend, frontend, infra, functions, docs, ci}; Severity ∈ {blocker, high, medium, low}; Status ∈
{open, in-progress, fixed, wontfix, duplicate}.

## Numerically-ordered open bugs (12 after additions)

| ID | Area | Sev | One-liner |
|---|---|---|---|
| BUG-0054 | infra | medium | Stray Event Grid → `doc-processing` poison envelopes; translator fix designed (ADR 0028), `blob_event` cloud deploy deferred. |
| BUG-0055 | infra | medium | App Insights receives zero telemetry from function host + backend — no production observability. |
| BUG-0058 | functions | medium | `azd deploy function` skips the `prepackage` hook → ships a stale `build-functions/` artifact. |
| BUG-0077 | functions | low | Enhancement: auto-deindex on blob delete (`BlobDeleted`); Phase 1 committed, deploy deferred. |
| BUG-0081 | infra | high | Frontend never deploys via `azd deploy frontend` (appservice host + docker mismatch); manual mitigation, durable fix pending. |
| BUG-0082 | backend | medium | Backend crash-loops when Postgres unreachable (no connect timeout). |
| BUG-0088 | functions | high | `.docx` ingest fails — 0 chunks, both messages poison; root cause undetermined. |
| BUG-0090 | infra | high | Production admin panel unreachable (401) — no Easy Auth identity source feeds the backend. |
| BUG-0092 | frontend | high | Chat History panel fails on split-host deploy — build-time `VITE_BACKEND_URL` vs runtime `getBackendUrl()` seam. |
| BUG-0093 | frontend | low | Delete Data "Last modified" column always empty — remove the column. (NEW) |
| BUG-0094 | backend | medium | Public file-serve route missing (v1 `GET /api/files/<filename>`). (NEW) |
| BUG-0095 | backend | low | Bulk history delete missing (v1 `DELETE /history/delete_all`). (NEW) |

## Potential Next Research

- Confirm exact `DeleteData.tsx` table column markup + any `last_modified` formatter to remove (BUG-0093).
  - Reference: v2/src/frontend/src/pages/admin/DeleteData/DeleteData.tsx
- Confirm `v2/src/backend/routers/history.py` route set has no bulk delete + both provider impls (BUG-0095).
  - Reference: v2/src/backend/routers/history.py
- Confirm citation rendering source-URI handling to wire the file-serve route (BUG-0094).
  - Reference: v2/src/backend/routers/admin.py (`_validate_filename`, `GET /api/admin/documents`)

## Notes / disposition of the other §M gaps (NOT filed, per operator)

- Explore Data admin page — deferred, not needed for v1.
- Page-number restitching pipeline (`bp_combine_pages_and_chunknos`) — deferred, not needed for v1.
