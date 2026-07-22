/**
 * Coral Header. Mirrors the reference architecture's
 * `commonComponents/components/Header/Header.tsx`:
 *   - Left brand: a clickable <Avatar shape="square" color="neutral">
 *     wrapping the multi-agent brand mark that navigates back to the
 *     home / chat view, followed by a "<title> | <subtitle>" label row.
 *   - Right tools: <HeaderTools> -- Fluent <Toolbar> with new-chat, a
 *     gated admin entry, history toggle, theme toggle. The admin pages
 *     are reached solely through that gated admin entry, so a non-admin
 *     session never sees a dead-end link.
 *
 * The accessible name "app-header" testid is preserved verbatim.
 */
import { Avatar } from "@fluentui/react-components";
import { type JSX } from "react";
import type { UserInfo } from "@/models/auth";
import type { Section } from "@/models/sections";
import { HeaderTools } from "./HeaderTools";
import { MultiAgentLogo } from "./MultiAgentLogo";
import styles from "./Header.module.css";

export type AppView = Section;

export interface HeaderProps {
  title: string;
  subtitle?: string;
  historyOpen: boolean;
  onToggleHistory: () => void;
  onNewChat: () => void;
  onNavigateHome?: () => void;
  adminAvailable?: boolean | null;
  onOpenAdmin?: () => void;
  userInfo?: UserInfo | null;
}

const DEFAULT_SUBTITLE = "Solution Accelerator";

export function Header({
  title,
  subtitle = DEFAULT_SUBTITLE,
  historyOpen,
  onToggleHistory,
  onNewChat,
  onNavigateHome,
  adminAvailable,
  onOpenAdmin,
  userInfo,
}: HeaderProps): JSX.Element {
  return (
    <header className={styles.header} data-testid="app-header">
      <div className={styles.brand}>
        <button
          type="button"
          className={styles.brandButton}
          onClick={onNavigateHome}
          aria-label="Go to home"
          title="Home"
          data-testid="header-home"
        >
          <Avatar
            shape="square"
            color="neutral"
            icon={<MultiAgentLogo size={20} />}
            size={28}
          />
        </button>
        <div className={styles.titleStack}>
          <h1 className={styles.title}>{title}</h1>
          {subtitle !== "" && (
            <>
              <span aria-hidden="true" className={styles.divider}>
                |
              </span>
              <span className={styles.subtitle}>{subtitle}</span>
            </>
          )}
        </div>
      </div>
      <HeaderTools
        historyOpen={historyOpen}
        onToggleHistory={onToggleHistory}
        onNewChat={onNewChat}
        adminAvailable={adminAvailable ?? null}
        userInfo={userInfo ?? null}
        {...(onOpenAdmin !== undefined ? { onOpenAdmin } : {})}
      />
    </header>
  );
}
