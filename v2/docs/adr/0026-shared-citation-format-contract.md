# ADR 0026 — Shared citation-format contract across orchestrators and storage backends

- **Status**: Accepted
- **Date**: 2026-06-14
- **Phase**: 8 (agent runtime — citation parity; `BUG-0030` / `BUG-0016` / `BUG-0015`)
- **Pillar**: Stable Core (the shared CWYD prompt-composition seam + the single `citations.py` response-format point)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes / amends**: none — names and ratifies three invariants that ADRs [0007](0007-orchestrator-event-typed-sse-channel.md), [0021](0021-agent-framework-foundry-iq-kb-default.md), [0022](0022-config-resolution-error-on-incompatible-overrides.md), and [0025](0025-foundry-prompt-agent-ga-pattern.md) introduced piecemeal
- **Companion**: [ADR 0007](0007-orchestrator-event-typed-sse-channel.md) (typed SSE channel), [ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) (`agent_framework` + Foundry IQ KB), [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) (pgvector + `agent_framework` config guard), [ADR 0025](0025-foundry-prompt-agent-ga-pattern.md) (Prompt Agent GA pattern, "shared citation seam")

## Context

v1 rendered grounded answers with inline `[docN]` markers and a citations panel sourced from the retrieved documents. v2 must reach **parity for every supported runtime combination**, not just the default one.

The runtime matrix is two orchestrators × two storage backends:

