/**
 * Adapter that bridges our app-owned `<ThemeProvider>` (which persists
 * the active theme to `localStorage["cwyd.theme"]` and mirrors it to
 * `data-theme` on `<html>`) into Fluent UI v9's `<FluentProvider>`.
 *
 * Mounted as a child of `<ThemeProvider>` so it can read the active
 * theme via `useTheme()` and feed Fluent the matching theme object
 * (`teamsLightTheme` / `teamsDarkTheme`).
 *
 * Keeping `themeContext` as the source of truth (not Fluent's own
 * scheme detection) means our toggle button + persistence keep
 * working unchanged; Fluent components just inherit the matching
 * design tokens.
 *
 * Also owns the app-wide `<Toaster>` mount keyed by the exported
 * `TOASTER_ID`. The toaster lives inside `<FluentProvider>` so toast
 * surfaces inherit the active design tokens; any component below the
 * bridge can call `useToastController(TOASTER_ID)` to dispatch.
 */
import {
  FluentProvider,
  Toaster,
  teamsDarkTheme,
  teamsLightTheme,
} from "@fluentui/react-components";
import { type JSX, type ReactNode } from "react";
import { Theme, useTheme } from "./themeContext";

export const TOASTER_ID = "cwyd-toaster";

export function FluentThemeBridge({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  const { theme } = useTheme();
  return (
    <FluentProvider
      className="appFluentRoot"
      theme={theme === Theme.Dark ? teamsDarkTheme : teamsLightTheme}
    >
      {children}
      <Toaster toasterId={TOASTER_ID} />
    </FluentProvider>
  );
}
