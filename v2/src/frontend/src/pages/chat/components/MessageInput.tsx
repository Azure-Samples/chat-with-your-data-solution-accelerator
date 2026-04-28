/**
 * Pillar: Stable Core
 * Phase: 2
 *
 * Controlled chat input. Dispatches an `add` action with a fresh user
 * message on submit. Backend send (SSE) is wired in dev_plan #24; for now
 * this only updates local ChatContext so the shell is testable end-to-end.
 */
import { useState, type FormEvent } from "react";
import { useChat } from "../ChatContext";

function newId(): string {
  // crypto.randomUUID is available in modern browsers and jsdom 25+.
  return globalThis.crypto.randomUUID();
}

export function MessageInput() {
  const { dispatch } = useChat();
  const [draft, setDraft] = useState("");

  const trimmed = draft.trim();
  const canSend = trimmed.length > 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSend) return;
    dispatch({
      type: "add",
      message: { id: newId(), role: "user", content: trimmed },
    });
    setDraft("");
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
      />
      <button type="submit" disabled={!canSend}>
        Send
      </button>
    </form>
  );
}
