"""OpenAPI ``responses`` presence tests for the backend routers.

Documentation-only guard: every non-200 outcome a route can raise is
declared in its ``responses={}`` map so the generated OpenAPI spec (and
the TS client the frontend regenerates from it) documents the error
envelopes and the SSE dual content-type on the chat route.

Each test builds a minimal FastAPI app from a single router and calls
``app.openapi()`` -- schema generation only introspects route
signatures and does not invoke the endpoints, so no dependency wiring
is required (mirrors the ``app.openapi()`` pattern in
``tests/backend/routers/test_speech.py``). The tests would fail if a
route's ``responses`` map (or a specific code within it) were removed.
"""

from typing import Any

from fastapi import APIRouter, FastAPI

from backend.routers import (
    admin as admin_router,
    conversation as conversation_router,
    files as files_router,
    health as health_router,
    history as history_router,
    speech as speech_router,
)


def _spec_for(router: APIRouter) -> dict[str, Any]:
    """Build a one-router app and return its generated OpenAPI spec."""
    app = FastAPI()
    app.include_router(router)
    return app.openapi()


def test_files_get_declares_400_404_503() -> None:
    op = _spec_for(files_router.router)["paths"]["/api/files/{filename}"]["get"]
    assert {"400", "404", "503"} <= set(op["responses"])
    # The error envelope is wired to ErrorResponse (resolvable $ref).
    ref = op["responses"]["404"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ErrorResponse")
    # The path param carries its description.
    filename_param = next(p for p in op["parameters"] if p["name"] == "filename")
    assert filename_param["description"] == "Stored blob filename to stream."


def test_speech_get_declares_502_503() -> None:
    op = _spec_for(speech_router.router)["paths"]["/api/speech"]["get"]
    assert {"502", "503"} <= set(op["responses"])


def test_health_ready_declares_503_with_health_snapshot() -> None:
    op = _spec_for(health_router.router)["paths"]["/api/health/ready"]["get"]
    assert "503" in op["responses"]
    # The 503 body is the health snapshot, NOT an error envelope.
    ref = op["responses"]["503"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/HealthResponse")
    # The always-200 diagnostic route declares no error responses.
    diag = _spec_for(health_router.router)["paths"]["/api/health"]["get"]
    assert set(diag["responses"]) == {"200"}


def test_conversation_post_declares_dual_content_type_200() -> None:
    op = _spec_for(conversation_router.router)["paths"]["/api/conversation"]["post"]
    content = op["responses"]["200"]["content"]
    assert set(content) == {"application/json", "text/event-stream"}
    ref = content["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ConversationResponse")
    # The Accept header param carries its negotiation description.
    accept_param = next(p for p in op["parameters"] if p["name"] == "accept")
    assert "text/event-stream" in accept_param["description"]


def test_history_routes_declare_error_codes() -> None:
    paths = _spec_for(history_router.router)["paths"]
    get_conv = paths["/api/history/conversations/{conversation_id}"]["get"]
    assert "404" in get_conv["responses"]
    patch_conv = paths["/api/history/conversations/{conversation_id}"]["patch"]
    assert {"400", "404"} <= set(patch_conv["responses"])
    add_msg = paths["/api/history/conversations/{conversation_id}/messages"]["post"]
    assert "404" in add_msg["responses"]
    feedback = paths["/api/history/messages/{message_id}/feedback"]["post"]
    assert "404" in feedback["responses"]
    # The 204 delete route declares no domain error responses (the 422
    # present is FastAPI's auto path-param validation entry, not ours).
    delete_conv = paths["/api/history/conversations/{conversation_id}"]["delete"]
    assert "204" in delete_conv["responses"]
    assert "404" not in delete_conv["responses"]
    # The path param carries its description.
    conv_param = next(
        p for p in get_conv["parameters"] if p["name"] == "conversation_id"
    )
    assert conv_param["description"]


def test_admin_routes_declare_error_codes() -> None:
    paths = _spec_for(admin_router.router)["paths"]
    assert "422" in paths["/api/admin/config"]["patch"]["responses"]
    assert "503" in paths["/api/admin/documents"]["get"]["responses"]
    delete_doc = paths["/api/admin/documents/{source}"]["delete"]
    assert {"404", "503"} <= set(delete_doc["responses"])
    assert {"422", "503"} <= set(paths["/api/admin/documents/url"]["post"]["responses"])
    upload = paths["/api/admin/documents"]["post"]
    assert {"413", "415", "422", "503"} <= set(upload["responses"])
    assert "503" in paths["/api/admin/documents/reprocess"]["post"]["responses"]
    # The {source:path} param carries its description.
    source_param = next(p for p in delete_doc["parameters"] if p["name"] == "source")
    assert source_param["description"] == "Blob source path to de-index and delete."
