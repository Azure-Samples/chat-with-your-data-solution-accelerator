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
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type JSX,
} from "react";
import { useChat, type ChatMessage } from "../ChatContext";
import { streamChat, type StreamMessage } from "../../../api/streamChat";
import { useSpeechRecognition } from "../../../hooks/useSpeechRecognition";
import styles from "./MessageInput.module.css";

function newId(): string {
  // crypto.randomUUID is available in modern browsers and jsdom 25+.
  return globalThis.crypto.randomUUID();
}

function SendIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 2L11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  );
}

function MicIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 1 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 1 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function MicOffIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

export function MessageInput() {
  const { state, dispatch } = useChat();
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const speech = useSpeechRecognition();

  // Snapshot of the draft at the moment the mic was pressed. While
  // listening, the visible draft is `baseDraftRef.current` + a
  // separator + the live transcript, so the user can dictate ON TOP of
  // text they've already typed without losing it.
  const baseDraftRef = useRef("");

  useEffect(() => {
    if (!speech.isListening) return;
    const transcript = speech.transcript;
    const base = baseDraftRef.current;
    const separator = base.length > 0 && transcript.length > 0 ? " " : "";
    setDraft(base + separator + transcript);
  }, [speech.isListening, speech.transcript]);

  const trimmed = draft.trim();
  const canSend =
    trimmed.length > 0 && !isStreaming && !speech.isListening;
  const micDisabled = isStreaming || speech.error !== null;

  async function toggleMic() {
    if (speech.isListening) {
      await speech.stop();
      return;
    }
    baseDraftRef.current = draft;
    await speech.start();
  }

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
    <form
      onSubmit={handleSubmit}
      data-testid="message-input"
      className={styles.form}
    >
      <label htmlFor="message-input-field" className={styles.label}>
        Message
      </label>
      <input
        id="message-input-field"
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Type a message…"
        autoComplete="off"
        disabled={isStreaming || speech.isListening}
        className={styles.field}
      />
      <button
        type="button"
        onClick={toggleMic}
        disabled={micDisabled}
        aria-pressed={speech.isListening}
        aria-label={
          speech.error !== null
            ? `Microphone unavailable: ${speech.error}`
            : speech.isListening
              ? "Stop dictation"
              : "Start dictation"
        }
        title={
          speech.error !== null
            ? speech.error
            : speech.isListening
              ? "Stop dictation"
              : "Start dictation"
        }
        data-testid="message-input-mic"
        className={styles.mic}
      >
        {speech.isListening ? <MicOffIcon /> : <MicIcon />}
      </button>
      <button
        type="submit"
        disabled={!canSend}
        aria-label="Send"
        title="Send"
        className={styles.send}
      >
        <SendIcon />
      </button>
    </form>
  );
}
