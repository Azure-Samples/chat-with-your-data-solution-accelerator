/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — reference-architecture re-skin)
 *
 * Tests for `<PanelLeft>`, the left-rail layout primitive.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PanelLeft } from "@/components/CoralShell/PanelLeft";

describe("PanelLeft", () => {
  it("renders an aside landmark with data-coral-panel=\"left\" wrapping its children", () => {
    render(
      <PanelLeft aria-label="conversation history">
        <p data-testid="panel-left-content">hello</p>
      </PanelLeft>,
    );
    const aside = screen.getByRole("complementary", {
      name: /conversation history/i,
    });
    expect(aside).toHaveAttribute("data-coral-panel", "left");
    expect(aside.tagName).toBe("ASIDE");
    expect(screen.getByTestId("panel-left-content")).toBeInTheDocument();
  });

  it("composes a custom className with the base panel-left class", () => {
    render(
      <PanelLeft aria-label="sidebar" className="custom-extra">
        <span>x</span>
      </PanelLeft>,
    );
    const aside = screen.getByRole("complementary", { name: /sidebar/i });
    const tokens = aside.className.split(/\s+/).filter((t) => t.length > 0);
    expect(tokens.length).toBeGreaterThanOrEqual(2);
    expect(tokens).toContain("custom-extra");
  });
});
