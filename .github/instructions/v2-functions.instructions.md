---
description: "CWYD v2 Azure Functions conventions for the modular RAG indexing pipeline. Use when: editing v2/src/functions/**, adding a blueprint, adding a blob/queue/event-grid trigger, wiring an embedder, handling poison messages, registering a function in function_app.py, or building the batch_start / batch_push / add_url / search_skill pipeline."
applyTo: "v2/src/functions/**"
---

# v2 Azure Functions Conventions

## Stack

- Python 3.11, `azure-functions` ≥ 1.24, async function model where supported.
- Triggers: Blob (Event Grid source), Queue, HTTP. No timer triggers in v2 unless explicitly planned.
- Dependencies installed via `uv` against `v2/src/functions/pyproject.toml`.

## Layout

- `function_app.py` — sole registration entry; imports blueprints and `app.register_functions(bp)`.
- `blueprints/<name>.py` — one trigger per file. Files: `batch_start.py`, `batch_push.py`, `add_url.py`, `search_skill.py`.
- Pluggable logic is consumed via the registries in `v2/src/backend/core/providers/`. Specifically: parsers via `from backend.core.providers.parsers import registry as parsers_registry; parsers_registry.registry.get(ext)()`, embedders via `from backend.core.providers.embedders import registry as embedders_registry; embedders_registry.registry.get(key)(...)`, search via `from backend.core.providers.search import registry as search_registry; search_registry.registry.get(key)(...)`. Composition lives in `v2/src/backend/core/pipelines/ingestion.py` — blueprints invoke the pipeline, they do not duplicate parse/chunk/embed logic.

## Rules

1. **One trigger per file.** No multi-trigger blueprints.
2. **Idempotent.** Every handler computes a deterministic message key and skips if the key is already processed (track in a small `processing_state` table or blob metadata).
3. **Poison handling.** Always wrap the handler body in `try/except`; on failure, log with `exc_info=True` and re-raise so the runtime moves the message to `<queue>-poison`. Never silently swallow.
4. **No direct OpenAI SDK.** Embedders + LLM access go through the provider registry: `from backend.core.providers.embedders import registry as embedders_registry; embedders_registry.registry.get(settings.database.index_store)(...)` (and same shape for `providers.llm`). No module-level clients, no `from openai import …`.
5. **Settings.** Reuse `v2/src/backend/core/settings.py::AppSettings` via `get_settings()` — do not reinvent env loading.
6. **Pluggability.** Use the registry pattern from `v2/src/backend/core/registry.py`. Forbidden: `if/elif` over backend names (e.g. `if db_type == "cosmosdb": ...`) inside a blueprint — call `<domain>_registry.registry.get(key)(**kwargs)` instead. Per Hard Rule #13, provider `__init__.py` files are package markers — registry instances live in sibling `registry.py`. No `create()` factory wrappers.
7. **Tests.** Every blueprint has a sibling `tests/test_<name>.py` that invokes the handler with a constructed `func.QueueMessage` / `func.EventGridEvent` and asserts the side effects (pipeline called, queue message produced, etc.).

## Pipeline contract

```
Blob created/deleted → Event Grid → storage queue "doc-processing" → batch_start
batch_start → enqueue per-document messages → "doc-chunks" queue → batch_push
batch_push → parse + chunk + embed (FoundryIQ) + index (AzureSearch or pgvector)
add_url → HTTP trigger; same parse/embed/index path as batch_push
search_skill → HTTP trigger; called by AI Search custom skill, returns enrichments
```

## Resilience

Per `.github/copilot-instructions.md` Hard Rule #14 (SDK boundary resilience): every external SDK call inside a blueprint is wrapped in `try/except <SDK error umbrella>` with structured logging + re-raise. Functions has two trigger surfaces with distinct re-raise contracts. The decorators in `v2/src/functions/core/exception_mapping.py` own the outer translation; application code owns the narrow per-operation log lines.

**Queue triggers** — return `None`, re-raise on failure, wrap with `@log_queue_errors("<op_name>")`. The host's retry policy applies (default `maxDequeueCount=5` in `host.json`); after exhaustion the message lands on `<queue>-poison`.

