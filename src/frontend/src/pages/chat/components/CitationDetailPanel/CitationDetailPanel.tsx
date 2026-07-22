/**
 * Source detail column shown to the right of the chat transcript when
 * the user clicks a reference chip. Reads the selected citation from
 * chat state and renders, top to bottom: a "Citations" header with a
 * dismiss control, the document title, an "Open document" deep-link
 * (resolved by `deriveDocumentHref` from the citation's blob name or
 * URL, omitted when neither is usable), and the reference text
 * rendered through `<MarkdownContent>` so markdown in the snippet
 * becomes formatted HTML -- without `rehype-raw`, so any embedded raw
 * HTML stays escaped and XSS-safe.
 *
 * The header, title, and deep-link form a pinned head; only the
 * reference body scrolls, and it is keyed by citation id so switching
 * sources resets the body to the top instead of inheriting the prior
 * scroll position.
 *
 * Returns `null` when no citation is active so the column collapses
 * and the chat reclaims the full width. Dismissing dispatches
 * `close_citation`, which clears the active citation and unmounts the
 * column on the next render.
 */
import { Dismiss20Regular } from "@fluentui/react-icons";
import { ChatActionType, useChat } from "@/pages/chat/ChatContext";
import { MarkdownContent } from "@/pages/chat/components/MarkdownContent";
import { deriveDocumentHref } from "./documentHref";
import styles from "./CitationDetailPanel.module.css";

export function CitationDetailPanel() {
  const { state, dispatch } = useChat();
  const citation = state.activeCitation;
  if (citation === null) return null;

  const title = citation.title.length > 0 ? citation.title : "Source";
  const documentHref = deriveDocumentHref(citation);

  return (
    <aside
      className={styles.panel}
      aria-label="Citation detail"
      data-testid="citation-detail-panel"
    >
      <header className={styles.header}>
        <span className={styles.heading}>Citations</span>
        <button
          type="button"
          className={styles.dismiss}
          aria-label="Close citation detail"
          onClick={() => {
            dispatch({ type: ChatActionType.CloseCitation });
          }}
          data-testid="citation-detail-dismiss"
        >
          <Dismiss20Regular />
        </button>
      </header>
      <h3 className={styles.title} data-testid="citation-detail-title">
        {title}
      </h3>
      {documentHref !== null && (
        <a
          href={documentHref}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.link}
          data-testid="citation-detail-link"
        >
          Open document
        </a>
      )}
      <div
        key={citation.id}
        className={styles.body}
        data-testid="citation-detail-body"
      >
        <MarkdownContent content={citation.snippet} />
      </div>
    </aside>
  );
}
