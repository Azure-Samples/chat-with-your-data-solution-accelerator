/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest coverage for `deriveDocumentHref` — the citation -> document
 * link resolver. Exercises the blob-name, blob-URL, external-URL, and
 * empty cases plus the `VITE_BACKEND_URL` absolute-prefix wiring.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { deriveDocumentHref } from "@/pages/chat/components/CitationDetailPanel/documentHref";
import type { Citation } from "@/models/chat";

function citation(overrides: Partial<Citation>): Citation {
  return {
    id: "c-1",
    title: "",
    url: "",
    snippet: "",
    score: null,
    metadata: {},
    ...overrides,
  };
}

describe("deriveDocumentHref", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("builds a backend file route from a blob filename in the title", () => {
    expect(deriveDocumentHref(citation({ title: "Benefit_Options.pdf" }))).toBe(
      "/api/files/Benefit_Options.pdf",
    );
  });

  it("url-encodes a blob filename that contains spaces", () => {
    expect(
      deriveDocumentHref(citation({ title: "Employee Handbook.pdf" })),
    ).toBe("/api/files/Employee%20Handbook.pdf");
  });

  it("rewrites a raw blob-storage URL onto the backend file route", () => {
    expect(
      deriveDocumentHref(
        citation({
          url: "https://acct.blob.core.windows.net/documents/Benefit_Options.pdf",
        }),
      ),
    ).toBe("/api/files/Benefit_Options.pdf");
  });

  it("passes through a non-blob http URL verbatim", () => {
    expect(
      deriveDocumentHref(
        citation({ url: "https://contoso.com/policies/leave.pdf" }),
      ),
    ).toBe("https://contoso.com/policies/leave.pdf");
  });

  it("uses an http title as the external link when the url is empty", () => {
    expect(
      deriveDocumentHref(
        citation({ title: "https://contoso.com/news/update", url: "" }),
      ),
    ).toBe("https://contoso.com/news/update");
  });

  it("returns null when neither url nor title is usable", () => {
    expect(deriveDocumentHref(citation({ title: "", url: "" }))).toBeNull();
  });

  it("prefixes the backend file route with VITE_BACKEND_URL when set", () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://backend.example.com");
    expect(deriveDocumentHref(citation({ title: "Benefit_Options.pdf" }))).toBe(
      "https://backend.example.com/api/files/Benefit_Options.pdf",
    );
  });
});
