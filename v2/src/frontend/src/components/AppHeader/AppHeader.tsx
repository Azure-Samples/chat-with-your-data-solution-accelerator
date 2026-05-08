/**
 * Pillar: Stable Core
 * Phase: 6 (frontend polish, pulled forward for boss demo)
 *
 * App header: brand row (Azure logo + title) on the left, new-chat +
 * history + theme buttons on the right. Stateless w.r.t. history and
 * the chat transcript (parent owns both); owns its theme via the
 * ThemeProvider context.
 */
import type { JSX } from "react";
import { Plus } from "../icons";
import { useTheme } from "../../theme/themeContext";
import azureLogo from "../../assets/Azure.svg";
import styles from "./AppHeader.module.css";

export interface AppHeaderProps {
  title: string;
  historyOpen: boolean;
  onToggleHistory: () => void;
  onNewChat: () => void;
}

function SunIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
    </svg>
  );
}

function HistoryIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

export function AppHeader({
  title,
  historyOpen,
  onToggleHistory,
  onNewChat,
}: AppHeaderProps): JSX.Element {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "light" ? "dark" : "light";

  return (
    <header className={styles.header} data-testid="app-header">
      <div className={styles.brand}>
        <img src={azureLogo} alt="Azure" className={styles.logo} />
        <h1 className={styles.title}>{title}</h1>
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.iconButton}
          onClick={onNewChat}
          aria-label="New chat"
          title="New chat"
          data-testid="header-new-chat"
        >
          <Plus size={18} strokeWidth={2} aria-hidden="true" />
        </button>
        <button
          type="button"
          className={styles.iconButton}
          onClick={onToggleHistory}
          aria-pressed={historyOpen}
          aria-label="History"
          title="History"
        >
          <HistoryIcon />
        </button>
        <button
          type="button"
          className={styles.iconButton}
          onClick={toggleTheme}
          aria-label={`Switch to ${nextTheme} mode`}
          title={`Switch to ${nextTheme} mode`}
        >
          {theme === "light" ? <MoonIcon /> : <SunIcon />}
        </button>
      </div>
    </header>
  );
}
