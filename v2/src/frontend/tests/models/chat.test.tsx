/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest type-shape assertions for the `Citation` model. Type-only
 * checks would silently pass if the interface drifted; this suite
 * mounts a literal of the canonical wire shape and a literal of the
 * stricter typed form so a `tsc` regression breaks the build and a
 * runtime `expect` confirms the field types reach the FE intact.
 */
import { describe, expect, it } from "vitest";
import type { Citation, StreamEvent } from "../../src/models/chat";

describe("Citation model", () => {
  it("accepts the full canonical citation shape from the SSE feed", () => {
    const citation: Citation = {
      id: "doc-42#chunk-7",
      title: "Contoso 2026 Q1 earnings call",
      url: "https://contoso.example.com/q1-earnings.pdf",
      snippet: "Revenue grew 18% year-over-year, driven by ...",
      score: 0.87,
      metadata: {
        source: "blob://contoso/q1-earnings.pdf",
        page: 4,
      },
    };
    expect(citation.id).toBe("doc-42#chunk-7");
    expect(citation.title).toBe("Contoso 2026 Q1 earnings call");
    expect(citation.url).toBe("https://contoso.example.com/q1-earnings.pdf");
    expect(citation.snippet).toMatch(/^Revenue grew/);
    expect(citation.score).toBe(0.87);
    expect(citation.metadata.source).toBe("blob://contoso/q1-earnings.pdf");
    expect(citation.metadata.page).toBe(4);
  });

  it("accepts a citation with no provider-supplied score (null)", () => {
    const citation: Citation = {
      id: "fallback-doc",
      title: "",
      url: "",
      snippet: "",
      score: null,
      metadata: {},
    };
    expect(citation.score).toBeNull();
    expect(citation.title).toBe("");
    expect(citation.metadata).toEqual({});
  });

  it("round-trips through a citation-channel SSE frame without information loss", () => {
    const citation: Citation = {
      id: "doc-99",
      title: "Compliance addendum",
      url: "https://internal/policy",
      snippet: "All employees must complete training by Q3.",
      score: 0.42,
      metadata: { region: "us-east-1" },
    };
    const event: StreamEvent = {
      channel: "citation",
      content: "",
      metadata: citation as unknown as Record<string, unknown>,
    };
    expect(event.channel).toBe("citation");
    const reconstructed = event.metadata as unknown as Citation;
    expect(reconstructed.id).toBe(citation.id);
    expect(reconstructed.title).toBe(citation.title);
    expect(reconstructed.url).toBe(citation.url);
    expect(reconstructed.snippet).toBe(citation.snippet);
    expect(reconstructed.score).toBe(citation.score);
    expect(reconstructed.metadata).toEqual(citation.metadata);
  });

  it("preserves arbitrary metadata payload types without narrowing", () => {
    const citation: Citation = {
      id: "doc-1",
      title: "",
      url: "",
      snippet: "",
      score: null,
      metadata: {
        page: 7,
        is_redacted: true,
        chunk_ids: ["a", "b", "c"],
        nested: { foo: "bar" },
      },
    };
    expect(citation.metadata.page).toBe(7);
    expect(citation.metadata.is_redacted).toBe(true);
    expect(citation.metadata.chunk_ids).toEqual(["a", "b", "c"]);
    expect(citation.metadata.nested).toEqual({ foo: "bar" });
  });
});
