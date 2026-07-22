/**
 * Unit tests for `formatReasoning` -- the single shared formatter both
 * orchestrators' reasoning feeds flow through. The langgraph delta
 * stream (no section titles) must pass through verbatim; the
 * agent_framework block stream (bold section titles) must have its
 * titles dropped and bodies broken apart.
 */
import { describe, it, expect } from "vitest";

import {
  formatReasoning,
  superscriptReasoningCitations,
} from "@/pages/chat/components/reasoningText";

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
      "I will look it up.\nHere is the summary.",
    );
  });

  it("un-jams a second title that abuts the previous body", () => {
    const parts = [
      "**Searching**\n\nfirst body, focus on that!**Summarizing**\n\nsecond body.",
    ];
    expect(formatReasoning(parts)).toBe(
      "first body, focus on that!\nsecond body.",
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

describe("superscriptReasoningCitations", () => {
  it("rewrites a `[docN]` marker into a superscript token", () => {
    expect(superscriptReasoningCitations("see [doc6] here")).toContain(" ^6^ ");
  });

  it("rewrites a `doc[N]` marker, consuming the `doc` word", () => {
    const result = superscriptReasoningCitations("see doc[6] here");
    expect(result).toContain(" ^6^ ");
    expect(result).not.toContain("doc");
  });

  it("rewrites a `docs[N]` marker into a superscript token", () => {
    expect(superscriptReasoningCitations("per docs[3] above")).toContain(
      " ^3^ ",
    );
  });

  it("rewrites a bare `[N]` marker into a superscript token", () => {
    expect(superscriptReasoningCitations("noted in [9] earlier")).toContain(
      " ^9^ ",
    );
  });

  it("rewrites multiple markers in order and retains surrounding prose", () => {
    const result = superscriptReasoningCitations("docs[3] and [9]");
    expect(result).toContain("^3^");
    expect(result).toContain("^9^");
    expect(result.indexOf("^3^")).toBeLessThan(result.indexOf("^9^"));
    expect(result).toContain("and");
  });

  it("collapses consecutive duplicate markers into a single superscript", () => {
    const result = superscriptReasoningCitations("[doc1][doc1]");
    expect(result).toContain("^1^");
    expect(result.match(/\^1\^/g)).toHaveLength(1);
  });

  it("returns text unchanged when there are no markers", () => {
    expect(superscriptReasoningCitations("just plain reasoning.")).toBe(
      "just plain reasoning.",
    );
  });

  it("leaves a 4-digit bracket literal", () => {
    const result = superscriptReasoningCitations("published in [2026] finally");
    expect(result).toContain("[2026]");
    expect(result).not.toContain("^");
  });

  it("leaves a non-numeric bracket literal", () => {
    const result = superscriptReasoningCitations("see the [note] below");
    expect(result).toContain("[note]");
    expect(result).not.toContain("^");
  });
});
