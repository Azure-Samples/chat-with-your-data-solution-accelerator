/**
 * Pillar: Stable Core
 * Phase: 6 (frontend polish, pulled forward for boss demo)
 *
 * Tests for AppHeader: brand row + theme toggle + history toggle.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppHeader } from "../../src/components/AppHeader/AppHeader";
import { ThemeProvider } from "../../src/theme/themeContext";

function renderHeader(
  props?: Partial<React.ComponentProps<typeof AppHeader>>,
) {
  const onToggleHistory = props?.onToggleHistory ?? vi.fn();
  const onNewChat = props?.onNewChat ?? vi.fn();
  const utils = render(
    <ThemeProvider>
      <AppHeader
        title={props?.title ?? "Chat with your data"}
        historyOpen={props?.historyOpen ?? false}
        onToggleHistory={onToggleHistory}
        onNewChat={onNewChat}
      />
    </ThemeProvider>,
  );
  return { ...utils, onToggleHistory, onNewChat };
}

describe("AppHeader", () => {
  it("renders the title and the Azure logo with alt text", () => {
    renderHeader({ title: "Chat with your data" });
    expect(
      screen.getByRole("heading", { level: 1, name: /chat with your data/i }),
    ).toBeInTheDocument();
    expect(screen.getByAltText(/azure/i)).toBeInTheDocument();
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

  it("reflects historyOpen via aria-pressed", () => {
    renderHeader({ historyOpen: true });
    expect(screen.getByRole("button", { name: /history/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
