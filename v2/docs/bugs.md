---
title: CWYD v2 — Bug Registry
description: Canonical defect registry for CWYD v2. Records every observed defect (wrong or broken runtime behavior) with its root cause, fix, and cross-references to the daily worklog and the development plan.
author: CWYD Engineering
ms.date: 2026-06-11
topic: reference
keywords: bugs, defects, registry, v2, root cause, regression, recovery
estimated_reading_time: 14
---

## Purpose

This file is the canonical, file-based registry of **defects** in CWYD v2: behavior that is wrong, broken, or regressed against intent. It exists so bug history survives across sessions and is never trapped in ephemeral agent memory.

Record a bug here the moment it is observed, even before it is fixed. Update the same entry when it is fixed. Every entry is self-contained: a reader should understand the symptom, the root cause, and the fix without opening any other file.

## Relationship to the development plan

[development_plan.md](development_plan.md) §0.1 (backend) and §0.2 (frontend) are the **phase debt and task queues**: deferred work, refactors, and follow-ups that clear on each phase's end-of-phase audit cadence (Hard Rule #12). They are not a defect log.

The split:

* A **defect** (wrong or broken behavior) is recorded here in `bugs.md`. This is the canonical source of truth for defects.
* A **debt or task item** (deferred work, planned refactor, scoped follow-up) stays in the development plan debt queues.

When a defect also needs phase-audit visibility, the development plan keeps a one-line pointer row that references the `BUG-####` id here, and the full detail lives in this file. There is one source of truth per concern, never two.

## Conventions

### Identifiers

Bugs use a sequential, zero-padded id: `BUG-0001`, `BUG-0002`, and so on. Ids are never reused. The next free id is one greater than the highest id already in the registry.

### Closed-set fields

The registry uses three closed sets. Use only these values.

Area: `backend`, `frontend`, `infra`, `functions`, `docs`, `ci`.

Severity: `blocker` (nothing ships or a pipeline is dead), `high` (a core path is broken), `medium` (a path is degraded with a workaround), `low` (cosmetic or minor).

Status: `open`, `in-progress`, `fixed`, `wontfix`, `duplicate`.

### Placeholder rule

This file is tracked and may reach public GitHub. Never write real environment values (subscription, tenant, resource group, azd env name, resource suffix, identity ids, real FQDNs). Use the placeholder tokens defined in [adr/0019-no-env-specific-content-in-tracked-files.md](adr/0019-no-env-specific-content-in-tracked-files.md), for example `<SUFFIX>`, `<RESOURCE_GROUP>`, `<AZURE_SUBSCRIPTION_ID>`. Environment-variable names such as `AZURE_AI_SERVICES_ENDPOINT` are generic and may be written verbatim.

### How to add a bug

1. Allocate the next `BUG-####` id.
2. Add a row to the Registry table with status `open` (or `in-progress` if already being worked).
3. Add a `### BUG-####` subsection under Details with the symptom, root cause, fix, and references.
4. Cross-reference the day's worklog entry under [worklog/](worklog/), and add a pointer row in the development plan debt queue only if the defect needs phase-audit visibility.

## Registry

