/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
 *
 * Controlled chat input wired to the backend SSE feed.
 *
 * On submit:
 *   1. Dispatches an `add` action with the user message.
 *   2. Dispatches an `add` action with an assistant placeholder
 *      (`streaming: true`, empty `content`, empty `reasoning`).
 *   3. Calls `streamChat(history)` and folds each event into the
 *      placeholder via `append_answer` / `append_reasoning` /
 *      `set_error` actions on `ChatContext`.
 *   4. Dispatches `finish_stream` once the iterator completes.
 *
 * Citation and tool channels are intentionally dropped here — the demo
 * scope (per session plan) is pure-LLM chat with no RAG. Phase 5
 * follow-ups (citation cards, tool-step visualization) live on the FE
 * team's #24 backlog.
 *
 * Input + Send are disabled while a stream is in flight so the user
 * can't fire a second request mid-response.
 */
import { useState, type FormEvent } from "react";
import { useChat, type ChatMessage } from "../ChatContext";
import { streamChat, type StreamMessage } from "../../../api/streamChat";

function newId(): string {
  // crypto.randomUUID is available in modern browsers and jsdom 25+.
  return globalThis.crypto.randomUUID();
}

export function MessageInput() {
  const { state, dispatch } = useChat();
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const trimmed = draft.trim();
  const canSend = trimmed.length > 0 && !isStreaming;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSend) return;

    const userMessage: ChatMessage = {
      id: newId(),
      role: "user",
      content: trimmed,
    };
    const assistantId = newId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      reasoning: [],
      streaming: true,
    };

    // Snapshot history BEFORE the dispatch — `state.messages` from this
    // closure is the pre-dispatch value, and we add the new user turn
    // ourselves to keep the wire payload aligned with what the user
    // actually saw on screen at submit time.
    const history: StreamMessage[] = [
      ...state.messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user", content: trimmed },
    ];

    dispatch({ type: "add", message: userMessage });
    dispatch({ type: "add", message: assistantMessage });
    setDraft("");
    setIsStreaming(true);

    try {
      for await (const ev of streamChat(history)) {
        switch (ev.channel) {
          case "answer":
            dispatch({
              type: "append_answer",
              id: assistantId,
              chunk: ev.content,
            });
            break;
          case "reasoning":
            dispatch({
              type: "append_reasoning",
              id: assistantId,
              chunk: ev.content,
            });
            break;
          case "error":
            dispatch({
              type: "set_error",
              id: assistantId,
              error: ev.content,
            });
            break;
          // citation + tool intentionally dropped for the demo.
        }
      }
      dispatch({ type: "finish_stream", id: assistantId });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      dispatch({ type: "set_error", id: assistantId, error: message });
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} data-testid="message-input">
      <label htmlFor="message-input-field">Message</label>
      <input
        id="message-input-field"
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Type a message…"
        autoComplete="off"
        disabled={isStreaming}
      />
      <button type="submit" disabled={!canSend}>
        Send
      </button>
    </form>
  );
}
