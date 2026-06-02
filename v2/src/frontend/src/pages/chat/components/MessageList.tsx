/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half) +
 *        6 (visual polish — bubble layout, pulled forward for boss demo;
 *           H6 patch 2026-05-08: live "Thinking…" panel) +
 *        4 (MACAE re-skin — assistant runs as full-width prose with no
 *           bubble; user is a brand-tinted right-aligned chip; avatars
 *           use Fluent v9 icons; empty state uses Fluent Chat48 +
 *           Title2 "Start a conversation".) +
 *        7 (Testing + Documentation — wire <FeedbackButtons> per
 *           assistant message; optimistic set_feedback dispatch then
 *           POST /api/history/messages/{id}/feedback via setFeedback();
 *           rollback the dispatch on API failure.)
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
 * Finished assistant messages (`streaming !== true`) additionally
 * render a <FeedbackButtons> row. Click flow is optimistic: dispatch
 * `set_feedback` first so the thumb visually "locks in" before the
 * fetch round-trip, then call `setFeedback()`. If the POST fails the
 * dispatch rolls back to the prior value so the UI matches reality.
 * The reasoning panel and error notice render unchanged when feedback
 * is present — feedback is a sibling, not a wrapper.
 *
 * All `data-testid` and `data-role` attributes are preserved verbatim
 * from the Phase-5 contract — visual changes only.
 */
import { useCallback } from "react";
import {
  Bot20Regular,
  Chat48Regular,
  Person20Regular,
} from "@fluentui/react-icons";
import { useChat } from "../ChatContext";
import type { ChatMessage } from "../../../models/chat";
import { setFeedback } from "../../../api/feedback";
import { FeedbackButtons } from "./FeedbackButtons";
import styles from "./MessageList.module.css";

export function MessageList() {
  const { state, dispatch } = useChat();

  const handleFeedback = useCallback(
    async (m: ChatMessage, value: string): Promise<void> => {
      const previous = m.feedback ?? null;
      dispatch({ type: "set_feedback", id: m.id, feedback: value });
      try {
        await setFeedback(m.id, value);
      } catch {
        // Rollback: the backend rejected the feedback (404/422/5xx),
        // so revert the optimistic dispatch and let the UI reflect
        // reality. We intentionally swallow the error — there is no
        // user-visible error surface for feedback failures today,
        // and the rollback is the only visible-tier correction.
        dispatch({ type: "set_feedback", id: m.id, feedback: previous });
      }
    },
    [dispatch],
  );

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
          {m.role === "assistant" && m.streaming !== true && (
            <FeedbackButtons
              messageId={m.id}
              feedback={m.feedback}
              onSubmit={(value) => handleFeedback(m, value)}
            />
          )}
        </li>
      ))}
    </ol>
  );
}
