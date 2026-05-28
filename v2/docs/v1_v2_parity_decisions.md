# v1 → v2 Parity Decisions

**Status:** RECOMMENDED — awaiting user sign-off (2026-05-28).
**Type:** Gating planning artifact for Phase 7 (single doc, snapshot — never updated mid-stream once signed).
**Source audit:** 3-agent sweep cached in session memory; 150 v1 items inventoried, 114 require user attention (see audit reconciliation in session plan).
**Scope:** classifies every gap row from the audit into one of five buckets so the dev_plan §0.1 debt queue and §4.7.x Phase 7 task list can be appended deterministically in the next implementation passes.

## Classification buckets

| Bucket | Meaning | Downstream action |
|---|---|---|
| ✅ CONFIRM-DESIGN | v2 correctly drops; no action needed | nothing — closed by sign-off |
| 🆕 NEW-DEBT-ROW | adds to dev_plan §0.1 debt queue | clears in P-PARITY-IMPL pass before Phase 7 |
| 🚀 PHASE-7-WORK | adds to dev_plan §4.7.x as a Phase 7 task | sequenced during Phase 7 opening turn |
| ⏭ DEFER-PHASE-8 | explicit defer past v2 MVP | nothing in v2 |
| 🔍 VERIFY-FIRST | needs spot-check before classification | one turn of read-only research, then reclassify |

## VERIFY-FIRST resolutions (run 2026-05-28)

| # | Audit claim | Verified finding | Final classification |
|---|---|---|---|
| T1-5 | "VERIFY whether v2 reads `AZURE_CONTENT_SAFETY_ENDPOINT` — likely XS-S toggle row" | `ContentSafetyGuard` ships in `v2/src/backend/core/tools/content_safety.py` and `chat.py` accepts it as `\| None`, **but**: (1) zero `AppSettings.content_safety` sub-model; (2) zero `dependencies.py` / `app.py` wiring that constructs `ContentSafetyClient` from settings; (3) zero `AZURE_CONTENT_SAFETY_*` env-var references anywhere in backend; (4) constructor docstring promises wiring "in `backend/app.py` lifespan" but that wiring is absent. **The wiring path itself is missing**, not just the toggle. | 🆕 NEW-DEBT-ROW `CONTENT-SAFETY-WIRING-DEBT` (M — settings sub-model + ContentSafetyClient lifespan wiring + dependencies.py injection + admin toggle in same row) |

## Tier 1 — Operator/admin loses runtime control (18 items)

