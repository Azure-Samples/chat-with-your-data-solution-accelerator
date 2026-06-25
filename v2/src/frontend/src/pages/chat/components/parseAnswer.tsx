/**
 * Pillar: Stable Core
 * Phase: 6 (visual polish)
 *
 * Pure transform that prepares an assistant answer for v1-style
 * superscript citation rendering. The model emits citation markers as
 * bracketed plain text (`[doc1]`, `[doc2]`, …) keyed to the message's
 * `citations` array on the wire. Each citation's `id` field is the
 * marker string (e.g. `[doc5]`), so lookup is by id rather than by
 * position — this handles the pgvector path where
 * `filter_to_referenced` prunes citations without renumbering. This
 * walks markers left to right, deduplicates the sources they point at,
 * renumbers them `1..K` in first-appearance order, and rewrites each
 * marker into the `^K^` token that `remark-supersub` turns into a
 * `<sup>` node. Consecutive duplicate superscripts collapse to one.
 * Markers whose id does not resolve against the citation list are left
 * verbatim so the wire content is never destroyed.
 *
 * The returned `citations` list is the deduplicated, renumbered subset
 * the answer actually references, so the superscript numbers and a
 * downstream reference block stay in lockstep. The rewritten
 * `markdownText` is consumed by the answer-body `MarkdownContent` with
 * `enableSupersub` set.
 */
import type { Citation } from "@/models/chat";

const DOC_MARKER_PATTERN = /\[doc(\d+)\]/g;
const CONSECUTIVE_DUPLICATE_SUP_PATTERN = /\^(\d+)\^(?:\s*\^\1\^)+/g;

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

  // Build an id-keyed map so [docN] resolves regardless of whether the
  // wire list was pruned (pgvector filter_to_referenced) or renumbered
  // (Foundry IQ normalize_kb_citations). Falls back to positional
  // lookup for backward compatibility with any path that uses a
  // sequential 1-based index as the citation id.
  const byId = new Map<string, Citation>();
  for (const c of citations) {
    byId.set(c.id, c);
  }

  const renumbered: Citation[] = [];
  const displayNumberById = new Map<string, number>();

  const rewritten = content.replace(
    DOC_MARKER_PATTERN,
    (raw: string, oneBasedStr: string): string => {
      const marker = `[doc${oneBasedStr}]`;
      const oneBased = Number.parseInt(oneBasedStr, 10);
      // Prefer id-based lookup; fall back to positional for compat.
      const citation =
        byId.get(marker) ??
        (oneBased >= 1 && oneBased <= citations.length
          ? citations[oneBased - 1]
          : undefined);
      if (citation === undefined) {
        // Unresolved marker — keep the literal text visible.
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

  const collapsed = rewritten.replace(
    CONSECUTIVE_DUPLICATE_SUP_PATTERN,
    "^$1^",
  );

  return { markdownText: collapsed, citations: renumbered };
}
