# ADR 0030 — Assistant Type prompt presets (JSON-sourced) + post-answering defaults in admin config

- **Status**: Accepted
- **Date**: 2026-06-22
- **Phase**: 7 (admin / configuration surface; `BUG-0076`)
- **Pillar**: Scenario Pack (the contract / employee preset *content*) + Configuration Layer (the admin plumbing that selects + serves it)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **References**: `BUG-0076`; [ADR 0026](0026-shared-citation-format-contract.md) (one prompt seam, `resolve_cwyd_instructions`, guardrail wraps); [ADR 0027](0027-agent-framework-app-side-rag-on-pgvector.md) (agent_framework app-side RAG); companion to [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) / [ADR 0024](0024-withdraw-per-tenant-runtime-config-single-tenant.md) (RuntimeConfig)

## Context

v1's admin Configuration page has an **Assistant Type** selector (`default` / `contract assistant` / `employee assistant`). Changing it loads a per-type **answering prompt** into the editable prompt field; the operator saves, and the chat agent answers under that persona. v1 also ships non-empty **post-answering prompt** and **post-answering filter message** defaults. (`code/backend/pages/04_Configuration.py`; presets in `code/backend/batch/utilities/helpers/config/default.json` + `default_contract_assistant_prompt.txt` + `default_employee_assistant_prompt.txt`.)

v2 dropped this. The admin Configuration page exposes the editable persona (`cwyd_agent_instructions`) and the post-answering fields, but: there is **no Assistant Type selector**, and `post_answering_prompt` / `post_answering_filter_message` default to **empty strings** (`BUG-0076`). Operators cannot pick a use-case persona, and the post-answering fields look unconfigured.

A structural mismatch makes a verbatim port impossible. v1's per-type prompts are **user-message RAG templates** carrying `{sources}` / `{question}` placeholders and a trailing `Answer:`. v2 has **no placeholder substitution** — verified in **both** orchestrators:

| | persona (`cwyd_agent_instructions`) | sources | question |
|---|---|---|---|
| **langgraph** | leading **system** message | separate `Sources:\n{block}` **system** message | user turn |
| **agent_framework** | agent **`instructions`** field (`build_agent` → `_resolve_definition` → `resolve_cwyd_instructions`, guardrail-wrapped — [agents/base.py](../../src/backend/core/providers/agents/base.py)) | KB MCP tool server-side (cosmos) **or** app-side prepend to the user turn (pgvector, [ADR 0027](0027-agent-framework-app-side-rag-on-pgvector.md)) | user turn |

So `{sources}` / `{question}` / `Answer:` pasted into v2's persona would be **literal dead text** — and for `agent_framework` even more clearly so, since the Responses thread drops system messages. The v1 *behavioral* instructions (the contract "Point 1 / Point 2" document-handling rules; the employee HR persona) are exactly what `cwyd_agent_instructions` is for, and **are** honored by both orchestrators.

Hard Rule #20 / [ADR 0026](0026-shared-citation-format-contract.md) constrains the design: there is **one** prompt seam (`resolve_cwyd_instructions`) and the fixed `CWYD_GUARDRAIL` always bookends any operator text. The assistant-type preset is therefore a **persona body**, never a re-introduction of a per-orchestrator or templated prompt.

## Decision

