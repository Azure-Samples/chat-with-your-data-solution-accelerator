---
title: CWYD v2 — Bug Registry
description: Canonical defect registry for CWYD v2. Records every observed defect (wrong or broken runtime behavior) with its root cause, fix, and cross-references to the daily worklog and the development plan.
author: CWYD Engineering
ms.date: 2026-06-10
topic: reference
keywords: bugs, defects, registry, v2, root cause, regression, recovery
estimated_reading_time: 6
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