| ID | Found | Fixed | Area | Severity | Status | Summary |
|---|---|---|---|---|---|---|
| BUG-0001 | 2026-06-10 | 2026-06-10 | backend | blocker | fixed | Embeddings call routes to the Foundry project endpoint (no embeddings path → `404`) and omits `dimensions`. |
| BUG-0002 | 2026-06-10 | 2026-06-10 | backend | blocker | fixed | Parser-minted chunk id is an illegal Azure AI Search document key, so Search push fails with `InvalidDocumentKey`. |
| BUG-0003 | 2026-06-11 | — | backend | high | open | `GET /api/admin/documents` returns `503` even with search fully configured: `list_sources` facets the `title` field, which is not `facetable` in the index schema, so Azure AI Search raises `FieldNotFacetable` and the router maps it to 503. |
| BUG-0004 | 2026-06-11 | 2026-06-11 | frontend | medium | fixed | The admin Orchestrator field is a free-text input; it should be a dropdown of the known orchestrator keys. |
| BUG-0005 | 2026-06-11 | 2026-06-11 | frontend | low | fixed | The admin Configuration labels show internal config-key names such as `(orchestrator_name)`. |
| BUG-0006 | 2026-06-11 | 2026-06-11 | backend | medium | fixed | Content Safety defaults to disabled; it should default to enabled. |
| BUG-0007 | 2026-06-11 | 2026-06-11 | backend | medium | fixed | The default agent instructions do not carry the vetted v1 default prompt text. |
| BUG-0008 | 2026-06-11 | 2026-06-11 | frontend | medium | fixed | The separate Prompt editor page should be removed and folded into the Configuration page, matching v1. |
| BUG-0009 | 2026-06-11 | 2026-06-11 | frontend | medium | fixed | The admin Log level field is a free-text input; it should be a dropdown of the known log levels (`DEBUG`/`INFO`/`WARNING`/`ERROR`). |
| BUG-0010 | 2026-06-11 | — | frontend | low | open | Numeric config fields should validate numeric entry on the frontend; the admin Configuration page already enforces this (`type=number` + bounds), so the affected surface needs confirmation. |
| BUG-0011 | 2026-06-11 | — | backend | high | open | An authored agent prompt is not RAI-validated and fully replaces the system instructions, so it can supersede the system guardrail ("uber") prompt. |
| BUG-0012 | 2026-06-11 | — | frontend | low | open | The assistant robot avatar and the Thinking (reasoning) panel are not aligned in the chat message layout. |
| BUG-0013 | 2026-06-11 | — | backend | medium | open | The Thinking/reasoning feed never shows: the backend emits no `reasoning` SSE frames, so the (correctly wired) frontend panel stays empty. |
| BUG-0014 | 2026-06-11 | — | frontend | medium | open | Assistant responses render as raw markdown; the markdown is not converted to HTML as it is in v1. |
| BUG-0015 | 2026-06-11 | — | frontend | low | open | The citation/reference block styling under an answer does not match v1. |
| BUG-0016 | 2026-06-11 | — | frontend | medium | open | Inline `[docN]` references render as literal-text buttons; they should render like v1 (superscript citation links). |
| BUG-0017 | 2026-06-11 | — | backend | high | open | Starting a conversation does not persist it to chat history, so new conversations never appear in the left history column. |
| BUG-0018 | 2026-06-11 | — | frontend | low | open | The chat history left column shows the backend database name (`backend: <db_type>`); it should not. |
| BUG-0019 | 2026-06-11 | — | frontend | low | open | Remove the New chat section and functionality from the chat history left column. |

## Details

### BUG-0001 — Embeddings routed to the project endpoint and missing `dimensions`

Area: backend. Severity: blocker. Status: fixed (found and fixed 2026-06-10).

Symptom: the `batch_push` ingestion pipeline could not produce a single embedded chunk. `FoundryIQ.embed()` returned `404`.

Root cause: `FoundryIQ.embed()` reused the project-scoped OpenAI client that is correct for chat and agents. The Foundry **project** route exposes no `embeddings` path, so every embeddings request returned `404`. The call also never passed `dimensions`, so a `text-embedding-3-large` deployment would emit 3072-dimension vectors against the 1536-dimension `content_vector` index field.

Fix: a new `FoundryIQ._get_embeddings_client()` targets the **account** endpoint (`AZURE_AI_SERVICES_ENDPOINT` plus `/openai/v1`), and `embed()` now passes `dimensions=settings.openai.embedding_dimensions`.

Why it was not caught earlier: `test_foundry_iq.py` fully mocks the OpenAI client, which hid the project-versus-account routing distinction.

