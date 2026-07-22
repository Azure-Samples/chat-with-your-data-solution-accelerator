/**
 * Shared citation-token utility for the two surfaces that render document
 * citations as superscripts: the answer body (`parseAnswer`) and the
 * reasoning panel (`superscriptReasoningCitations`). Both rewrite their
 * markers into the `^N^` token that `remark-supersub` turns into a
 * `<sup>`, and both then collapse runs of the same superscript (separated
 * only by whitespace) down to one. That collapse is the single shared
 * step, defined here once so both surfaces behave identically from one
 * definition.
 */

// Runs of the same superscript token, separated only by whitespace, that
// collapse to a single `<sup>`.
const CONSECUTIVE_DUPLICATE_SUP = /\^(\d+)\^(?:\s*\^\1\^)+/g;

/**
 * Collapse consecutive duplicate `^N^` superscript tokens (separated only
 * by whitespace) into a single `^N^`. Text with no such run is returned
 * unchanged.
 */
export function collapseConsecutiveSuperscripts(text: string): string {
  return text.replace(CONSECUTIVE_DUPLICATE_SUP, "^$1^");
}
