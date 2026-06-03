/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Source citations surfaced under a finished assistant message.
 * Renders a Fluent v9 `<Accordion>` collapsed by default; each
 * citation lands as its own `<AccordionItem>` keyed by the
 * provider-supplied `id`. The header shows the citation title (or a
 * `[docN]`-style fallback when the wire omits one) plus the optional
 * score badge; the panel body shows the snippet body and a clickable
 * URL deep-link that opens the source in a new tab with safe
 * `rel="noopener noreferrer"` semantics.
 *
 * Empty / absent `citations` props short-circuit to `null` so the
 * panel adds zero DOM noise to messages with no sources.
 *
 * The accordion is controlled internally so the optional
 * `focusedCitationId` prop (driven by inline `[docN]` token clicks
 * in the answer bubble) can auto-expand the matching item without
 * stealing the user's manual open/close state. The effect is
 * additive — focusing a new item never collapses items the user has
 * already opened.
 */
import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
} from "@fluentui/react-components";
import type { Citation } from "../../../../models/chat";
import styles from "./CitationPanel.module.css";

export interface CitationPanelProps {
  messageId: string;
  citations: Citation[];
  /**
   * Citation id the parent has flagged as focused (typically because
   * the user clicked an inline `[docN]` token in the answer bubble).
   * When the id matches one of the supplied citations the matching
   * accordion item is auto-expanded; unknown ids and `null` are
   * ignored so this prop is always safe to wire even when no token
   * focus has happened yet.
   */
  focusedCitationId?: string | null;
}

function headerLabel(citation: Citation, index: number): string {
  if (citation.title.length > 0) return citation.title;
  return `[doc${index + 1}]`;
}

function formatScore(score: number | null): string | null {
  if (score === null) return null;
  // Render as a percentage with no decimals so the badge stays narrow
  // in the collapsed accordion header.
  return `${Math.round(score * 100)}%`;
}

export function CitationPanel({
  messageId,
  citations,
  focusedCitationId = null,
}: CitationPanelProps) {
  const [openItems, setOpenItems] = useState<string[]>([]);

  useEffect(() => {
    if (focusedCitationId === null) return;
    // Only react when the focused id resolves to one of our citations
    // — unknown ids (stale state from a previous message, mistyped
    // token, etc.) must not mutate the open set.
    const isKnown = citations.some((c) => c.id === focusedCitationId);
    if (!isKnown) return;
    setOpenItems((prev) =>
      prev.includes(focusedCitationId) ? prev : [...prev, focusedCitationId],
    );
  }, [focusedCitationId, citations]);

  if (citations.length === 0) return null;

  return (
    <section
      data-testid={`citation-panel-${messageId}`}
      aria-label="Sources"
      className={styles.section}
    >
      <h3 className={styles.heading}>Sources</h3>
      <Accordion
        collapsible
        multiple
        openItems={openItems}
        onToggle={(_event, data) => {
          setOpenItems(data.openItems as string[]);
        }}
        data-testid={`citation-list-${messageId}`}
      >
        {citations.map((citation, index) => {
          const scoreLabel = formatScore(citation.score);
          return (
            <AccordionItem
              key={citation.id}
              value={citation.id}
              data-testid={`citation-${messageId}-${citation.id}`}
            >
              <AccordionHeader
                data-testid={`citation-${messageId}-${citation.id}-header`}
              >
                <span className={styles.headerRow}>
                  <span className={styles.title}>
                    {headerLabel(citation, index)}
                  </span>
                  {scoreLabel !== null && (
                    <span
                      className={styles.score}
                      data-testid={`citation-${messageId}-${citation.id}-score`}
                    >
                      {scoreLabel}
                    </span>
                  )}
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
          );
        })}
      </Accordion>
    </section>
  );
}
