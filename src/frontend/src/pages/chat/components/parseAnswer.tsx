/**
 * Pure transform that prepares an assistant answer for v1-style
 * superscript citation rendering. The model emits citation markers as
 * bracketed plain text (`[doc1]`, `[doc2]`, …) positionally keyed to the
 * message's `citations` array on the wire -- 1-based, so `[doc1]` maps to
 * `citations[0]`. This walks those markers left to right, deduplicates
 * the sources they point at, renumbers them `1..K` in first-appearance
 * order, and rewrites each marker into the `^K^` token that
 * `remark-supersub` turns into a `<sup>` node. Consecutive duplicate
 * superscripts collapse to one. Markers whose index does not resolve
 * against the citation list are left verbatim so the wire content is
 * never destroyed.
 *
 * The returned `citations` list is the deduplicated, renumbered subset
 * the answer actually references, so the superscript numbers and a
 * downstream reference block stay in lockstep. The rewritten
 * `markdownText` is consumed by the answer-body `MarkdownContent` with
 * `enableSupersub` set.
 */
import type { Citation } from "@/models/chat";

import { collapseConsecutiveSuperscripts } from "./citationTokens";

const DOC_MARKER_PATTERN = /\[doc(\d+)\]/g;

export interface ParsedAnswer {
  markdownText: string;
  citations: Citation[];
}

export function parseAnswer(
  content: string,
  citations: Citation[] | undefined,
): ParsedAnswer {
  if (citations === undefined || citations.length === 0) {
    return { markdownText: content, citations: [] };
  }

  const renumbered: Citation[] = [];
  const displayNumberById = new Map<string, number>();

  const rewritten = content.replace(
    DOC_MARKER_PATTERN,
    (raw: string, oneBasedStr: string): string => {
      const oneBased = Number.parseInt(oneBasedStr, 10);
      const citation =
        oneBased >= 1 && oneBased <= citations.length
          ? citations[oneBased - 1]
          : undefined;
      if (citation === undefined) {
        // Out-of-bounds marker -- keep the literal text visible.
        return raw;
      }
      let displayNumber = displayNumberById.get(citation.id);
      if (displayNumber === undefined) {
        displayNumber = renumbered.length + 1;
        displayNumberById.set(citation.id, displayNumber);
        renumbered.push(citation);
      }
      return ` ^${displayNumber}^ `;
    },
  );

  const collapsed = collapseConsecutiveSuperscripts(rewritten);

  return { markdownText: collapsed, citations: renumbered };
}
