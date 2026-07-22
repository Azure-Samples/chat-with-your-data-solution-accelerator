/**
 * Unit tests for the shared citation-token collapse helper consumed by
 * both the answer body (`parseAnswer`) and the reasoning panel
 * (`superscriptReasoningCitations`).
 */
import { describe, it, expect } from "vitest";

import { collapseConsecutiveSuperscripts } from "@/pages/chat/components/citationTokens";

describe("collapseConsecutiveSuperscripts", () => {
  it("collapses a whitespace-separated run of the same superscript to one", () => {
    expect(collapseConsecutiveSuperscripts("^1^ ^1^")).toBe("^1^");
  });

  it("collapses adjacent duplicates with no whitespace", () => {
    expect(collapseConsecutiveSuperscripts("^2^^2^")).toBe("^2^");
  });

  it("collapses a run of three to a single token", () => {
    expect(collapseConsecutiveSuperscripts("^5^ ^5^ ^5^")).toBe("^5^");
  });

  it("does not collapse distinct adjacent superscripts", () => {
    expect(collapseConsecutiveSuperscripts("^1^ ^2^")).toBe("^1^ ^2^");
  });

  it("returns text without a superscript run unchanged", () => {
    expect(collapseConsecutiveSuperscripts("plain ^1^ text")).toBe(
      "plain ^1^ text",
    );
  });

  it("returns marker-free text unchanged", () => {
    expect(collapseConsecutiveSuperscripts("no markers here")).toBe(
      "no markers here",
    );
  });
});
