/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Wire shapes + chat-domain state types. Mirrors the conversation /
 * history / SSE surfaces in `v2/src/backend/`:
 *
 * - `StreamChannel` / `StreamEvent` / `StreamMessage` mirror the SSE
 *   contract pinned by `backend.core.types.OrchestratorChannel` and
 *   the `POST /api/conversation` request body (see ADR 0007).
 * - `MessageRole` / `ChatMessage` / `ChatState` are the FE-owned
 *   domain state shapes held by `<ChatProvider>` and its reducer.
 *   `ChatMessage.feedback` mirrors `backend.core.types.MessageRecord.feedback`.
 * - `HistoryConversation` mirrors a single row of
 *   `GET /api/history/conversations`.
 */

export type StreamChannel =
  | "reasoning"
  | "tool"
  | "answer"
  | "citation"
  | "error";

export interface StreamMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface StreamEvent {
  channel: StreamChannel;
  content: string;
  metadata: Record<string, unknown>;
}

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  /** Reasoning frames collected from the SSE feed. Empty/absent for user msgs. */
  reasoning?: string[];
  /** True while an SSE stream is actively appending to this message. */
  streaming?: boolean;
  /** Inline error notice from a `channel: "error"` SSE frame. */
  error?: string;
  /**
   * Persisted feedback value for this message, mirrored from
   * `MessageRecord.feedback`. `null` (or absent) means the user has not
   * submitted feedback yet; a non-empty string is the freeform value the
   * backend stored (e.g. `"positive"`, `"negative"`, or a structured
   * reason payload). `<FeedbackButtons>` reads this to drive the
   * selected-state visualization.
   */
  feedback?: string | null;
}

export interface ChatState {
  messages: ChatMessage[];
}

export interface HistoryConversation {
  id: string;
  title: string;
  updated_at: string;
}
