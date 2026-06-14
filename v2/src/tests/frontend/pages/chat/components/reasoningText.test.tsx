/**
 * Pillar: Stable Core
 * Phase: 6 (visual polish)
 *
 * Unit tests for `formatReasoning` — the single shared formatter both
 * orchestrators' reasoning feeds flow through. The langgraph delta
 * stream (no section titles) must pass through verbatim; the
 * agent_framework block stream (bold section titles) must have its
 * titles dropped and bodies broken apart.
 */
import { describe, it, expect } from "vitest";

import { formatReasoning } from "@/pages/chat/components/reasoningText";

describe("formatReasoning", () => {
  it("returns char-level deltas unchanged when there are no section titles", () => {
    expect(formatReasoning(["delta1", "delta2"])).toBe("delta1delta2");
  });

  it("returns plain reasoning chunks as the verbatim join", () => {
    expect(formatReasoning(["thinking step 1", "thinking step 2"])).toBe(
      "thinking step 1thinking step 2",
    );
  });

  it("drops bold section titles and breaks the bodies apart", () => {
    const parts = [
      "**Searching for employee benefits**\n\nI will look it up.",
      "**Summarizing health benefits**\n\nHere is the summary.",
    ];
    expect(formatReasoning(parts)).toBe(
      "I will look it up.\n\nHere is the summary.",
    );
  });

  it("un-jams a second title that abuts the previous body", () => {
    const parts = [
      "**Searching**\n\nfirst body, focus on that!**Summarizing**\n\nsecond body.",
    ];
    expect(formatReasoning(parts)).toBe(
      "first body, focus on that!\n\nsecond body.",
    );
  });

  it("collapses the blank lines left by adjacent titles", () => {
    expect(formatReasoning(["**A**\n\n**B**\n\nonly body."])).toBe("only body.");
  });

  it("leaves inline bold intact when it is not a standalone title", () => {
    expect(formatReasoning(["I think **this** matters here."])).toBe(
      "I think **this** matters here.",
    );
  });

  it("returns an empty string for empty input", () => {
    expect(formatReasoning([])).toBe("");
  });
});
