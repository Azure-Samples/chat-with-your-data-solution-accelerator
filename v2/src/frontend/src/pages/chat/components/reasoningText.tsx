/**
 * Pillar: Stable Core
 * Phase: 6 (visual polish)
 *
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

// A model-emitted section title: a bold span on its own line — `**Title**`
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