References: [worklog/2026-06-10.md](worklog/2026-06-10.md); [development_plan.md](development_plan.md) §0.1 `INGEST-EMBED-DOCKEY`.

### BUG-0002 — Parser chunk id is an illegal Azure AI Search document key

Area: backend. Severity: blocker. Status: fixed (found and fixed 2026-06-10).

Symptom: after embeddings were fixed, the Azure AI Search push step failed with `InvalidDocumentKey`, so no document reached the index.

Root cause: parsers minted `Chunk.id` as `f"{source}__{index}"`. When `source` is a filename, its extension dot makes the key illegal. Azure AI Search document keys allow only letters, digits, `_`, `-`, and `=`.

Fix: a new Stable Core helper `BaseParser.make_chunk_id(source, index)` hashes the readable `f"{source}__{index}"` through SHA-256 into a key-safe hex digest (mirrors the v1 `source_document.py` hashing precedent). Both parsers call it. The readable name survives on `Chunk.source` and the Search `title` field, and the read-side `_to_result` already treats `id` as opaque.

Why it was not caught earlier: the parser tests asserted the raw `id` literal, which baked the invalid key charset into the expectation. A new `test_base.py` (5 tests) now asserts key safety with a charset regex against the helper contract instead of a magic string.

References: [worklog/2026-06-10.md](worklog/2026-06-10.md); [development_plan.md](development_plan.md) §0.1 `INGEST-EMBED-DOCKEY`.

### BUG-0003 — Admin documents endpoint returns 503 (`list_sources` facets the non-facetable `title` field)

Area: backend. Severity: high. Status: open (found 2026-06-11).

Symptom: `GET /api/admin/documents` returns `503 Service Unavailable` (body `{"detail":"Azure dependency temporarily unavailable."}`), so the admin Delete data grid cannot list indexed sources. Reproduced locally 2026-06-11 against the live cloud data plane **with search fully configured** (endpoint, index, and knowledge base all set, and the `search` readiness check passing) — the listing still 503s.

Root cause: `list_sources()` in `backend/core/providers/search/azure_search.py` issues `client.search(search_text="*", facets=["title,count:10000,sort:value"], top=0)` to bucket chunks by their `title` field, then reads `paged.get_facets()`. The configured index schema does not mark `title` as `facetable`, so Azure AI Search rejects the request with `HttpResponseError` — `(OperationNotAllowed) The field 'title' has not been marked as facetable in the schema` (`Code: FieldNotFacetable`). The SDK-boundary handler in `backend/routers/admin.py` maps that `AzureError` to `HTTPException(503)` per the resilience contract. The failure is independent of endpoint configuration; it fires whenever the index used by the deployment lacks a facetable `title` field. The earlier hypothesis (empty endpoint → `search_provider` is `None` → 503) is a separate latent pass-through path, not the cause of the observed 503.

Proposed fix (direction, to be settled in the fix turn): prefer a code-side fix in `list_sources()` so the endpoint is robust to existing index schemas — derive the source listing without faceting `title` (for example facet on a field declared `facetable`, or page documents and aggregate distinct sources client-side). Optionally, also mark the source-grouping field `facetable` in the index schema. Separately, decide whether the `search_provider is None` pass-through state should degrade gracefully (empty `ListDocumentsResponse` + a "search not configured" signal) instead of a hard `503`, and track that as its own concern.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0004 — Orchestrator field is free text instead of a dropdown

Area: frontend. Severity: medium. Status: fixed (found 2026-06-11, fixed 2026-06-11).

Symptom: on the admin Configuration page the Orchestrator field is a single-line text input, so an operator can type an invalid key and save it.

Root cause: `orchestrator_name` is declared as a text field in the `FIELD_SPECS` array in `frontend/src/pages/admin/Configuration/Configuration.tsx`; there is no select control bound to the known orchestrator keys.

