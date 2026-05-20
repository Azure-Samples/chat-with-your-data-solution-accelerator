/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Adapter that bridges our app-owned `<ThemeProvider>` (which persists
 * the active theme to `localStorage["cwyd.theme"]` and mirrors it to
 * `data-theme` on `<html>`) into Fluent UI v9's `<FluentProvider>`.
 *
 * Mounted as a child of `<ThemeProvider>` so it can read the active
 * theme via `useTheme()` and feed Fluent the matching theme object
 * (`teamsLightTheme` / `teamsDarkTheme`, mirroring MACAE).
 *
 * Keeping `themeContext` as the source of truth (not Fluent's own
 * scheme detection) means our toggle button + persistence keep
 * working unchanged; Fluent components just inherit the matching
 * design tokens.
 */
import {
  FluentProvider,
  teamsDarkTheme,
  teamsLightTheme,
} from "@fluentui/react-components";
import { type JSX, type ReactNode } from "react";
import { useTheme } from "./themeContext";

export function FluentThemeBridge({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  const { theme } = useTheme();
  return (
    <FluentProvider
      theme={theme === "dark" ? teamsDarkTheme : teamsLightTheme}
    >
      {children}
    </FluentProvider>
  );
}
