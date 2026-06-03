/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Coral Header. Mirrors MACAE's
 * `commonComponents/components/Header/Header.tsx`:
 *   - Left brand: <Avatar shape="square" color="neutral"> wrapping
 *     <MsftColorLogo/> + a "<title> | <subtitle>" label row.
 *   - Middle nav (optional): <nav> with one button per primary view
 *     (Chat, Admin). The Admin button only renders when the caller
 *     reports `adminAvailable === true` so non-admin sessions never
 *     see a dead-end link.
 *   - Right tools: <HeaderTools> — Fluent <Toolbar> with new-chat,
 *     history toggle, theme toggle.
 *
 * The accessible name "app-header" testid is preserved verbatim.
 */
import { Avatar, Button } from "@fluentui/react-components";
import { type JSX } from "react";
import type { Section } from "@/models/sections";
import { HeaderTools } from "./HeaderTools";
import { MsftColorLogo } from "./MsftColorLogo";
import styles from "./Header.module.css";

export type AppView = Section;

export interface HeaderProps {
  title: string;
  subtitle?: string;
  historyOpen: boolean;
  onToggleHistory: () => void;
  onNewChat: () => void;
  view?: AppView;
  onSelectView?: (view: AppView) => void;
  adminAvailable?: boolean | null;
}

const DEFAULT_SUBTITLE = "Solution Accelerator";

function adminStatusAttr(adminAvailable: boolean | null | undefined): string {
  if (adminAvailable === true) return "available";
  if (adminAvailable === false) return "forbidden";
  return "loading";
}

export function Header({
  title,
  subtitle = DEFAULT_SUBTITLE,
  historyOpen,
  onToggleHistory,
  onNewChat,
  view,
  onSelectView,
  adminAvailable,
}: HeaderProps): JSX.Element {
  const showNav = view !== undefined && onSelectView !== undefined;
  return (
    <header className={styles.header} data-testid="app-header">
      <div className={styles.brand}>
        <Avatar
          shape="square"
          color="neutral"
          name="Microsoft"
          icon={<MsftColorLogo size={20} />}
          size={28}
        />
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
      {showNav && (
        <nav
          aria-label="Primary"
          className={styles.nav}
          data-testid="primary-nav"
          data-admin-status={adminStatusAttr(adminAvailable)}
        >
          <Button
            appearance={view === "chat" ? "primary" : "subtle"}
            aria-current={view === "chat" ? "page" : undefined}
            data-testid="nav-chat"
            onClick={() => {
              onSelectView("chat");
            }}
          >
            Chat
          </Button>
          {adminAvailable === true && (
            <>
              <Button
                appearance={view === "admin-ingest" ? "primary" : "subtle"}
                aria-current={view === "admin-ingest" ? "page" : undefined}
                data-testid="nav-admin-ingest"
                onClick={() => {
                  onSelectView("admin-ingest");
                }}
              >
                Ingest data
              </Button>
              <Button
                appearance={view === "admin-delete" ? "primary" : "subtle"}
                aria-current={view === "admin-delete" ? "page" : undefined}
                data-testid="nav-admin-delete"
                onClick={() => {
                  onSelectView("admin-delete");
                }}
              >
                Delete data
              </Button>
              <Button
                appearance={view === "admin-config" ? "primary" : "subtle"}
                aria-current={view === "admin-config" ? "page" : undefined}
                data-testid="nav-admin-config"
                onClick={() => {
                  onSelectView("admin-config");
                }}
              >
                Configuration
              </Button>
            </>
          )}
        </nav>
      )}
      <HeaderTools
        historyOpen={historyOpen}
        onToggleHistory={onToggleHistory}
        onNewChat={onNewChat}
      />
    </header>
  );
}
