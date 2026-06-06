# CWYD v2 — Chat History

> Pillar: **Stable Core** · Phase: **5** (Admin + Frontend Merge) · Phase: **6** (Functions ingest blueprints)
> Source files: [v2/src/backend/routers/history.py](../src/backend/routers/history.py), [v2/src/backend/routers/conversation.py](../src/backend/routers/conversation.py), [v2/src/backend/core/providers/databases/](../src/backend/core/providers/databases/), [v2/src/backend/core/types.py](../src/backend/core/types.py)

This document explains how CWYD v2 stores conversations and messages, how a conversation continuation works across requests, and how the streaming chat flow relates to (and deliberately does **not** replay through) the chat-history store.

The frontend integration of these routes is tracked as **Phase 5-FE-HISTORY** in [development_plan.md](development_plan.md) §0.1. **The backend half of every route below is shipped and tested.** A typed FE history client + history side-panel + "New chat" wiring are the remaining work.

---

## 1. Design principles

1. **Chat history is part of the database provider, not a separate registry.** Conversations and messages are not stored in some isolated "chat-history backend" — they are part of `BaseDatabaseClient` ([v2/src/backend/core/providers/databases/base.py](../src/backend/core/providers/databases/base.py)) alongside runtime-config and agent rows. The single deploy-time `databaseType` choice (Cosmos OR Postgres, see [infrastructure.md](infrastructure.md) §2.2.1) drives the whole set. There is no `chat_history.registry` — there is `databases_registry`.
2. **User-scoped by storage primitive, not by query filter.** Cosmos partitions by `/userId`. Postgres carries `user_id` on every row and the index is `(user_id, updated_at DESC)`. Cross-user reads are not "a query that could leak" — they are not on the read path at all. The `user_id` always comes from the authenticated principal, never from the request body.
3. **The chat endpoint does not auto-load history.** `POST /api/conversation` accepts an optional `conversation_id` but does **not** read past messages from the database to build the prompt. The caller (frontend) is responsible for the continuation: fetch prior turns via `GET /api/history/conversations/{id}`, include them in the `messages[]` it sends, then receive the response. This keeps the chat pipeline stateless across requests and makes message-history loading a deliberate, observable round-trip rather than hidden middleware.
4. **No SSE replay, no event store.** A streaming response is consumed exactly once. There is no resume-from-checkpoint, no per-event persistence during the stream, no in-progress-stream re-attach. If a client disconnects mid-stream, the work continues server-side (the orchestrator runs to completion), but the partial output is lost. The recovery model is "re-issue the request," not "re-attach to the stream."
5. **Persistence is the caller's explicit act.** After a chat turn completes, the FE persists the user message and the assistant message by appending to the conversation via `POST /api/history/conversations/{id}/messages`. The backend chat pipeline does not auto-persist. This separation (chat is streaming compute; history is durable storage) is what lets the chat flow stay backend-stateless.
6. **UUIDs everywhere.** Conversation IDs and message IDs are server-assigned UUID4 strings. The client never invents them. Both backends generate the ID on the create path; Postgres uses native `UUID` column type, Cosmos uses string.
7. **Idempotent deletes.** `DELETE /api/history/conversations/{id}` returns 204 whether the conversation existed or not. The FE never has to special-case "already gone" — re-sending the DELETE is safe.

---

## 2. Routes

