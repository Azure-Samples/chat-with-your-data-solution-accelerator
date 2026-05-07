/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
 *
 * Renders the chat transcript from ChatContext. Each message renders a
 * single <li> with `<strong>{role}:</strong> {content}`. Assistant messages
 * carrying SSE-derived metadata are decorated:
 *   - `reasoning?: string[]` (non-empty) → collapsible <details> panel,
 *     summary "▸ Show reasoning", collapsed by default; one <li> per frame.
 *   - `error?: string`                   → inline `role="alert"` notice.
 * Both decorations are skipped when the field is absent or empty so user
 * messages and pre-stream placeholders render unchanged.
 */
import { useChat } from "../ChatContext";

export function MessageList() {
  const { state } = useChat();

  if (state.messages.length === 0) {
    return (
      <p data-testid="message-list-empty">No messages yet. Say hello.</p>
    );
  }

  return (
    <ol data-testid="message-list">
      {state.messages.map((m) => (
        <li
          key={m.id}
          data-testid={`message-${m.id}`}
          data-role={m.role}
        >
          <strong>{m.role}:</strong> {m.content}
          {m.reasoning && m.reasoning.length > 0 && (
            <details data-testid={`message-${m.id}-reasoning`}>
              <summary>{"\u25B8 Show reasoning"}</summary>
              <ol>
                {m.reasoning.map((entry, idx) => (
                  <li key={idx}>{entry}</li>
                ))}
              </ol>
            </details>
          )}
          {m.error && (
            <p
              data-testid={`message-${m.id}-error`}
              role="alert"
            >
              {m.error}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
