/**
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

describe("FluentThemeBridge -- DOM mounting", () => {
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
    const { ThemeProvider } = await import("@/theme/themeContext");
    const { FluentThemeBridge } = await import(
      "@/theme/FluentThemeBridge"
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

  it("tags the FluentProvider wrapper with the appFluentRoot height-chain class", async () => {
    const { ThemeProvider } = await import("@/theme/themeContext");
    const { FluentThemeBridge } = await import(
      "@/theme/FluentThemeBridge"
    );

    render(
      <ThemeProvider>
        <FluentThemeBridge>
          <span data-testid="fluent-child">child</span>
        </FluentThemeBridge>
      </ThemeProvider>,
    );

    // Walk up from the child to Fluent's wrapper div and assert it
    // carries the `appFluentRoot` class. tokens.css uses that class to
    // continue the height:100% chain through Fluent's wrapper; without
    // it the shell falls back to 100vh and the page double-scrolls.
    let node: HTMLElement | null = screen.getByTestId("fluent-child");
    let providerClass = "";
    while (node !== null) {
      const cls = node.getAttribute("class") ?? "";
      if (/\bfui-FluentProvider/.test(cls)) {
        providerClass = cls;
        break;
      }
      node = node.parentElement;
    }
    expect(providerClass).toMatch(/\bappFluentRoot\b/);
  });
});

describe("FluentThemeBridge -- theme flip", () => {
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
        Toaster: () => <div data-testid="mocked-toaster" />,
        teamsLightTheme: { __id: "teamsLightTheme" },
        teamsDarkTheme: { __id: "teamsDarkTheme" },
      };
    });

    const { Theme, ThemeProvider, useTheme } = await import(
      "@/theme/themeContext"
    );
    const { FluentThemeBridge } = await import(
      "@/theme/FluentThemeBridge"
    );

    function FlipProbe(): React.JSX.Element {
      const { setTheme } = useTheme();
      return (
        <button
          type="button"
          data-testid="flip-to-dark"
          onClick={() => setTheme(Theme.Dark)}
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

    // Initial light render -- last theme prop captured should be the
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

describe("FluentThemeBridge -- Toaster mount", () => {
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

  it("mounts a Fluent v9 Toaster with the exported TOASTER_ID inside the provider", async () => {
    const toasterProps: Array<{ toasterId?: unknown }> = [];

    vi.doMock("@fluentui/react-components", () => {
      type ProviderProps = {
        children?: React.ReactNode;
        theme?: unknown;
      };
      type ToasterProps = {
        toasterId?: unknown;
      };
      return {
        FluentProvider: ({ children }: ProviderProps) => (
          <div data-testid="mocked-fluent-provider">{children}</div>
        ),
        Toaster: (props: ToasterProps) => {
          toasterProps.push(props);
          return <div data-testid="mocked-toaster" />;
        },
        teamsLightTheme: { __id: "teamsLightTheme" },
        teamsDarkTheme: { __id: "teamsDarkTheme" },
      };
    });

    const { ThemeProvider } = await import("@/theme/themeContext");
    const { FluentThemeBridge, TOASTER_ID } = await import(
      "@/theme/FluentThemeBridge"
    );

    render(
      <ThemeProvider>
        <FluentThemeBridge>
          <span data-testid="toaster-child">child</span>
        </FluentThemeBridge>
      </ThemeProvider>,
    );

    // Constant has its expected literal value so consumers can import
    // it without spelunking through Fluent's internals.
    expect(TOASTER_ID).toBe("cwyd-toaster");

    // Toaster was rendered with the canonical id…
    const toaster = screen.getByTestId("mocked-toaster");
    expect(toaster).toBeInTheDocument();
    const latest = toasterProps.at(-1);
    expect(latest?.toasterId).toBe(TOASTER_ID);

    // …and it lives inside the provider tree (sibling of children),
    // not as a detached portal outside it.
    const provider = screen.getByTestId("mocked-fluent-provider");
    expect(provider.contains(toaster)).toBe(true);
    expect(provider.contains(screen.getByTestId("toaster-child"))).toBe(true);
  });
});