| Orchestrator | Storage | Retrieval mechanism | Native marker the model emits |
|---|---|---|---|
| `langgraph` | Azure AI Search | client-side `BaseSearch.search` (injected, keyed by `index_store`) | `[docN]` (we inject the numbered sources block; the model echoes it) |
| `langgraph` | pgvector | client-side `BaseSearch.search` (**same** code path, different provider) | `[docN]` (same) |
| `agent_framework` | Azure AI Search | server-side Foundry IQ Knowledge Base MCP tool | `【N:M†source】` (Foundry's native annotation) |
| `agent_framework` | pgvector | — (no Knowledge Base source exists) | — (rejected at config) |

Two failure modes threaten parity, both called out by the repo owner:

1. **Prompt drift.** If each orchestrator authored its own grounding / citation-format prompt, the two paths would diverge in how they ground, refuse, and mark citations.
2. **Multiple response-format points.** If each orchestrator shaped its citation output inline in its own `run()`, the wire shape (`[docN]` inline + the `Citation` model) would drift and the frontend could not render both uniformly.

The owner's direction: **the grounding prompt must be shared (one input point), the LLM response must be normalized to the citation format in exactly one place (one output point), and the same formatting solution must apply to pgvector** — not a cosmosdb-only feature.

Retrieval *mechanism* legitimately differs by storage — `langgraph` runs client-side RAG over the `index_store`-keyed provider (Hard Rule #4 registry dispatch), while `agent_framework` delegates to a server-side Foundry IQ KB whose only knowledge source is the Azure AI Search index ([ADR 0021](0021-agent-framework-foundry-iq-kb-default.md)). A pgvector deployment has no Azure AI Search index, so `agent_framework` cannot ground there; that cell is already rejected with a 409 at the single config-resolution choke point ([ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md)).

The pieces exist; this ADR **names the contract** so future orchestrators, stores, and tools inherit it by rule rather than by re-discovery.

## Decision

Three invariants govern every grounded answer, regardless of orchestrator or storage backend.

### R1 — Single prompt input point (shared grounding prompt)

Both orchestrators ground through the **same** composed instructions: `compose_cwyd_instructions(CWYD_DEFAULT_BODY)` resolved via `resolve_cwyd_instructions(...)` in [definitions.py](../../src/backend/core/agents/definitions.py). The fixed `CWYD_GUARDRAIL` — which carries the exact out-of-domain fallback string, the `[doc+index]` citation-format directive, and the creative-content ban — **bookends** any operator-authored persona.

- `langgraph` injects the resolved instructions as its leading system message.
- `agent_framework` resolves the same instructions through `build_agent` / `_resolve_definition`.
- The no-override case is byte-identical to the `CWYD_AGENT.instructions` default for both.

No orchestrator may define its own grounding or citation-format prompt. The guardrail is the only place the model is told how to cite.

### R2 — Single response-format (output) point

All citation shaping converges in **one module**: [backend/core/tools/citations.py](../../src/backend/core/tools/citations.py). Two entry points produce the **same** wire shape — inline `[docN]` markers plus the `Citation` model emitted on the typed `citation` SSE channel ([ADR 0007](0007-orchestrator-event-typed-sse-channel.md)):

- `format_sources_block(...)` + `build_citations(...)` + `filter_to_referenced(...)` — the **client-side** path. `langgraph` injects a numbered `[docN]` sources block; the model echoes the markers; only markers actually referenced in the answer emit a `Citation`.
- `normalize_kb_citations(answer, citations)` — the **server-side** path. `agent_framework` lets the Foundry KB emit its native `【N:M†source】` annotations, then rewrites each to the grouping-ordered `[docN]` and renumbers the `Citation` ids to match (`BUG-0030`, landed + live-verified 2026-06-14).

No orchestrator formats citations inline in its own `run()`. An orchestrator's job is to *produce* `(answer, citations)`; `citations.py` *shapes* them.

### R3 — Backend-agnostic formatting; retrieval keyed by storage

Formatting is independent of the storage backend. `langgraph`'s `format_sources_block` is identical whether the injected `BaseSearch` provider is Azure AI Search or pgvector — pgvector inherits `[docN]` for free. Retrieval, by contrast, is selected by the `index_store` registry key (Hard Rule #4): `search_registry.registry.get(index_store)(...)`.

The one cell with no coherent retrieval — `agent_framework` + pgvector — is **rejected at config** ([ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md), HTTP 409) rather than given a divergent, store-specific formatter. Rejecting the incoherent combo keeps the format contract closed without a second code path.

## Consequences

- **+** True parity: every served combination emits inline `[docN]` + the `Citation` model; the frontend renders one shape.
- **+** One place to change the citation format (R2) and one place to change the grounding prompt (R1) — drift is structurally prevented.
- **+** pgvector is a first-class citizen of the citation contract (R3), not a degraded mode.
- **+** New orchestrators inherit the contract by rule: produce `(answer, citations)`, ground through `resolve_cwyd_instructions`, never format inline.
- **−** The native-marker normalizer (`normalize_kb_citations`) is specific to the Foundry KB annotation shape; a future server-side grounding source with a different native marker needs its own normalizer entry point — but it still lands in the single `citations.py` module (R2 holds).
- **−** Friendly title / snippet recovery for KB citations remains open (the `BUG-0030` remainder): the KB annotation carries only the raw `mcp://searchindex/<key>`, so the right-panel filename/snippet needs either a KB citation-field-mapping change or a secondary Azure AI Search lookup by document key. This ADR fixes the *marker + id* contract; the *display-metadata* recovery is tracked separately and does not change R1/R2/R3.

## Alternatives considered

- **A — Per-orchestrator citation formatting** (each `run()` shapes its own markers). Rejected: this is precisely the drift the repo owner flagged; it would let `langgraph` and `agent_framework` diverge on marker shape and `Citation` fields.
- **B — `agent_framework` + pgvector via client-side `[docN]` injection** (the same mechanism `langgraph` uses). This is [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) Alternative C restated. Rejected: it re-implements `langgraph`'s client-side RAG inside the Foundry agent for a combination that discards the agent's entire reason to exist (server-side KB grounding). The config guard is simpler, already shipped, and already tested.
- **C — Format in the prompt only** (instruct the model to emit `[docN]` and trust it, no post-processing). Rejected for `agent_framework`: the Foundry KB tool emits native `【N:M†source】` annotations regardless of the prompt, so a deterministic post-process (R2's `normalize_kb_citations`) is mandatory, not optional.
- **D — A separate "retrieval-keyed-by-storage" ADR** distinct from this one. Rejected as redundant: retrieval-keyed-by-storage is the *mechanism* half of R3 and is already governed by Hard Rule #4 + [ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) / [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md); folding it into R3 keeps one decision per ADR without splitting a single contract across two files.
