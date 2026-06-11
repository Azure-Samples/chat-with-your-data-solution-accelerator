---
title: CWYD v2 — Bug Registry
description: Canonical defect registry for CWYD v2. Records every observed defect (wrong or broken runtime behavior) with its root cause, fix, and cross-references to the daily worklog and the development plan.
author: CWYD Engineering
ms.date: 2026-06-11
topic: reference
keywords: bugs, defects, registry, v2, root cause, regression, recovery
estimated_reading_time: 9
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
| BUG-0003 | 2026-06-11 | — | backend | high | open | `GET /api/admin/documents` returns `503` when the deployment has no search endpoint configured, because the lifespan leaves the search provider unset. |
| BUG-0004 | 2026-06-11 | — | frontend | medium | open | The admin Orchestrator field is a free-text input; it should be a dropdown of the known orchestrator keys. |
| BUG-0005 | 2026-06-11 | — | frontend | low | open | The admin Configuration labels show internal config-key names such as `(orchestrator_name)`. |
| BUG-0006 | 2026-06-11 | — | backend | medium | open | Content Safety defaults to disabled; it should default to enabled. |
| BUG-0007 | 2026-06-11 | — | backend | medium | open | The default agent instructions do not carry the vetted v1 default prompt text. |
| BUG-0008 | 2026-06-11 | — | frontend | medium | open | The separate Prompt editor page should be removed and folded into the Configuration page, matching v1. |

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

### BUG-0003 — Admin documents endpoint returns 503 when no search endpoint is configured

Area: backend. Severity: high. Status: open (found 2026-06-11).

Symptom: `GET /api/admin/documents` returns `503 Service Unavailable`, so the admin Delete data grid cannot list indexed sources.

Root cause: when `index_store` is `azure_search` and `settings.search.endpoint` is empty, the FastAPI lifespan in `backend/app.py` leaves `app.state.search_provider` as `None` (the intended pass-through mode for the backend-only dev profile). The `get_search_provider` dependency in `backend/dependencies.py` then returns `None`, and `list_documents_endpoint` in `backend/routers/admin.py` raises `HTTPException(503)`. Any environment without an Azure AI Search endpoint breaks the admin documents list.

Proposed fix (direction, to be settled in the fix turn): if the environment is expected to have search, correct the endpoint configuration or injection so the provider is constructed; if pass-through is a valid state, the endpoint should degrade gracefully — return an empty `ListDocumentsResponse` with a clear "search not configured" signal the admin UI can render — instead of a hard `503`.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0004 — Orchestrator field is free text instead of a dropdown

Area: frontend. Severity: medium. Status: open (found 2026-06-11).

Symptom: on the admin Configuration page the Orchestrator field is a single-line text input, so an operator can type an invalid key and save it.

Root cause: `orchestrator_name` is declared as a text field in the `FIELD_SPECS` array in `frontend/src/pages/admin/Configuration/Configuration.tsx`; there is no select control bound to the known orchestrator keys.

Proposed fix: render a dropdown sourced from the first-party orchestrator keys `langgraph` and `agent_framework` (the `OrchestratorName` enum in `backend/core/settings.py`, registered in `backend/core/providers/orchestrators/registry.py`). Decide in the fix turn whether to keep a free-text escape hatch for third-party registered keys, since the settings type is widened to `OrchestratorName | str`.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0005 — Admin configuration labels show internal config-key names

Area: frontend. Severity: low. Status: open (found 2026-06-11).

Symptom: every field label on the admin Configuration page appends the raw config key in parentheses, for example "Orchestrator (orchestrator_name)" and "Content safety (content_safety_enabled)".

Root cause: the label rendering in `frontend/src/pages/admin/Configuration/Configuration.tsx` appends each field spec's key to its human-readable label.

Proposed fix: render the human-readable label only and drop the parenthetical config-key suffix.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0006 — Content Safety defaults to disabled

Area: backend. Severity: medium. Status: open (found 2026-06-11).

Symptom: Content Safety starts disabled by default, so the input pre-filter does not run unless an operator opts in.

Root cause: `ContentSafetySettings.enabled` defaults to `False` in `backend/core/settings.py`, a deliberate opt-in. Production infrastructure already sets `AZURE_CONTENT_SAFETY_ENABLED` to `true` in Bicep, and the lifespan activates the client only when both `enabled` is true and an endpoint is set; the shipped `.env.sample` leaves it `false`.

Proposed fix: change the default to `True`. This is safe because the lifespan gates the client on both `enabled` and a configured endpoint — with no endpoint the client stays `None` and the guard is inert. Confirm the intent in the fix turn before flipping the default.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0007 — Default agent instructions do not carry the v1 default prompt text

Area: backend. Severity: medium. Status: open (found 2026-06-11).

Symptom: the v2 default system prompt does not reflect the vetted default answering prompt that v1 ships.

Root cause: the v1 default prompt text lives in `code/backend/batch/utilities/helpers/config/default.json` (the `answering_system_prompt` and `answering_user_prompt` keys). v2 defines its built-in instructions as `CWYD_AGENT` in `backend/core/agents/definitions.py` and never ported the v1 default text.

Proposed fix: port only the v1 default answering prompt text into the v2 `CWYD_AGENT` instructions default, adapted to v2's single-instructions model. The v1 per-business-unit assistant-type system (Default, Contract assistant, Employee assistant) is out of scope.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).

### BUG-0008 — Separate Prompt editor page should fold into Configuration

Area: frontend. Severity: medium. Status: open (found 2026-06-11).

Symptom: v2 exposes a dedicated Prompt editor page, whereas v1 edits all prompts inline on a single Configuration page.

Root cause: the prompt-editor route was added during the `#35d` admin merge. `frontend/src/pages/admin/PromptEditor/PromptEditor.tsx` is wired through `frontend/src/models/sections.tsx` (the `AdminPrompt` section and its `/admin/prompt` route), `frontend/src/App.tsx` (the route element), `frontend/src/pages/admin/AdminLayout.tsx`, and the header nav — built as v1 parity, but v1 has no separate editor.

Proposed fix: move editing of `cwyd_agent_instructions` into the Configuration page field set, then remove the Prompt editor page, its route, its nav entries, and its tests. Update the `#35d` and `U-P7-PROMPT` trail in the development plan in the fix turn.

References: [worklog/2026-06-11.md](worklog/2026-06-11.md).
