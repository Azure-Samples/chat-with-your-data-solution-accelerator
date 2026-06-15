/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Source references surfaced under a finished assistant message.
 * Renders a collapsible reference block that mirrors the v1 chat
 * appearance: a single "N references" / "1 reference" toggle (with a
 * chevron that flips between closed and open) reveals a numbered list
 * of sources. Each source is a Fluent v9 `<AccordionItem>` keyed by
 * the provider-supplied `id`; its header shows the 1-based position
 * and the citation title (or a `Citation N` fallback when the wire
 * omits one), and its panel body shows the snippet plus a clickable
 * URL deep-link that opens the source in a new tab with safe
 * `rel="noopener noreferrer"` semantics.
 *
 * The inner list stays mounted but `hidden` while the block is
 * collapsed, so inline `[docN]` token focus can resolve a citation
 * even before the user opens the block.
 *
 * Empty / absent `citations` props short-circuit to `null` so the
 * block adds zero DOM noise to messages with no sources.
 *
 * Both the outer block and the inner items are controlled internally
 * so the optional `focusedCitationId` prop (driven by inline `[docN]`
 * token clicks in the answer bubble) can open the block and expand
 * the matching item without stealing the user's manual open/close
 * state. The effect is additive — focusing a new item never collapses
 * items the user has already opened.
 */
import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
} from "@fluentui/react-components";
import {
  ChevronDown16Regular,
  ChevronRight16Regular,
} from "@fluentui/react-icons";
import type { Citation } from "@/models/chat";
import styles from "./CitationPanel.module.css";

export interface CitationPanelProps {
  messageId: string;
  citations: Citation[];
  /**
   * Citation id the parent has flagged as focused (typically because
   * the user clicked an inline `[docN]` token in the answer bubble).
   * When the id matches one of the supplied citations the block opens
   * and the matching item is auto-expanded; unknown ids and `null`
   * are ignored so this prop is always safe to wire even when no
   * token focus has happened yet.
   */
  focusedCitationId?: string | null;
}

function headerLabel(citation: Citation, index: number): string {
  if (citation.title.length > 0) return citation.title;
  return `Citation ${index + 1}`;
}

function toggleLabel(count: number): string {
  return count === 1 ? "1 reference" : `${count} references`;
}

export function CitationPanel({
  messageId,
  citations,
  focusedCitationId = null,
}: CitationPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [openItems, setOpenItems] = useState<string[]>([]);

  useEffect(() => {
    if (focusedCitationId === null) return;
    // Only react when the focused id resolves to one of our citations
    // — unknown ids (stale state from a previous message, mistyped
    // token, etc.) must not open the block or mutate the open set.
    const isKnown = citations.some((c) => c.id === focusedCitationId);
    if (!isKnown) return;
    setExpanded(true);
    setOpenItems((prev) =>
      prev.includes(focusedCitationId) ? prev : [...prev, focusedCitationId],
    );
  }, [focusedCitationId, citations]);

  if (citations.length === 0) return null;

  const bodyId = `citations-body-${messageId}`;

  return (
    <section
      data-testid={`citation-panel-${messageId}`}
      aria-label="References"
      className={styles.section}
    >
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={() => setExpanded((value) => !value)}
        data-testid={`citations-toggle-${messageId}`}
      >
        {expanded ? <ChevronDown16Regular /> : <ChevronRight16Regular />}
        <span className={styles.toggleLabel}>
          {toggleLabel(citations.length)}
        </span>
      </button>
      <div id={bodyId} hidden={!expanded} data-testid={bodyId}>
        <Accordion
          collapsible
          multiple
          openItems={openItems}
          onToggle={(_event, data) => {
            setOpenItems(data.openItems as string[]);
          }}
          data-testid={`citation-list-${messageId}`}
        >
          {citations.map((citation, index) => (
            <AccordionItem
              key={citation.id}
              value={citation.id}
              data-testid={`citation-${messageId}-${citation.id}`}
            >
              <AccordionHeader
                data-testid={`citation-${messageId}-${citation.id}-header`}
              >
                <span className={styles.headerRow}>
                  <span className={styles.number} aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className={styles.title}>
                    {headerLabel(citation, index)}
                  </span>
                </span>
              </AccordionHeader>
              <AccordionPanel
                data-testid={`citation-${messageId}-${citation.id}-panel`}
              >
                {citation.snippet.length > 0 && (
                  <p className={styles.snippet}>{citation.snippet}</p>
                )}
                {citation.url.length > 0 && (
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.link}
                    data-testid={`citation-${messageId}-${citation.id}-link`}
                  >
                    Open source
                  </a>
                )}
              </AccordionPanel>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
