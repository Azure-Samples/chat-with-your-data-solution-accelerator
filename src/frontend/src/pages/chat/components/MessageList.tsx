/**
 * Renders the chat transcript from ChatContext. Each message renders a
 * single <li> holding one flex `.row`: a 28x28 round avatar (Fluent
 * Person20Regular for user, Bot20Regular for assistant) at the row
 * start, then the message content. The row direction flips per role
 * (user-right / assistant-left) via CSS Modules driven by the
 * `data-role` attribute. A user message places its right-aligned chip
 * bubble directly in the row. An assistant message places a vertical
 * content column beside the avatar -- so the avatar lines up on the same
 * horizontal line as the column's first item (the reasoning panel while
 * streaming, else the answer) -- and that column stacks the answer bubble,
 * a static "AI-generated content may be incorrect" disclaimer under any
 * finished answer, plus the SSE-derived decorations:
 *   - `streaming === true` OR non-empty `reasoning?: string[]` → a
 *     <details> reasoning panel. While streaming the panel is forced
 *     open with summary "Thinking…" + animated dots; once
 *     `finish_stream` clears `streaming`, the summary collapses to
 *     "▸ Thought process" and
 *     the user can re-expand on demand. Body is formatted by
 *     `formatReasoning`: foundry_iq emits per-token deltas, so per-<li>
 *     would read as one-character mush -- we concatenate at render time
 *     (keeping the array shape on the wire), drop the model's bold
 *     section titles, and break the remaining reasoning bodies apart so
 *     both orchestrators render the same way. Inline citation markers in
 *     the reasoning body are then normalized to `^N^` superscript tokens
 *     by `superscriptReasoningCitations` and rendered via `enableSupersub`,
 *     so the panel shows the same tiny superscript numbers as the answer.
 *   - referenced `Citation[]` (finished messages only) → a
 *     `<CitationPanel>` reference block under the answer, showing the
 *     renumbered subset that `parseAnswer` cited so the chip numbers
 *     match the answer's `[docN]` superscripts (falling back to the
 *     full list when the answer has no inline markers). Hidden while
 *     the message is still streaming so the block doesn't churn as
 *     new sources arrive.
 *   - `error?: string`                   → dispatched as a Fluent v9
 *     error-intent Toast (the app-wide `<Toaster>` is mounted by
 *     `<FluentThemeBridge>`). A per-component `Set<"<id>::<err>">`
 *     ref dedupes so identical SSE error frames or React Strict
 *     Mode double-invocation surface only one toast per failure.
 * Both decorations are skipped when neither field applies.
 */
import { useEffect, useRef } from "react";
import {
  Toast,
  ToastBody,
  ToastTitle,
  useToastController,
} from "@fluentui/react-components";
import {
  Bot20Regular,
  Chat48Regular,
  Person20Regular,
} from "@fluentui/react-icons";
import { ChatActionType, useChat } from "@/pages/chat/ChatContext";
import { TOASTER_ID } from "@/theme/FluentThemeBridge";
import { MarkdownContent } from "./MarkdownContent";
import { parseAnswer } from "./parseAnswer";
import { formatReasoning, superscriptReasoningCitations } from "./reasoningText";
import { CitationPanel } from "./CitationPanel/CitationPanel";
import styles from "./MessageList.module.css";