All routes are mounted under `/api/history/`. All are user-scoped (the caller's authenticated principal is the `user_id` filter; no admin role required, no cross-user reads). All return JSON.

### 2.1 `GET /api/history/conversations` → `list[Conversation]`

List the calling user's conversations, ordered newest-first by `updated_at`. Powers the FE history side-panel.

Status: `200`.

### 2.2 `GET /api/history/conversations/{id}` → `ConversationDetail`

Fetch a single conversation plus its full message history (oldest-first). This is the endpoint the FE calls when restoring a conversation — read once, then build the chat request with the returned messages.

Status: `200` on success · `404` when the conversation is missing or owned by a different user (the two failure modes are not distinguished — both surface as 404 to avoid information leak).

Response shape: `{ conversation: Conversation, messages: list[MessageRecord] }`.

### 2.3 `POST /api/history/conversations` → `Conversation`

Create a new empty conversation. Server-assigns `id` (UUID4), `created_at`, `updated_at`. The caller may pass a `title`; if omitted, the title is the empty string until renamed.

Status: `201`.

### 2.4 `PATCH /api/history/conversations/{id}` → `Conversation`

Rename a conversation. Body: `{ title: str }`. Bumps `updated_at`.

Status: `200` on success · `404` when missing.

### 2.5 `DELETE /api/history/conversations/{id}` → `204`

Delete a conversation and all of its messages. **Idempotent** — returns `204` whether the conversation existed or not.

- **Cosmos:** delete the conversation item + a parameterized fan-out delete of all messages with matching `conversationId` in the user's partition.
- **Postgres:** single `DELETE FROM conversations WHERE id = $1 AND user_id = $2`; messages cascade via FK `ON DELETE CASCADE`.

Status: `204`.

### 2.6 `POST /api/history/conversations/{id}/messages` → `MessageRecord`

Append a single message to a conversation. Body: `{ role: "user" | "assistant" | "system", content: str, feedback?: str }`. Server-assigns `id`, `created_at`, bumps the parent conversation's `updated_at`.

Status: `201` on success · `404` when the conversation is missing (raises `KeyError` from the storage layer, mapped to 404).

This is how the FE persists a chat turn — two calls (one for the user message, one for the assistant message) after the SSE stream completes. The order matters for the timeline view but not for correctness.

---

## 3. Persistence layer

The store sits behind `BaseDatabaseClient` ([v2/src/backend/core/providers/databases/base.py](../src/backend/core/providers/databases/base.py)). Every method below is implemented by both `CosmosDatabaseClient` and `PostgresDatabaseClient`.

```text
list_conversations(user_id)                        -> Sequence[Conversation]
get_conversation(id, user_id)                      -> Conversation | None
create_conversation(user_id, title)                -> Conversation
rename_conversation(id, user_id, title)            -> Conversation        # KeyError if missing
delete_conversation(id, user_id)                   -> None                # idempotent
list_messages(conversation_id, user_id)            -> Sequence[MessageRecord]   # oldest-first
add_message(conversation_id, user_id, message)     -> MessageRecord       # KeyError if missing
```

### 3.1 Cosmos DB layout

Source: [v2/src/backend/core/providers/databases/cosmosdb.py](../src/backend/core/providers/databases/cosmosdb.py).

- **Container:** shared per-deployment item container (typically `cwyd-items`); same container also holds runtime-config, agent, and audit rows distinguished by `type`.
- **Partition key:** `/userId`. Every conversation and every message carries the owning user's id in this field — list/read operations are single-partition queries.
- **Conversation item:** `{ id: <uuid4>, userId: <principal>, type: "conversation", title: <str>, createdAt: <iso>, updatedAt: <iso> }` (`CosmosItemType.CONVERSATION`).
- **Message item:** `{ id: <uuid4>, userId: <principal>, type: "message", conversationId: <uuid4>, role: <str>, content: <str>, createdAt: <iso>, feedback?: <str> }` (`CosmosItemType.MESSAGE`).
- **Reads:** `get_conversation` is a point-read by `(id, user_id)` (single RU). `list_messages` is a parameterized query within the partition: `SELECT * FROM c WHERE c.type = "message" AND c.conversationId = @cid ORDER BY c.createdAt ASC`.

### 3.2 PostgreSQL layout

Source: [v2/src/backend/core/providers/databases/postgres.py](../src/backend/core/providers/databases/postgres.py).

```sql
CREATE TABLE conversations (
    id         UUID PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id              UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    feedback        TEXT
);

CREATE INDEX idx_conversations_user_updated ON conversations (user_id, updated_at DESC);
CREATE INDEX idx_messages_conv_created      ON messages (conversation_id, created_at);
```

- **Foreign key cascade.** Deleting a `conversations` row cascades the children — the route does not have to fan-out a separate `DELETE FROM messages`.
- **Indexes match the query shape.** The list-conversations index is `(user_id, updated_at DESC)`; the list-messages index is `(conversation_id, created_at)`. The router never queries a path that would force a sequential scan.
- **`KeyError` on missing parent.** `add_message` to a non-existent conversation raises `KeyError` (caught by the router and surfaced as 404). The PostgreSQL FK constraint is the enforcement — the router does not pre-check.

### 3.3 Registry wiring

Both implementations register under `databases_registry` ([v2/src/backend/core/providers/databases/registry.py](../src/backend/core/providers/databases/registry.py)). The lifespan resolves the active backend once at startup:

```python
from backend.core.providers.databases import registry as databases_registry

db = databases_registry.registry.get(settings.database.db_type)(
    settings=settings,
    credential=credential,
)
```

`settings.database.db_type` (env: `AZURE_DB_TYPE`, default `"cosmosdb"`) is one of `"cosmosdb"` or `"postgresql"`. Per [infrastructure.md](infrastructure.md) §2.2.1 this is a deploy-time, one-shot choice — it is **not** in the admin-mutable `AdminConfig` set.

---

## 4. Conversation continuation contract

### 4.1 The chat flow does not auto-load history

`POST /api/conversation` ([v2/src/backend/routers/conversation.py](../src/backend/routers/conversation.py)) accepts `ConversationRequest` with an optional `conversation_id`. That id is **echoed** through to `ConversationResponse.conversation_id` and made available to the orchestrator in its event metadata — but the chat service does **not** read past messages from the database when the request arrives.

Concretely: if the FE sends `{ conversation_id: "...", messages: [<just the new user turn>] }`, the orchestrator sees only the one new turn. Past context is the FE's responsibility to assemble.

### 4.2 How a continuation actually works (FE responsibility)

```text
1. User clicks an existing conversation in the history side-panel.
2. FE  →  GET /api/history/conversations/<id>
   FE  ←  { conversation, messages: [ ...full ordered history... ] }
3. User types a new message in the chat input.
4. FE  →  POST /api/conversation
            { conversation_id: <id>, messages: [ ...history + new user turn... ] }
   FE  ←  SSE stream (reasoning, tool, answer, citation, error events)
5. Stream completes.
6. FE  →  POST /api/history/conversations/<id>/messages   (user message)
   FE  →  POST /api/history/conversations/<id>/messages   (assistant message)
```

Steps 6 are why "no auto-persist" is a contract, not an oversight — the FE is in control of *what* gets persisted (e.g., it may choose not to persist a failed turn, or to persist a sanitized assistant reply).

### 4.3 New conversation flow

```text
1. User clicks "New chat".
2. FE clears its local conversation_id.    (no server call yet — see note below)
3. User sends first message.
4. FE  →  POST /api/conversation
            { conversation_id: null, messages: [ <just the user turn> ] }
   FE  ←  SSE stream.
5. Stream completes.
6. FE  →  POST /api/history/conversations   (server-assigns new UUID4)
   FE  ←  { id: <new uuid>, title: "", ... }
7. FE  →  POST /api/history/conversations/<new>/messages  (user message)
   FE  →  POST /api/history/conversations/<new>/messages  (assistant message)
8. FE stores <new uuid> as its current conversation_id for subsequent turns.
```

The FE may alternatively pre-create the conversation row at step 2 (POST /api/history/conversations) and pass the new id into the first chat request. Both flows are valid — the choice is a FE-UX call.

### 4.4 Non-existent id behavior

If the FE passes a `conversation_id` to `POST /api/conversation` that the database has never seen, the chat flow does not fail — the orchestrator runs over whatever `messages[]` was sent, and the id is echoed back. The first time that id is touched on the history surface (a `GET /api/history/conversations/<id>` or an `add_message` call), the missing row surfaces:

- `GET /api/history/conversations/<id>` → `404`.
- `POST /api/history/conversations/<id>/messages` → `KeyError` from storage → `404` from the route.

This is by design: the chat pipeline is decoupled from history; a stale FE id in flight cannot break the chat response.

---

## 5. Streaming vs. persistence

### 5.1 What the orchestrator emits

The chat pipeline ([v2/src/backend/core/pipelines/chat.py](../src/backend/core/pipelines/chat.py)) drives an orchestrator that yields `OrchestratorEvent` records ([v2/src/backend/core/types.py](../src/backend/core/types.py)). Every event carries a `channel`:

- `REASONING` — model reasoning trace (o-series traces go here)
- `TOOL` — tool-call invocations + results
- `ANSWER` — the assistant's user-facing reply (may stream as multiple deltas)
- `CITATION` — retrieved-document references attached to the answer
- `ERROR` — terminal failure, ends the stream

Channels are values of a `StrEnum` (Hard Rule #11). The FE renders `REASONING` in a collapsible panel; `ANSWER` in the main chat bubble; `CITATION` attached to the bubble.

### 5.2 What gets persisted (and when)

**Nothing during the stream.** No per-event row, no checkpoint, no streaming write-amplification on the database. The pipeline is pure compute.

**After the stream, on the caller's initiative.** Two POSTs to `/api/history/conversations/{id}/messages` — one for the user message, one for the assistant message. The FE composes the assistant message by accumulating `ANSWER` deltas from the stream.

This separation has three deliberate consequences:

1. The chat pipeline is testable as pure async-generator code with no DB mocks.
2. The history store does not see "ghost" assistant rows from streams the FE abandoned mid-flight.
3. Reasoning traces are *not* persisted by default — they live in the SSE event log and (optionally) in Application Insights, but not on the message row. If a deployment wants persistent reasoning, that is an explicit FE choice (write the reasoning into the assistant message's `content` or a future extension field), not a backend default.

### 5.3 What "no SSE replay" means in practice

There is no `Last-Event-ID` handling, no event-store rehydration, no resume-from-checkpoint. If a client disconnects mid-stream:

- The orchestrator continues running server-side until it completes (it is not cancelled by client disconnect).
- The partial output is dropped on the floor — the FE has no way to re-attach to the in-flight stream.
- The user-visible recovery model is "re-issue the request." If the FE chose to pre-create the conversation and append the user message before sending the chat request (step-3-then-step-6 in §4.3), the re-issued request is straightforward.

A future "resume in-flight stream" capability would require an event-store layer between the orchestrator and SSE serializer — that is **not** in scope for any current phase. Tracked only conceptually; not a debt-queue item.

---

## 6. Test coverage

| Suite | Count (approx.) | What it locks |
|---|---|---|
| [v2/tests/backend/core/providers/databases/test_cosmosdb.py](../tests/backend/core/providers/databases/test_cosmosdb.py) | 50+ | Registry key, item-type discriminators, conversations CRUD, message append + list-by-conversation, feedback field, user-id isolation, point-read shape, SDK error logged-and-re-raised |
| [v2/tests/backend/core/providers/databases/test_postgres.py](../tests/backend/core/providers/databases/test_postgres.py) | 40+ | Schema bootstrap idempotency, pool lifecycle, parameterized SQL shape, FK violation → `KeyError`, user-id isolation on every read, cascade on conversation delete |
| [v2/tests/backend/test_conversation.py](../tests/backend/test_conversation.py) | (router-level) | `POST /api/conversation` SSE vs JSON modes, orchestrator registry dispatch, agent resolver seam, `conversation_id` echo-through, request-shape validation |
| [v2/tests/backend/test_history.py](../tests/backend/test_history.py) | (router-level) | All six history routes: 200/201/204 success paths, 404 on missing or cross-user, ordering on `list_messages`, idempotent delete, FK cascade visible through the API |

Current full-suite baseline: **1879 passed / 1 skipped / 3 deselected / 4 warnings** (Phase 7 backend-tier drained; see [development_plan.md](development_plan.md) §0).
