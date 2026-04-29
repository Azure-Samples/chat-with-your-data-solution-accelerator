/**
 * Pillar: Scenario Pack
 * Phase: 2
 *
 * Composes the chat shell: <ChatProvider> + <HistoryPanel> +
 * <MessageList> + <MessageInput>. The history panel landed in
 * dev_plan #32; SSE wiring lands in #24, conversation-id rehydration
 * in #25.
 */
import { useState } from "react";
import { ChatProvider } from "./ChatContext";
import { HistoryPanel } from "./components/HistoryPanel";
import { MessageList } from "./components/MessageList";
import { MessageInput } from "./components/MessageInput";

export function ChatPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <ChatProvider>
      <section aria-label="chat" data-testid="chat-page">
        <h2>Chat</h2>
        <HistoryPanel
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <MessageList />
        <MessageInput />
      </section>
    </ChatProvider>
  );
}
