/**
 * Pillar: Stable Core
 * Phase: 2
 *
 * Renders the chat transcript from ChatContext. Pure presentational
 * component — subscribes via useChat() and emits one <li> per message.
 * Backend wiring (SSE answer/reasoning events) lands in dev_plan #24.
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
        </li>
      ))}
    </ol>
  );
}