export function MessageList() {
  const { state, dispatch } = useChat();
  const { dispatchToast } = useToastController(TOASTER_ID);
  // Bottom sentinel scrolled into view whenever the transcript grows so
  // the freshest answer and live streaming tokens stay visible.
  const bottomRef = useRef<HTMLDivElement | null>(null);
  // Track every (message id, error string) pair we have already
  // toasted so identical error frames -- or React Strict Mode's
  // double-invoked effect in dev -- do not stutter the toaster. A
  // ref (not state) is right here: the dedupe set is internal
  // bookkeeping that must not trigger a re-render when it grows.
  const seenErrorsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    for (const m of state.messages) {
      if (typeof m.error !== "string" || m.error.length === 0) continue;
      const key = `${m.id}::${m.error}`;
      if (seenErrorsRef.current.has(key)) continue;
      seenErrorsRef.current.add(key);
      dispatchToast(
        <Toast>
          <ToastTitle>Message failed</ToastTitle>
          <ToastBody>{m.error}</ToastBody>
        </Toast>,
        { intent: "error" },
      );
    }
  }, [state.messages, dispatchToast]);

  // Compute a content-aware dep so the effect fires on every streamed
  // token, not just on add/finish. The last message's content length
  // changes on every append_answer dispatch.
  const lastContentLen =
    state.messages.length > 0
      ? (state.messages.at(-1)?.content.length ?? 0)
      : 0;
  useEffect(() => {
    if (state.messages.length === 0) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [state.messages.length, lastContentLen]);

  if (state.messages.length === 0) {
    return (
      <div className={styles.empty}>
        <Chat48Regular
          aria-hidden="true"
          className={styles.emptyIcon ?? ""}
        />
        <p data-testid="message-list-empty" className={styles.emptyText}>
          Start a conversation
        </p>
      </div>
    );
  }

  return (
    <>
      <ol data-testid="message-list" className={styles.list}>
      {state.messages.map((m) => {
        // The answer bubble renders the renumbered `[docN]` superscripts
        // from parseAnswer, so the reference block must show the same
        // referenced subset in the same order for the chip numbers to
        // line up. When the answer carries no inline markers, fall back
        // to the full citation list so sourced-but-unmarked answers
        // still surface their references.
        const parsed = parseAnswer(m.content, m.citations);
        const referencedCitations =
          parsed.citations.length > 0 ? parsed.citations : (m.citations ?? []);
        return (
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
              {m.role === "assistant" ? (
                <div className={styles.content}>
                  {(m.streaming === true ||
                    (m.reasoning !== undefined && m.reasoning.length > 0) ||
                    (m.reasoningPlaceholder !== undefined &&
                      m.reasoningPlaceholder.length > 0)) && (
                    <details
                      data-testid={`message-${m.id}-reasoning`}
                      className={styles.reasoning}
                      open={m.streaming === true}
                    >
                      <summary data-streaming={m.streaming ? "true" : "false"}>
                        {m.streaming ? (
                          <>
                            Thinking
                            <span
                              className={styles.thinkingDots}
                              aria-hidden="true"
                            >
                              <span />
                              <span />
                              <span />
                            </span>
                          </>
                        ) : (
                          "\u25B8 Thought process"
                        )}
                      </summary>
                      <MarkdownContent
                        className={styles.reasoningBody}
                        content={
                          m.reasoning && m.reasoning.length > 0
                            ? superscriptReasoningCitations(
                                formatReasoning(m.reasoning),
                              )
                            : (m.reasoningPlaceholder ?? "")
                        }
                        enableSupersub
                      />
                    </details>
                  )}
                  <MarkdownContent
                    className={styles.bubble}
                    content={parsed.markdownText}
                    enableSupersub
                  />
                  {m.streaming !== true && m.content.length > 0 && (
                    <p
                      data-testid={`answer-disclaimer-${m.id}`}
                      className={styles.disclaimer}
                    >
                      AI-generated content may be incorrect
                    </p>
                  )}
                  {m.streaming !== true && referencedCitations.length > 0 && (
                    <CitationPanel
                      messageId={m.id}
                      citations={referencedCitations}
                      onSelectCitation={(citation) => {
                        dispatch({
                          type: ChatActionType.ShowCitation,
                          citation,
                        });
                      }}
                    />
                  )}
                </div>
              ) : (
                <div className={styles.bubble}>{m.content}</div>
              )}
            </div>
          </li>
        );
      })}
      </ol>
      <div
        ref={bottomRef}
        data-testid="message-list-bottom"
        aria-hidden="true"
        className={styles.bottom ?? ""}
      />
    </>
  );
}
