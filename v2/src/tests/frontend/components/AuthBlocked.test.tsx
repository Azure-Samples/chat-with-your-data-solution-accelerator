/**
 * Pillar: Stable Core
 * Phase: 5 (frontend — user identity)
 *
 * Tests for <AuthBlocked>, the full-view screen shown when auth is
 * enforced but no signed-in user could be resolved. Asserts the alert
 * region, the heading, the operator guidance, the external setup links
 * (opened safely in a new tab), and the decorative shield icon.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AuthBlocked } from "@/components/AuthBlocked/AuthBlocked";
import { FluentThemeBridge } from "@/theme/FluentThemeBridge";
import { ThemeProvider } from "@/theme/themeContext";

function renderBlocked() {
  return render(
    <ThemeProvider>
      <FluentThemeBridge>
        <AuthBlocked />
      </FluentThemeBridge>
    </ThemeProvider>,
  );
}

describe("AuthBlocked", () => {
  it("renders an alert region with the auth-blocked heading", () => {
    renderBlocked();
    expect(screen.getByTestId("auth-blocked")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /authentication not configured/i,
      }),
    ).toBeInTheDocument();
  });

  it("explains that the app requires sign-in but no user was found", () => {
    renderBlocked();
    expect(
      screen.getByText(/no signed-in user could be found/i),
    ).toBeInTheDocument();
  });

  it("links to the Azure Portal, opened safely in a new tab", () => {
    renderBlocked();
    const link = screen.getByRole("link", { name: /azure portal/i });
    expect(link).toHaveAttribute("href", "https://portal.azure.com/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("links to the App Service authentication setup instructions", () => {
    renderBlocked();
    const link = screen.getByRole("link", { name: /these instructions/i });
    expect(link.getAttribute("href")).toMatch(/learn\.microsoft\.com/);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("shows the configuration-propagation note", () => {
    renderBlocked();
    expect(
      screen.getByText(/takes a few minutes to apply/i),
    ).toBeInTheDocument();
  });

  it("renders a decorative shield icon hidden from assistive tech", () => {
    const { container } = renderBlocked();
    const icon = container.querySelector("svg");
    expect(icon).not.toBeNull();
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });
});
