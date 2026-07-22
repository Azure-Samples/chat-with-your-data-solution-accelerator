"""Router-level smoke for the ``backend-only`` compose profile.

Asserts the FastAPI app boots and serves all routes without the
``functions`` container as a peer -- the literal "backend works
without functions" claim. Routes that depend on the LLM provider
are exercised only via their input-validation path (422 on bad
body) so the smoke does not require a Foundry-shaped mock.

Driven by the ``backend-only smoke`` workflow:
``docker compose -f docker-compose.dev.yml -f docker-compose.smoke.yml --profile backend-only up``
followed by ``uv run pytest -m smoke tests/smoke/ -v``.
"""

import os

import httpx
import pytest

_BACKEND_URL = os.environ.get("CWYD_SMOKE_BACKEND_URL", "http://localhost:8000")
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@pytest.mark.smoke
async def test_health_endpoint_returns_200_with_valid_shape() -> None:
    """``GET /api/health`` always returns HTTP 200 with a valid shape.

    The endpoint's contract (see ``backend/routers/health.py``) is to
    return 200 unconditionally so it remains reachable for diagnostics
    when dependencies are failing. The ``status`` field carries
    severity. We accept any of ``pass | degraded | fail`` because the
    smoke stack uses dummy Foundry credentials -- the foundry check
    legitimately fails, but ``/api/health`` itself stays up.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(f"{_BACKEND_URL}/api/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") in {"pass", "degraded", "fail"}, body
    assert body.get("version") == "v2", body
    assert isinstance(body.get("checks"), list), body


@pytest.mark.smoke
async def test_openapi_lists_conversation_route() -> None:
    """``GET /openapi.json`` includes the conversation route.

    Proves the FastAPI app registered every router during lifespan
    (history / speech / conversation / health). If router wiring
    regresses, ``/api/conversation`` disappears from the schema and
    this test fails before the path-validation smoke even runs.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(f"{_BACKEND_URL}/openapi.json")

    assert response.status_code == 200, response.text
    schema = response.json()
    paths = schema.get("paths", {})
    assert "/api/conversation" in paths, sorted(paths.keys())
    assert "post" in paths["/api/conversation"], paths["/api/conversation"]


@pytest.mark.smoke
async def test_conversation_route_rejects_empty_messages() -> None:
    """``POST /api/conversation`` with an empty ``messages`` array returns 422.

    Proves the route is reachable and FastAPI is running its Pydantic
    request validation. ``ConversationRequest.messages`` is declared
    with ``Field(min_length=1)`` (see
    ``backend/models/conversation.py``), so an empty list is rejected
    before any orchestrator / LLM call is dispatched. This is the
    deepest non-LLM assertion we can make without mocking Foundry's
    project-endpoint shape end-to-end.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{_BACKEND_URL}/api/conversation",
            json={"messages": []},
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 422, response.text
    body = response.json()
    assert "detail" in body, body
    # FastAPI 422 payload: list of error objects, each with a `loc`
    # pointing at the failing field. Sanity-check that the failure is
    # about `messages`, not some unrelated dependency-injection break.
    error_locs = [tuple(err.get("loc", [])) for err in body["detail"]]
    assert any("messages" in loc for loc in error_locs), body
