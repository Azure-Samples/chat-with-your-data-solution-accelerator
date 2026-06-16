"""Live cross-user history-isolation check (integration lane).

Pillar: Stable Core
Phase: 6

Proves the chat-history surface is partitioned per caller: a conversation
created by one Easy Auth principal is invisible to a second principal, and the
second principal cannot delete it. The history routes derive ``user_id`` from
the ``x-ms-client-principal-id`` header and pass it to every database call, so
a second caller reads an empty list, gets a ``404`` on a direct lookup, and
their delete is a no-op against the owner's partition. Both principals are
synthetic test ids, never real Entra object ids (Hard Rule #18). The test
self-cleans the row it creates.
"""

import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

# Two distinct synthetic principals. The SPA forwards the resolved object id
# in the ``x-ms-client-principal-id`` header; here two fixed ids stand in for
# two signed-in users so the partitioning can be asserted deterministically.
_USER_A_HEADERS = {"x-ms-client-principal-id": "integration-user-a"}
_USER_B_HEADERS = {"x-ms-client-principal-id": "integration-user-b"}


async def test_history_is_isolated_per_user_live(
    live_client: httpx.AsyncClient,
) -> None:
    """User B can neither see nor delete User A's conversation."""
    title = f"integration-isolation-{uuid.uuid4()}"

    created = await live_client.post(
        "/api/history/conversations",
        json={"title": title},
        headers=_USER_A_HEADERS,
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json().get("id", "")
    assert conversation_id, created.json()

    try:
        # User B's list never surfaces A's conversation...
        b_list = await live_client.get(
            "/api/history/conversations", headers=_USER_B_HEADERS
        )
        assert b_list.status_code == 200, b_list.text
        assert all(
            conv.get("id") != conversation_id for conv in b_list.json()
        ), b_list.json()

        # ...a direct read of A's id under B's principal is a 404 (the scoped
        # lookup returns None)...
        b_read = await live_client.get(
            f"/api/history/conversations/{conversation_id}", headers=_USER_B_HEADERS
        )
        assert b_read.status_code == 404, b_read.text

        # ...B's delete is idempotent (always 204) but a no-op on A's
        # partition: it never removes a row B does not own...
        b_delete = await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=_USER_B_HEADERS
        )
        assert b_delete.status_code == 204, b_delete.text

        # ...so A still owns and can read the conversation after B's delete.
        a_read = await live_client.get(
            f"/api/history/conversations/{conversation_id}", headers=_USER_A_HEADERS
        )
        assert a_read.status_code == 200, a_read.text
        assert a_read.json()["conversation"]["id"] == conversation_id, a_read.json()
    finally:
        # Best-effort cleanup under the owning principal.
        await live_client.delete(
            f"/api/history/conversations/{conversation_id}", headers=_USER_A_HEADERS
        )
