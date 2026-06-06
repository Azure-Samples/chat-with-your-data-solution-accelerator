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

## Resilience

Per `.github/copilot-instructions.md` Hard Rule #14 (SDK boundary resilience): every external SDK call inside a Functions blueprint, helper, or extension class is wrapped in `try/except <SDK error umbrella>` with structured logging + the trigger-type-specific re-raise contract. Functions has two trigger surfaces; each has a distinct contract.

**Queue trigger contract** — the handler must return `None` and re-raise on failure so the Functions host's retry → poison-queue policy engages. The `@log_queue_errors("<op_name>")` decorator in `v2/src/functions/core/exception_mapping.py` (U7i) owns the boundary: it wraps the handler body in `try/except Exception as exc: logger.exception("<op_name> queue handler failed", extra={"operation": "<op_name>", ...}); raise`. Application code inside the handler still wraps its own SDK calls in narrow `except AzureError` / `except asyncpg.PostgresError` blocks with operation-specific `extra=` keys; the decorator is the outer safety net, not the only line of defense.

```python
@app.queue_trigger(arg_name="msg", queue_name="doc-chunks", connection="AzureWebJobsStorage")
@log_queue_errors("batch_push")
async def batch_push(msg: func.QueueMessage) -> None:
    envelope = parse_push_message(msg)
    try:
        await batch_push_handler(envelope, search_writer=search_client, ...)
    except AzureError:
        logger.exception(
            "batch_push pipeline failed",
            extra={"operation": "batch_push", "document_id": envelope.document_id},
        )
        raise
```

**HTTP trigger contract** — the handler must always return `func.HttpResponse` (never raise into the host, never `return None`). The `@map_function_exceptions("<op_name>")` decorator in `v2/src/functions/core/exception_mapping.py` (U7 series) owns the `ValidationError` → 422 / `AzureError` → 502 / `Exception` → 500 ladder per `v2/docs/exception_handling_policy.md` §"Functions blueprints". Application code inside the handler still wraps SDK calls in narrow excepts so the structured `extra=` log line fires at the boundary; the decorator translates uncaught exceptions into the right `HttpResponse` shape.

```python
@app.route(route="add_url", methods=["POST"])
@map_function_exceptions("add_url")
async def add_url(req: func.HttpRequest) -> func.HttpResponse:
    body = read_json_body(req, AddUrlRequest)  # raises ValidationError → 422
    try:
        bytes_ = await fetch_url(body.url)
    except httpx.HTTPError:
        logger.exception("fetch_url failed", extra={"operation": "fetch_url", "url": body.url})
        raise  # decorator translates to 502
    return json_response({"status": "queued"}, status=202)
```

**Three obligations stay identical** to backend-core (logger.exception + structured `extra=` with `operation` + `provider`/domain keys + re-raise). The trigger-type contracts above just set how the re-raise reaches the host.

**Silent excepts are forbidden** under the same `v2/tests/shared/test_no_silent_excepts.py` AST gate that covers backend code.

**Idempotency is the resilience pair to retries.** Because queue triggers re-deliver on failure, every blueprint handler must compute a deterministic message key (document hash, blob path, URL+timestamp) and skip if already processed. The retry loop is correctness only if the side effects are safe to repeat.

## Typing standard

Same discipline as `.github/instructions/v2-backend-core.instructions.md` §Typing standard. `pyright --strict` runs on `v2/src/functions/core/**` with 0/0/0 CI target. Boundary classification for `Any`:

| Class | Functions-side example | Why permitted |
|---|---|---|
| **SDK response shape kept loose** | `data: dict[str, Any] = blob_client.download_blob().readall_json()` | azure-storage / azure-functions returns dicts shaped by the SDK; narrow at the use site if a Pydantic envelope exists. |
| **Pydantic extensibility field** | `metadata: dict[str, Any]` on `BatchPushQueueMessage`, ingestion envelopes, `IngestionEvent` | Open-shape extension point for downstream blueprints; consumers narrow at use site. |
| **`azure.functions` runtime types** | `req: func.HttpRequest`, `msg: func.QueueMessage`, `func.HttpResponse(body, status_code=...)` | These ARE the typed boundary; `func.*` symbols carry their own pyright stubs and need no `Any`. Do NOT widen them. |

**Forbidden** in `functions/core/**`: `Any` in handler return types (must be `None` for queue, `func.HttpResponse` for HTTP), `Any` in cross-blueprint queue-envelope fields (declare a Pydantic model in `functions/core/contracts.py` instead), `Any` in storage-client factory return types (the SDK provides typed factories — use them).

**`cast(...)` / `# pyright: ignore` discipline** is identical to backend-core: inline comment naming the SDK boundary OR map to a tracked §0.1 debt row in `v2/docs/development_plan.md`. The known Functions-side debt rows today are `U8i-EMBEDDER-CTOR-DEBT` and `U8i-SEARCH-WRITER-PROTOCOL-DEBT` (both ride on the search-writer Protocol boundary).

## Banned (mirrors v2-backend-core)

- `from openai import …` anywhere in `v2/src/functions/core/**` — Foundry IQ via `backend.core.providers.llm` only.
- `semantic_kernel`, `promptflow`.
- Module-level `client = SomeClient(...)`.
- Sync DB drivers (`psycopg2`) on runtime paths; `asyncpg` only.
- `if/elif` over provider names — call `<domain>_registry.registry.get(key)(**kwargs)` from `backend.core.providers.<domain>.registry`.
- `from __future__ import annotations` and `if TYPE_CHECKING:` (banned across all of `v2/`; CU-013 amendment).
- Any runtime code in an `__init__.py` (Hard Rule #13 — package markers only; registry instances + eager imports live in sibling `registry.py`).
- **Re-defining a symbol that already lives in `backend.core`.** If you find yourself doing this, the right move is to import from `backend.core` (or extract a leaf module under `backend.core/`) — not to copy-paste.

## Tests

Tests for `functions/core/**` mirror the source tree at `v2/tests/functions/core/**`. They follow the same conventions as `v2/tests/backend/core/**` — see [`v2-tests.instructions.md`](v2-tests.instructions.md) for fixture patterns, mock strategy, and SSE-event assertion helpers.
