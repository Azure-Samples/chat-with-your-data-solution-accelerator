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

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

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


async def test_message_metadata_column_round_trips_live(
    live_client: httpx.AsyncClient,
    user_headers: dict[str, str],
) -> None:
    """A persisted message carries a `metadata` field end-to-end through
    the real backend. The bare ``POST /messages`` route writes no metadata,
    so the value defaults to ``{}`` -- which is enough to prove (a) the live
    schema actually has the JSONB ``metadata`` column (the write would fail
    otherwise) and (b) the read path (``list_messages`` -> the detail route)
    surfaces it. A non-empty citation payload is exercised by the
    conversation-reload check once the answer path persists citations.
    """
    title = f"integration-meta-{uuid.uuid4()}"
    create = await live_client.post(
        "/api/history/conversations", json={"title": title}, headers=user_headers
    )
    assert create.status_code == 201, create.text
    conversation_id = create.json().get("id", "")
    assert conversation_id, create.json()

    try:
        added = await live_client.post(
            f"/api/history/conversations/{conversation_id}/messages",
            json={"role": "assistant", "content": "metadata probe"},
            headers=user_headers,
        )
        assert added.status_code == 201, added.text
        # The create response is a MessageRecord, which now carries metadata.
        assert added.json().get("metadata") == {}, added.json()

        detail = await live_client.get(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
        assert detail.status_code == 200, detail.text
        probe = next(
            (
                m
                for m in detail.json().get("messages", [])
                if m.get("content") == "metadata probe"
            ),
            None,
        )
        assert probe is not None, detail.json().get("messages")
        # The read path surfaces the JSONB column on every message.
        assert probe.get("metadata") == {}, probe
    finally:
        await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )


async def test_conversation_persists_citations_to_history_live(
    live_client: httpx.AsyncClient,
    user_headers: dict[str, str],
    collect_sse: Callable[..., Awaitable[list[Any]]],
) -> None:
    """End-to-end: a chat turn's grounding citations land in the persisted
    assistant message and resurface on conversation reload.

    Drives the real orchestrator + KB through ``POST /api/conversation`` in
    SSE mode, reads the resolved conversation id from the terminal
    ``conversation`` control frame, then reloads the thread via the history
    detail route. Whatever citations the answer streamed on the ``citation``
    channel must reappear -- deduplicated, same ids, same order -- under the
    persisted assistant message's ``metadata["citations"]``. When the live KB
    grounds nothing the stream carries no citations and both sides are empty;
    the POST -> persist -> reload round-trip is exercised either way.
    """
    question = "What is included in the Northwind Health Plus plan?"

    events = await collect_sse(
        live_client,
        "/api/conversation",
        json_body={"messages": [{"role": "user", "content": question}]},
        headers=user_headers,
    )

    conversation_frame = next(
        (event for event in reversed(events) if event.event == "conversation"), None
    )
    assert conversation_frame is not None, [event.event for event in events]
    conversation_id = json.loads(conversation_frame.data)["conversation_id"]
    assert conversation_id

    # Citation ids the live answer streamed, deduplicated in arrival order --
    # the same dedup-by-id the persistence wrapper applies.
    streamed_ids: list[str] = []
    for event in events:
        if event.event != "citation":
            continue
        cid = json.loads(event.data).get("metadata", {}).get("id")
        if isinstance(cid, str) and cid not in streamed_ids:
            streamed_ids.append(cid)

    try:
        detail = await live_client.get(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
        assert detail.status_code == 200, detail.text
        assistant = next(
            (
                m
                for m in detail.json().get("messages", [])
                if m.get("role") == "assistant"
            ),
            None,
        )
        assert assistant is not None, detail.json().get("messages")
        stored = assistant.get("metadata", {}).get("citations", [])
        stored_ids = [citation.get("id") for citation in stored]
        # The persisted citation ids match exactly what the answer streamed.
        assert stored_ids == streamed_ids, {
            "streamed": streamed_ids,
            "stored": stored_ids,
        }
    finally:
        await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=user_headers
        )
