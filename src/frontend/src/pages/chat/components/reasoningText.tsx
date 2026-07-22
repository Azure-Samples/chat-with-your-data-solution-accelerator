/**
 * Pure formatter for the assistant reasoning feed. Both orchestrators
 * stream onto the same `reasoning` SSE channel but at different
 * granularities: `langgraph` emits char-level summary deltas from a
 * single pre-retrieval reasoning pass, while `agent_framework` emits
 * one summary block per agentic turn, each prefixed by a bold section
 * title (e.g. `**Searching for employee benefits**`). This helper is
 * the single place both feeds converge, so the rendered panel reads
 * identically regardless of orchestrator: the model's bold section
 * titles are dropped and the remaining bodies are separated by a
 * single line break (no blank line between sections). Text that
 * carries no such titles (the langgraph delta stream) is returned as
 * the verbatim join.
 */
import { collapseConsecutiveSuperscripts } from "./citationTokens";

// A model-emitted section title: a bold span on its own line -- `**Title**`
// immediately followed by a line break, with any whitespace on either
// side. Inline bold that is not followed by a newline (rare in reasoning
// summaries) is left intact so genuine emphasis survives.
const SECTION_TITLE = /\s*\*\*[^*\n]+\*\*[ \t]*\n+/g;

export function formatReasoning(parts: string[]): string {
  const joined = parts.join("");
  return joined
    .replace(SECTION_TITLE, "\n")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

// The reasoning citation marker family the model interleaves into its
// chain-of-thought: `[docN]`, `doc[N]`, `docs[N]`, and bare `[N]`. The
// captured group is the number verbatim. The `\d{1,3}` cap admits 1–3
// digit indices and excludes 4-digit brackets (e.g. `[2026]`), which are
// prose, not citation markers.
const REASONING_CITATION_MARKER = /(?:docs?\s*)?\[(?:doc)?(\d{1,3})\]/gi;

/**
 * Pure marker→superscript normalizer for the reasoning feed. It rewrites
 * every reasoning citation marker (`[docN]`, `doc[N]`, `docs[N]`, bare
 * `[N]`) into the ` ^N^ ` token that `remark-supersub` renders as a
 * `<sup>` node -- the same token the answer body's `parseAnswer`
 * produces, so both feeds drive `remark-supersub` identically. The
 * number is emitted verbatim: the reasoning panel is chain-of-thought,
 * not a clickable citation surface, so there is no renumbering against a
 * `citations` array. Leading/trailing spaces around each token preserve
 * a word boundary in adjacent prose, and consecutive duplicate
 * superscripts collapse to one. Text carrying no markers is returned
 * unchanged; whitespace trimming is `formatReasoning`'s concern, so this
 * helper composes after it.
 */
export function superscriptReasoningCitations(text: string): string {
  return collapseConsecutiveSuperscripts(
    text.replace(REASONING_CITATION_MARKER, " ^$1^ "),
  );
}
