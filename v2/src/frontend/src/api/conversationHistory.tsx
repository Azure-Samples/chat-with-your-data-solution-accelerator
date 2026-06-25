/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
 *
 * Fetch one persisted conversation and map its stored messages onto the
 * frontend `ChatMessage[]` shape so selecting a past conversation in the
 * history panel rehydrates the full transcript — including the grounding
 * citations persisted in each assistant message's `metadata.citations`
 * (no retrieval re-run). This is the single seam that talks to
 * `GET /api/history/conversations/{id}`; the panel / page wiring consumes
 * the returned `{ conversationId, messages }` to drive a `LoadConversation`
 * dispatch on `<ChatProvider>`'s reducer.
 *
 * The backend origin comes from the runtime `getBackendUrl()` seam
 * (the `/config` `backendUrl` resolved at boot, falling back to
 * build-time `VITE_BACKEND_URL`) so a single build targets both the
 * same-origin dev proxy and the deployed separate-origin backend
 * without a rebuild — matching the `streamChat` / `documentHref` /
 * `HistoryPanel` base convention.
 */
import type { ChatMessage, Citation, MessageRole } from "@/models/chat";
import { userIdHeaders } from "@/api/auth";
import { getBackendUrl } from "@/api/runtimeConfig";

/** Result of {@link fetchConversation}: the resolved id + rehydrated transcript. */
export interface LoadedConversation {
  conversationId: string;
  messages: ChatMessage[];
}

/**
 * One stored message as returned by `GET /api/history/conversations/{id}`.
 * Mirrors `backend.core.types.MessageRecord`; only the fields the chat
 * transcript renders are read, so `conversation_id` / `created_at` /
 * `feedback` are intentionally omitted here.
 */
interface MessageRecordWire {
  id: string;
  role: string;
  content: string;
  metadata?: Record<string, unknown>;
}

/** Wire shape of `GET /api/history/conversations/{id}` (`ConversationDetail`). */
interface ConversationDetailWire {
  messages?: MessageRecordWire[];
}

function backendUrl(): string {
  return getBackendUrl();
}

function asMessageRole(role: string): MessageRole | null {
  return role === "user" || role === "assistant" ? role : null;
}

/**
 * Narrow a persisted citation payload (`Citation.model_dump(mode="json")`)
 * into the typed `Citation`. Returns `null` for a payload missing the
 * required non-empty `id` so a malformed stored entry is dropped rather
 * than rendered as an anchorless panel section. Mirrors the SSE-side
 * narrowing in `MessageInput`'s `parseCitation` — same wire shape, a
 * separate (persisted) seam.
 */
function toCitation(raw: unknown): Citation | null {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const id = record.id;
  if (typeof id !== "string" || id.length === 0) {
    return null;
  }
  const rawScore = record.score;
  const score =
    typeof rawScore === "number" && Number.isFinite(rawScore) ? rawScore : null;
  const rawMeta = record.metadata;
  const metadata =
    rawMeta !== null && typeof rawMeta === "object" && !Array.isArray(rawMeta)
      ? (rawMeta as Record<string, unknown>)
      : {};
  return {
    id,
    title: typeof record.title === "string" ? record.title : "",
    url: typeof record.url === "string" ? record.url : "",
    snippet: typeof record.snippet === "string" ? record.snippet : "",
    score,
    metadata,
  };
}

/**
 * Pull the persisted grounding citations off a stored message. Citations
 * ride `metadata.citations` as a list of serialized `Citation`s (written
 * by `persist_turn`); a user turn — or an assistant turn with none —
 * yields `[]`, and malformed entries are dropped.
 */
function citationsFrom(metadata: Record<string, unknown> | undefined): Citation[] {
  const raw = metadata?.citations;
  if (!Array.isArray(raw)) {
    return [];
  }
  const citations: Citation[] = [];
  for (const entry of raw) {
    const citation = toCitation(entry);
    if (citation !== null) {
      citations.push(citation);
    }
  }
  return citations;
}

/**
 * Map one stored message onto a `ChatMessage`, or `null` when its role is
 * outside the rendered set. Backend `ChatRole` also carries `system` /
 * `tool`; the chat transcript renders only `user` / `assistant`, so the
 * other roles are dropped from the rehydrated view.
 */
function toChatMessage(record: MessageRecordWire): ChatMessage | null {
  const role = asMessageRole(record.role);
  if (role === null) {
    return null;
  }
  const citations = citationsFrom(record.metadata);
  return {
    id: record.id,
    role,
    content: record.content,
    ...(citations.length > 0 ? { citations } : {}),
  };
}

/**
 * Fetch a persisted conversation and rehydrate it as a `ChatMessage[]`
 * transcript keyed by `conversationId`. `system` / `tool` messages are
 * dropped; each assistant turn's stored citations are rehydrated so the
 * citation panels render without re-running retrieval.
 *
 * @throws Error when the response status is not 2xx (404 when the
 * conversation does not exist or is not owned by the caller).
 */
export async function fetchConversation(id: string): Promise<LoadedConversation> {
  const url = `${backendUrl()}/api/history/conversations/${encodeURIComponent(id)}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json", ...userIdHeaders() },
  });
  if (!response.ok) {
    throw new Error(
      `fetchConversation: request failed with status ${response.status}`,
    );
  }
  const detail = (await response.json()) as ConversationDetailWire;
  const records = Array.isArray(detail.messages) ? detail.messages : [];
  const messages: ChatMessage[] = [];
  for (const record of records) {
    const message = toChatMessage(record);
    if (message !== null) {
      messages.push(message);
    }
  }
  return { conversationId: id, messages };
}
