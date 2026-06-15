/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest coverage for `<CitationPanel>` — the v1-style reference block:
 * a collapsible "N references / 1 reference" toggle that reveals a row
 * of numbered reference chips. Clicking a chip calls `onSelectCitation`
 * with the full citation (the parent opens the source detail column);
 * the panel itself never expands inline.
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
const docLong: Citation = {
  id: "doc-long",
  title:
    "Woodgrove_Insurance_Benefits_Overview_For_All_Employees.pdf - Part 1",
  url: "https://example.com/long",
  snippet: "Long snippet.",
  score: null,
  metadata: {},
};

function renderPanel(props: {
  messageId: string;
  citations: Citation[];
  onSelectCitation?: (citation: Citation) => void;
}) {
  const onSelectCitation = props.onSelectCitation ?? (() => {});
  return render(
    <FluentProvider theme={webLightTheme}>
      <CitationPanel
        messageId={props.messageId}
        citations={props.citations}
        onSelectCitation={onSelectCitation}
      />
    </FluentProvider>,
  );
}

function toggleButton(messageId: string): HTMLButtonElement {
  return screen.getByTestId(
    `citations-toggle-${messageId}`,
  ) as HTMLButtonElement;
}

function chipButton(messageId: string, citationId: string): HTMLButtonElement {
  return screen.getByTestId(
    `citation-${messageId}-${citationId}`,
  ) as HTMLButtonElement;
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

  it("hides the chip list until the toggle is expanded", () => {
    renderPanel({ messageId: "m1", citations: [docA] });
    const body = screen.getByTestId("citations-body-m1");
    expect(body.hasAttribute("hidden")).toBe(true);

    fireEvent.click(toggleButton("m1"));
    expect(body.hasAttribute("hidden")).toBe(false);

    fireEvent.click(toggleButton("m1"));
    expect(body.hasAttribute("hidden")).toBe(true);
  });

  it("toggles aria-expanded when the reference toggle is clicked", () => {
    renderPanel({ messageId: "m1", citations: [docA] });

    const toggle = toggleButton("m1");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("renders one chip per citation, numbered by 1-based position", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });
    fireEvent.click(toggleButton("m1"));

    const chipA = chipButton("m1", "doc-a");
    expect(chipA.tagName.toLowerCase()).toBe("button");
    expect(chipA).toHaveTextContent("1");
    expect(chipA).toHaveTextContent("Source A");

    const chipB = chipButton("m1", "doc-b");
    expect(chipB).toHaveTextContent("2");
    expect(chipB).toHaveTextContent("Source B");
  });

  it("falls back to 'Citation N' when the title is missing", () => {
    renderPanel({ messageId: "m1", citations: [docBare] });
    fireEvent.click(toggleButton("m1"));
    expect(chipButton("m1", "doc-bare")).toHaveTextContent("Citation 1");
  });

  it("middle-truncates a long chip label but keeps its tail", () => {
    renderPanel({ messageId: "m1", citations: [docLong] });
    fireEvent.click(toggleButton("m1"));

    const chip = chipButton("m1", "doc-long");
    expect(chip.textContent).toContain("...");
    // The disambiguating part suffix stays visible after truncation.
    expect(chip.textContent?.endsWith("- Part 1")).toBe(true);
    // The full untruncated filename must not be rendered verbatim.
    expect(chip.textContent).not.toContain(
      "Woodgrove_Insurance_Benefits_Overview_For_All_Employees.pdf",
    );
  });

  it("calls onSelectCitation with the full citation when a chip is clicked", () => {
    const onSelect = vi.fn();
    renderPanel({
      messageId: "m1",
      citations: [docA, docB],
      onSelectCitation: onSelect,
    });
    fireEvent.click(toggleButton("m1"));
    fireEvent.click(chipButton("m1", "doc-b"));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(docB);
  });

  it("does not render a relevance score badge", () => {
    renderPanel({ messageId: "m1", citations: [docA, docB] });
    fireEvent.click(toggleButton("m1"));

    expect(screen.queryByTestId("citation-m1-doc-a-score")).toBeNull();
    expect(screen.queryByTestId("citation-m1-doc-b-score")).toBeNull();
  });

  it("no longer renders inline accordion header/panel/link nodes", () => {
    renderPanel({ messageId: "m1", citations: [docA] });
    fireEvent.click(toggleButton("m1"));

    expect(screen.queryByTestId("citation-m1-doc-a-header")).toBeNull();
    expect(screen.queryByTestId("citation-m1-doc-a-panel")).toBeNull();
    expect(screen.queryByTestId("citation-m1-doc-a-link")).toBeNull();
  });
});
