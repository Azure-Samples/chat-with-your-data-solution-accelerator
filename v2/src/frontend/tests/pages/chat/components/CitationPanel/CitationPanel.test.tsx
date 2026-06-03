/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest coverage for `<CitationPanel>` rendering and interaction.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { CitationPanel } from "../../../../../src/pages/chat/components/CitationPanel/CitationPanel";
import type { Citation } from "../../../../../src/models/chat";

const docA: Citation = {
  id: "doc-a",
  title: "Source A",
  url: "https://example.com/a",
  snippet: "Snippet body for source A.",
  score: 0.91,
  metadata: { kind: "blob" },
};
const docB: Citation = {
  id: "doc-b",
  title: "Source B",
  url: "https://example.com/b",
  snippet: "Snippet body for source B.",
  score: null,
  metadata: {},
};
const docBare: Citation = {
  id: "doc-bare",
  title: "",
  url: "",
  snippet: "",
  score: null,
  metadata: {},
};

function renderPanel(props: {
  messageId: string;
  citations: Citation[];
  focusedCitationId?: string | null;
}) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <CitationPanel {...props} />
    </FluentProvider>,
  );
}

describe("CitationPanel", () => {
  it("renders nothing when the citations array is empty", () => {
    renderPanel({ messageId: "m1", citations: [] });
    // FluentProvider mounts its own theme + portal nodes regardless,
    // so the only stable signal that <CitationPanel> short-circuited
    // is the absence of the panel data-testid.
    expect(screen.queryByTestId("citation-panel-m1")).toBeNull();
    expect(screen.queryByText("Sources")).toBeNull();
  });

  it("renders a section labelled 'Sources' with one accordion item per citation", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });

    const section = screen.getByTestId("citation-panel-m1");
    expect(section.tagName.toLowerCase()).toBe("section");
    expect(section.getAttribute("aria-label")).toBe("Sources");
    expect(screen.getByText("Sources")).toBeInTheDocument();

    expect(screen.getByTestId("citation-m1-doc-a")).toBeInTheDocument();
    expect(screen.getByTestId("citation-m1-doc-b")).toBeInTheDocument();
  });

  it("uses the citation title as the accordion header label", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });

    expect(
      screen.getByTestId("citation-m1-doc-a-header"),
    ).toHaveTextContent("Source A");
    expect(
      screen.getByTestId("citation-m1-doc-b-header"),
    ).toHaveTextContent("Source B");
  });

  it("falls back to '[docN]' header labels when the title is missing", () => {
    renderPanel({ messageId: "m1", citations: [docBare] });

    expect(
      screen.getByTestId("citation-m1-doc-bare-header"),
    ).toHaveTextContent("[doc1]");
  });

  it("renders a score badge only when the citation exposes one", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });

    const badge = screen.getByTestId("citation-m1-doc-a-score");
    expect(badge).toHaveTextContent("91%");
    expect(screen.queryByTestId("citation-m1-doc-b-score")).toBeNull();
  });

  it("renders panel snippet + deep-link when both are present", () => {
    renderPanel({ messageId: "m1", citations: [docA] });
    // Expand the accordion so its panel body mounts into the DOM.
    fireEvent.click(
      screen
        .getByTestId("citation-m1-doc-a-header")
        .querySelector("button")!,
    );

    expect(screen.getByText(/Snippet body for source A\./)).toBeInTheDocument();
    const link = screen.getByTestId("citation-m1-doc-a-link") as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("https://example.com/a");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("omits the snippet paragraph and link when those fields are empty", () => {
    renderPanel({ messageId: "m1", citations: [docBare] });
    // Expand the accordion to confirm the body mounts but skips the
    // empty children — the panel itself is intentionally clickable so
    // the user can confirm "no extra body".
    fireEvent.click(
      screen
        .getByTestId("citation-m1-doc-bare-header")
        .querySelector("button")!,
    );

    expect(screen.queryByTestId("citation-m1-doc-bare-link")).toBeNull();
    expect(screen.getByTestId("citation-m1-doc-bare-panel")).toBeInTheDocument();
  });

  it("starts collapsed and expands the panel on header click", () => {
    renderPanel({ messageId: "m1", citations: [docA] });

    const header = screen
      .getByTestId("citation-m1-doc-a-header")
      .querySelector("button");
    expect(header).not.toBeNull();
    expect(header!.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(header!);
    expect(header!.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(header!);
    expect(header!.getAttribute("aria-expanded")).toBe("false");
  });

  it("supports expanding multiple panels simultaneously", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });

    const headerA = screen
      .getByTestId("citation-m1-doc-a-header")
      .querySelector("button")!;
    const headerB = screen
      .getByTestId("citation-m1-doc-b-header")
      .querySelector("button")!;

    fireEvent.click(headerA);
    fireEvent.click(headerB);
    expect(headerA.getAttribute("aria-expanded")).toBe("true");
    expect(headerB.getAttribute("aria-expanded")).toBe("true");
  });

  it("links use safe target+rel so opening a source does not leak the opener window", () => {
    // Spy on window.open to confirm the anchor uses native navigation
    // rather than a JS handler that would skip the rel guard.
    const openSpy = vi
      .spyOn(window, "open")
      .mockImplementation(() => null);
    try {
      renderPanel({ messageId: "m1", citations: [docA] });
      // Expand so the link is rendered into the layout tree.
      fireEvent.click(
        screen
          .getByTestId("citation-m1-doc-a-header")
          .querySelector("button")!,
      );
      const link = screen.getByTestId("citation-m1-doc-a-link");
      expect(link.getAttribute("target")).toBe("_blank");
      expect(link.getAttribute("rel")).toBe("noopener noreferrer");
      // jsdom does not navigate on click, so we just confirm no JS
      // handler hijacks the anchor — window.open should NOT fire.
      fireEvent.click(link);
      expect(openSpy).not.toHaveBeenCalled();
    } finally {
      openSpy.mockRestore();
    }
  });
});