Proposed fix: render a dropdown sourced from the first-party orchestrator keys `langgraph` and `agent_framework` (the `OrchestratorName` enum in `backend/core/settings.py`, registered in `backend/core/providers/orchestrators/registry.py`). Decide in the fix turn whether to keep a free-text escape hatch for third-party registered keys, since the settings type is widened to `OrchestratorName | str`.

Fix: added an `OrchestratorName` closed-set map (`langgraph`, `agent_framework`) to `frontend/src/models/admin.tsx` mirroring the backend StrEnum, extended `FieldSpec` with a `select` kind plus an `options` list, and rendered the Orchestrator field as a Fluent UI `Select` dropdown. Escape-hatch decision: no free-text input is kept, but if the running config already holds a key outside the first-party set (allowed by the widened `OrchestratorName | str` backend type), that current value is added as an extra option so it stays selectable and is never silently dropped. The wire field `orchestrator_name` stays a plain `string`, and `validateField` now treats `select` as a closed choice. Covered by the Configuration Vitest suite (`src/tests/frontend/pages/admin/Configuration/Configuration.test.tsx`); full frontend suite green (371 tests).

Follow-up defect (persistence): after the dropdown shipped, selecting `agent_framework` and saving reported success but the field reverted to `langgraph` on reload. Root cause: the admin client `getAdminConfig()` in `frontend/src/api/admin.tsx` read `GET /api/admin/config` — the plain env-default snapshot that intentionally ignores overrides — instead of `GET /api/admin/config/effective`, the endpoint that overlays the persisted `RuntimeConfig` from `app.state.runtime_overrides`. The `PATCH /api/admin/config` write persisted and live-reloaded the override correctly; only the read-back used the wrong source, so every override field (the orchestrator was just the visible one) reverted on reload. Fix: pointed `getAdminConfig()` at `/api/admin/config/effective` and unwrapped the `values` payload, and added an `EffectiveAdminConfig` wire type to `frontend/src/models/admin.tsx` mirroring the backend model. The backend env-vs-effective endpoint split is intentional (backend tests pin `/api/admin/config` as the env-only snapshot), so no backend change was made. Covered by the admin client Vitest suite (`src/tests/frontend/api/admin.test.tsx`, `getAdminConfig` block now asserts the effective endpoint and the unwrapped override-resolved value); full frontend suite green (371 tests).

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0005 — Admin configuration labels show internal config-key names

Area: frontend. Severity: low. Status: fixed (found 2026-06-11, fixed 2026-06-11).

Symptom: every field label on the admin Configuration page appends the raw config key in parentheses, for example "Orchestrator (orchestrator_name)" and "Content safety (content_safety_enabled)".

Root cause: the label rendering in `frontend/src/pages/admin/Configuration/Configuration.tsx` appends each field spec's key to its human-readable label.

Proposed fix: render the human-readable label only and drop the parenthetical config-key suffix.

Fix: removed the `<span>` that rendered `({spec.key})` from the field label so it shows only the human-readable `spec.label`, and deleted the now-dead `.fieldName` CSS class. Added a test asserting rendered labels contain the human text and never the parenthetical config key.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0006 — Content Safety defaults to disabled

Area: backend. Severity: medium. Status: fixed (found 2026-06-11, fixed 2026-06-11).

Symptom: Content Safety starts disabled by default, so the input pre-filter does not run unless an operator opts in.

Root cause: `ContentSafetySettings.enabled` defaults to `False` in `backend/core/settings.py`, a deliberate opt-in. Production infrastructure already sets `AZURE_CONTENT_SAFETY_ENABLED` to `true` in Bicep, and the lifespan activates the client only when both `enabled` is true and an endpoint is set; the shipped `.env.sample` leaves it `false`.

Proposed fix: change the default to `True`. This is safe because the lifespan gates the client on both `enabled` and a configured endpoint — with no endpoint the client stays `None` and the guard is inert. Confirm the intent in the fix turn before flipping the default.

