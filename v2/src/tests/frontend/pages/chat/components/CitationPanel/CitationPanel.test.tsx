/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest coverage for `<CitationPanel>` — the v1-style reference block:
 * a collapsible "N references / 1 reference" toggle that reveals a
 * numbered list of source items, each expanding to its snippet and a
 * safe new-tab deep-link.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { CitationPanel } from "@/pages/chat/components/CitationPanel/CitationPanel";
import type { Citation } from "@/models/chat";

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

function toggleButton(messageId: string): HTMLButtonElement {
  return screen.getByTestId(
    `citations-toggle-${messageId}`,
  ) as HTMLButtonElement;
}

function itemHeaderButton(
  messageId: string,
  citationId: string,
): HTMLButtonElement {
  const button = screen
    .getByTestId(`citation-${messageId}-${citationId}-header`)
    .querySelector("button");
  if (button === null) {
    throw new Error(`no accordion header button for ${citationId}`);
  }
  return button as HTMLButtonElement;
}

describe("CitationPanel", () => {
  it("renders nothing when the citations array is empty", () => {
    renderPanel({ messageId: "m1", citations: [] });
    // FluentProvider mounts its own theme + portal nodes regardless,
    // so the only stable signal that <CitationPanel> short-circuited
    // is the absence of the panel + toggle data-testids.
    expect(screen.queryByTestId("citation-panel-m1")).toBeNull();
    expect(screen.queryByTestId("citations-toggle-m1")).toBeNull();
  });

  it("renders a References section with a collapsed-by-default toggle", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });

    const section = screen.getByTestId("citation-panel-m1");
    expect(section.tagName.toLowerCase()).toBe("section");
    expect(section.getAttribute("aria-label")).toBe("References");

    const toggle = toggleButton("m1");
    expect(toggle).toHaveTextContent("2 references");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("labels the toggle '1 reference' (singular) for a single citation", () => {
    renderPanel({ messageId: "m1", citations: [docA] });
    expect(toggleButton("m1")).toHaveTextContent("1 reference");
  });

  it("expands and collapses the reference list when the toggle is clicked", () => {
    renderPanel({ messageId: "m1", citations: [docA] });

    const toggle = toggleButton("m1");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("numbers each citation by its 1-based position", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });
    fireEvent.click(toggleButton("m1"));

    const headerA = screen.getByTestId("citation-m1-doc-a-header");
    expect(headerA).toHaveTextContent("1");
    expect(headerA).toHaveTextContent("Source A");

    const headerB = screen.getByTestId("citation-m1-doc-b-header");
    expect(headerB).toHaveTextContent("2");
    expect(headerB).toHaveTextContent("Source B");
  });

  it("falls back to 'Citation N' when the title is missing", () => {
    renderPanel({ messageId: "m1", citations: [docBare] });
    fireEvent.click(toggleButton("m1"));

    expect(
      screen.getByTestId("citation-m1-doc-bare-header"),
    ).toHaveTextContent("Citation 1");
  });

  it("does not render a relevance score badge", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });
    fireEvent.click(toggleButton("m1"));

    expect(screen.queryByTestId("citation-m1-doc-a-score")).toBeNull();
    expect(screen.queryByTestId("citation-m1-doc-b-score")).toBeNull();
  });

  it("renders item snippet + deep-link when both are present", () => {
    renderPanel({ messageId: "m1", citations: [docA] });
    fireEvent.click(toggleButton("m1"));
    // Expand the item so its panel body mounts into the DOM.
    fireEvent.click(itemHeaderButton("m1", "doc-a"));

    expect(screen.getByText(/Snippet body for source A\./)).toBeInTheDocument();
    const link = screen.getByTestId(
      "citation-m1-doc-a-link",
    ) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("https://example.com/a");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("omits the snippet paragraph and link when those fields are empty", () => {
    renderPanel({ messageId: "m1", citations: [docBare] });
    fireEvent.click(toggleButton("m1"));
    fireEvent.click(itemHeaderButton("m1", "doc-bare"));

    expect(screen.queryByTestId("citation-m1-doc-bare-link")).toBeNull();
    expect(
      screen.getByTestId("citation-m1-doc-bare-panel"),
    ).toBeInTheDocument();
  });

  it("expands an item on its header click and collapses on a second click", () => {
    renderPanel({ messageId: "m1", citations: [docA] });
    fireEvent.click(toggleButton("m1"));

    const header = itemHeaderButton("m1", "doc-a");
    expect(header.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(header);
    expect(header.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(header);
    expect(header.getAttribute("aria-expanded")).toBe("false");
  });

  it("supports expanding multiple items simultaneously", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });
    fireEvent.click(toggleButton("m1"));

    const headerA = itemHeaderButton("m1", "doc-a");
    const headerB = itemHeaderButton("m1", "doc-b");
    fireEvent.click(headerA);
    fireEvent.click(headerB);
    expect(headerA.getAttribute("aria-expanded")).toBe("true");
    expect(headerB.getAttribute("aria-expanded")).toBe("true");
  });

  it("links use safe target+rel so opening a source does not leak the opener window", () => {
    // Spy on window.open to confirm the anchor uses native navigation
    // rather than a JS handler that would skip the rel guard.
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    try {
      renderPanel({ messageId: "m1", citations: [docA] });
      fireEvent.click(toggleButton("m1"));
      fireEvent.click(itemHeaderButton("m1", "doc-a"));
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
  it("auto-opens the toggle and expands the matching item when focusedCitationId resolves", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: "doc-b",
    });
    expect(toggleButton("m1").getAttribute("aria-expanded")).toBe("true");
    expect(itemHeaderButton("m1", "doc-a").getAttribute("aria-expanded")).toBe(
      "false",
    );
    expect(itemHeaderButton("m1", "doc-b").getAttribute("aria-expanded")).toBe(
      "true",
    );
  });

  it("leaves the list collapsed when focusedCitationId is null", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: null,
    });
    expect(toggleButton("m1").getAttribute("aria-expanded")).toBe("false");
    expect(itemHeaderButton("m1", "doc-a").getAttribute("aria-expanded")).toBe(
      "false",
    );
    expect(itemHeaderButton("m1", "doc-b").getAttribute("aria-expanded")).toBe(
      "false",
    );
  });

  it("ignores focusedCitationId values that do not match any citation id", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: "doc-nope",
    });
    expect(toggleButton("m1").getAttribute("aria-expanded")).toBe("false");
    expect(itemHeaderButton("m1", "doc-a").getAttribute("aria-expanded")).toBe(
      "false",
    );
  });

  it("preserves a user-opened item when focus later targets a different item", () => {
    const { rerender } = render(
      <FluentProvider theme={webLightTheme}>
        <CitationPanel
          messageId="m1"
          citations={[docA, docB]}
          focusedCitationId={null}
        />
      </FluentProvider>,
    );
    // User opens the block, then item A.
    fireEvent.click(toggleButton("m1"));
    fireEvent.click(itemHeaderButton("m1", "doc-a"));
    // Parent now flips focus to item B (e.g. an inline reference click).
    rerender(
      <FluentProvider theme={webLightTheme}>
        <CitationPanel
          messageId="m1"
          citations={[docA, docB]}
          focusedCitationId="doc-b"
        />
      </FluentProvider>,
    );
    // Both items are open — focus is additive, never destructive, so
    // the user's manual A stays put.
    expect(itemHeaderButton("m1", "doc-a").getAttribute("aria-expanded")).toBe(
      "true",
    );
    expect(itemHeaderButton("m1", "doc-b").getAttribute("aria-expanded")).toBe(
      "true",
    );
  });

  it("user can still collapse a focus-expanded item by clicking its header", () => {
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      focusedCitationId: "doc-a",
    });
    const headerA = itemHeaderButton("m1", "doc-a");
    expect(headerA.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(headerA);
    expect(headerA.getAttribute("aria-expanded")).toBe("false");
  });
});
