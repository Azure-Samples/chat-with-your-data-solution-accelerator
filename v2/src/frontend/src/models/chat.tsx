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

export const StreamChannel = {
  Reasoning: "reasoning",
  Tool: "tool",
  Answer: "answer",
  Citation: "citation",
  Error: "error",
} as const;
export type StreamChannel = (typeof StreamChannel)[keyof typeof StreamChannel];

export interface StreamMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface StreamEvent {
  channel: StreamChannel;
  content: string;
  metadata: Record<string, unknown>;
}

/**
 * One source citation surfaced alongside an answer. Mirrors
 * `backend.core.types.Citation`: `id` is the provider-specific
 * source / chunk id (used for dedupe and `[docN]` token wiring);
 * `title`, `url`, `snippet` are renderable display fields; `score`
 * is the normalized 0..1 relevance when the provider exposes one;
 * `metadata` carries the rest of the provider payload verbatim so
 * the panel can surface per-provider extras without a wire change.
 */
export interface Citation {
  id: string;
  title: string;
  url: string;
  snippet: string;
  score: number | null;
  metadata: Record<string, unknown>;
}

export const MessageRole = {
  User: "user",
  Assistant: "assistant",
} as const;
export type MessageRole = (typeof MessageRole)[keyof typeof MessageRole];

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
  /**
   * Citations collected from `channel: "citation"` SSE frames during
   * the answer stream. Each entry is the wire mirror of
   * `backend.core.types.Citation`. The reducer dedupes by `id` so a
   * single source surfaced across multiple chunks lands once.
   * Rendered by `<CitationPanel>`; absent / empty arrays hide the
   * panel entirely.
   */
  citations?: Citation[];
}

export interface ChatState {
  messages: ChatMessage[];
  /**
   * Id of the citation the user most recently focused via an inline
   * `[docN]` answer-bubble token. `<CitationPanel>` reads this to
   * auto-expand the matching accordion item. `null` means no inline
   * focus is active — the panel renders with all items collapsed.
   * Cleared by future history navigation, conversation reset, or
   * an explicit user-driven panel close.
   */
  focusedCitationId: string | null;
}

export interface HistoryConversation {
  id: string;
  title: string;
  updated_at: string;
}
