# Citation rendering parity plan (v2)

> **Pillar:** Stable Core (the shared citation contract) + Customization Layer (the frontend rendering surface)
> **Phase:** 8 (agent runtime — citation parity)
> **Status:** Active. Backend marker/id parity is landed and live-verified, and KB citation display-metadata recovery is **landed via fallback (b)** (secondary Search lookup by doc-key) and **live-confirmed 2026-06-15** — `BUG-0030` is **fixed**. Option (a) (the KB `sourceDataFields` seed) stays in as correct KB config but was insufficient on its own (the Responses `url_citation` annotation carries only the raw `mcp://` doc-key). Remaining open items are the frontend `BUG-0016` / `BUG-0015` rendering polish.

This plan tracks reaching **v1 citation-rendering parity** in v2 across both orchestrators and both storage backends. The architectural contract it implements is [ADR 0026](adr/0026-shared-citation-format-contract.md) (R1/R2/R3). Defects driving the work: `BUG-0030` (native KB markers leaking into the answer), `BUG-0033` (url "None" leak), `BUG-0016` / `BUG-0015` (frontend superscript + references block + right panel). The canonical defect detail lives in [bugs.md](bugs.md); this file is the roadmap.

## Goal

A grounded answer renders the same way regardless of which orchestrator served it or which store backed retrieval:

1. Inline `[docN]` markers in the answer text, shown as clickable superscript tokens.
2. A collapsible "N references" block listing the cited sources.
3. A right-side detail view showing the selected citation's title and snippet.

## The contract (ADR 0026)