Fix: flipped `ContentSafetySettings.enabled` to default `True` (secure-by-default) and set `.env.sample` `AZURE_CONTENT_SAFETY_ENABLED=true` (chosen with the operator). The lifespan gate still requires both `enabled` and a non-empty endpoint, so the new default is inert until `AZURE_CONTENT_SAFETY_ENDPOINT` is set; production (which already provisions the endpoint via Bicep) is unchanged. Updated the settings docstring, the `.env.sample` comment, and the two backend tests that pinned the old `False` default (`test_content_safety_settings_defaults_when_unset` now asserts `True`; `test_init_content_safety_client_returns_none_when_disabled` now opts out explicitly).

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0007 — Default agent instructions do not carry the v1 default prompt text

Area: backend. Severity: medium. Status: fixed (found 2026-06-11, fixed 2026-06-11).

Symptom: the v2 default system prompt does not reflect the vetted default answering prompt that v1 ships.

Root cause: the v1 default prompt text lives in `code/backend/batch/utilities/helpers/config/default.json` (the `answering_system_prompt` and `answering_user_prompt` keys). v2 defines its built-in instructions as `CWYD_AGENT` in `backend/core/agents/definitions.py` and never ported the v1 default text. The functional impact is that the prior minimal prompt never told the model the `[docN]` inline citation format, yet the v2 citation pipeline depends on it: the langgraph orchestrator injects a `Sources:` system message, the model is expected to emit `[docN]` markers, and `filter_to_referenced` (`backend/core/tools/citations.py`) extracts those markers into `citation` SSE events. Without the format instruction, citations were unreliable.

Fix: ported v1's `answering_system_prompt` into `CWYD_AGENT.instructions` as a strict near-verbatim port (Option A, chosen with the operator) -- kept the two code-generation lines and the "private model trained by Open AI" line, and reproduced v1's exact text (including its sub-bullet indentation and its original wording quirks) so the prompt stays the vetted, shipped text. The **only** adaptation was dropping v1's stale knowledge-cutoff line ("Your internal knowledge ... only current until ... 2021 ... The current date will be provided in the system message."), because v2 injects no current date. The v1 per-business-unit assistant-type system (Default / Contract assistant / Employee assistant) and the separate `answering_user_prompt` user-turn template remain out of scope. Updated the test (renamed `test_cwyd_agent_grounds_in_knowledge_base` -> `test_cwyd_agent_carries_vetted_v1_default_prompt`) to assert the ported content: grounds in "retrieved documents", carries the `[doc+index]` citation format, preserves the out-of-domain refusal string, and confirms the 2021 line is gone. `name`/`tools` assertions unchanged. 173 backend tests pass (agents + admin + orchestrators).

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0008 — Separate Prompt editor page should fold into Configuration

Area: frontend. Severity: medium. Status: fixed (found 2026-06-11, fixed 2026-06-11).

Symptom: v2 exposes a dedicated Prompt editor page, whereas v1 edits all prompts inline on a single Configuration page.

Root cause: the prompt-editor route was added during the `#35d` admin merge. `frontend/src/pages/admin/PromptEditor/PromptEditor.tsx` is wired through `frontend/src/models/sections.tsx` (the `AdminPrompt` section and its `/admin/prompt` route), `frontend/src/App.tsx` (the route element), `frontend/src/pages/admin/AdminLayout.tsx`, and the header nav — built as v1 parity, but v1 has no separate editor.