```python
@app.queue_trigger(arg_name="msg", queue_name="doc-chunks", connection="AzureWebJobsStorage")
@log_queue_errors("batch_push")
async def batch_push(msg: func.QueueMessage) -> None:
    envelope = parse_push_message(msg)
    try:
        await batch_push_handler(envelope, search_writer=client, ...)
    except AzureError:
        logger.exception(
            "batch_push pipeline failed",
            extra={"operation": "batch_push", "document_id": envelope.document_id},
        )
        raise
```

**HTTP triggers** — always return `func.HttpResponse`, wrap with `@map_function_exceptions("<op_name>")`. The decorator owns the `ValidationError` → 422 / `AzureError` → 502 / `Exception` → 500 ladder. Application code re-raises so the decorator can translate.

```python
@app.route(route="add_url", methods=["POST"])
@map_function_exceptions("add_url")
async def add_url(req: func.HttpRequest) -> func.HttpResponse:
    body = read_json_body(req, AddUrlRequest)
    try:
        bytes_ = await fetch_url(body.url)
    except httpx.HTTPError:
        logger.exception("fetch_url failed", extra={"operation": "fetch_url", "url": body.url})
        raise
    return json_response({"status": "queued"}, status=202)
```

**Three obligations** (identical to backend-core §Resilience):

1. `logger.exception(...)` — captures the traceback.
2. Structured `extra={"operation": ..., "provider": ..., ...}` — snake_case keys.
3. Re-raise — bare `raise`, or `raise DomainError(...) from exc`. Silent excepts are AST-banned by `v2/tests/shared/test_no_silent_excepts.py`.

**Idempotency is mandatory** — because the retry loop replays the queue message, every handler computes a deterministic key (document hash, blob path + ETag, URL + timestamp) and short-circuits if already processed. The retry policy is only safe if side effects are repeat-safe.

**Module-level clients are forbidden** — build storage/queue/search clients per-invocation from `backend.core.providers.storage` factories (or via `Depends`-style injection where applicable). The Functions host instantiates the module once but invocations are concurrent; module-level state is a sharing hazard.

## Typing standard

Same discipline as `.github/instructions/v2-backend-core.instructions.md` §Typing standard. `pyright --strict` runs on `v2/src/functions/core/**` with 0/0/0 CI target (blueprint surface code under `v2/src/functions/<blueprint>/**` is on `basic` mode pending Phase 6 close-out per `v2/pyproject.toml`).

**Boundary classification for `Any`** (the only permitted use sites in blueprints):

| Class | Functions-side example | Why permitted |
|---|---|---|
| **SDK response shape kept loose** | `payload: dict[str, Any] = json.loads(msg.get_body())` | `azure.functions` `QueueMessage.get_body()` returns `bytes`; the decoded payload shape is set by the producer blueprint — narrow via the cross-blueprint Pydantic envelope in `functions/core/contracts.py`. |
| **Pydantic extensibility field** | `metadata: dict[str, Any]` on `BatchPushQueueMessage`, ingestion envelopes | Open-shape extension point for downstream blueprints. |
| **`azure.functions` runtime types** | `req: func.HttpRequest`, `msg: func.QueueMessage`, `func.HttpResponse(...)` | Already typed by the SDK — use them as-is, never widen. |

**Forbidden:**

- `Any` in handler return types — must be `None` (queue) or `func.HttpResponse` (HTTP).
- `Any` in cross-blueprint queue-envelope fields — declare a Pydantic model in `functions/core/contracts.py` (or backend-core for shared shapes).
- `Any` returned from `backend.core.providers.*` registry lookups inside a blueprint — the provider Protocol gives you the typed surface; cast only at the explicit SDK-Protocol mismatch (one of the known U8i debt rows).

**`cast(...)` and `# pyright: ignore` discipline** is identical to backend-core: inline comment naming the SDK boundary OR map to a tracked §0.1 debt row in `v2/docs/development_plan.md`. Today's Functions-side debt rows are `U8i-EMBEDDER-CTOR-DEBT` and `U8i-SEARCH-WRITER-PROTOCOL-DEBT`.

## Banned

- Synchronous HTTP calls (`requests`).
- `from openai import …`.
- Reading env vars directly with `os.environ[...]` outside of `AppSettings`.
- Storing secrets in env vars (use Managed Identity + RBAC).
