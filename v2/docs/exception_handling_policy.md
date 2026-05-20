# Exception handling policy (v2)

> **Pillar:** Stable Core (cross-cutting policy)
> **Phase:** 5.5 (Phase C — Try/catch policy + sweep)
> **Status:** Authoritative. New `try/except` blocks in `v2/src/**` MUST follow the layer table below.

This doc captures the per-layer try/except contract for v2. It is the policy artifact landed in Phase C sub-unit C1; the mechanical sweeps in C2–C4 implement it. Phase 6 picks it up for `functions/core/**` (C5 deferred). It is enforced by:

1. **Reviewers** — code review consults this table.
2. **AST invariant** — [v2/tests/no_silent_excepts.py](../tests/no_silent_excepts.py) fails CI on banned constructs.
3. **Test-first contract** (Hard Rule #2 in [.github/copilot-instructions.md](../../.github/copilot-instructions.md)) — every new `try/except` block ships with a failure-path test that drives the exception branch.

## Why this policy exists

User report (2026-05-06): *"I noticed lack of try/catch, and with that we can debug better when something goes wrong."* The codebase had ample `await client.X(...)` calls with no narrow SDK catch, so the first failure mode was an unhelpful 500 with a SDK stack trace bubbling all the way up to the FastAPI default handler. The policy below standardizes how each layer wraps its calls so:

- **Provider failures stay observable** — narrow SDK catches log structured context (deployment, operation) at the boundary.
- **Routers stay safe** — top-level handlers convert domain exceptions to sanitized `HTTPException` (no PII / stack-trace leakage).
- **Pipelines stay alive** — SSE generators never silently die mid-stream; errors flow as `OrchestratorEvent(channel=ERROR, ...)` events for the FE reasoning panel.
- **Lifespan stays loud** — startup failures re-raise so the container restart loop is the recovery path.

## Layer policy

| Layer | Catch policy | Log policy | Re-raise / surface |
|---|---|---|---|
| **Provider entry points** (`backend/core/providers/**/*.py` public methods) | Catch narrow SDK exceptions (`CosmosResourceNotFoundError`, `HttpResponseError`, `asyncpg.PostgresError`, `openai.APIError`, `azure.core.exceptions.AzureError`); let unknown propagate. | `logger.exception(msg, extra={"deployment": ..., "operation": ...})` — pyright-strict + structured. | Re-raise as the same SDK exception (preserves stack) OR convert to a typed domain exception (`OrchestratorError`, `DatabaseError`) when SDK noise leaks into the API surface. |
| **Routers** (`backend/routers/**.py` handlers) | Top-level `try/except` per handler OR app-level `add_exception_handler` for cross-cutting upstream SDK errors (preferred when the same status-code mapping repeats across N handlers); catch domain exceptions + `Exception` as a final safety net (with `# noqa: BLE001 -- final safety net for handler X`). | `logger.exception(...)` with `request.method`, `request.url.path`, `user_id`, `correlation_id`. | Convert to sanitized `HTTPException(status_code=...)` (or `JSONResponse` from an app-level handler) -- never leak SDK payloads (PII risk) or stack traces. |
| **Pipelines** (`backend/core/pipelines/chat.py` async generators) | `try/except` inside the generator body; never let an unhandled exception kill the SSE stream silently. | `logger.exception(...)` + emit `OrchestratorEvent(channel=ERROR, ...)` for the FE reasoning panel. | `yield` the error event; do not re-raise (would 500 the SSE response mid-stream). |
| **Lifespan** (`backend/app.py::_lifespan`) | Catch + re-raise with the failing provider name in the message. Best-effort cleanup paths during shutdown may use broad `except Exception` with `# noqa: BLE001 -- shutdown is best-effort`. | `logger.exception("startup failed: <provider>", ...)`. | Re-raise on startup; swallow + log on shutdown. Startup failure must be loud; container restart loop is the recovery path. |
| **Functions blueprints** (`functions/core/**` triggers, Phase 6+) | Top-level `try/except` per trigger; specific catches for Storage / Cosmos / OpenAI errors before the catch-all. | `logger.exception(...)` (Functions runtime auto-pipes to App Insights). | Escalate to poison queue per Functions retry policy; do not raise generic `Exception` (kills the worker). |

## Cross-cutting rules

These apply to every layer and are enforced by [v2/tests/no_silent_excepts.py](../tests/no_silent_excepts.py):

- **Banned: silent swallow.** `except <anything>: pass` (or `except <anything>: ...` whose body is exactly one `pass` / `Ellipsis` / docstring) is banned everywhere under `v2/src/**`. If you genuinely want to ignore an exception, log it (`logger.debug("ignoring X: %s", exc)`) so the decision is visible.
- **Banned: `except BaseException`.** Catches `KeyboardInterrupt` and `SystemExit`, hangs Ctrl-C, breaks process management. Always wrong in v2/.
- **Discouraged: bare `except:`.** Same problem as `BaseException`. Banned by Ruff `E722`; reinforced here.
- **Discouraged: broad `except Exception` without a `# noqa: BLE001 -- <reason>` comment.** The `noqa` is the explicit opt-out marker that tells reviewers "this catch is intentional, here's why." Code without the marker should catch a narrow, documented SDK exception type.

### Known pending exemptions (cleared during Phase C sweep)

The AST invariant test ([v2/tests/no_silent_excepts.py](../tests/no_silent_excepts.py)) now holds **0 exemptions**. Phase C closed both pre-policy sites:

- C2 closure removed `v2/src/backend/core/providers/databases/cosmosdb.py` -- inner per-message `CosmosResourceNotFoundError` catch now logs the idempotent skip via `logger.debug` with both message id and conversation id in the structured payload.
- C3 closure removed `v2/src/backend/core/pipelines/chat.py` line 143 -- malformed-citation `pass` replaced with `logger.debug("ignoring malformed citation metadata", extra={"operation": "citation_parse", "pipeline": "chat", "citation_id": cid, "error": str(exc)})`. The cited document still streams to the SSE consumer as the original orchestrator event (only post-prompt grounding loses that one source).

C2 sweep coverage by sub-unit:

- C2a: `cosmosdb.py` silent-swallow removal.
- C2b: `cosmosdb.py` 7 SDK boundaries wrapped (read / upsert / delete / patch).
- C2c: `postgres.py` 9 SDK boundaries wrapped (`asyncpg.PostgresError` umbrella).
- C2d: `foundry_iq.py` 8 + `azure_search.py` 2 = 10 SDK boundaries wrapped.
- C2e: `agents/base.py` 2 + `agents/foundry.py` 1 = 3 SDK boundaries wrapped. `get_agent` keeps the existing `ResourceNotFoundError` orphan-recovery branch FIRST in the except ladder; the added `AzureError` branch surfaces non-404 failures (auth, transport, 5xx). `create_agent` adds the umbrella catch with deployment + agent name in extras. `aclose` widens to `(AzureError, OSError)` and downgrades to `logger.warning` per shutdown policy.

After C3, silent swallow and `except BaseException` are unconditionally banned across `v2/src/**`. Adding a new entry to `_EXEMPTIONS` is **not the right escape hatch** -- fix the construct.

## Required pattern

Every new `try/except` block lands with a test that drives the exception path:

```python
# v2/src/backend/core/providers/databases/cosmosdb.py
async def get_item(self, item_id: str) -> dict[str, Any]:
    try:
        return await self._container.read_item(item_id, partition_key=item_id)
    except CosmosResourceNotFoundError:
        logger.exception(
            "cosmos read_item not found",
            extra={"item_id": item_id, "container": self._container_name},
        )
        raise  # let router map to 404
```

```python
# v2/tests/backend/core/providers/databases/test_cosmosdb.py
async def test_get_item_not_found_logs_and_reraises(caplog) -> None:
    fake_container = FakeContainer(read_raises=CosmosResourceNotFoundError(...))
    provider = CosmosProvider(container=fake_container)
    with pytest.raises(CosmosResourceNotFoundError):
        await provider.get_item("missing-id")
    assert "cosmos read_item not found" in caplog.text
```

## Logger setup (mandatory)

Use the OTel-instrumented logger configured in [v2/src/backend/app.py](../src/backend/app.py) so traces flow to App Insights via `azure-monitor-opentelemetry` (wired by Q14d in the old plan). Do **not** instantiate `logging.getLogger(__name__)` ad-hoc inside helper modules without going through the wiring described in [v2/docs/observability.md](observability.md) (if/when that doc lands; until then follow the imports already in `backend/app.py`).

## How to add a new try/except (developer checklist)

1. Identify the layer (provider / router / pipeline / lifespan / functions).
2. Pick the narrowest exception type from the SDK / domain that you actually want to handle.
3. Write the failing test first (Hard Rule #2): drive the exception path, assert on the log message + the surface (re-raise / `HTTPException` / SSE error event).
4. Add the `try/except` with the layer-appropriate log call + surface.
5. Run `uv run pytest -q` and `uv run pyright`. Both must pass.
6. If the AST invariant test ([v2/tests/no_silent_excepts.py](../tests/no_silent_excepts.py)) fails, fix the construct — do **not** add the file to its exemption list (the list is empty by design).

## Existing intentional catches (as of Phase C close)

The following 9 broad `except Exception` blocks are intentional and pre-date this policy. All carry `# noqa: BLE001` with rationale:

- `v2/src/backend/app.py` lines 142, 146, 150, 154, 158 — best-effort cleanup paths in `_lifespan` shutdown branch.
- `v2/src/backend/app.py` `_unhandled_exception_handler` (Phase C4 — final safety net for app-level dispatch; logs full `exc_info` and returns sanitized 500).
- `v2/src/backend/routers/conversation.py` line 80 — top-level handler safety net (surfaced to client SSE channel).
- `v2/src/backend/core/pipelines/chat.py` line 146 — malformed citation metadata is non-fatal; pipeline keeps streaming and the failure is logged at DEBUG via `logger.debug("ignoring malformed citation metadata", extra={...})` (Phase C3 closure).
- `v2/src/backend/core/providers/llm/foundry_iq.py` line 321 — surfaces to SSE error channel.
- `v2/src/backend/core/providers/llm/base.py` line 136 — surfaces to SSE error channel.

New broad catches added in Phase C2–C4 follow the same `# noqa: BLE001 -- <reason>` convention.

## App-level exception handlers (Phase C4)

`backend/app.py::_install_exception_handlers` registers the following handlers on the FastAPI app at construction time. They apply uniformly to every router (conversation / history / admin / health) so per-handler `try/except` for these cross-cutting upstream errors is **not** required (and is discouraged — use the app-level handler instead so the sanitized message stays single-sourced).

| Exception | Status | Sanitized detail |
|---|---|---|
| `openai.APIError` | 502 | `Upstream model error.` |
| `azure.cosmos.exceptions.CosmosHttpResponseError` | 503 | `Database temporarily unavailable.` |
| `asyncpg.PostgresError` | 503 | `Database temporarily unavailable.` |
| `azure.core.exceptions.AzureError` | 503 | `Azure dependency temporarily unavailable.` |
| `Exception` (final safety net) | 500 | `Internal server error.` |

Dispatch order is FastAPI's MRO walk over `type(exc).__mro__` against the handler dict, so the more specific class always wins (e.g. a `CosmosHttpResponseError` -- which extends `azure-core`'s `HttpResponseError` -- lands on the Cosmos handler, not the generic `AzureError` handler). `HTTPException` and `RequestValidationError` keep their FastAPI defaults; the `Exception` final safety net is only reached for unhandled types.

Every handler logs at ERROR via `logger.exception(...)` with structured extras `{method, path, user_id, exception_class}` so triage can reconstruct the full SDK detail from App Insights without leaking it to the client. Coverage is locked in by `v2/tests/backend/test_app_exception_handlers.py` (8 tests, including pass-through invariants for `HTTPException` and `RequestValidationError`).
