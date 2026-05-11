/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half) +
 *        6 (visual polish — bubble layout, pulled forward for boss demo;
 *           H6 patch 2026-05-08: live "Thinking…" panel) +
 *        4 (MACAE re-skin — assistant runs as full-width prose with no
 *           bubble; user is a brand-tinted right-aligned chip; avatars
 *           use Fluent v9 icons; empty state uses Fluent Chat48 +
 *           Title2 "Start a conversation".)
 *
 * Renders the chat transcript from ChatContext. Each message renders a
 * single <li> with a per-row layout: a 28x28 round avatar (Fluent
 * Person20Regular for user, Bot20Regular for assistant) + a content
 * region. The row direction flips per role (user-right / assistant-left)
 * via CSS Modules driven by the `data-role` attribute. Assistant
 * messages carrying SSE-derived metadata are decorated:
 *   - `streaming === true` OR non-empty `reasoning?: string[]` → a
 *     <details> reasoning panel. While streaming the panel is forced
 *     open with summary "Thinking…" + animated dots so the boss-demo
 *     viewer sees the model think live; once `finish_stream` clears
 *     `streaming`, the summary collapses to "▸ Thought process" and
 *     the user can re-expand on demand. Body joins all reasoning
 *     chunks (foundry_iq emits per-token deltas, so per-<li> would
 *     read as one-character mush — we concatenate at render time and
 *     keep the array shape on the wire).
 *   - `error?: string`                   → inline `role="alert"` notice.
 * Both decorations are skipped when neither field applies.
 *
 * All `data-testid` and `data-role` attributes are preserved verbatim
 * from the Phase-5 contract — visual changes only.
 */
import {
  Bot20Regular,
  Chat48Regular,
  Person20Regular,
} from "@fluentui/react-icons";
import { useChat } from "../ChatContext";
import styles from "./MessageList.module.css";

export function MessageList() {
  const { state } = useChat();

  if (state.messages.length === 0) {
    return (
      <div className={styles.empty}>
        <Chat48Regular
          aria-hidden="true"
          className={styles.emptyIcon}
        />
        <p data-testid="message-list-empty" className={styles.emptyText}>
          Start a conversation
        </p>
      </div>
    );
  }

  return (
    <ol data-testid="message-list" className={styles.list}>
      {state.messages.map((m) => (
        <li
          key={m.id}
          data-testid={`message-${m.id}`}
          data-role={m.role}
          className={styles.item}
        >
          <div className={styles.row}>
            <span
              className={styles.avatar}
              data-role={m.role}
              aria-hidden="true"
            >
              {m.role === "user" ? <Person20Regular /> : <Bot20Regular />}
            </span>
            <span className={styles.srOnly}>{m.role}</span>
            <div className={styles.bubble}>{m.content}</div>
          </div>
          {(m.streaming === true ||
            (m.reasoning && m.reasoning.length > 0)) && (
            <details
              data-testid={`message-${m.id}-reasoning`}
              className={styles.reasoning}
              open={m.streaming === true}
            >
              <summary data-streaming={m.streaming ? "true" : "false"}>
                {m.streaming ? (
                  <>
                    Thinking
                    <span className={styles.thinkingDots} aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </span>
                  </>
                ) : (
                  "\u25B8 Thought process"
                )}
              </summary>
              <div className={styles.reasoningBody}>
                {m.reasoning?.join("") ?? ""}
              </div>
            </details>
          )}
          {m.error && (
            <p
              data-testid={`message-${m.id}-error`}
              role="alert"
              className={styles.error}
            >
              {m.error}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
