/**
 * Pillar: Scenario Pack
 * Phase: 2
 *
 * Composes the chat shell: <ChatProvider> + <MessageList> + <MessageInput>.
 * No backend wiring yet — that lands with the SSE client in dev_plan #24.
 */
import { ChatProvider } from "./ChatContext";
import { MessageList } from "./components/MessageList";
import { MessageInput } from "./components/MessageInput";

export function ChatPage() {
  return (
    <ChatProvider>
      <section aria-label="chat" data-testid="chat-page">
        <h2>Chat</h2>
        <MessageList />
        <MessageInput />
      </section>
    </ChatProvider>
  );
}
