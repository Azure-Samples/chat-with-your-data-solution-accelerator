/**
 * Tests for the Coral shell layout primitives. Verifies:
 *   1. Children render inside a `<CoralShellColumn>`.
 *   2. Children render inside a `<CoralShellRow>`.
 *   3. Both forward a custom `className` (composed, not replaced).
 *   4. Both surface a `data-coral-shell` discriminator so layout-aware
 *      tests + browser inspector queries can target them without
 *      depending on CSS-Module-hashed class names.
 *
 * No styling is asserted (Fluent tokens are runtime CSS custom
 * properties; we don't pin token values in tests). The contract this
 * module owns is structural: the wrapper exists, has the right
 * discriminator, and accepts user className composition.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoralShellColumn } from "@/components/CoralShell/CoralShellColumn";
import { CoralShellRow } from "@/components/CoralShell/CoralShellRow";

describe("CoralShellColumn", () => {
  it("renders children inside a column wrapper marked data-coral-shell='column'", () => {
    render(
      <CoralShellColumn>
        <span data-testid="column-child">child</span>
      </CoralShellColumn>,
    );
    const child = screen.getByTestId("column-child");
    expect(child).toBeInTheDocument();
    const wrapper = child.parentElement;
    expect(wrapper).not.toBeNull();
    expect(wrapper?.getAttribute("data-coral-shell")).toBe("column");
  });

  it("composes a custom className after the base shell class", () => {
    render(
      <CoralShellColumn className="custom-extra">
        <span data-testid="column-child">child</span>
      </CoralShellColumn>,
    );
    const wrapper = screen.getByTestId("column-child").parentElement;
    expect(wrapper).not.toBeNull();
    const cls = wrapper?.getAttribute("class") ?? "";
    expect(cls).toContain("custom-extra");
    // Base class is a CSS-Module hash; we don't pin it, but the
    // composed className must have at least one OTHER class besides
    // "custom-extra" to prove we composed instead of replaced.
    expect(cls.trim().split(/\s+/).length).toBeGreaterThanOrEqual(2);
  });
});

describe("CoralShellRow", () => {
  it("renders children inside a row wrapper marked data-coral-shell='row'", () => {
    render(
      <CoralShellRow>
        <span data-testid="row-child">child</span>
      </CoralShellRow>,
    );
    const child = screen.getByTestId("row-child");
    expect(child).toBeInTheDocument();
    const wrapper = child.parentElement;
    expect(wrapper).not.toBeNull();
    expect(wrapper?.getAttribute("data-coral-shell")).toBe("row");
  });

  it("composes a custom className after the base row class", () => {
    render(
      <CoralShellRow className="row-extra">
        <span data-testid="row-child">child</span>
      </CoralShellRow>,
    );
    const wrapper = screen.getByTestId("row-child").parentElement;
    expect(wrapper).not.toBeNull();
    const cls = wrapper?.getAttribute("class") ?? "";
    expect(cls).toContain("row-extra");
    expect(cls.trim().split(/\s+/).length).toBeGreaterThanOrEqual(2);
  });
});
