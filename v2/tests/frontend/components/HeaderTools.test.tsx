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
import {
  resolveDisplayName,
  userInitials,
} from "@/components/Header/userIdentity";
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
          {...(props?.userInfo !== undefined
            ? { userInfo: props.userInfo }
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

  it("renders a light-gray guest avatar showing 'G' when no user is signed in", () => {
    renderTools();
    expect(screen.getByTestId("header-user-avatar")).toBeInTheDocument();
    expect(screen.getByText("G")).toBeInTheDocument();
  });

  it("renders the signed-in user's initials in the avatar", () => {
    renderTools({
      userInfo: {
        userId: "oid-1",
        claims: [{ typ: "name", val: "John Doe" }],
      },
    });
    expect(screen.getByText("JD")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /john doe/i }),
    ).toBeInTheDocument();
  });
});

describe("resolveDisplayName", () => {
  it("returns Guest when no user is signed in", () => {
    expect(resolveDisplayName(null)).toBe("Guest");
    expect(resolveDisplayName(undefined)).toBe("Guest");
  });

  it("prefers the name claim", () => {
    expect(
      resolveDisplayName({
        userId: "x",
        claims: [{ typ: "name", val: "Ada Lovelace" }],
      }),
    ).toBe("Ada Lovelace");
  });

  it("falls back to preferred_username when name is absent", () => {
    expect(
      resolveDisplayName({
        userId: "x",
        claims: [{ typ: "preferred_username", val: "ada@example.com" }],
      }),
    ).toBe("ada@example.com");
  });

  it("returns Guest when no name-bearing claim is present", () => {
    expect(
      resolveDisplayName({ userId: "x", claims: [{ typ: "roles", val: "admin" }] }),
    ).toBe("Guest");
  });
});

describe("userInitials", () => {
  it("uses the first letters of the first two parts", () => {
    expect(userInitials("John Doe")).toBe("JD");
  });

  it("uses the first letter of a single-part name", () => {
    expect(userInitials("Madonna")).toBe("M");
  });

  it("returns G for Guest", () => {
    expect(userInitials("Guest")).toBe("G");
  });

  it("strips parenthetical segments before taking initials", () => {
    expect(userInitials("John (Contoso) Doe")).toBe("JD");
  });
});
