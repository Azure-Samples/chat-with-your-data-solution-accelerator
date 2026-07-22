/**
 * Light/dark theme primitive for the v2 frontend. Owns:
 *   - the active theme (`"light" | "dark"`),
 *   - localStorage persistence (key `cwyd.theme`),
 *   - mirroring the value to `document.documentElement.dataset.theme`
 *     so `tokens.css` can switch CSS custom properties via the
 *     `[data-theme="dark"]` selector.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type JSX,
  type ReactNode,
} from "react";

export const Theme = {
  Light: "light",
  Dark: "dark",
} as const;
export type Theme = (typeof Theme)[keyof typeof Theme];

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (next: Theme) => void;
}

const STORAGE_KEY = "cwyd.theme";
const DEFAULT_THEME: Theme = Theme.Light;

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readInitialTheme(): Theme {
  if (typeof window === "undefined") {
    return DEFAULT_THEME;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === Theme.Light || stored === Theme.Dark) {
    return stored;
  }
  return DEFAULT_THEME;
}

export function ThemeProvider({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  const [theme, setThemeState] = useState<Theme>(() => readInitialTheme());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // localStorage unavailable (private mode, etc.) -- non-fatal.
    }
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) =>
      prev === Theme.Light ? Theme.Dark : Theme.Light,
    );
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, toggleTheme, setTheme }),
    [theme, toggleTheme, setTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    throw new Error("useTheme must be used inside a ThemeProvider");
  }
  return ctx;
}