Fix: adopted the v1 structure — `cwyd_agent_instructions` is now a multi-line `kind: "text"` field with `allowEmpty: true` at the top of `FIELD_SPECS` on the Configuration page, rendered through the existing `<Textarea>` branch exactly like `post_answering_prompt`. It is added to `RAI_GUARDED_FIELDS`, so a 422 RAI rejection surfaces inline on the field row. v1 has no per-field "Reset to default" button; clearing the textarea and saving sends an empty string, which `_resolve_definition` (`backend/core/providers/agents/base.py`) already treats identically to `null` (both fall back to the built-in `CWYD_AGENT` default), so reset-to-default is preserved without extra `null` plumbing. Removed the standalone page and all its wiring: deleted `frontend/src/pages/admin/PromptEditor/` (page + CSS) and `tests/frontend/pages/admin/PromptEditor/`, dropped the `AdminPrompt` member + its `SectionPath` entry from `sections.tsx`, removed the `admin-subnav-prompt` nav item from `AdminLayout.tsx`, and removed the `PromptEditor` import + `/admin/prompt` route from `App.tsx`. The folded coverage lives in `tests/frontend/pages/admin/Configuration/Configuration.test.tsx` (textarea render, empty-allowed, PATCH, inline RAI rejection + clear). The wire models already declared the field across `AdminConfig` / `RuntimeConfig` / `AdminConfigPatch`, so no model or backend change was needed.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0009 — Log level field is free text instead of a dropdown

Area: frontend. Severity: medium. Status: fixed (found 2026-06-11, fixed 2026-06-11).

Symptom: on the admin Configuration page the Log level field is a single-line text input, so an operator can type an arbitrary string and save it.

Root cause: `log_level` is declared with `kind: "text"` in the `FIELD_SPECS` array in `frontend/src/pages/admin/Configuration/Configuration.tsx`, so it renders through the text `<Input>` branch. The field hint even enumerates the closed set (`DEBUG`, `INFO`, `WARNING`, `ERROR`), but no select control is bound to it — the page imports only `Button`, `Input`, `Switch`, and `Textarea` from `@fluentui/react-components`.

Fix: rendered `log_level` as a dropdown over the closed set, reusing the same `kind: "select"` machinery as the orchestrator field (BUG-0004). Added a `LogLevel` closed-set const (`Debug`/`Info`/`Warning`/`Error` → `DEBUG`/`INFO`/`WARNING`/`ERROR`) to `frontend/src/models/admin.tsx`, mirroring the existing `OrchestratorName` `as const` + literal-union pattern; the wire field stays a plain `string` because the backend stores `log_level` as a free-form logging level name (`settings.observability.log_level: str = "INFO"`, no backend enum). Switched the `log_level` `FieldSpec` to `kind: "select"` with `options: [LogLevel.Debug, LogLevel.Info, LogLevel.Warning, LogLevel.Error]` and imported `LogLevel`. No change was needed to the select render branch, `selectOptions` derivation, `validateField` (select branch already present), `computePatch` (already sends `log_level` as a string), or `configToForm`. The pre-existing "empty text fields" validation test used `log_level` as its example non-empty text field; since `log_level` is now a select (and after BUG-0008 no `kind: "text"` field is non-`allowEmpty`), that test was retargeted to assert the select-cleared path (`must be selected`). Added two tests: a dropdown-render assertion (`SELECT` tag, options `["DEBUG","INFO","WARNING","ERROR"]`, value `INFO`) and a PATCH assertion (`patchAdminConfig` called with `{ log_level: "DEBUG" }`). Frontend suite green at 370 tests (31 files).

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0004.

### BUG-0010 — Numeric config fields should validate numeric entry

Area: frontend. Severity: low. Status: open (found 2026-06-11).

Symptom (as reported): numeric configuration values should have frontend validation that enforces a numeric entry.

Current state: on the admin Configuration page the numeric fields (`openai_temperature`, `openai_max_tokens`, `search_top_k`) already render through the `kind === "number"` branch in `frontend/src/pages/admin/Configuration/Configuration.tsx` as `<Input type="number">` with `step`, `min`, and `max`. `handleNumberChange` coerces a non-parseable entry to `NaN`; `validateField` returns "must be a number" for a `NaN` or non-number value and enforces the min/max bounds; the error renders inline and `anyFieldInvalid` blocks Save. The requested validation therefore appears already satisfied on the admin Configuration surface.

