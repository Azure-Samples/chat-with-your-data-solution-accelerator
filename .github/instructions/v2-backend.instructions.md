---
description: "CWYD v2 FastAPI backend conventions. Use when: editing v2/src/backend/**, adding a router, adding a route, wiring dependency injection, configuring lifespan, adding middleware, adding OpenTelemetry, defining Pydantic request/response models, or exposing a new endpoint."
applyTo: "v2/src/backend/**"
---

# v2 Backend (FastAPI) Conventions

## Stack

- FastAPI ≥ 0.115, Uvicorn ≥ 0.34, Pydantic v2.
- Async-only routes. No `def`-style sync handlers in routers.
- Dependency injection via `Depends(...)` from `backend/dependencies.py`. No module-level singletons.
- Telemetry: `azure-monitor-opentelemetry` configured in `app.py` lifespan, exporting **directly** to Application Insights when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set; no-op otherwise. Rationale: Stable Core minimality + plug-and-play (backend-only profile must boot without any sidecar). Do **not** introduce a standalone OTel collector container — it is not in [v2/docs/development_plan.md](../../v2/docs/development_plan.md) and adds a runtime that violates the plug-and-play contract.

## Structure

- `app.py` — app factory, lifespan, CORS, OTel. **App-level exception handlers do not live here** — they are extracted to `exception_handlers.py` (keeps the factory free of router-policy logic); `create_app()` only imports and calls `install_exception_handlers(app)`.
- `exception_handlers.py` — the app-level exception-handler subsystem (sanitized SDK-failure responses + the domain `ConfigResolutionError` → 409 handler). Public `install_exception_handlers(app)` is the single registration entry point, called once from `create_app()`. Per the policy in [v2/docs/exception_handling_policy.md](../../v2/docs/exception_handling_policy.md) "Routers" row: domain/SDK failures surface as sanitized HTTP responses with no stack-trace, PII, or upstream payload leaked.
- `dependencies.py` — settings, LLM helper, DB factory, search handler — all as cached `Depends`.
- `routers/<area>.py` — one router per area, prefixed `/api/<area>`.
- `models/` — Pydantic request/response models. **Never** return raw dicts.

## Rules

1. Every endpoint declares a `response_model` (or `response_class=StreamingResponse` for SSE).
2. Every router file has a sibling `tests/test_<area>.py` using `httpx.AsyncClient` + `ASGITransport`.
3. SSE endpoints stream `OrchestratorEvent` JSON per the channel protocol in `v2-workflow.instructions.md`.
4. CORS is permissive in dev (`*`) and locked to `BACKEND_CORS_ORIGINS` (Pydantic setting) in deployed envs.
5. Auth: use the `Depends(require_user)` / `Depends(require_admin)` helpers from `backend/routers/auth.py`. Do not roll JWT parsing inline.
6. No `print` — use `logging.getLogger(__name__)`. OTel picks it up.
7. No direct DB clients in routers — go through the provider registry: `from backend.core.providers.databases import registry as databases_registry; databases_registry.registry.get(settings.database.db_type)(...)`. Same rule for search (`backend/core/providers/search/`) and LLM (`backend/core/providers/llm/`). Per Hard Rule #13, provider `__init__.py` files are package markers — registry instances live in sibling `registry.py`. No `create()` factory wrappers.
8. Errors raise `HTTPException` with a stable `detail` shape: `{"code": "<snake_case>", "message": "<human>"}`.

## Anti-patterns

- Importing from `code/` (v1).
- Synchronous I/O (`requests`, `psycopg2.connect`) — use `httpx.AsyncClient` and `asyncpg`.
- Catching `Exception` without re-raising or logging with `exc_info=True`.
- Adding a route without an OpenAPI summary + tag.
- In-function imports — Hard Rule #17 in [.github/copilot-instructions.md](../copilot-instructions.md) requires all imports at module top (no lazy stdlib imports, no profile-conditional branches). Enforced by `v2/tests/shared/test_imports_at_top_only.py`.

## Testing pattern

```python
from httpx import ASGITransport, AsyncClient
import pytest

@pytest.mark.asyncio
async def test_health_returns_200(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
        assert r.status_code == 200
```
