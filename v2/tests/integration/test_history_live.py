"""Live chat-history checks (integration lane).

Pillar: Stable Core
Phase: 6

Exercises the chat-history CRUD surface against the real database backend
(``cosmosdb`` / ``postgresql`` -- whichever the live env wires) over the
in-process app boot. The lifecycle test creates a uniquely-titled
conversation, appends a message, reads it back to prove real persistence,
then deletes it (self-cleanup, idempotent). The conversation is partitioned
under a synthetic ``integration-user`` principal (Hard Rule #18).
"""

import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_history_status_live_reports_enabled_backend(
    live_client: httpx.AsyncClient,
) -> None:
    """``GET /api/history/status`` reports an enabled, named backend."""
    response = await live_client.get("/api/history/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("enabled") is True, body
    assert body.get("db_type"), body


async def test_conversation_lifecycle_live_persists_and_deletes(
    live_client: httpx.AsyncClient,
    user_headers: dict[str, str],
) -> None:
    """Create -> append -> read-back -> delete round-trips through the real DB."""
    title = f"integration-test-{uuid.uuid4()}"
    message_content = "Integration lifecycle probe."

    create = await live_client.post(
        "/api/history/conversations", json={"title": title}, headers=user_headers
    )
    assert create.status_code == 201, create.text
    conversation_id = create.json().get("id", "")
    assert conversation_id, create.json()
    assert create.json().get("title") == title

    try:
        added = await live_client.post(
            f"/api/history/conversations/{conversation_id}/messages",
            json={"role": "user", "content": message_content},
            headers=user_headers,
        )
        assert added.status_code == 201, added.text
        message = added.json()
        assert message.get("id"), message
        assert message.get("conversation_id") == conversation_id, message
        assert message.get("role") == "user", message
        assert message.get("content") == message_content, message

        detail = await live_client.get(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["conversation"]["id"] == conversation_id, detail_body
        assert any(
            m.get("content") == message_content
            for m in detail_body.get("messages", [])
        ), detail_body.get("messages")

        # Happy-path delete of an existing row returns 204...
        deleted = await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
        assert deleted.status_code == 204, deleted.text

        # ...delete is idempotent on an already-removed row...
        again = await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
        assert again.status_code == 204, again.text

        # ...and the conversation is gone.
        gone = await live_client.get(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
        assert gone.status_code == 404, gone.text
    finally:
        # Best-effort cleanup: if an assertion above left the row behind,
        # remove it so the live database is not polluted across runs.
        await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