Proposed fix: confirm in the fix turn which numeric surface the user observed lacking validation (for example a deployed build that predates the current Configuration page, or a numeric input outside the admin Configuration page). If a gap is reproduced, extend numeric-entry validation there; otherwise close as already-implemented.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0011 — Authored prompt is not RAI-validated and can supersede the system prompt

Area: backend. Severity: high. Status: open (found 2026-06-11).

Symptom: when an agent prompt is authored, it is not screened by Responsible AI (RAI) validation, and it can override the system's master ("uber") guardrail prompt.

Root cause: two facets. (1) Guardrail precedence — `backend/core/providers/agents/base.py` applies the configured `cwyd_agent_instructions` with `definition.model_copy(update={"instructions": text})`, so the authored text fully **replaces** the `CWYD_AGENT` system instructions rather than being appended beneath a fixed guardrail prompt. Only `RAI_AGENT` and future safety surfaces are override-shielded (`if definition.name != CWYD_AGENT.name: return definition`), so an authored `CWYD_AGENT` prompt can supersede the intended system instructions. (2) RAI validation coverage — the RAI safety classifier guards only `post_answering_prompt` on save (`RAI_GUARDED_FIELDS` on the frontend; the classifier path in `backend/models/admin.py` and `backend/services/admin.py`). The primary `cwyd_agent_instructions` (the system prompt) is not run through the RAI classifier. End-user chat input is screened by Content Safety (`ContentSafetyGuard` in `backend/app.py`) but is not RAI-classified in the conversation router.

Proposed fix (direction, to be settled in the fix turn): (a) anchor the configured instructions beneath a non-overridable system guardrail prompt so authored text cannot supersede the system "uber" prompt; (b) extend RAI validation to cover the authored `cwyd_agent_instructions`, and decide whether end-user chat input should also be RAI-classified rather than only Content-Safety screened.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0006, BUG-0007.

### BUG-0012 — Robot avatar and Thinking panel are not aligned

Area: frontend. Severity: low. Status: open (found 2026-06-11).

Symptom: in the chat transcript the assistant robot avatar icon and the Thinking (reasoning) panel do not line up.

Root cause: in `frontend/src/pages/chat/components/MessageList.tsx` the assistant avatar (`Bot20Regular`) sits inside the `.row` flex container next to the message bubble, but the reasoning `<details>` panel is rendered as a sibling block at the `<li>` level — outside `.row` — so it starts at the list-item left edge instead of aligning with the avatar/bubble column.

Proposed fix: align the reasoning panel with the bubble column (for example move it inside the bubble column or apply the same left offset as the avatar gutter). Settle the exact layout in the fix turn.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0013 — Thinking/reasoning feed never shows

Area: backend. Severity: medium. Status: open (found 2026-06-11).

Symptom: the Thinking/reasoning feed is never visible in the chat UI.

Root cause: the frontend reasoning panel in `frontend/src/pages/chat/components/MessageList.tsx` renders only while `m.streaming === true` or when `m.reasoning` has content, and its body is `m.reasoning.join("")`. The SSE handling in the chat input flow appends `reasoning` frames to `m.reasoning`, so the frontend is wired correctly — but the backend orchestrator emits no `reasoning`-channel SSE frames at runtime (the default `langgraph` orchestrator does not surface o-series reasoning), so `m.reasoning` stays empty and the panel collapses to nothing once streaming ends.

Proposed fix (direction): emit `reasoning`-channel `OrchestratorEvent`s from the orchestrator when a reasoning summary is available, so the existing frontend panel renders. Confirm in the fix turn which orchestrator(s) should surface reasoning and the source of the reasoning text.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0014 — Assistant response markdown is not converted to HTML

Area: frontend. Severity: medium. Status: open (found 2026-06-11).

Symptom: assistant answers display as raw markdown (literal `**bold**`, list markers, headings, fenced code, tables) instead of rendered HTML.

