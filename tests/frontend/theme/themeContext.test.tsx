/**
 * Tests for the ThemeProvider + useTheme primitive that owns light/dark
 * mode for the v2 frontend. Theme is persisted to localStorage and
 * mirrored to `document.documentElement.dataset.theme` so CSS custom
 * properties in `tokens.css` can switch via `[data-theme="dark"]`.
 */
import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider, useTheme } from "@/theme/themeContext";

const STORAGE_KEY = "cwyd.theme";

function wrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

describe("ThemeProvider / useTheme", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to light theme when localStorage is empty", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("toggles from light to dark and back", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("light");

    act(() => result.current.toggleTheme());
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");

    act(() => result.current.toggleTheme());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("persists the theme to localStorage on toggle", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    act(() => result.current.toggleTheme());
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("restores the persisted theme from localStorage on mount", () => {
    window.localStorage.setItem(STORAGE_KEY, "dark");
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("renders children inside the provider", () => {
    render(
      <ThemeProvider>
        <span data-testid="child">hello</span>
      </ThemeProvider>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("hello");
  });

  it("throws a clear error when useTheme is called outside ThemeProvider", () => {
    // Suppress the expected React error log for the throwing render.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useTheme())).toThrow(
      /useTheme must be used inside a ThemeProvider/i,
    );
    spy.mockRestore();
  });
});
