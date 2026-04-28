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
- Pluggable logic is consumed via the registries in `v2/src/shared/providers/`. Specifically: parsers via `providers.parsers.create(...)`, embedders via `providers.embedders.create(...)`, search via `providers.search.create(...)`. Composition lives in `v2/src/shared/pipelines/ingestion.py` — blueprints invoke the pipeline, they do not duplicate parse/chunk/embed logic.

## Rules

1. **One trigger per file.** No multi-trigger blueprints.
2. **Idempotent.** Every handler computes a deterministic message key and skips if the key is already processed (track in a small `processing_state` table or blob metadata).
3. **Poison handling.** Always wrap the handler body in `try/except`; on failure, log with `exc_info=True` and re-raise so the runtime moves the message to `<queue>-poison`. Never silently swallow.
4. **No direct OpenAI SDK.** Embedders go through `providers.embedders.create(settings.database.index_store, ...)`; LLM access goes through `providers.llm.create("foundry_iq", ...)`. No module-level clients, no `from openai import …`.
5. **Settings.** Reuse `v2/src/shared/settings.py::AppSettings` via `get_settings()` — do not reinvent env loading.
6. **Pluggability.** Use the registry pattern from `v2/src/shared/registry.py`. Forbidden: `if/elif` over backend names (e.g. `if db_type == "cosmosdb": ...`) inside a blueprint — call `domain.create(key, ...)` instead.
7. **Tests.** Every blueprint has a sibling `tests/test_<name>.py` that invokes the handler with a constructed `func.QueueMessage` / `func.EventGridEvent` and asserts the side effects (pipeline called, queue message produced, etc.).

## Pipeline contract

```
Blob created/deleted → Event Grid → storage queue "doc-processing" → batch_start
batch_start → enqueue per-document messages → "doc-chunks" queue → batch_push
batch_push → parse + chunk + embed (FoundryIQ) + index (AzureSearch or pgvector)
add_url → HTTP trigger; same parse/embed/index path as batch_push
search_skill → HTTP trigger; called by AI Search custom skill, returns enrichments
```

## Banned

- Synchronous HTTP calls (`requests`).
- `from openai import …`.
- Reading env vars directly with `os.environ[...]` outside of `AppSettings`.
- Storing secrets in env vars (use Managed Identity + RBAC).