describe("CitationPanel focusedCitationId wiring", () => {
  it("auto-expands the matching item when focusedCitationId resolves to a citation", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: "doc-b",
    });
    const headerA = screen
      .getByTestId("citation-m1-doc-a-header")
      .querySelector("button")!;
    const headerB = screen
      .getByTestId("citation-m1-doc-b-header")
      .querySelector("button")!;
    expect(headerA.getAttribute("aria-expanded")).toBe("false");
    expect(headerB.getAttribute("aria-expanded")).toBe("true");
  });

  it("leaves every item collapsed when focusedCitationId is null", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: null,
    });
    const headerA = screen
      .getByTestId("citation-m1-doc-a-header")
      .querySelector("button")!;
    const headerB = screen
      .getByTestId("citation-m1-doc-b-header")
      .querySelector("button")!;
    expect(headerA.getAttribute("aria-expanded")).toBe("false");
    expect(headerB.getAttribute("aria-expanded")).toBe("false");
  });

  it("ignores focusedCitationId values that do not match any citation id", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: "doc-nope",
    });
    expect(
      screen
        .getByTestId("citation-m1-doc-a-header")
        .querySelector("button")!
        .getAttribute("aria-expanded"),
    ).toBe("false");
    expect(
      screen
        .getByTestId("citation-m1-doc-b-header")
        .querySelector("button")!
        .getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("user-driven open state is preserved when focus targets a different item", () => {
    const { rerender } = render(
      <FluentProvider theme={webLightTheme}>
        <CitationPanel
          messageId="m1"
          citations={[docA, docB]}
          focusedCitationId={null}
        />
      </FluentProvider>,
    );
    // User opens item A manually.
    fireEvent.click(
      screen
        .getByTestId("citation-m1-doc-a-header")
        .querySelector("button")!,
    );
    // Parent now flips focus to item B (e.g. a [doc2] token click).
    rerender(
      <FluentProvider theme={webLightTheme}>
        <CitationPanel
          messageId="m1"
          citations={[docA, docB]}
          focusedCitationId="doc-b"
        />
      </FluentProvider>,
    );
    // Both items should now be open — focus is additive, never
    // destructive, so the user's manual A stays put.
    expect(
      screen
        .getByTestId("citation-m1-doc-a-header")
        .querySelector("button")!
        .getAttribute("aria-expanded"),
    ).toBe("true");
    expect(
      screen
        .getByTestId("citation-m1-doc-b-header")
        .querySelector("button")!
        .getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("user can still collapse a focus-expanded item by clicking its header", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: "doc-a",
    });
    const headerA = screen
      .getByTestId("citation-m1-doc-a-header")
      .querySelector("button")!;
    expect(headerA.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(headerA);
    expect(headerA.getAttribute("aria-expanded")).toBe("false");
  });
});
