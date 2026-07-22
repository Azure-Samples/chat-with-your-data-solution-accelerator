/**
 * Wire shapes + chat-domain state types. Mirrors the conversation /
 * history / SSE surfaces in `src/backend/`:
 *
 * - `StreamChannel` / `StreamEvent` / `StreamMessage` mirror the SSE
 *   contract pinned by `backend.core.types.OrchestratorChannel` and
 *   the `POST /api/conversation` request body (see ADR 0007).
 * - `MessageRole` / `ChatMessage` / `ChatState` are the FE-owned
 *   domain state shapes held by `<ChatProvider>` and its reducer.
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
  /**
   * Transient retrieval narration from a `reasoning` SSE frame marked
   * `metadata.placeholder`. Held apart from `reasoning` so the panel can
   * show it only until real model reasoning arrives: the renderer
   * prefers `reasoning` when non-empty and falls back to this otherwise,
   * so a reasoning-capable model drops it the instant the first native
   * frame streams, while a non-reasoning model keeps it as the sole
   * panel content.
   */
  reasoningPlaceholder?: string;
  /** True while an SSE stream is actively appending to this message. */
  streaming?: boolean;
  /** Inline error notice from a `channel: "error"` SSE frame. */
  error?: string;
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
   * Id of the conversation this transcript belongs to, or `null` for a
   * fresh chat whose first turn has not been persisted yet. Set from the
   * terminal `conversation` SSE control frame once the backend persists a
   * turn, or from a history selection when an existing conversation is
   * loaded; cleared by a reset / new-chat so the next message starts a
   * new conversation.
   */
  conversationId: string | null;
  /**
   * Id of the citation the user most recently focused via an inline
   * `[docN]` answer-bubble token. `<CitationPanel>` reads this to
   * auto-expand the matching accordion item. `null` means no inline
   * focus is active -- the panel renders with all items collapsed.
   * Cleared by future history navigation, conversation reset, or
   * an explicit user-driven panel close.
   */
  focusedCitationId: string | null;
  /**
   * The citation whose source detail is shown in the right-side
   * detail column. Set when the user clicks a reference chip
   * (`show_citation`) and cleared when the column is dismissed
   * (`close_citation`) or the conversation resets. `null` means the
   * detail column is closed and the chat occupies the full width.
   */
  activeCitation: Citation | null;
}

export interface HistoryConversation {
  id: string;
  title: string;
  updated_at: string;
}