- **R1 — one prompt input point.** Both orchestrators ground through `resolve_cwyd_instructions(...)` over `CWYD_DEFAULT_BODY`; the fixed `CWYD_GUARDRAIL` owns the citation-format directive and the fallback string. No per-orchestrator grounding prompt.
- **R2 — one response-format point.** All citation shaping lives in [tools/citations.py](../src/backend/core/tools/citations.py). `format_sources_block` (client-side `[docN]`) and `normalize_kb_citations` (native-marker rewrite) emit the **same** `[docN]` inline form + `Citation` model.
- **R3 — backend-agnostic formatting.** Retrieval is keyed by `index_store` (Hard Rule #4); formatting is identical for Azure AI Search and pgvector. The `agent_framework` + pgvector cell is rejected at config ([ADR 0022](adr/0022-config-resolution-error-on-incompatible-overrides.md), HTTP 409), not given a divergent formatter.

## Runtime matrix and status

| Orchestrator | Store | Path | Marker → `[docN]` | Status |
|---|---|---|---|---|
| `langgraph` | Azure AI Search | client-side `format_sources_block` | injected `[docN]`, echoed | Landed |
| `langgraph` | pgvector | **same** `format_sources_block` | injected `[docN]`, echoed | Landed |
| `agent_framework` | Azure AI Search | KB MCP → `normalize_kb_citations` | native `【N:M†source】` rewritten | Landed + live-verified (2026-06-14) |
| `agent_framework` | pgvector | rejected at config (409) | n/a | Guarded + tested |

## Done

- **A0 — live annotation capture (hard gate).** Captured a real `(answer, annotations)` pair from an `agent_framework` run to fix the marker → annotation mapping. Proved the native marker is `【N:M†source】` (12 chars) and that `M` is the KB internal source index, **inverted** from citation order — so the mapping must use `annotated_regions` grouping order, not `N:M`.
- **A2 — `normalize_kb_citations`** in [citations.py](../src/backend/core/tools/citations.py). Offset-anchored: for each citation it slices `answer[start:end]` over `metadata["annotated_regions"]`, rewrites only spans that `fullmatch` the native-marker regex, renumbers ids to `[docN]`, then strips any residual native marker unconditionally. 29 unit tests.
- **A4 — wire-in** to `agent_framework.run`: assemble `(answer, citations)`, run `normalize_kb_citations`, then emit `citation` events + the final `answer`. Live integration (`-m integration -k in_domain`, real Foundry IQ + Azure AI Search): 3 passed; the raw model answer carried `【6:0†source】 … 【6:1†source】` and the served response is `[docN]` with no `【 †】`.
- **Config guard** ([ADR 0022](adr/0022-config-resolution-error-on-incompatible-overrides.md)). `resolve_effective_config` raises `ConfigResolutionError` → HTTP 409 for `agent_framework` + pgvector, reading the post-override orchestrator so an admin flip is rejected too. Covered by `test_resolve_raises_on_pgvector_with_agent_framework`, `test_resolve_raises_when_override_flips_pgvector_to_agent_framework`, and the 409 handler test.
- **Frontend rendering surface.** Inline `[docN]` tokens render as clickable buttons ([answerTokens.tsx](../src/frontend/src/pages/chat/components/answerTokens.tsx)); the sources panel lists references and auto-expands the matching item on token click ([CitationPanel](../src/frontend/src/pages/chat/components/CitationPanel)); markdown renders XSS-safe with no `rehype-raw` ([MarkdownContent.tsx](../src/frontend/src/pages/chat/components/MarkdownContent.tsx)). Wired in [MessageList.tsx](../src/frontend/src/pages/chat/components/MessageList.tsx).
- **B — KB citation enrichment (fallback (b)), live-confirmed 2026-06-15.** `enrich_kb_citations(citations, fetch_document)` (injected lookup, no Search import — Hard Rule #20 R2) + `BaseSearch.get_document_by_key` (`AzureSearch` override) + a best-effort wire-in to `agent_framework.run` after `normalize_kb_citations` backfill friendly `title` / `snippet` / `url` on KB citations via a by-key Search lookup; a present-but-null `url` maps to `""` (a second `str(None)`→`"None"` site fixed in `AzureSearch._to_result`, distinct from `BUG-0033`). Closes `BUG-0030`.

## Resolved — KB citation display-metadata recovery (fallback (b), 2026-06-15)

**Resolved via fallback (b)** — an app-side secondary Azure AI Search lookup by doc-key, landed as three test-first units and live-confirmed on 2026-06-15: `enrich_kb_citations(citations, fetch_document)` in [citations.py](../src/backend/core/tools/citations.py) (injected `fetch_document`, so no Search import — Hard Rule #20 R2), `BaseSearch.get_document_by_key` with an `AzureSearch` override, and a best-effort wire-in to `agent_framework.run` after `normalize_kb_citations` (guarded `try/except AzureError` → degrade to the raw-id citation, never drops it). A null-`url` document also stopped serializing as the string `"None"` (a second `str(None)` site in `AzureSearch._to_result`, distinct from `BUG-0033`). Live A0 capture now serves `Citation(id="[doc1]", title="Benefit_Options.pdf", snippet=<chunk text>, url="")` with `metadata["source_id"]` retaining the raw `mcp://searchindex/<key>`. Canonical detail in [bugs.md](bugs.md) `BUG-0030`. The historical investigation that led here is retained below.

A4 fixed the **marker + id**; the remaining gap was the **friendly title / snippet** for `agent_framework` citations: the live KB annotation carried only the raw `mcp://searchindex/<key>` on `title`, with no snippet, so the right-side detail view showed a raw id (or a blank) for KB-grounded answers while `langgraph` answers showed the real document fields.

**Chosen path: (a) KB citation-field-mapping config.** The operator selected configuring the Knowledge Base to return the document fields, because the orchestrator set is open (Hard Rule #20 / [ADR 0026](adr/0026-shared-citation-format-contract.md)) and a Foundry-IQ-side field mapping keeps title/snippet recovery out of every orchestrator's code — zero new formatter, minimal maintenance. The knob is `searchIndexParameters.sourceDataFields` on the knowledge source (Azure AI Search KB REST `2025-11-01-preview`, "request additional fields for referenced source data"). Landed in the `post_provision` seed: `_build_knowledge_base_seed` now requests `title` / `url` / `content` as source-data fields (module constant `KNOWLEDGE_SOURCE_SOURCE_DATA_FIELDS`, test `test_build_knowledge_base_seed_shape`).

**Live verification done (2026-06-14) — option (a) is insufficient.** Re-seeded the live KB (`python -m scripts.post_provision`) then captured a fresh A0 `agent_framework` run: the answer normalizes correctly to inline `[doc1]` (no native `【N:M†source】` leak), but the served `Citation` still carries `title` = `url` = the raw `mcp://searchindex/<key>` with an empty `snippet`. The `sourceDataFields` knob enriches the KB tool's *referenced source data* but does **not** surface on the Responses `url_citation` annotation that `citations_from_annotations` reads. The seed change is harmless and stays in (correct KB config, costs nothing), but it does not on its own close `BUG-0030`.

Fallbacks if (a) does not surface friendly fields after the re-seed:

- **(b) Secondary Azure AI Search lookup by document key — RECOMMENDED, now proven viable (2026-06-14).** After `citations_from_annotations`, resolve each `mcp://searchindex/<key>` to its document and backfill `title` / `snippet` from the index we already own. Deterministic, app-side. The contingency is **confirmed**: a read-only `get_document(key=<doc-key>)` against the chat index resolved both captured doc-keys to real documents — `id` == the `<key>` hash, `title` == the sample filename, `content` == the chunk snippet. Design constraint before implementing: this gives `agent_framework`'s citation path a dependency on the search provider for enrichment (one `get_document` per unique cited doc), so it stays an app-side post-step that honors Hard Rule #20 R2 — the enrichment is a lookup, not a second formatter; the single `[docN]` + `Citation` shape is unchanged.
- **(c) Degraded `[docN]`-only** — ship without friendly metadata for KB citations; the marker + references block still work, the detail view shows the `[docN]` label only.

**Resolved 2026-06-15:** enrichment backfills the friendly `title` / `snippet`, so the served `Citation` no longer carries a raw `mcp://` value in its display fields — the scheme survives only on `metadata["source_id"]` for traceability.

## Validation

- Backend unit + shared AST gates: 991 passed, 1 skipped.
- `pyright --strict`: clean on `citations.py` + `agent_framework.py`.
- Live integration (`agent_framework`, cosmosdb mode, real Foundry IQ): `-k in_domain` 3 passed.
- Frontend: vitest green across the chat components; `tsc --noEmit` clean for both the app and the test tree.

## References

- [ADR 0026](adr/0026-shared-citation-format-contract.md) — the R1/R2/R3 contract.
- [ADR 0022](adr/0022-config-resolution-error-on-incompatible-overrides.md) — the pgvector + `agent_framework` 409 guard.
- [ADR 0021](adr/0021-agent-framework-foundry-iq-kb-default.md) — `agent_framework` default + Foundry IQ KB.
- [ADR 0007](adr/0007-orchestrator-event-typed-sse-channel.md) — the typed `citation` SSE channel.
- [bugs.md](bugs.md) — `BUG-0030`, `BUG-0033`, `BUG-0016`, `BUG-0015` defect detail.
