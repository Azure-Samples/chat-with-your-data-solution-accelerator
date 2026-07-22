"""Chat history router tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from starlette.requests import Request

from backend.app import create_app
from backend.core.tools.content_safety import ContentSafetyVerdict
from backend.core.types import ChatMessage, Conversation, MessageRecord
from backend.dependencies import (
    get_app_settings,
    get_content_safety_guard,
    get_database_client,
    get_user_id,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_TEST_USER_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class _FakeSettings:
    class _D:
        db_type = "cosmosdb"

    database = _D()


def _conv(
    *, id: str = "c-1", title: str = "t", user_id: str = _TEST_USER_ID
) -> Conversation:
    return Conversation(
        id=id,
        user_id=user_id,
        title=title,
        created_at="2026-04-28T00:00:00+00:00",
        updated_at="2026-04-28T00:00:00+00:00",
    )


def _msg(
    *, id: str = "m-1", conversation_id: str = "c-1", content: str = "hi"
) -> MessageRecord:
    return MessageRecord(
        id=id,
        conversation_id=conversation_id,
        role="user",
        content=content,
        created_at="2026-04-28T00:00:00+00:00",
    )


class _FakeGuard:
    """Stand-in for ContentSafetyGuard that records screened text.

    ``flagged`` decides the verdict so a test can exercise both the
    block path (-> 400) and the clean path (-> rename proceeds).
    """

    def __init__(self, *, flagged: bool) -> None:
        self._flagged = flagged
        self.screened: list[str] = []

    async def screen(self, text: str) -> ContentSafetyVerdict:
        self.screened.append(text)
        if self._flagged:
            return ContentSafetyVerdict(flagged=True, triggered=["Hate"])
        return ContentSafetyVerdict(flagged=False)


@pytest.fixture
def app_with_fake_db():
    app = create_app()
    db = MagicMock()
    db.list_conversations = AsyncMock(return_value=[_conv()])
    db.get_conversation = AsyncMock(return_value=_conv())
    db.create_conversation = AsyncMock(return_value=_conv(title="new"))
    db.rename_conversation = AsyncMock(return_value=_conv(title="renamed"))
    db.delete_conversation = AsyncMock(return_value=None)
    db.list_messages = AsyncMock(return_value=[_msg()])
    db.add_message = AsyncMock(return_value=_msg(content="added"))
    db.set_feedback = AsyncMock(return_value=None)

    app.dependency_overrides[get_database_client] = lambda: db
    app.dependency_overrides[get_app_settings] = lambda: _FakeSettings()
    # Pin user_id so tests don't need to pretend Easy Auth is wired.
    app.dependency_overrides[get_user_id] = lambda: _TEST_USER_ID
    app.state._test_db = db  # type: ignore[attr-defined]
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# ---------------------------------------------------------------------------
# get_user_id helper
# ---------------------------------------------------------------------------


def test_get_user_id_reads_easy_auth_header() -> None:
    scope: dict[str, Any] = {
        "type": "http",
        "headers": [
            (
                b"x-ms-client-principal-id",
                b"3f2504e0-4f89-41d3-9a0c-0305e82c3301",
            )
        ],
    }
    assert get_user_id(Request(scope)) == "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


def test_get_user_id_falls_back_to_default_guid_when_header_missing() -> None:
    scope: dict[str, Any] = {"type": "http", "headers": []}
    assert get_user_id(Request(scope)) == "00000000-0000-0000-0000-000000000000"


def test_get_user_id_falls_back_to_default_guid_when_not_a_guid() -> None:
    scope: dict[str, Any] = {
        "type": "http",
        "headers": [(b"x-ms-client-principal-id", b"not-a-guid")],
    }
    assert get_user_id(Request(scope)) == "00000000-0000-0000-0000-000000000000"


def test_get_user_id_accepts_all_zeros_default_user() -> None:
    """The frontend's all-zeros default id is a valid GUID."""
    scope: dict[str, Any] = {
        "type": "http",
        "headers": [
            (
                b"x-ms-client-principal-id",
                b"00000000-0000-0000-0000-000000000000",
            )
        ],
    }
    assert get_user_id(Request(scope)) == "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


async def test_status_returns_db_type(app_with_fake_db) -> None:
    async with _client(app_with_fake_db) as client:
        resp = await client.get("/api/history/status")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True, "db_type": "cosmosdb"}


# ---------------------------------------------------------------------------
# Conversations CRUD
# ---------------------------------------------------------------------------


