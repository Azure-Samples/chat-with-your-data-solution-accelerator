/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Tests for <HeaderTools>: the right-side header toolbar. Covers the
 * always-on new-chat / history / theme buttons plus the admin entry
 * button, which only renders when the caller reports
 * `adminAvailable === true` and supplies an `onOpenAdmin` handler.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HeaderTools } from "@/components/Header/HeaderTools";
import { FluentThemeBridge } from "@/theme/FluentThemeBridge";
import { ThemeProvider } from "@/theme/themeContext";

function renderTools(props?: Partial<React.ComponentProps<typeof HeaderTools>>) {
  const onToggleHistory = props?.onToggleHistory ?? vi.fn();
  const onNewChat = props?.onNewChat ?? vi.fn();
  const onOpenAdmin = props?.onOpenAdmin ?? vi.fn();
  const utils = render(
    <ThemeProvider>
      <FluentThemeBridge>
        <HeaderTools
          historyOpen={props?.historyOpen ?? false}
          onToggleHistory={onToggleHistory}
          onNewChat={onNewChat}
          onOpenAdmin={onOpenAdmin}
          {...(props?.adminAvailable !== undefined
            ? { adminAvailable: props.adminAvailable }
            : {})}
        />
      </FluentThemeBridge>
    </ThemeProvider>,
  );
  return { ...utils, onToggleHistory, onNewChat, onOpenAdmin };
}

describe("HeaderTools", () => {
  it("always renders the new chat, history, and theme buttons", () => {
    renderTools();
    expect(
      screen.getByRole("button", { name: /new chat/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /history/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /switch to dark mode/i }),
    ).toBeInTheDocument();
  });

  it("renders the admin button when adminAvailable is true", () => {
    renderTools({ adminAvailable: true });
    expect(screen.getByTestId("header-admin")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^admin$/i }),
    ).toBeInTheDocument();
  });

  it("hides the admin button when adminAvailable is false", () => {
    renderTools({ adminAvailable: false });
    expect(screen.queryByTestId("header-admin")).not.toBeInTheDocument();
  });

  it("hides the admin button while the admin probe is in flight (null)", () => {
    renderTools({ adminAvailable: null });
    expect(screen.queryByTestId("header-admin")).not.toBeInTheDocument();
  });

  it("calls onOpenAdmin when the admin button is clicked", () => {
    const { onOpenAdmin } = renderTools({ adminAvailable: true });
    fireEvent.click(screen.getByTestId("header-admin"));
    expect(onOpenAdmin).toHaveBeenCalledTimes(1);
  });

  it("calls onNewChat when the new chat button is clicked", () => {
    const { onNewChat } = renderTools();
    fireEvent.click(screen.getByRole("button", { name: /new chat/i }));
    expect(onNewChat).toHaveBeenCalledTimes(1);
  });

  it("calls onToggleHistory when the history button is clicked", () => {
    const { onToggleHistory } = renderTools();
    fireEvent.click(screen.getByRole("button", { name: /history/i }));
    expect(onToggleHistory).toHaveBeenCalledTimes(1);
  });
});
