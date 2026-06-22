/**
 * Pillar: Stable Core
 * Phase: 6 (visual polish)
 *
 * Vitest coverage for `parseAnswer()` — the pure transform that
 * rewrites `[docN]` markers into `^K^` superscript tokens and returns
 * the deduplicated, renumbered citation subset the answer references.
 */
import { describe, expect, it } from "vitest";
import { parseAnswer } from "@/pages/chat/components/parseAnswer";
import type { Citation } from "@/models/chat";

const cit1: Citation = {
  id: "doc-alpha",
  title: "Alpha",
  url: "https://example.com/alpha",
  snippet: "alpha snippet",
  score: 0.5,
  metadata: {},
};
const cit2: Citation = {
  id: "doc-beta",
  title: "Beta",
  url: "https://example.com/beta",
  snippet: "beta snippet",
  score: null,
  metadata: {},
};
const cit3: Citation = {
  id: "doc-gamma",
  title: "Gamma",
  url: "https://example.com/gamma",
  snippet: "gamma snippet",
  score: 0.1,
  metadata: {},
};

describe("parseAnswer", () => {
  it("returns the content verbatim when citations is undefined", () => {
    const result = parseAnswer("see [doc1] for details", undefined);
    expect(result.markdownText).toBe("see [doc1] for details");
    expect(result.citations).toEqual([]);
  });

  it("returns the content verbatim when citations is empty", () => {
    const result = parseAnswer("see [doc1] for details", []);
    expect(result.markdownText).toBe("see [doc1] for details");
    expect(result.citations).toEqual([]);
  });

  it("leaves content unchanged and references nothing when there are no markers", () => {
    const result = parseAnswer("plain answer with no markers", [cit1]);
    expect(result.markdownText).toBe("plain answer with no markers");
    expect(result.citations).toEqual([]);
  });

  it("rewrites a single [doc1] marker to a ^1^ superscript token", () => {
    const result = parseAnswer("prefix [doc1] suffix", [cit1]);
    expect(result.markdownText).toMatch(/^prefix\s+\^1\^\s+suffix$/);
    expect(result.markdownText).toContain(" ^1^ ");
    expect(result.citations).toEqual([cit1]);
  });

  it("renders multiple distinct markers in order as ^1^ and ^2^", () => {
    const result = parseAnswer("a [doc1] b [doc2] c", [cit1, cit2]);
    expect(result.markdownText).toMatch(/^a\s+\^1\^\s+b\s+\^2\^\s+c$/);
    expect(result.citations).toEqual([cit1, cit2]);
  });

  it("deduplicates a repeated citation to one entry but keeps both superscripts", () => {
    const result = parseAnswer("[doc1] and [doc1]", [cit1]);
    expect(result.markdownText).toMatch(/\^1\^\s+and\s+\^1\^/);
    expect(result.citations).toEqual([cit1]);
  });

  it("renumbers out-of-order markers in first-appearance order", () => {
    const result = parseAnswer("[doc2] then [doc1]", [cit1, cit2]);
    expect(result.markdownText).toMatch(/^\s*\^1\^\s+then\s+\^2\^\s*$/);
    // [doc2] appears first -> display 1 -> cit2; [doc1] -> display 2 -> cit1.
    expect(result.citations).toEqual([cit2, cit1]);
  });

  it("leaves an out-of-bounds [doc9] marker verbatim and references nothing", () => {
    const result = parseAnswer("see [doc9] end", [cit1]);
    expect(result.markdownText).toBe("see [doc9] end");
    expect(result.citations).toEqual([]);
  });

  it("leaves [doc0] verbatim because numbering is 1-based", () => {
    const result = parseAnswer("see [doc0] end", [cit1]);
    expect(result.markdownText).toBe("see [doc0] end");
    expect(result.citations).toEqual([]);
  });

  it("collapses consecutive duplicate superscripts to a single token", () => {
    const result = parseAnswer("answer [doc1][doc1] done", [cit1]);
    const supCount = (result.markdownText.match(/\^1\^/g) ?? []).length;
    expect(supCount).toBe(1);
    expect(result.citations).toEqual([cit1]);
  });

  it("does not collapse distinct adjacent superscripts", () => {
    const result = parseAnswer("answer [doc1][doc2] done", [cit1, cit2]);
    expect(result.markdownText).toContain("^1^");
    expect(result.markdownText).toContain("^2^");
    expect(result.citations).toEqual([cit1, cit2]);
  });

  it("returns only the referenced subset of citations", () => {
    const result = parseAnswer("only [doc2] here", [cit1, cit2, cit3]);
    expect(result.markdownText).toMatch(/^only\s+\^1\^\s+here$/);
    expect(result.citations).toEqual([cit2]);
  });

  it("keeps resolvable markers while leaving out-of-bounds ones verbatim", () => {
    const result = parseAnswer("[doc1] and [doc9]", [cit1]);
    expect(result.markdownText).toContain("^1^");
    expect(result.markdownText).toContain("[doc9]");
    expect(result.citations).toEqual([cit1]);
  });
});
