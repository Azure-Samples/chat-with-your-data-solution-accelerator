/**
 * Pillar: Scenario Pack
 * Phase: 2 +
 *        6 (visual polish — page grid layout, pulled forward for boss demo) +
 *        4 (reference-architecture re-skin — sidebar moved LEFT, hosted inside CoralShellRow)
 *
 * Composes the chat shell: <ChatProvider> + <HistoryPanel> +
 * <MessageList> + <MessageInput>. The history panel landed in
 * dev_plan #32; SSE wiring lands in #24, conversation-id rehydration
 * in #25. Phase-6 polish wraps the body in a CSS Modules grid: optional
 * sidebar (driven by `historyOpen` from the parent App shell) docked
 * on the LEFT (matching the reference architecture) + a centered main column with scrolling
 * messages above the composer. Page height is governed by the parent
 * `<CoralShellRow>` (flex:1 / min-height:0) — this shell just fills
 * 100% and lets its grid cells handle their own overflow.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchConversation } from "@/api/conversationHistory";
import { ChatProvider, useChat } from "./ChatContext";
import { PanelLeft } from "@/components/CoralShell/PanelLeft";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
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
  const { state, dispatch } = useChat();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [historyReloadKey, setHistoryReloadKey] = useState(0);
  const prevConversationIdRef = useRef<string | null>(state.conversationId);
  const citationOpen = state.activeCitation !== null;

  // A brand-new conversation is "inserted" when the backend mints its
  // id at the end of the first persisted turn, flipping conversationId
  // null -> non-null. Bumping `historyReloadKey` on that transition
  // makes the history panel silently re-fetch so the new entry appears.
  // Selecting a past conversation from an empty chat also flips
  // null -> non-null; that yields one harmless silent refetch.
  useEffect(() => {
    if (
      prevConversationIdRef.current === null &&
      state.conversationId !== null
    ) {
      setHistoryReloadKey((key) => key + 1);
    }
    prevConversationIdRef.current = state.conversationId;
  }, [state.conversationId]);

  // Selecting a past conversation rehydrates its stored transcript +
  // persisted citations: highlight the row, fetch the saved messages,
  // then replace the live transcript via `load_conversation`.
  const handleSelect = useCallback(
    (id: string): void => {
      setSelectedId(id);
      void fetchConversation(id)
        .then((loaded) => {
          dispatch({
            type: "load_conversation",
            conversationId: loaded.conversationId,
            messages: loaded.messages,
          });
        })
        .catch(() => {
          // A failed load leaves the current transcript intact; the row
          // stays highlighted so re-selecting retries.
        });
    },
    [dispatch],
  );

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
        <HistoryPanel
          selectedId={selectedId}
          onSelect={handleSelect}
          reloadKey={historyReloadKey}
        />
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
      <ErrorBoundary>
        <ChatShell historyOpen={historyOpen} />
      </ErrorBoundary>
    </ChatProvider>
  );
}
