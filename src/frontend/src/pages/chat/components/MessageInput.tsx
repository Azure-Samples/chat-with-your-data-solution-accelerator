/**
 * Controlled chat input wired to the backend SSE feed.
 *
 * On submit:
 *   1. Dispatches an `add` action with the user message.
 *   2. Dispatches an `add` action with an assistant placeholder
 *      (`streaming: true`, empty `content`, empty `reasoning`).
 *   3. Calls `streamChat(history)` and folds each event into the
 *      placeholder via `append_answer` / `append_reasoning` /
 *      `append_citation` / `set_error` actions on `ChatContext`.
 *   4. Dispatches `finish_stream` once the iterator completes.
 *
 * Citation frames are narrowed via the local `parseCitation` helper
 * before dispatch so a malformed wire payload (missing `id`) is
 * dropped at the boundary rather than corrupting reducer state. The
 * tool channel is still dropped.
 *
 * Input + Send are disabled while a stream is in flight so the user
 * can't fire a second request mid-response. The mic toggle uses
 * Fluent's <ToggleButton>, which emits `aria-pressed` natively in line
 * with the existing test contract.
 */
import {
  useEffect,
  useRef,
  useState,
  type SyntheticEvent,
} from "react";
import { Button, ToggleButton } from "@fluentui/react-components";
import {
  Broom24Regular,
  Mic24Regular,
  MicOff24Regular,
  Send24Regular,
  Stop24Regular,
} from "@fluentui/react-icons";
import { useChat } from "@/pages/chat/ChatContext";
import { streamChat } from "@/api/streamChat";
import type {
  ChatMessage,
  Citation,
  StreamMessage,
} from "@/models/chat";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import styles from "./MessageInput.module.css";

function newId(): string {
  // crypto.randomUUID is available in modern browsers and jsdom 25+.
  return globalThis.crypto.randomUUID();
}

/**
 * Narrow a `citation` SSE frame's `metadata` payload into the typed
 * `Citation` shape. Returns `null` when the wire is missing the
 * required `id` field -- without an id the reducer can't dedupe, and
 * a panel section with no source identifier has no anchor to link
 * to, so dropping is safer than rendering a half-built section.
 * Missing optional fields fall back to the same defaults Pydantic v2
 * applies on the backend (`title=""`, `url=""`, `snippet=""`,
 * `score=None`, `metadata={}`).
 */
function parseCitation(metadata: Record<string, unknown>): Citation | null {
  const id = metadata.id;
  if (typeof id !== "string" || id.length === 0) return null;
  const rawScore = metadata.score;
  const score =
    typeof rawScore === "number" && Number.isFinite(rawScore)
      ? rawScore
      : null;
  const rawMeta = metadata.metadata;
  const inner =
    rawMeta !== null &&
    typeof rawMeta === "object" &&
    !Array.isArray(rawMeta)
      ? (rawMeta as Record<string, unknown>)
      : {};
  return {
    id,
    title: typeof metadata.title === "string" ? metadata.title : "",
    url: typeof metadata.url === "string" ? metadata.url : "",
    snippet:
      typeof metadata.snippet === "string" ? metadata.snippet : "",
    score,
    metadata: inner,
  };
}

