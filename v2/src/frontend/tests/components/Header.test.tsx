/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Tests for the Coral <Header> component. Same behavioural contract
 * as the prior <AppHeader> (preserved verbatim accessible names, the
 * `data-testid="app-header"` discriminator, the same callback wiring)
 * but the brand visuals are now MACAE-faithful: Microsoft 4-square
 * logo + "<title> | <subtitle>" pattern.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Header } from "@/components/Header/Header";
import { FluentThemeBridge } from "@/theme/FluentThemeBridge";
import { ThemeProvider } from "@/theme/themeContext";

function renderHeader(props?: Partial<React.ComponentProps<typeof Header>>) {
  const onToggleHistory = props?.onToggleHistory ?? vi.fn();
  const onNewChat = props?.onNewChat ?? vi.fn();
  const utils = render(
    <ThemeProvider>
      <FluentThemeBridge>
        <Header
          title={props?.title ?? "Chat with your data"}
          {...(props?.subtitle !== undefined ? { subtitle: props.subtitle } : {})}
          historyOpen={props?.historyOpen ?? false}
          onToggleHistory={onToggleHistory}
          onNewChat={onNewChat}
        />
      </FluentThemeBridge>
    </ThemeProvider>,
  );
  return { ...utils, onToggleHistory, onNewChat };
}

describe("Header", () => {
  it("renders the title, the default subtitle, and a Microsoft brand logo", () => {
    renderHeader({ title: "Chat with your data" });
    expect(
      screen.getByRole("heading", { level: 1, name: /chat with your data/i }),
    ).toBeInTheDocument();
    // Default subtitle from MACAE pattern: "<title> | Solution Accelerator".
    expect(screen.getByText(/solution accelerator/i)).toBeInTheDocument();
    // The 4-square Microsoft logo is rendered as an <svg role="img">
    // with aria-label="Microsoft" so it is announced by screen readers.
    const logos = screen.getAllByRole("img", { name: /microsoft/i });
    expect(logos.length).toBeGreaterThan(0);
  });

  it("renders a custom subtitle when provided", () => {
    renderHeader({ title: "Hello", subtitle: "Demo Build" });
    expect(screen.getByText(/demo build/i)).toBeInTheDocument();
  });

  it("toggles the theme when the theme button is clicked", () => {
    renderHeader();
    const toggle = screen.getByRole("button", { name: /switch to dark mode/i });
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(
      screen.getByRole("button", { name: /switch to light mode/i }),
    ).toBeInTheDocument();
  });

  it("calls onToggleHistory when the history button is clicked", () => {
    const { onToggleHistory } = renderHeader();
    fireEvent.click(screen.getByRole("button", { name: /history/i }));
    expect(onToggleHistory).toHaveBeenCalledTimes(1);
  });

  it("calls onNewChat when the new chat button is clicked", () => {
    const { onNewChat } = renderHeader();
    fireEvent.click(screen.getByRole("button", { name: /new chat/i }));
    expect(onNewChat).toHaveBeenCalledTimes(1);
  });

  it("reflects historyOpen via aria-pressed on the history toggle", () => {
    renderHeader({ historyOpen: true });
    const historyBtn = screen.getByRole("button", { name: /history/i });
    expect(historyBtn).toHaveAttribute("aria-pressed", "true");
  });
});