Root cause: `frontend/src/pages/chat/components/answerTokens.tsx` (`renderAnswerTokens`) only tokenizes `[docN]` citation markers and otherwise pushes raw text slices as plain strings; it performs no markdown-to-HTML conversion, and the v2 frontend has no markdown renderer dependency. v1 renders answers through `react-markdown` (`code/frontend/src/components/Answer/Answer.tsx`).

Proposed fix (direction): render the answer text through a markdown renderer (matching v1's `react-markdown` behavior) while preserving the inline `[docN]` citation tokenization. Adding a dependency is a structural change — raise it for confirmation in the fix turn (Hard Rule #10).

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0016.

### BUG-0015 — Citation/reference block should look like v1

Area: frontend. Severity: low. Status: open (found 2026-06-11).

Symptom: the reference block shown under an assistant answer does not match the v1 appearance.

Root cause: the v2 reference block is rendered by `frontend/src/pages/chat/components/CitationPanel/CitationPanel.tsx` with its own styling, which differs from the v1 citation presentation (`code/frontend/src/components/Answer/Answer.tsx` plus `Answer.module.css` `.citationContainer` and `.citation`).

Proposed fix: restyle the reference block to match v1. Settle the exact visual parity in the fix turn.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0016.

### BUG-0016 — Inline references should render like v1

Area: frontend. Severity: medium. Status: open (found 2026-06-11).

Symptom: inline citation markers inside the answer render as literal `[docN]` text buttons; v1 shows them as compact superscript citation links.

Root cause: `frontend/src/pages/chat/components/answerTokens.tsx` renders each resolved `[docN]` marker as `<button>{raw}</button>` — the literal bracket text — rather than as a v1-style superscript citation index.

Proposed fix: render resolved inline citations in the v1 style (superscript numbered links) while keeping the click-to-focus behavior. Settle the exact rendering in the fix turn.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0014, BUG-0015.

### BUG-0017 — New conversation is not saved to history

Area: backend. Severity: high. Status: open (found 2026-06-11).

Symptom: when a user starts a conversation by sending a message, the conversation does not appear in the left-hand chat history column.

Root cause: `POST /api/conversation` in `backend/routers/conversation.py` runs the orchestrator and streams the answer but performs no chat-history writes. History persistence is entirely client-driven through the separate `/api/history/*` endpoints — the only create path is the explicit New chat button in `HistoryPanel` (`handleNew` → `POST /api/history/conversations`). So a conversation begun by simply typing a first message is never persisted server-side and never appears in the history list.

Proposed fix (direction): persist the conversation and its turns as part of the conversation flow — either server-side in the conversation router or by having the chat flow create and persist a conversation on the first message. Settle the exact persistence trigger and ownership in the fix turn.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0019.

### BUG-0018 — Chat history column shows the backend database name

Area: frontend. Severity: low. Status: open (found 2026-06-11).

Symptom: the chat history left column header shows `backend: <db_type>` — the configured chat-history database discriminator.

Root cause: `frontend/src/pages/chat/components/HistoryPanel.tsx` renders `<p data-testid="history-db-type">backend: {status.db_type}</p>` from the `/api/history/status` response in the panel header.

Proposed fix: remove the `history-db-type` display from the panel header.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0019 — Remove the New chat section from the history column

Area: frontend. Severity: low. Status: open (found 2026-06-11).

Symptom: the chat history left column contains a New chat section that should be removed.

Root cause: `frontend/src/pages/chat/components/HistoryPanel.tsx` renders a New chat button (`data-testid="history-new"`) wired to `handleNew` (`POST /api/history/conversations`). Related New-chat wiring exists outside the panel — the header `HeaderTools` `onNewChat` control and the `newChatNonce` flow in `App.tsx`.

Proposed fix: remove the New chat button and `handleNew` from the history panel; decide in the fix turn whether the header New-chat affordance and the `newChatNonce` wiring are also in scope.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md); related BUG-0017.
