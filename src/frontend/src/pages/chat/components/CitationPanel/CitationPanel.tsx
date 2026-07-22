/**
 * Source references surfaced under a finished assistant message.
 * Renders a collapsible reference block that mirrors the v1 chat
 * appearance: a single "N references" / "1 reference" toggle (with a
 * chevron that flips between closed and open) reveals a row of
 * numbered reference chips. Each chip is a `<button>` keyed by the
 * provider-supplied `id` showing the 1-based position and the
 * citation title (or a `Citation N` fallback when the wire omits
 * one), middle-truncated to keep a long filename on one line.
 *
 * Clicking a chip does not expand inline; it calls `onSelectCitation`
 * with the full citation so a parent can open the source detail
 * column. The chip block owns only its own open/closed state.
 *
 * Empty / absent `citations` props short-circuit to `null` so the
 * block adds zero DOM noise to messages with no sources.
 */
import { useState } from "react";
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
   * Invoked with the full citation when the user clicks a reference
   * chip. The parent decides what to show (typically the source
   * detail column) -- the panel itself does not expand inline.
   */
  onSelectCitation: (citation: Citation) => void;
}

function headerLabel(citation: Citation, index: number): string {
  if (citation.title.length > 0) return citation.title;
  return `Citation ${index + 1}`;
}

function toggleLabel(count: number): string {
  return count === 1 ? "1 reference" : `${count} references`;
}

const CITATION_LABEL_MAX = 50;
const CITATION_LABEL_EDGE = 20;

/**
 * Middle-truncate a chip label so a long filename stays on one line
 * while keeping its meaningful tail (e.g. the `.pdf - Part 1` suffix)
 * visible -- mirrors the v1 `createCitationFilepath` head/tail elision.
 * Labels at or under the threshold pass through verbatim.
 */
export function formatCitationLabel(label: string): string {
  if (label.length <= CITATION_LABEL_MAX) return label;
  return `${label.slice(0, CITATION_LABEL_EDGE)}...${label.slice(
    -CITATION_LABEL_EDGE,
  )}`;
}

export function CitationPanel({
  messageId,
  citations,
  onSelectCitation,
}: CitationPanelProps) {
  const [expanded, setExpanded] = useState(false);

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
        onClick={() => {
          setExpanded((value) => !value);
        }}
        data-testid={`citations-toggle-${messageId}`}
      >
        {expanded ? <ChevronDown16Regular /> : <ChevronRight16Regular />}
        <span className={styles.toggleLabel}>
          {toggleLabel(citations.length)}
        </span>
      </button>
      <div
        id={bodyId}
        hidden={!expanded}
        data-testid={bodyId}
        className={styles.chipList}
      >
        {citations.map((citation, index) => (
          <button
            key={citation.id}
            type="button"
            className={styles.chip}
            onClick={() => {
              onSelectCitation(citation);
            }}
            data-testid={`citation-${messageId}-${citation.id}`}
          >
            <span className={styles.chipNumber} aria-hidden="true">
              {index + 1}
            </span>
            <span className={styles.chipLabel}>
              {formatCitationLabel(headerLabel(citation, index))}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
