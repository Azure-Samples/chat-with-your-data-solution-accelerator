/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Tests for FluentThemeBridge: verifies it (1) actually mounts a
 * Fluent v9 `<FluentProvider>` around its children (which carries a
 * `fui-FluentProvider*` className from Fluent's griffel runtime) and
 * (2) flips the `theme` prop from `teamsLightTheme` → `teamsDarkTheme`
 * when our own `<ThemeProvider>` toggles light → dark.
 *
 * The second test mocks `@fluentui/react-components` so we can assert
 * on the actual prop passed in (rather than chasing griffel-generated
 * styles inside jsdom, which is flaky and a Fluent-internal detail).
 */
import { act, render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

describe("FluentThemeBridge — DOM mounting", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    vi.resetModules();
    vi.unmock("@fluentui/react-components");
  });

  it("wraps children in a Fluent v9 FluentProvider DOM node", async () => {
    const { ThemeProvider } = await import("../../src/theme/themeContext");
    const { FluentThemeBridge } = await import(
      "../../src/theme/FluentThemeBridge"
    );

    render(
      <ThemeProvider>
        <FluentThemeBridge>
          <span data-testid="fluent-child">child</span>
        </FluentThemeBridge>
      </ThemeProvider>,
    );

    const child = screen.getByTestId("fluent-child");
    expect(child).toBeInTheDocument();

    // Fluent v9 emits a class name beginning with `fui-FluentProvider`
    // on the wrapper it renders around its children. If the bridge
    // really mounted FluentProvider, that wrapper exists in the
    // ancestor chain.
    let node: HTMLElement | null = child;
    let foundFluentProvider = false;
    while (node !== null) {
      const cls = node.getAttribute("class") ?? "";
      if (/\bfui-FluentProvider/.test(cls)) {
        foundFluentProvider = true;
        break;
      }
      node = node.parentElement;
    }
    expect(foundFluentProvider).toBe(true);
  });
});

describe("FluentThemeBridge — theme flip", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    vi.resetModules();
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    vi.resetModules();
    vi.unmock("@fluentui/react-components");
  });

  it("flips the FluentProvider `theme` prop when ThemeProvider switches light → dark", async () => {
    const themeProps: Array<unknown> = [];

    vi.doMock("@fluentui/react-components", () => {
      type ProviderProps = {
        children?: React.ReactNode;
        theme?: unknown;
      };
      return {
        FluentProvider: ({ children, theme }: ProviderProps) => {
          themeProps.push(theme);
          return <div data-testid="mocked-fluent-provider">{children}</div>;
        },
        teamsLightTheme: { __id: "teamsLightTheme" },
        teamsDarkTheme: { __id: "teamsDarkTheme" },
      };
    });

    const { ThemeProvider, useTheme } = await import(
      "../../src/theme/themeContext"
    );
    const { FluentThemeBridge } = await import(
      "../../src/theme/FluentThemeBridge"
    );

    function FlipProbe(): React.JSX.Element {
      const { setTheme } = useTheme();
      return (
        <button
          type="button"
          data-testid="flip-to-dark"
          onClick={() => setTheme("dark")}
        >
          flip
        </button>
      );
    }

    render(
      <ThemeProvider>
        <FluentThemeBridge>
          <FlipProbe />
        </FluentThemeBridge>
      </ThemeProvider>,
    );

    // Initial light render — last theme prop captured should be the
    // light-theme sentinel from our mock.
    const initialTheme = themeProps.at(-1) as { __id?: string } | undefined;
    expect(initialTheme?.__id).toBe("teamsLightTheme");

    act(() => {
      screen.getByTestId("flip-to-dark").click();
    });

    const flippedTheme = themeProps.at(-1) as { __id?: string } | undefined;
    expect(flippedTheme?.__id).toBe("teamsDarkTheme");
  });
});
