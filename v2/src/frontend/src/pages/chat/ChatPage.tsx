/**
 * Pillar: Scenario Pack
 * Phase: 2 +
 *        6 (visual polish — page grid layout, pulled forward for boss demo)
 *
 * Composes the chat shell: <ChatProvider> + <HistoryPanel> +
 * <MessageList> + <MessageInput>. The history panel landed in
 * dev_plan #32; SSE wiring lands in #24, conversation-id rehydration
 * in #25. Phase-6 polish wraps the body in a CSS Modules grid: optional
 * sidebar (driven by `historyOpen` from the parent App shell) + a
 * centered main column with scrolling messages above the composer.
 */
import { useState } from "react";
import { ChatProvider } from "./ChatContext";
import { HistoryPanel } from "./components/HistoryPanel";
import { MessageList } from "./components/MessageList";
import { MessageInput } from "./components/MessageInput";
import styles from "./ChatPage.module.css";

export interface ChatPageProps {
  historyOpen?: boolean;
}

export function ChatPage({ historyOpen = false }: ChatPageProps = {}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <ChatProvider>
      <section
        aria-label="chat"
        data-testid="chat-page"
        className={styles.shell}
        data-history-open={historyOpen ? "true" : "false"}
      >
        <h2 className={styles.srOnly}>Chat</h2>
        <div className={styles.main}>
          <div className={styles.scroll}>
            <div className={styles.column}>
              <MessageList />
            </div>
          </div>
          <div className={styles.composer}>
            <div className={styles.composerColumn}>
              <MessageInput />
            </div>
          </div>
        </div>
        <aside className={styles.sidebar}>
          <HistoryPanel selectedId={selectedId} onSelect={setSelectedId} />
        </aside>
      </section>
    </ChatProvider>
  );
}
