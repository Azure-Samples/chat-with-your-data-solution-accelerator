/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest coverage for `renderAnswerTokens()`.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { renderAnswerTokens } from "@/pages/chat/components/answerTokens";
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

function renderHarness(node: React.ReactNode) {
  return render(<div data-testid="harness">{node}</div>);
}

describe("renderAnswerTokens", () => {
  it("returns the content verbatim when no citations are supplied", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "see [doc1] for details",
        "m1",
        undefined,
        onClick,
      ),
    );
    expect(screen.getByTestId("harness")).toHaveTextContent(
      "see [doc1] for details",
    );
    expect(screen.queryByTestId("answer-token-m1-1")).toBeNull();
  });

  it("returns the content verbatim when citations array is empty", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "see [doc1] for details",
        "m1",
        [],
        onClick,
      ),
    );
    expect(screen.queryByTestId("answer-token-m1-1")).toBeNull();
  });

  it("returns plain text unchanged when no tokens are present", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "plain answer with no markers",
        "m1",
        [cit1],
        onClick,
      ),
    );
    expect(screen.getByTestId("harness")).toHaveTextContent(
      "plain answer with no markers",
    );
    expect(screen.queryByTestId("answer-token-m1-1")).toBeNull();
  });

  it("renders a single resolvable [doc1] token as a clickable button", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "prefix [doc1] suffix",
        "m1",
        [cit1],
        onClick,
      ),
    );
    const harness = screen.getByTestId("harness");
    expect(harness.textContent).toBe("prefix [doc1] suffix");
    const button = screen.getByTestId("answer-token-m1-1");
    expect(button.tagName.toLowerCase()).toBe("button");
    expect(button.getAttribute("type")).toBe("button");
    expect(button.getAttribute("data-citation-id")).toBe("doc-alpha");
  });

  it("renders multiple resolvable tokens", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "first [doc1] second [doc2] end",
        "m1",
        [cit1, cit2],
        onClick,
      ),
    );
    expect(screen.getByTestId("answer-token-m1-1")).toBeInTheDocument();
    expect(screen.getByTestId("answer-token-m1-2")).toBeInTheDocument();
    expect(screen.getByTestId("harness").textContent).toBe(
      "first [doc1] second [doc2] end",
    );
  });

  it("renders out-of-bounds tokens (index > citations.length) as literal text", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "see [doc7] for details",
        "m1",
        [cit1],
        onClick,
      ),
    );
    expect(screen.queryByTestId("answer-token-m1-7")).toBeNull();
    expect(screen.getByTestId("harness").textContent).toBe(
      "see [doc7] for details",
    );
  });

  it("renders [doc0] as literal text (1-based numbering)", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "see [doc0] for details",
        "m1",
        [cit1],
        onClick,
      ),
    );
    expect(screen.queryByTestId("answer-token-m1-0")).toBeNull();
    expect(screen.getByTestId("harness").textContent).toBe(
      "see [doc0] for details",
    );
  });

  it("clicking a token fires onCitationClick with the resolved citation id", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "see [doc1] and [doc2]",
        "m1",
        [cit1, cit2],
        onClick,
      ),
    );
    fireEvent.click(screen.getByTestId("answer-token-m1-2"));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith("doc-beta");
  });

  it("handles adjacent tokens with no separator", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "answer [doc1][doc2] done",
        "m1",
        [cit1, cit2],
        onClick,
      ),
    );
    expect(screen.getByTestId("answer-token-m1-1")).toBeInTheDocument();
    expect(screen.getByTestId("answer-token-m1-2")).toBeInTheDocument();
    expect(screen.getByTestId("harness").textContent).toBe(
      "answer [doc1][doc2] done",
    );
  });

  it("handles tokens at the very start and very end of the content", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens(
        "[doc1] in the middle [doc2]",
        "m1",
        [cit1, cit2],
        onClick,
      ),
    );
    expect(screen.getByTestId("answer-token-m1-1")).toBeInTheDocument();
    expect(screen.getByTestId("answer-token-m1-2")).toBeInTheDocument();
    expect(screen.getByTestId("harness").textContent).toBe(
      "[doc1] in the middle [doc2]",
    );
  });

  it("renders an empty string as nothing without throwing", () => {
    const onClick = vi.fn();
    renderHarness(
      renderAnswerTokens("", "m1", [cit1], onClick),
    );
    expect(screen.getByTestId("harness").textContent).toBe("");
  });
});