export function MessageInput() {
  const { state, dispatch } = useChat();
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const speech = useSpeechRecognition();

  // Snapshot of the draft when the mic was pressed, so dictation appends
  // on top of already-typed text instead of replacing it.
  const baseDraftRef = useRef("");

  // Holds the AbortController for the in-flight stream so the Cancel
  // button can abort it. Cleared in the submit `finally` so a stale
  // controller can't fire a no-op abort against a closed stream.
  const controllerRef = useRef<AbortController | null>(null);

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

  async function handleSubmit(event: SyntheticEvent<HTMLFormElement>) {
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

    // Snapshot history BEFORE the dispatch -- `state.messages` from this
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

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      for await (const ev of streamChat(history, {
        // Continue the active thread when one exists; `null` starts a
        // fresh conversation -- the backend mints the id and returns it
        // on the terminal `conversation` control frame, surfaced via
        // `onConversationId` below.
        conversationId: state.conversationId,
        signal: controller.signal,
        // Record the backend-resolved id so the next turn appends to
        // the same conversation instead of starting another.
        onConversationId: (conversationId) => {
          dispatch({ type: "set_conversation_id", conversationId });
        },
      })) {
        switch (ev.channel) {
          case "answer":
            dispatch({
              type: "append_answer",
              id: assistantId,
              chunk: ev.content,
            });
            break;
          case "reasoning":
            // A `placeholder`-marked frame is the transient retrieval
            // narration: route it to the placeholder slot (shown only
            // until real reasoning lands) instead of the reasoning
            // stream, so it is dropped the instant a native frame
            // arrives.
            if (ev.metadata.placeholder === true) {
              dispatch({
                type: "set_reasoning_placeholder",
                id: assistantId,
                text: ev.content,
              });
            } else {
              dispatch({
                type: "append_reasoning",
                id: assistantId,
                chunk: ev.content,
              });
            }
            break;
          case "error":
            dispatch({
              type: "set_error",
              id: assistantId,
              error: ev.content,
            });
            break;
          case "citation": {
            const citation = parseCitation(ev.metadata);
            if (citation !== null) {
              dispatch({
                type: "append_citation",
                id: assistantId,
                citation,
              });
            }
            break;
          }
          // tool channel is intentionally dropped.
        }
      }
      dispatch({ type: "finish_stream", id: assistantId });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User-initiated cancel -- keep whatever content streamed in,
        // mark the message done, do NOT surface an error toast.
        dispatch({ type: "finish_stream", id: assistantId });
      } else {
        const message = err instanceof Error ? err.message : String(err);
        dispatch({ type: "set_error", id: assistantId, error: message });
      }
    } finally {
      controllerRef.current = null;
      setIsStreaming(false);
    }
  }

  function handleCancel() {
    controllerRef.current?.abort();
  }

  function handleClear() {
    dispatch({ type: "reset" });
  }

  const clearDisabled = isStreaming || state.messages.length === 0;

  const micLabel =
    speech.error !== null
      ? `Microphone unavailable: ${speech.error}`
      : speech.isListening
        ? "Stop dictation"
        : "Start dictation";
  const micTitle =
    speech.error ?? (speech.isListening ? "Stop dictation" : "Start dictation");

  return (
    <form
      onSubmit={(e) => {
        void handleSubmit(e);
      }}
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
        onChange={(e) => {
          setDraft(e.target.value);
        }}
        placeholder="Type a message…"
        autoComplete="off"
        disabled={isStreaming || speech.isListening}
        className={styles.field}
      />
      <Button
        appearance="subtle"
        shape="circular"
        type="button"
        onClick={handleClear}
        disabled={clearDisabled}
        aria-label="New conversation"
        title="Clear conversation"
        data-testid="message-input-clear"
        icon={<Broom24Regular />}
        className={styles.mic}
      />
      <ToggleButton
        appearance="subtle"
        shape="circular"
        checked={speech.isListening}
        onClick={() => {
          void toggleMic();
        }}
        disabled={micDisabled}
        aria-label={micLabel}
        title={micTitle}
        data-testid="message-input-mic"
        icon={
          speech.isListening ? <MicOff24Regular /> : <Mic24Regular />
        }
        className={styles.mic}
      />
      {isStreaming ? (
        <Button
          appearance="primary"
          shape="circular"
          type="button"
          onClick={handleCancel}
          aria-label="Cancel"
          title="Stop generating"
          data-testid="message-input-cancel"
          icon={<Stop24Regular />}
          className={styles.send}
        />
      ) : (
        <Button
          appearance="primary"
          shape="circular"
          type="submit"
          disabled={!canSend}
          aria-label="Send"
          title="Send"
          icon={<Send24Regular />}
          className={styles.send}
        />
      )}
    </form>
  );
}
