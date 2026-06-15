/**
 * Pillar: Scenario Pack
 * Phase: 2 +
 *        6 (visual polish — page grid layout, pulled forward for boss demo) +
 *        4 (MACAE re-skin — sidebar moved LEFT, hosted inside CoralShellRow)
 *
 * Composes the chat shell: <ChatProvider> + <HistoryPanel> +
 * <MessageList> + <MessageInput>. The history panel landed in
 * dev_plan #32; SSE wiring lands in #24, conversation-id rehydration
 * in #25. Phase-6 polish wraps the body in a CSS Modules grid: optional
 * sidebar (driven by `historyOpen` from the parent App shell) docked
 * on the LEFT (matching MACAE) + a centered main column with scrolling
 * messages above the composer. Page height is governed by the parent
 * `<CoralShellRow>` (flex:1 / min-height:0) — this shell just fills
 * 100% and lets its grid cells handle their own overflow.
 */
import { useState } from "react";
import { ChatProvider, useChat } from "./ChatContext";
import { PanelLeft } from "@/components/CoralShell/PanelLeft";
import { HistoryPanel } from "./components/HistoryPanel";
import { MessageList } from "./components/MessageList";
import { MessageInput } from "./components/MessageInput";
import { CitationDetailPanel } from "./components/CitationDetailPanel/CitationDetailPanel";
import styles from "./ChatPage.module.css";

export interface ChatPageProps {
  historyOpen?: boolean;
}

/**
 * Context-reading body. Lives inside <ChatProvider> so it can read the
 * active citation and drive the `data-citation-open` flag that widens
 * the right-hand source detail column. The chat `.main` cell is `1fr`,
 * so opening the column narrows the conversation (push layout) instead
 * of overlaying it.
 */
function ChatShell({ historyOpen }: { historyOpen: boolean }) {
  const { state } = useChat();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const citationOpen = state.activeCitation !== null;
  return (
    <section
      aria-label="chat"
      data-testid="chat-page"
      className={styles.shell}
      data-history-open={historyOpen ? "true" : "false"}
      data-citation-open={citationOpen ? "true" : "false"}
    >
      <h2 className={styles.srOnly}>Chat</h2>
      <PanelLeft
        aria-label="conversation history"
        className={styles.sidebar}
      >
        <HistoryPanel selectedId={selectedId} onSelect={setSelectedId} />
      </PanelLeft>
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
      <div className={styles.citationColumn}>
        <CitationDetailPanel />
      </div>
    </section>
  );
}

export function ChatPage({ historyOpen = false }: ChatPageProps = {}) {
  return (
    <ChatProvider>
      <ChatShell historyOpen={historyOpen} />
    </ChatProvider>
  );
}