1. **Bring back the Assistant Type selector, mapped to `cwyd_agent_instructions`.** Three types — `default`, `contract assistant`, `employee assistant` (an `AssistantType` `StrEnum`, Hard Rule #11). Selecting a type loads that preset's body into the editable Answering-prompt field; the operator may then edit it; on save it persists as `cwyd_agent_instructions` and flows to the agent through the **existing** seam (`resolve_effective_config` → `system_prompt` / agent `instructions`, guardrail-wrapped). No new chat-path code.

2. **Prompts live in a JSON file, not in Python.** A new `v2/src/backend/core/agents/assistant_presets.json` holds the three persona bodies plus the shared `post_answering_prompt` and `post_answering_filter_message` defaults and `default_assistant_type`. A small loader module reads it once and exposes typed accessors. **`CWYD_DEFAULT_BODY` moves into this JSON** as the `default` preset (so the operator-editable persona is data, not code). **`CWYD_GUARDRAIL` stays hardcoded** in `definitions.py` — it is non-negotiable safety and must never be operator- or JSON-editable.

3. **Contract / employee presets are *adapted*, not verbatim.** Keep the behavioral / persona instructions; strip the `{sources}` / `{question}` / `Answer:` RAG scaffolding that v2 handles automatically (sources are injected by the orchestrator; citations are enforced by the guardrail). The `default` preset keeps v2's current well-tuned `CWYD_DEFAULT_BODY`. The adapted bodies are reviewed before wiring; a verbatim variant may be A/B-tested live.

4. **Presets ride in the existing config response — no new endpoint.** `GET /api/admin/config` and `/config/effective` carry a read-only `{type: body}` presets map plus the current `ai_assistant_type`, so the frontend dropdown has the bodies it needs to populate the textarea on change. A dedicated `/assistant-types` endpoint is rejected as overkill.

5. **Populate the post-answering *text* defaults; leave the feature OFF.** `post_answering_prompt` and `post_answering_filter_message` default to the (v1-derived) JSON values instead of empty strings, so the fields read as configured. `post_answering_enabled` stays **`false`** by default — enabling it adds a second groundedness LLM pass per answer, which the operator opts into deliberately. Post-answering is **not** per-assistant-type (shared, matching v1).

6. **Persist the selected type; reset restores everything.** `ai_assistant_type` is added to `RuntimeConfig` so the dropdown reflects the last choice on reload. Reset-to-default (the existing all-null `RuntimeConfig` merge patch) clears it → effective config returns `default` + the default persona + the populated post-answering text.

7. **Bring v1's tooltips, adapted — rendered in the frontend.** Each field in the admin Configuration page ([Configuration.tsx](../../src/frontend/src/pages/admin/Configuration/Configuration.tsx)) gains a `tooltip` on its `FIELD_SPEC`, shown via a Fluent UI info affordance next to the label. v1's `post_answering_prompt` / `post_answering_filter` tooltips come ~verbatim; the assistant-type and answering-prompt tooltips are adapted to v2's system-persona model; v2-only fields (orchestrator, temperature, max_tokens, semantic search, top_k, log level, content safety, post-answering enabled) get concise new tooltips. Tooltip strings are **frontend-local UI text** (in `FIELD_SPECS`), distinct from the prompt *content* (the backend JSON) — they are not operator-editable.

## Consequences

- **+** Operators regain v1's use-case personas (contract / employee) with one click; the selected persona flows to **both** orchestrators through the single existing seam — zero chat-path change, guardrail still enforced.
- **+** Prompt content is **data** (`assistant_presets.json`), editable without a code change; the guardrail stays code (safety preserved). Scenario Packs can grow by adding JSON entries.
- **+** No new endpoint, no new persistence concept — the presets ride existing config payloads; the new `ai_assistant_type` field reuses the `RuntimeConfig` override + live-reload machinery.
- **+** The post-answering fields stop looking broken (populated text), without silently doubling LLM cost (feature stays off until enabled).
- **−** Contract / employee presets are **adapted**, not byte-identical to v1 — a content review step is required, and answers may differ slightly from v1 (mitigated by the optional live A/B).
- **−** `CWYD_DEFAULT_BODY` becomes a re-export of the JSON `default` preset; a test asserts the default preset still carries its key phrases so the move cannot silently drift.
- **−** A new JSON file + loader + one `RuntimeConfig` field + frontend dropdown/tooltips touch several layers (backend types, models, router, services; frontend models, page, api client). Sequenced one unit/turn, test-first, each phase green.

## Alternatives considered

- **Paste v1 prompts verbatim.** Rejected: `{sources}` / `{question}` / `Answer:` are literal dead text in v2 (no substitution in either orchestrator), most visibly in `agent_framework` (system messages dropped). Keeps the letter, breaks the intent.
- **Re-introduce a templated user-prompt with `{sources}` / `{question}` substitution.** Rejected: re-adds a second prompt surface, violating Hard Rule #20 / [ADR 0026](0026-shared-citation-format-contract.md) (one prompt seam, guardrail wraps), and duplicates retrieval the orchestrator already does.
- **Dedicated `GET /api/admin/assistant-types` endpoint.** Rejected by the operator as overkill — the presets are part of the default config and ride the existing config response.
- **Keep prompts hardcoded in Python.** Rejected per the operator requirement: prompt content should be a JSON file, not code.
- **Enable post-answering by default.** Rejected: it adds a per-answer groundedness LLM call and can replace answers with the filter message — an opt-in, not a default.
- **Per-assistant-type post-answering prompt.** Rejected: v1 keeps post-answering shared across types; no evidence per-type is wanted.
