/**
 * Tests for the <MultiAgentLogo> brand mark: it renders as an
 * accessible <svg role="img"> labelled "Multi-agent", honours the
 * `size` prop, and fills with the brand foreground design token.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MultiAgentLogo } from "@/components/Header/MultiAgentLogo";

describe("MultiAgentLogo", () => {
  it("renders an accessible svg labelled Multi-agent", () => {
    render(<MultiAgentLogo />);
    expect(screen.getByRole("img", { name: /multi-agent/i })).toBeInTheDocument();
  });

  it("applies the size prop to width and height", () => {
    render(<MultiAgentLogo size={20} />);
    const svg = screen.getByRole("img", { name: /multi-agent/i });
    expect(svg).toHaveAttribute("width", "20");
    expect(svg).toHaveAttribute("height", "20");
  });

  it("fills the mark with the brand foreground design token", () => {
    const { container } = render(<MultiAgentLogo />);
    const path = container.querySelector("path");
    expect(path).toHaveAttribute("fill", "var(--colorBrandForeground1)");
  });
});