async def test_list_conversations_returns_user_scoped_results(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.get("/api/history/conversations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "c-1"
    db.list_conversations.assert_awaited_once_with(_TEST_USER_ID)


async def test_create_conversation_returns_201_and_persists_via_client(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.post("/api/history/conversations", json={"title": "new"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "new"
    db.create_conversation.assert_awaited_once_with(user_id=_TEST_USER_ID, title="new")


async def test_get_conversation_returns_conversation_plus_messages(
    app_with_fake_db,
) -> None:
    async with _client(app_with_fake_db) as client:
        resp = await client.get("/api/history/conversations/c-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation"]["id"] == "c-1"
    assert len(body["messages"]) == 1


async def test_get_conversation_404_when_missing(app_with_fake_db) -> None:
    db = app_with_fake_db.state._test_db
    db.get_conversation = AsyncMock(return_value=None)
    async with _client(app_with_fake_db) as client:
        resp = await client.get("/api/history/conversations/nope")
    assert resp.status_code == 404


async def test_rename_conversation_returns_renamed_payload(
    app_with_fake_db,
) -> None:
    async with _client(app_with_fake_db) as client:
        resp = await client.patch(
            "/api/history/conversations/c-1", json={"title": "renamed"}
        )
    assert resp.status_code == 200
    assert resp.json()["title"] == "renamed"


async def test_rename_conversation_404_when_keyerror(app_with_fake_db) -> None:
    db = app_with_fake_db.state._test_db
    db.rename_conversation = AsyncMock(side_effect=KeyError("c-1"))
    async with _client(app_with_fake_db) as client:
        resp = await client.patch("/api/history/conversations/c-1", json={"title": "r"})
    assert resp.status_code == 404


async def test_rename_conversation_422_when_title_blank(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.patch(
            "/api/history/conversations/c-1", json={"title": "   "}
        )
    assert resp.status_code == 422
    db.rename_conversation.assert_not_awaited()


async def test_rename_conversation_422_when_title_empty(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.patch("/api/history/conversations/c-1", json={"title": ""})
    assert resp.status_code == 422
    db.rename_conversation.assert_not_awaited()


async def test_rename_conversation_strips_surrounding_whitespace(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.patch(
            "/api/history/conversations/c-1", json={"title": "  New name  "}
        )
    assert resp.status_code == 200
    db.rename_conversation.assert_awaited_once_with("c-1", _TEST_USER_ID, "New name")


async def test_rename_conversation_400_when_title_flagged_by_content_safety(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    guard = _FakeGuard(flagged=True)
    app_with_fake_db.dependency_overrides[get_content_safety_guard] = lambda: guard
    async with _client(app_with_fake_db) as client:
        resp = await client.patch(
            "/api/history/conversations/c-1", json={"title": "bad title"}
        )
    assert resp.status_code == 400
    assert guard.screened == ["bad title"]
    db.rename_conversation.assert_not_awaited()


async def test_rename_conversation_screens_clean_title_then_persists(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    guard = _FakeGuard(flagged=False)
    app_with_fake_db.dependency_overrides[get_content_safety_guard] = lambda: guard
    async with _client(app_with_fake_db) as client:
        resp = await client.patch(
            "/api/history/conversations/c-1", json={"title": "Clean title"}
        )
    assert resp.status_code == 200
    assert guard.screened == ["Clean title"]
    db.rename_conversation.assert_awaited_once_with("c-1", _TEST_USER_ID, "Clean title")


async def test_rename_conversation_skips_screening_when_guard_disabled(
    app_with_fake_db,
) -> None:
    # No get_content_safety_guard override -> the dep resolves to None
    # (the test app's state has no content_safety_client), so a rename
    # proceeds without a content-safety round-trip.
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.patch(
            "/api/history/conversations/c-1", json={"title": "No guard"}
        )
    assert resp.status_code == 200
    db.rename_conversation.assert_awaited_once_with("c-1", _TEST_USER_ID, "No guard")


async def test_delete_conversation_returns_204_idempotently(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.delete("/api/history/conversations/c-1")
    assert resp.status_code == 204
    db.delete_conversation.assert_awaited_once_with("c-1", _TEST_USER_ID)


# ---------------------------------------------------------------------------
# Messages + feedback
# ---------------------------------------------------------------------------


async def test_add_message_returns_201_and_forwards_chatmessage(
    app_with_fake_db,
) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.post(
            "/api/history/conversations/c-1/messages",
            json={"role": "user", "content": "hi"},
        )
    assert resp.status_code == 201
    assert resp.json()["content"] == "added"
    call = db.add_message.await_args
    assert call.kwargs["conversation_id"] == "c-1"
    assert call.kwargs["user_id"] == _TEST_USER_ID
    msg = call.kwargs["message"]
    assert isinstance(msg, ChatMessage)
    assert msg.content == "hi"


async def test_add_message_404_when_parent_missing(app_with_fake_db) -> None:
    db = app_with_fake_db.state._test_db
    db.add_message = AsyncMock(side_effect=KeyError("c-1"))
    async with _client(app_with_fake_db) as client:
        resp = await client.post(
            "/api/history/conversations/c-1/messages",
            json={"role": "user", "content": "hi"},
        )
    assert resp.status_code == 404


async def test_set_feedback_returns_204(app_with_fake_db) -> None:
    db = app_with_fake_db.state._test_db
    async with _client(app_with_fake_db) as client:
        resp = await client.post(
            "/api/history/messages/m-1/feedback",
            json={"feedback": "positive"},
        )
    assert resp.status_code == 204
    db.set_feedback.assert_awaited_once_with("m-1", _TEST_USER_ID, "positive")


async def test_set_feedback_404_when_message_missing(app_with_fake_db) -> None:
    db = app_with_fake_db.state._test_db
    db.set_feedback = AsyncMock(side_effect=KeyError("m-1"))
    async with _client(app_with_fake_db) as client:
        resp = await client.post(
            "/api/history/messages/m-1/feedback",
            json={"feedback": "positive"},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_rename_rejects_empty_title(app_with_fake_db) -> None:
    async with _client(app_with_fake_db) as client:
        resp = await client.patch("/api/history/conversations/c-1", json={"title": ""})
    assert resp.status_code == 422


async def test_add_message_rejects_blank_content(app_with_fake_db) -> None:
    async with _client(app_with_fake_db) as client:
        resp = await client.post(
            "/api/history/conversations/c-1/messages",
            json={"role": "user", "content": ""},
        )
    assert resp.status_code == 422
