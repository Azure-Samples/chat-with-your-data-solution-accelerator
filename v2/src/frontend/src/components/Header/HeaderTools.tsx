/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Header toolbar slot for the right side of <Header>. Owns the icon
 * buttons that wrap into the header chrome:
 *   - new chat        (delegates to onNewChat)
 *   - history toggle  (delegates to onToggleHistory; aria-pressed
 *                      mirrors historyOpen)
 *   - theme toggle    (delegates to ThemeProvider via useTheme())
 *
 * Uses Fluent v9 <Toolbar> + <ToolbarButton> + <ToolbarToggleButton>
 * (mirrors MACAE's HeaderTools): the toggle button natively manages
 * `aria-pressed`, replacing our hand-rolled attribute on the previous
 * <button> implementation.
 *
 * The accessible names ("New chat", "History", "Switch to dark mode" /
 * "Switch to light mode") are preserved verbatim from the old
 * <AppHeader> so existing tests + screen-reader expectations don't
 * regress.
 */
import {
  Toolbar,
  ToolbarButton,
  ToolbarToggleButton,
} from "@fluentui/react-components";
import {
  Add20Regular,
  History20Regular,
  WeatherMoon20Regular,
  WeatherSunny20Regular,
} from "@fluentui/react-icons";
import { type JSX } from "react";
import { useTheme } from "../../theme/themeContext";
import styles from "./Header.module.css";

export interface HeaderToolsProps {
  historyOpen: boolean;
  onToggleHistory: () => void;
  onNewChat: () => void;
}

export function HeaderTools({
  historyOpen,
  onToggleHistory,
  onNewChat,
}: HeaderToolsProps): JSX.Element {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "light" ? "dark" : "light";
  const themeIcon =
    theme === "light" ? <WeatherMoon20Regular /> : <WeatherSunny20Regular />;

  return (
    <Toolbar
      aria-label="Header actions"
      size="small"
      className={styles.tools}
      // Fluent v9 <Toolbar> owns toggle-button checked state via its
      // `checkedValues` map (keyed by `name`); individual
      // <ToolbarToggleButton> instances do not accept a `checked` prop.
      checkedValues={{ "header-actions": historyOpen ? ["history"] : [] }}
    >
      <ToolbarButton
        appearance="subtle"
        aria-label="New chat"
        title="New chat"
        data-testid="header-new-chat"
        icon={<Add20Regular />}
        onClick={onNewChat}
      />
      <ToolbarToggleButton
        appearance="subtle"
        aria-label="History"
        title="History"
        // Toolbar's toggle group uses `name` + `value` to dedupe state;
        // a unique pair is required so this button can be controlled.
        name="header-actions"
        value="history"
        icon={<History20Regular />}
        onClick={onToggleHistory}
      />
      <ToolbarButton
        appearance="subtle"
        aria-label={`Switch to ${nextTheme} mode`}
        title={`Switch to ${nextTheme} mode`}
        icon={themeIcon}
        onClick={toggleTheme}
      />
    </Toolbar>
  );
}
