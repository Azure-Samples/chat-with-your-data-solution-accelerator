/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest coverage for `<CitationDetailPanel>` — the right-side source
 * detail column. Verifies it stays unmounted with no active citation,
 * renders the title + deep-link + markdown reference text when a
 * citation is selected, escapes raw HTML in the snippet, and clears
 * itself when dismissed.
 */
import { describe, expect, it } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { CitationDetailPanel } from "@/pages/chat/components/CitationDetailPanel/CitationDetailPanel";
import {
  ChatActionType,
  ChatProvider,
  useChat,
} from "@/pages/chat/ChatContext";
import type { Citation } from "@/models/chat";

const docFull: Citation = {
  id: "doc-1",
  title: "Benefit_Options.pdf - Part 1",
  url: "https://example.com/benefit-options.pdf",
  snippet: "**Health** coverage with <b>raw</b> markup.",
  score: null,
  metadata: {},
};
const docNoUrl: Citation = {
  id: "doc-2",
  title: "No Link Source.pdf",
  url: "",
  snippet: "Plain text body.",
  score: null,
  metadata: {},
};
const docEmpty: Citation = {
  id: "doc-3",
  title: "",
  url: "",
  snippet: "Body with no source link.",
  score: null,
  metadata: {},
};

/**
 * Test harness: a sibling control that can show a citation or close
 * the panel through the real reducer, rendered next to the panel under
 * a shared <ChatProvider>.
 */
function Harness({ citation }: { citation: Citation }) {
  const { dispatch } = useChat();
  return (
    <>
      <button
        type="button"
        data-testid="harness-show"
        onClick={() =>
          dispatch({ type: ChatActionType.ShowCitation, citation })
        }
      >
        show
      </button>
      <CitationDetailPanel />
    </>
  );
}

function renderHarness(citation: Citation) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ChatProvider>
        <Harness citation={citation} />
      </ChatProvider>
    </FluentProvider>,
  );
}

/**
 * Switch harness: two controls that show two different citations through
 * the real reducer, so a test can verify the panel updates in place when
 * the active citation changes.
 */
function SwitchHarness() {
  const { dispatch } = useChat();
  return (
    <>
      <button
        type="button"
        data-testid="show-a"
        onClick={() =>
          dispatch({ type: ChatActionType.ShowCitation, citation: docFull })
        }
      >
        a
      </button>
      <button
        type="button"
        data-testid="show-b"
        onClick={() =>
          dispatch({ type: ChatActionType.ShowCitation, citation: docNoUrl })
        }
      >
        b
      </button>
      <CitationDetailPanel />
    </>
  );
}

function renderSwitchHarness() {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ChatProvider>
        <SwitchHarness />
      </ChatProvider>
    </FluentProvider>,
  );
}

describe("CitationDetailPanel", () => {
  it("renders nothing when no citation is active", () => {
    renderHarness(docFull);
    expect(screen.queryByTestId("citation-detail-panel")).toBeNull();
  });

  it("renders the title, open-document link, and reference body once a citation is shown", () => {
    renderHarness(docFull);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });

    expect(screen.getByTestId("citation-detail-panel")).toBeInTheDocument();
    expect(screen.getByTestId("citation-detail-title")).toHaveTextContent(
      "Benefit_Options.pdf - Part 1",
    );

    const link = screen.getByTestId(
      "citation-detail-link",
    ) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe(
      "https://example.com/benefit-options.pdf",
    );
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("renders markdown in the reference text as HTML", () => {
    renderHarness(docFull);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });

    const body = screen.getByTestId("citation-detail-body");
    const strong = body.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong).toHaveTextContent("Health");
  });

  it("escapes raw HTML in the snippet rather than rendering it", () => {
    renderHarness(docFull);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });

    const body = screen.getByTestId("citation-detail-body");
    // No rehype-raw: the `<b>` in the snippet must not become a real
    // bold element — it is rendered as escaped literal text.
    expect(body.querySelector("b")).toBeNull();
    expect(body.textContent).toContain("<b>raw</b>");
  });

  it("derives a backend file link from the blob title when the citation has no URL", () => {
    renderHarness(docNoUrl);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });

    expect(screen.getByTestId("citation-detail-panel")).toBeInTheDocument();
    const link = screen.getByTestId(
      "citation-detail-link",
    ) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/api/files/No%20Link%20Source.pdf");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("omits the open-document link when the citation has no url and no title", () => {
    renderHarness(docEmpty);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });

    expect(screen.getByTestId("citation-detail-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("citation-detail-link")).toBeNull();
  });

  it("clears the panel when the dismiss control is clicked", () => {
    renderHarness(docFull);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });
    expect(screen.getByTestId("citation-detail-panel")).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByTestId("citation-detail-dismiss"));
    });
    expect(screen.queryByTestId("citation-detail-panel")).toBeNull();
  });

  it("keeps the title and open-document link outside the scrolling body", () => {
    renderHarness(docFull);
    act(() => {
      fireEvent.click(screen.getByTestId("harness-show"));
    });

    const body = screen.getByTestId("citation-detail-body");
    const title = screen.getByTestId("citation-detail-title");
    const link = screen.getByTestId("citation-detail-link");
    // The pinned head (title + link) must sit outside the scroll region so
    // it stays visible no matter how far the reference body is scrolled.
    expect(body.contains(title)).toBe(false);
    expect(body.contains(link)).toBe(false);
  });

  it("remounts the reference body when the active citation changes so it resets to the top", () => {
    renderSwitchHarness();
    act(() => {
      fireEvent.click(screen.getByTestId("show-a"));
    });
    const firstBody = screen.getByTestId("citation-detail-body");
    expect(screen.getByTestId("citation-detail-title")).toHaveTextContent(
      "Benefit_Options.pdf - Part 1",
    );

    act(() => {
      fireEvent.click(screen.getByTestId("show-b"));
    });
    const secondBody = screen.getByTestId("citation-detail-body");
    expect(screen.getByTestId("citation-detail-title")).toHaveTextContent(
      "No Link Source.pdf",
    );
    // key={citation.id} forces a fresh body node on citation change, so a
    // stale scroll position cannot carry over from the previous source.
    expect(secondBody).not.toBe(firstBody);
  });
});
