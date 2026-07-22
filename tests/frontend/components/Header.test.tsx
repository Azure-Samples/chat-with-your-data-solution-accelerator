/**
 * Tests for the Coral <Header> component. Same behavioural contract
 * as the prior <AppHeader> (preserved verbatim accessible names, the
 * `data-testid="app-header"` discriminator, the same callback wiring)
 * but the brand visuals are now reference-architecture-faithful: Microsoft 4-square
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
  const onNavigateHome = props?.onNavigateHome ?? vi.fn();
  const onOpenAdmin = props?.onOpenAdmin ?? vi.fn();
  const utils = render(
    <ThemeProvider>
      <FluentThemeBridge>
        <Header
          title={props?.title ?? "Chat with your data"}
          {...(props?.subtitle !== undefined ? { subtitle: props.subtitle } : {})}
          historyOpen={props?.historyOpen ?? false}
          onToggleHistory={onToggleHistory}
          onNewChat={onNewChat}
          onNavigateHome={onNavigateHome}
          onOpenAdmin={onOpenAdmin}
          {...(props?.adminAvailable !== undefined
            ? { adminAvailable: props.adminAvailable }
            : {})}
        />
      </FluentThemeBridge>
    </ThemeProvider>,
  );
  return { ...utils, onToggleHistory, onNewChat, onNavigateHome, onOpenAdmin };
}

describe("Header", () => {
  it("renders the title, the default subtitle, and a clickable multi-agent home logo", () => {
    renderHeader({ title: "Chat with your data" });
    expect(
      screen.getByRole("heading", { level: 1, name: /chat with your data/i }),
    ).toBeInTheDocument();
    // Default subtitle from the reference-architecture pattern: "<title> | Solution Accelerator".
    expect(screen.getByText(/solution accelerator/i)).toBeInTheDocument();
    // The brand logo is now a multi-agent badge wrapped in a button that
    // returns to the home / chat view.
    expect(screen.getByTestId("header-home")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /go to home/i }),
    ).toBeInTheDocument();
  });

  it("calls onNavigateHome when the brand logo is clicked", () => {
    const { onNavigateHome } = renderHeader();
    fireEvent.click(screen.getByTestId("header-home"));
    expect(onNavigateHome).toHaveBeenCalledTimes(1);
  });

  it("renders the multi-agent brand mark itself, not an initials fallback", () => {
    // Fluent's Avatar hides its `icon` slot whenever a `name` yields
    // initials, so the brand mark must render with no `name` (otherwise
    // the Avatar shows the "M" of "Multi-agent" instead of the logo).
    // viewBox "0 0 33 32" is unique to <MultiAgentLogo>.
    const { container } = renderHeader();
    expect(
      container.querySelector('svg[viewBox="0 0 33 32"]'),
    ).not.toBeNull();
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

  it("renders the admin entry button when adminAvailable is true", () => {
    renderHeader({ adminAvailable: true });
    expect(screen.getByTestId("header-admin")).toBeInTheDocument();
  });

  it("calls onOpenAdmin when the admin entry button is clicked", () => {
    const { onOpenAdmin } = renderHeader({ adminAvailable: true });
    fireEvent.click(screen.getByTestId("header-admin"));
    expect(onOpenAdmin).toHaveBeenCalledTimes(1);
  });

  it("does not render the admin entry button when adminAvailable is not true", () => {
    renderHeader({ adminAvailable: false });
    expect(screen.queryByTestId("header-admin")).not.toBeInTheDocument();
  });
});
