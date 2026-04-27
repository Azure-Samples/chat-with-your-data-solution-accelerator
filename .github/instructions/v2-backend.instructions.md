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

- `app.py` — app factory, lifespan, CORS, OTel.
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
7. No direct DB clients in routers — call `chat_history.create(settings.database.db_type, ...)` from `v2/src/providers/chat_history/`. Same rule for search (`providers/search/`) and LLM (`providers/llm/`).
8. Errors raise `HTTPException` with a stable `detail` shape: `{"code": "<snake_case>", "message": "<human>"}`.

## Anti-patterns

- Importing from `code/` (v1).
- Synchronous I/O (`requests`, `psycopg2.connect`) — use `httpx.AsyncClient` and `asyncpg`.
- Catching `Exception` without re-raising or logging with `exc_info=True`.
- Adding a route without an OpenAPI summary + tag.

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