| # | v1 item | Proposed classification | Notes |
|---|---|---|---|
| T1-1 | `document_processors[*].chunking.{strategy,size,overlap}` | 🆕 **NEW-DEBT-ROW** `CHUNK-CONFIG-DEBT` | Reverses dev_plan D2 → Hard Rule #10 user gate at clear-time. M-L effort. |
| T1-2 | `prompts.{answering_system_prompt,answering_user_prompt,condense_question_prompt}` | 🆕 **NEW-DEBT-ROW** `PROMPT-CUSTOMIZATION-DEBT` | Touches every orchestrator. M-L. |
| T1-3 | `prompts.post_answering_prompt` + `messages.post_answering_filter` | 🆕 **NEW-DEBT-ROW** `POSTPROMPT-CONFIG-DEBT` | S. |
| T1-4 | `prompts.enable_post_answering_prompt` toggle | 🆕 **NEW-DEBT-ROW** `POSTPROMPT-TOGGLE-DEBT` | XS. |
| T1-5 | `prompts.enable_content_safety` toggle | 🆕 **NEW-DEBT-ROW** `CONTENT-SAFETY-WIRING-DEBT` (M — see VERIFY-FIRST row above) | Scope broader than original row — entire wiring path missing. |
| T1-6 | `prompts.ai_assistant_type` + `/api/assistanttype` + `<AssistantTypeSection>` | 🚀 **PHASE-7-WORK** | Branding/persona runtime selection — feature, not bug. |
| T1-7 | `orchestrator.strategy` runtime selector | ✅ **CONFIRM-DESIGN** | Already in v2 admin router scope (#35d open). |
| T1-8 | `logging.log_user_interactions` + `logging.log_tokens` toggles | ✅ **CONFIRM-DESIGN** | Always-on logging is deliberate observability stance. |
| T1-9 | `enable_chat_history` toggle | ✅ **CONFIRM-DESIGN** | v2 always persists; covered by `database.db_type`. |
| T1-10 | `database_type` runtime selector | ✅ **CONFIRM-DESIGN** | Bicep-pinned; schema migration is not runtime-safe. |
| T1-11 | `integrated_vectorization_config.{max_page_length,page_overlap_length}` | ✅ **CONFIRM-DESIGN** | D2 removed integrated vectorization. |
| T1-12 | `example.{documents,user_question,answer}` few-shot inputs | ✅ **CONFIRM-DESIGN** | Orchestrator-internal; not runtime-tunable. |
| T1-13 | `AZURE_OPENAI_TOP_P` | 🆕 **NEW-DEBT-ROW** `OPENAI-TOP-P-DEBT` | XS. |
| T1-14 | `AZURE_OPENAI_STOP_SEQUENCE` | 🆕 **NEW-DEBT-ROW** `OPENAI-STOP-SEQ-DEBT` | XS. |
| T1-15 | `AZURE_OPENAI_SYSTEM_MESSAGE` env-var override | ✅ **CONFIRM-DESIGN** | Subsumed by T1-2 if pursued. |
| T1-16 | `AZURE_SEARCH_FILTER` (raw OData) | ✅ **CONFIRM-DESIGN** | Security — raw OData = injection vector. |
| T1-17 | `AZURE_COSMOSDB_ENABLE_FEEDBACK` + FE feedback thumbs | 🚀 **PHASE-7-WORK** | FE wiring (backend `/api/history/messages/{id}/feedback` exists). Overlap with T3-4. |
| T1-18 | `PACKAGE_LOGGING_LEVEL` + `AZURE_LOGGING_PACKAGES` | 🆕 **NEW-DEBT-ROW** `PACKAGE-LOG-LEVEL-DEBT` | XS. |

## Tier 2 — Admin UI feature gaps (4 items)

| # | v1 item | Proposed classification | Notes |
|---|---|---|---|
| T2-1 | `01_Ingest_Data.py` (file upload UI, URL form, reprocess-all) | 🚀 **PHASE-7-WORK** | Scope expansion on #35d. L. |
| T2-2 | `02_Explore_Data.py` (search-index browser + chunk viewer) | 🚀 **PHASE-7-WORK** | M. |
| T2-3 | `03_Delete_Data.py` (multi-select delete) | 🚀 **PHASE-7-WORK** | M. |
| T2-4 | `04_Configuration.py` (prompts/chunking/logging/orchestrator editor) | 🚀 **PHASE-7-WORK** | Already #35d (open, non-blocking). |

## Tier 3 — Chat UX feature gaps (6 items)

| # | v1 item | Proposed classification | Notes |
|---|---|---|---|
| T3-1 | Citation panel (`<CitationPanel>` + clickable `[docN]`) | 🚀 **PHASE-7-WORK** | Already #24 partial open. M-L. |
| T3-2 | TTS speaker button | ⏭ **DEFER-PHASE-8** | Adds Speech SDK synthesis dependency. |
| T3-3 | Share URL button | ⏭ **DEFER-PHASE-8** | Low value. |
| T3-4 | Feedback thumbs + reason picker | 🚀 **PHASE-7-WORK** | Overlap with T1-17. S-M. |
| T3-5 | Assistant type cards (`<AssistantTypeSection>` empty-state) | 🚀 **PHASE-7-WORK** | Conditional on T1-6 landing. S. |
| T3-6 | `/api/checkauth` + FE auth-enforcement dialog | ✅ **CONFIRM-DESIGN** | Middleware-gated; hard 401 from server is the failure mode. |

## Tier 4 — Architecture/schema parity gaps (19 items, all confirm)

| # | v1 item(s) | Proposed classification | Notes |
|---|---|---|---|
| T4-1..14 | All 14 `AZURE_SEARCH_FIELDS_*` / `_COLUMN` env vars | ✅ **CONFIRM-DESIGN** | v2 owns `Chunk` + `SearchDocument` schema. |
| T4-15 | `AZURE_SEARCH_DIMENSIONS` | ✅ **CONFIRM-DESIGN** | Auto-detect from index. |
| T4-16 | `AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION` + indexer/datasource names | ✅ **CONFIRM-DESIGN** | D2 — always client-side chunking. |
| T4-17 | `AZURE_SEARCH_INDEX_IS_PRECHUNKED` | ✅ **CONFIRM-DESIGN** | v2 design assumption. |
| T4-18 | `AZURE_SEARCH_ENABLE_IN_DOMAIN` | ✅ **CONFIRM-DESIGN** | Always-restrict is RAG default. |
| T4-19 | `AZURE_SEARCH_DOC_UPLOAD_BATCH_SIZE` | ✅ **CONFIRM-DESIGN** | Functions ingestion manages internally. |

## Tier 5 — Already cited in dev_plan §2.1 (8 items, all confirm)

All 8 items are legitimate Hard Rule #7 removals per dev_plan §2.1. No action.

| # | v1 item(s) | Proposed classification |
|---|---|---|
| T5-1 | `AZURE_AUTH_TYPE` (keys mode) | ✅ **CONFIRM-DESIGN** |
| T5-2 | All 9 `*_KEY` secrets | ✅ **CONFIRM-DESIGN** |
| T5-3 | `USE_KEY_VAULT` + `AZURE_KEY_VAULT_ENDPOINT` | ✅ **CONFIRM-DESIGN** |
| T5-4 | `PROMPT_FLOW_*` + `AZURE_ML_WORKSPACE_NAME` | ✅ **CONFIRM-DESIGN** |
| T5-5 | `SEMANTIC_KERNEL_SYSTEM_PROMPT` + `OPEN_AI_FUNCTIONS_SYSTEM_PROMPT` | ✅ **CONFIRM-DESIGN** |
| T5-6 | `CONVERSATION_FLOW=byod` | ✅ **CONFIRM-DESIGN** |
| T5-7 | Streamlit `Admin.py` + 4 pages | ✅ **CONFIRM-DESIGN** (replaced by REST + React) |
| T5-8 | `LOAD_CONFIG_FROM_BLOB_STORAGE` | ✅ **CONFIRM-DESIGN** (DB-backed config) |

## Tier 6 — Ingestion parser coverage (5 items)

| # | v1 item | Proposed classification | Notes |
|---|---|---|---|
| T6-1 | PDF parser (Document Intelligence layout API) | 🆕 **NEW-DEBT-ROW** `PDF-PARSER-DEBT` | Real product gap. M. |
| T6-2 | DOCX parser | 🆕 **NEW-DEBT-ROW** `DOCX-PARSER-DEBT` | M. |
| T6-3 | MD/HTML parser | 🆕 **NEW-DEBT-ROW** `MD-HTML-PARSER-DEBT` | S-M. |
| T6-4 | JSON parser (RecursiveJsonSplitter) | 🆕 **NEW-DEBT-ROW** `JSON-PARSER-DEBT` | S. |
| T6-5 | Image parsers (jpeg/jpg/png + tiff/bmp) | ⏭ **DEFER-PHASE-8** | Computer Vision deferred from v2 MVP. |

## Roll-up — proposed bucket counts

| Bucket | Count of rows |
|---|---|
| ✅ CONFIRM-DESIGN | 32 (Tier 1: 8 + Tier 3: 1 + Tier 4: 19 collapsed [6 rows representing 19 items] + Tier 5: 8 + Tier 6: 0) — by row count: 23 rows |
| 🆕 NEW-DEBT-ROW | 12 (T1-1, T1-2, T1-3, T1-4, T1-5 reclassified, T1-13, T1-14, T1-18, T6-1, T6-2, T6-3, T6-4) |
| 🚀 PHASE-7-WORK | 8 (T1-6, T1-17, T2-1, T2-2, T2-3, T2-4, T3-1, T3-4, T3-5) — 9 if T3-5 counted separate from T1-6 |
| ⏭ DEFER-PHASE-8 | 3 (T3-2, T3-3, T6-5) |
| 🔍 VERIFY-FIRST | 0 (T1-5 resolved above) |

## Downstream artifacts (triggered on user sign-off)

1. **dev_plan §0.1 appends (12 new debt rows)** — one row per NEW-DEBT-ROW classification, all marked `⏭ open` with the original v1 item, why-it-was-flagged, what-fix-looks-like, blast radius, files touched at clear-time, and "Cleared in: P-PARITY-IMPL pass."
2. **dev_plan §4.7.x appends (up to 9 Phase 7 task rows)** — one task per PHASE-7-WORK classification, sequenced during Phase 7 opening turn (T1-6 + T3-5 grouped if T3-5 stays conditional; T1-17 + T3-4 grouped as a single FE feedback unit).
3. **Session memory update** — flip P-PARITY-DECISIONS to ✅ done; flip P-PARITY-IMPL from "skip if zero new debt rows" to "ordered 12-unit pass before Phase 7 opens".
4. **No code, no tests** — this turn is doc-only.

## Sign-off checklist (next turn)

User confirms ONE of:
- **ACCEPT ALL** as proposed → I append the 12 §0.1 rows + 9 §4.7.x rows, flip session memory, end turn green.
- **ACCEPT WITH OVERRIDES** → user lists the specific row IDs to reclassify (e.g. "T1-2 → PHASE-7-WORK instead of NEW-DEBT-ROW"), I apply, then append.
- **REJECT + REVISE** → user describes the gap in the classification logic, I redraft.

This doc becomes immutable after sign-off ("user-signed snapshot" per session plan).
