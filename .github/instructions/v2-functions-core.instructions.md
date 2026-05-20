---
description: "CWYD v2 functions/core conventions — ingestion-only code, backend.core extensions, AND Functions-only runtime helpers (HTTP response shaping, exception mapping decorators, cross-blueprint wire contracts). Use when: editing v2/src/functions/core/**; adding an ingestion-only parser or chunker subclass; extending a backend.core provider with blob/queue-storage tracking; wiring a Functions blueprint that reuses backend.core machinery; adding a Functions-runtime helper that wraps azure.functions types or carries a queue envelope."
applyTo: "v2/src/functions/core/**"
---

# v2 functions/core Conventions

`functions/core/` is the **opt-in shared layer** for code that is needed only when an operator runs the Functions container (i.e. when they want CWYD to ingest and index their own files). The backend container runs **without** any code from this folder — that is the binding "backend is standalone" invariant introduced by the Phase 5.5 refactor.

**There is no `functions/_shared/` folder.** All cross-blueprint helpers that are Functions-only live here under `functions/core/`. Any helper that backend could also use lives in `backend/core/` and gets imported from there. This is the single decision rule that keeps the codebase from duplicating storage clients, settings access, or any other primitive.

## Anti-duplication invariant (binding)

> **No symbol is defined twice.** If a parser, chunker, embedder, or any other building block is needed by both backend (chat) and functions (ingestion), it lives in `v2/src/backend/core/` and `functions/core/` imports it. `functions/core/` only exists for ingestion-side code that backend has no use for, or for thin extension classes that subclass a `backend.core` base.

This means every file under `functions/core/` should fall into one of three shapes:

1. **Ingestion-only** — code with no chat-time consumer (e.g. a blob-storage URI tracker that records source URLs onto chunks for the indexer queue). Imports from `backend.core` freely; nothing in `backend.core` imports back.
2. **Extension subclass** — a subclass of a `backend.core` base that adds ingestion-specific behavior (e.g. a `BaseParser` subclass that emits per-page provenance metadata the chat path discards). The base class stays in `backend.core`; only the subclass lives here.
3. **Functions-runtime helper** — a helper that wraps `azure.functions` types (`HttpRequest`, `HttpResponse`, `Blueprint`, `FunctionApp`) or carries a Functions-only wire contract (queue envelope, blueprint-to-blueprint message), with no chat-time consumer. Examples: `json_response()` for `func.HttpResponse`, an `@map_function_exceptions(...)` decorator that owns the 422/502/500 ladder, a `BatchPushQueueMessage` Pydantic envelope shared by `batch_start` (producer) and `batch_push` (consumer). These are NOT backend.core extensions — they exist because the Functions runtime has its own request/response surface that FastAPI does not.

## Where files live (the four-rule decision tree)

| Use case | Destination | Why |
|---|---|---|
| Used **only** by backend at chat/query time | `v2/src/backend/core/` | Backend stays standalone. |
| Used **only** by functions for ingestion | `v2/src/functions/core/` | Functions-specific; backend has no need to load it. |
| Used by **both** backend and functions | `v2/src/backend/core/` (functions imports it) | Single source of truth; backend container is the always-on consumer, so the canonical home is there. |
| Used **only** by functions but extends a `backend.core` library | `v2/src/functions/core/` (subclass) + base in `backend.core` | Extension lives where it is consumed; base stays where it is shared. |
| Wraps `azure.functions` types or carries a queue envelope shared across blueprints | `v2/src/functions/core/` | Functions-runtime surface FastAPI does not have; nothing for backend to consume. |

**Tie-breaker for storage/messaging clients**: anything that builds a `ContainerClient` / `QueueClient` / `CosmosClient` / `BlobClient` from a credential + endpoint is **storage-account math + SDK plumbing**, not Functions-specific. It lives in `backend/core/providers/storage/` (or the equivalent provider domain) and Functions blueprints import it. Do not put `client_factory`-style code under `functions/core/`.

## Phase 5.5 → Phase 6 status

`functions/core/` shipped **empty** at the end of Phase 5.5. The first concrete contents land in **Phase 6** (RAG indexing pipeline) when the modular blueprints (`batch_start`, `batch_push`, `add_url`, `search_skill`) need shared Functions-side helpers. The Phase 6 U7 unit series stands up:

* `functions/core/contracts.py` — cross-blueprint wire contracts (queue envelopes, ingestion job ids).
* `functions/core/http.py` — `json_response()`, `read_json_body()`, status constants for `func.HttpResponse`.
* `functions/core/exception_mapping.py` — `@map_function_exceptions("op_name")` decorator that owns the `ValidationError` → 422 / `AzureError` → 502 / `Exception` → 500 ladder per `v2/docs/exception_handling_policy.md` §"Functions blueprints".

Storage-side primitives (`resolve_storage_endpoints()`, `storage_clients()` async context manager) do **not** live here — they land under `v2/src/backend/core/providers/storage/` so backend can also consume them. Do not seed this folder with placeholder modules beyond the U7 set.

## Pillar header (binding)

Every `.py` under `functions/core/` opens with the standard CWYD pillar header docstring:

```
"""<one-line module purpose>.

Pillar: <Stable Core | Scenario Pack | Configuration Layer | Customization Layer>
Phase: <6 or later>
"""
```

Most files here will be **Stable Core** (the indexing pipeline is part of the always-needed-when-RAG-is-on layer); ingestion-side scenario customizations are **Scenario Pack**.

## Pyright strict (binding)

`functions/core/**` is on `pyright --strict` from day one (`v2/pyproject.toml` `[tool.pyright]` `strict` block). This is non-negotiable per the Phase 5.5 decision: the standalone-functions image must hold the same type-safety bar as the standalone-backend image.

## Banned (mirrors v2-backend-core)

- `from openai import …` anywhere in `v2/src/functions/core/**` — Foundry IQ via `backend.core.providers.llm` only.
- `semantic_kernel`, `promptflow`.
- Module-level `client = SomeClient(...)`.
- Sync DB drivers (`psycopg2`) on runtime paths; `asyncpg` only.
- `if/elif` over provider names — call the registry from `backend.core.providers.<domain>`.
- `from __future__ import annotations` and `if TYPE_CHECKING:` (banned across all of `v2/`; CU-013 amendment).
- **Re-defining a symbol that already lives in `backend.core`.** If you find yourself doing this, the right move is to import from `backend.core` (or extract a leaf module under `backend.core/`) — not to copy-paste.

## Tests

Tests for `functions/core/**` mirror the source tree at `v2/tests/functions/core/**`. They follow the same conventions as `v2/tests/backend/core/**` — see [`v2-tests.instructions.md`](v2-tests.instructions.md) for fixture patterns, mock strategy, and SSE-event assertion helpers.
