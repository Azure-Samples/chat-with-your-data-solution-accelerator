# v1 → v2 Parity Decisions

**Status:** SIGNED 2026-05-28 — immutable snapshot. User-locked via P-PARITY-DECISIONS planning sequence (Option B refinement + flip #4 + 6th bucket).
**Type:** Gating planning artifact for Phase 7. Drives one append to `development_plan.md` §0.1 (1 NEW-DEBT-ROW) and one new sub-section §4.7.1 (5 net-new task rows + 2 cross-references).
**Source audit:** 3-agent sweep cached in session memory; 150 v1 items inventoried, 114 require user attention (see audit reconciliation in session plan).
**Scope:** classifies every gap row from the audit into one of six buckets so the dev_plan §0.1 debt queue and §4.7.1 Phase 7 task list can be appended deterministically.

## 5-question validity test (gate for NEW-DEBT-ROW + PHASE-7-WORK)

Per Hard Rule #9 (v1 is spaghetti and is being *replaced*, never imitated): a v1→v2 row only earns a "do work" classification if **all five** questions pass. Failing any → REJECT-AS-V1-SPAGHETTI.

1. **Solves a real user problem** — not a v1 footgun, not "we added a knob because we could."
2. **Inside v2's deliberately-narrower MVP scope** — operator runtime configurability was narrowed in v2 (dev_plan §2.1 + pillar definitions).
3. **Doesn't reverse an explicit dev_plan §2.1 removal or §3 design decision** — reversals require a separate Hard Rule #10 product decision, not a silent §0.1 append.
4. **v1's implementation shape was correct** — some v1 features were buggy / over-engineered. If v2 should ship a different shape, REJECT the v1 row and open a fresh v2-native task.
5. **Cheaper to ship than to leave gap visible** — if the workaround (env var, CLI, portal) is acceptable for v2's early users, DEFER.

## Classification buckets

| Bucket | Meaning | Downstream action |
|---|---|---|
| ✅ CONFIRM-DESIGN | v2 correctly drops; no action needed | nothing — closed by sign-off |
| 🆕 NEW-DEBT-ROW | adds to dev_plan §0.1 debt queue | clears in P-PARITY-IMPL pass before Phase 7 |
| 🚀 PHASE-7-WORK | adds to dev_plan §4.7.1 as a Phase 7 task | sequenced during Phase 7 opening turn |
| ❌ REJECT-AS-V1-SPAGHETTI | failed validity test; v1 carryover acknowledged + dismissed | nothing — Hard Rule #9 enforcement |
| ⏭ DEFER-PHASE-8 | explicit defer past v2 MVP | nothing in v2 |
| 🔍 VERIFY-FIRST | needs spot-check before classification | one turn of read-only research, then reclassify |

## VERIFY-FIRST resolutions (run 2026-05-28)

| # | Audit claim | Verified finding | Final classification |
|---|---|---|---|
| T1-5 | "VERIFY whether v2 reads `AZURE_CONTENT_SAFETY_ENDPOINT` — likely XS-S toggle row" | `ContentSafetyGuard` ships in `v2/src/backend/core/tools/content_safety.py` and `chat.py:100` accepts it as `\| None`, **but**: (1) zero `AppSettings.content_safety` Pydantic sub-model; (2) zero `dependencies.py` / `app.py` `_lifespan` wiring constructs `ContentSafetyClient` from settings; (3) zero `AZURE_CONTENT_SAFETY_*` env-var references anywhere in backend; (4) constructor docstring promises wiring "in `backend/app.py` lifespan" but that wiring is absent. **The wiring path itself is missing**, not just the toggle. Half-finished commit, not a parity gap. Passes all 5 validity questions. | 🆕 NEW-DEBT-ROW `CONTENT-SAFETY-WIRING-DEBT` (M — settings sub-model + ContentSafetyClient lifespan wiring + dependencies.py injection + admin toggle + Bicep `cogContentSafety` module — 8-file touch surface, 1 unit per Hard Rule #1, follows `SpeechSettings` precedent) |

## Tier 1 — Operator/admin loses runtime control (18 items)

| # | v1 item | Validity test | Final classification | Notes |
|---|---|---|---|---|
| T1-1 | `document_processors[*].chunking.{strategy,size,overlap}` per file type | Fails #2 + #3 (reverses dev_plan D2) | ❌ **REJECT-AS-V1-SPAGHETTI** | v2 D2 explicitly removed this. Customization Layer pillar = fork the parser, not toggle at runtime. |
| T1-2 | `prompts.{answering_system_prompt,answering_user_prompt,condense_question_prompt}` | Fails #1 + #2 (silent eval drift footgun) | ❌ **REJECT-AS-V1-SPAGHETTI** | Runtime prompt-string editing is a v1 footgun. v2 path: edit prompts in source, redeploy. |
| T1-3 | `prompts.post_answering_prompt` + `messages.post_answering_filter` | Same as T1-2 | ❌ **REJECT-AS-V1-SPAGHETTI** | — |
| T1-4 | `prompts.enable_post_answering_prompt` toggle | Fails #1 (footgun if prompt itself rejected per T1-3) | ❌ **REJECT-AS-V1-SPAGHETTI** | Toggle via env var at deploy if ever needed. |
| T1-5 | `prompts.enable_content_safety` toggle | **Passes all 5** | 🆕 **NEW-DEBT-ROW** `CONTENT-SAFETY-WIRING-DEBT` | Genuine broken commit (see VERIFY-FIRST). Scope expanded — entire wiring path missing, not just toggle. |
| T1-6 | `prompts.ai_assistant_type` runtime selector + `/api/assistanttype` + `<AssistantTypeSection>` | Fails #1 + #2 (v1 persona-switcher was demo feature) | ❌ **REJECT-AS-V1-SPAGHETTI** | v2 path: brand via env vars + theme at deploy time (Customization Layer pillar). |
| T1-7 | `orchestrator.strategy` runtime selector | Passes (already in scope) | ✅ **CONFIRM-DESIGN** | Already covered by #35d (open). |
| T1-8 | `logging.log_user_interactions` + `logging.log_tokens` toggles | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Always-on logging is deliberate observability stance. |
| T1-9 | `enable_chat_history` toggle | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | v2 always persists; covered by `database.db_type`. |
| T1-10 | `database_type` runtime selector | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Bicep-pinned; schema migration is not runtime-safe. |
| T1-11 | `integrated_vectorization_config.{max_page_length,page_overlap_length}` | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | D2 removed integrated vectorization. |
| T1-12 | `example.{documents,user_question,answer}` few-shot inputs | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Orchestrator-internal; not runtime-tunable. |
| T1-13 | `AZURE_OPENAI_TOP_P` | Fails #1 + #5 (speculative knob, default works) | ❌ **REJECT-AS-V1-SPAGHETTI** | Set via env var if a customer asks. |
| T1-14 | `AZURE_OPENAI_STOP_SEQUENCE` | Fails #1 + #5 | ❌ **REJECT-AS-V1-SPAGHETTI** | Same as T1-13. |
| T1-15 | `AZURE_OPENAI_SYSTEM_MESSAGE` env-var override | Passes (T1-2 subsumes) | ✅ **CONFIRM-DESIGN** | Since T1-2 rejected, this stays at "edit in source." |
| T1-16 | `AZURE_SEARCH_FILTER` (raw OData) | Passes (security) | ✅ **CONFIRM-DESIGN** | Raw OData = injection vector. v2 forbids. |
| T1-17 | `AZURE_COSMOSDB_ENABLE_FEEDBACK` + FE feedback thumbs | **Passes all 5** | 🚀 **PHASE-7-WORK** (merged with T3-4) | Backend wired in #32b; FE thumbs are standard RAG UX. |
| T1-18 | `PACKAGE_LOGGING_LEVEL` + `AZURE_LOGGING_PACKAGES` | Fails #2 + #5 | ❌ **REJECT-AS-V1-SPAGHETTI** | Modern path: OpenTelemetry / App Insights filters, not env-var-driven Python `logging`. |

## Tier 2 — Admin UI feature gaps (4 items)

| # | v1 item | Validity test | Final classification | Notes |
|---|---|---|---|---|
| T2-1 | `01_Ingest_Data.py` (file upload + URL form + **reprocess-all** button) | **Passes all 5** (full v1 scope) | 🚀 **PHASE-7-WORK** | User pick: reprocess-all is an operator requirement at customer scale, not a footgun. Keep full v1 scope. |
| T2-2 | `02_Explore_Data.py` (search-index browser + chunk viewer) | Fails #5 (Azure Portal Search Explorer covers) | ⏭ **DEFER-PHASE-8** | Portal explorer is acceptable for v2 launch. |
| T2-3 | `03_Delete_Data.py` (multi-select delete from index + blob) | **Passes all 5** (full v1 scope) | 🚀 **PHASE-7-WORK** | User pick: multi-select-delete is an operator requirement at customer scale. GDPR + customer-deletion = real ask. Keep full v1 scope. |
| T2-4 | `04_Configuration.py` (prompts/chunking/logging/orchestrator editor) | Passes (already #35d) | 🚀 **PHASE-7-WORK** | Cross-reference to existing #35d in §0.1; no new row. |

## Tier 3 — Chat UX feature gaps (6 items)

| # | v1 item | Validity test | Final classification | Notes |
|---|---|---|---|---|
| T3-1 | Citation panel (`<CitationPanel>` + clickable `[docN]`) | Passes (already #24) | 🚀 **PHASE-7-WORK** | Cross-reference to existing #24 partial in §0.2; no new row. |
| T3-2 | TTS speaker button | Fails #5 | ⏭ **DEFER-PHASE-8** | Adds Speech SDK synthesis dependency; low priority. |
| T3-3 | Share URL button | Fails #1 | ⏭ **DEFER-PHASE-8** | Low value. |
| T3-4 | Feedback thumbs + reason picker | **Passes all 5** (merged with T1-17) | 🚀 **PHASE-7-WORK** | Single FE unit covers T1-17 + T3-4 together. |
| T3-5 | Assistant-type cards (`<AssistantTypeSection>` empty-state) | Conditional on T1-6 (rejected) | ❌ **REJECT-AS-V1-SPAGHETTI** | T1-6 rejected → T3-5 has nothing to render. |
| T3-6 | `/api/checkauth` + FE auth-enforcement dialog | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Middleware-gated; hard 401 from server is the failure mode. |

## Tier 4 — Architecture/schema parity gaps (19 items, all confirm)

| # | v1 item(s) | Validity test | Final classification | Notes |
|---|---|---|---|---|
| T4-1..14 | All 14 `AZURE_SEARCH_FIELDS_*` / `_COLUMN` env vars | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | v2 owns `Chunk` + `SearchDocument` schema. |
| T4-15 | `AZURE_SEARCH_DIMENSIONS` | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Auto-detect from index. |
| T4-16 | `AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION` + indexer/datasource names | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | D2 — always client-side chunking. |
| T4-17 | `AZURE_SEARCH_INDEX_IS_PRECHUNKED` | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | v2 design assumption. |
| T4-18 | `AZURE_SEARCH_ENABLE_IN_DOMAIN` | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Always-restrict is RAG default. |
| T4-19 | `AZURE_SEARCH_DOC_UPLOAD_BATCH_SIZE` | Passes (deliberate) | ✅ **CONFIRM-DESIGN** | Functions ingestion manages internally. |

## Tier 5 — Already cited in dev_plan §2.1 (8 items, all confirm)

All 8 items are legitimate Hard Rule #7 removals per dev_plan §2.1. No action.

| # | v1 item(s) | Final classification |
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

| # | v1 item | Validity test | Final classification | Notes |
|---|---|---|---|---|
| T6-1 | PDF parser (v1 = Document Intelligence layout API SDK) | Passes #1, #2, #3, #5 — fails #4 on **shape** | 🚀 **PHASE-7-WORK** (v2-native shape) | Ships as Foundry IQ ingestion skill, **NOT** v1's Document Intelligence SDK carryover. |
| T6-2 | DOCX parser | Same as T6-1 | 🚀 **PHASE-7-WORK** (v2-native shape) | Same Foundry IQ skill shape as T6-1. |
| T6-3 | MD/HTML parser (`WebDocumentLoading`) | Fails #5 (rare enterprise primary corpus) | ⏭ **DEFER-PHASE-8** | — |
| T6-4 | JSON parser (`RecursiveJsonSplitter` with configurable `max_chunk_size`) | Fails #4 + #5 (over-engineered config) | ⏭ **DEFER-PHASE-8** | — |
| T6-5 | Image parsers (jpeg/jpg/png + tiff/bmp) | Fails #2 (Computer Vision deferred from v2 MVP) | ⏭ **DEFER-PHASE-8** | — |

## Roll-up — final bucket counts (post-validity-test)

| Bucket | Count |
|---|---|
| 🆕 NEW-DEBT-ROW | **1** (T1-5 `CONTENT-SAFETY-WIRING-DEBT`) |
| 🚀 PHASE-7-WORK net-new | **5** (T1-17+T3-4 merged, T6-1, T6-2, T2-1 full scope, T2-3 full scope) |
| 🚀 PHASE-7-WORK already-open cross-ref | **2** (T2-4 → #35d, T3-1 → #24 partial) |
| ❌ REJECT-AS-V1-SPAGHETTI | **9** (T1-1, T1-2, T1-3, T1-4, T1-6, T1-13, T1-14, T1-18, T3-5) |
| ⏭ DEFER-PHASE-8 | **6** (T2-2, T3-2, T3-3, T6-3, T6-4, T6-5) |
| ✅ CONFIRM-DESIGN | **23** (T1-7..T1-12 + T1-15 + T1-16 = 8 · T3-6 = 1 · T4-1..T4-19 collapsed to 6 rows / 19 items · T5-1..T5-8 = 8) |
| 🔍 VERIFY-FIRST | **0** (T1-5 resolved above) |

Total rows classified: 1 + 5 + 2 + 9 + 6 + 23 = **46 row-level decisions** covering the full 114-item audit surface (Tier 4 rows collapse 14+1+1+1+1+1 = 19 items into 6 table entries).

## Downstream artifacts (executed alongside sign-off, 2026-05-28)

1. **`development_plan.md` §0.1 backend debt — 1 new row appended:** `CONTENT-SAFETY-WIRING-DEBT` (Phase 7 debt, M effort, status ⏭ open, Cleared in P-PARITY-IMPL pass).
2. **`development_plan.md` §4.7.1 — new sub-section created with 5 net-new task rows + 2 cross-references:**
   - #50 Feedback thumbs (T1-17 + T3-4 merged)
   - #51 PDF parser via Foundry IQ skill shape (T6-1)
   - #52 DOCX parser via Foundry IQ skill shape (T6-2)
   - #53 Ingest Data admin UI — full v1 scope incl. reprocess-all (T2-1)
   - #54 Delete Data admin UI — full v1 scope incl. multi-select (T2-3)
   - ⇢ #35d Configuration UI (T2-4 cross-reference to §0.1)
   - ⇢ #24 Citation panel (T3-1 cross-reference to §0.2)
3. **Session memory** `/memories/session/plan.md` updated: P-PARITY-DECISIONS flipped to ✅ done; P-PARITY-IMPL narrowed to "1-turn pass (CONTENT-SAFETY-WIRING-DEBT)" before Phase 7 opens.
4. **No code, no tests** — this sign-off turn is doc-only. Test suite / pyright / AST gates baselines unchanged.

## Sign-off (immutable after this point)

User locked the following decisions in the P-PARITY-DECISIONS planning sequence (2026-05-28):

- Apply **Option B** (validity-test refinement) over Option A (auto-funnel) or Option C (defer audit).
- Add ❌ **REJECT-AS-V1-SPAGHETTI** as the 6th bucket (Hard Rule #9 enforcement, codified in the validity-test gate above).
- **Flip borderline call #4:** keep T2-1 (reprocess-all) and T2-3 (multi-select-delete) at full v1 scope — operator requirements at customer scale, not footguns.
- **T6-1 / T6-2 (PDF + DOCX)** ship in Phase 7 with v2-native shape (Foundry IQ ingestion skill), **NOT** v1's Document Intelligence SDK carryover.
- **T6-3 / T6-4 / T6-5** (MD/HTML, JSON, images) defer to Phase 8.
- **T1-6** (assistant-type runtime selector) rejected as demo feature.
- Every PHASE-7-WORK row earns a fresh v2-native design at task-open time — **no automatic carryover of v1 implementation shapes**.

**This doc is now immutable.** Any subsequent re-classification requires a new gating turn that produces a fresh signed snapshot.

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
