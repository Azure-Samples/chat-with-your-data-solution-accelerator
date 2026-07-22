/**
 * Tests for <ErrorBoundary>, the chat-surface render-failure net. A
 * descendant that throws during render must yield the recoverable
 * fallback (alert region + heading + message + retry) instead of
 * unmounting to a blank page; "Try again" must clear the error and
 * re-render the children once the underlying cause is gone.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type JSX, type ReactNode } from "react";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { FluentThemeBridge } from "@/theme/FluentThemeBridge";
import { ThemeProvider } from "@/theme/themeContext";

function Bomb({ explode }: { explode: boolean }): JSX.Element {
  if (explode) {
    throw new Error("kaboom: malformed message");
  }
  return <p data-testid="bomb-ok">no boom</p>;
}

function renderBoundary(children: ReactNode) {
  return render(
    <ThemeProvider>
      <FluentThemeBridge>
        <ErrorBoundary>{children}</ErrorBoundary>
      </FluentThemeBridge>
    </ThemeProvider>,
  );
}

describe("ErrorBoundary", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs every caught render error to console.error; silence the
    // expected noise so the suite output stays clean.
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("renders its children when they do not throw", () => {
    renderBoundary(<Bomb explode={false} />);
    expect(screen.getByTestId("bomb-ok")).toBeInTheDocument();
    expect(
      screen.queryByTestId("error-boundary-fallback"),
    ).not.toBeInTheDocument();
  });

  it("renders the fallback with the error message when a child throws", () => {
    renderBoundary(<Bomb explode={true} />);
    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/kaboom: malformed message/)).toBeInTheDocument();
  });

  it("clears the error and re-renders children when Try again is clicked", () => {
    let shouldThrow = true;
    function Flaky(): JSX.Element {
      if (shouldThrow) {
        throw new Error("transient");
      }
      return <p data-testid="recovered">recovered</p>;
    }
    renderBoundary(<Flaky />);
    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    // The underlying cause is fixed before the operator retries.
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.getByTestId("recovered")).toBeInTheDocument();
    expect(
      screen.queryByTestId("error-boundary-fallback"),
    ).not.toBeInTheDocument();
  });
});
