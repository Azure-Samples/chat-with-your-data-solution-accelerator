/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Coral Header. Mirrors MACAE's
 * `commonComponents/components/Header/Header.tsx`:
 *   - Left brand: <Avatar shape="square" color="neutral"> wrapping
 *     <MsftColorLogo/> + a "<title> | <subtitle>" label row.
 *   - Right tools: <HeaderTools> — Fluent <Toolbar> with new-chat, a
 *     gated admin entry, history toggle, theme toggle. The admin pages
 *     are reached solely through that gated admin entry, so a non-admin
 *     session never sees a dead-end link.
 *
 * The accessible name "app-header" testid is preserved verbatim.
 */
import { Avatar } from "@fluentui/react-components";
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
  adminAvailable?: boolean | null;
  onOpenAdmin?: () => void;
}

const DEFAULT_SUBTITLE = "Solution Accelerator";

export function Header({
  title,
  subtitle = DEFAULT_SUBTITLE,
  historyOpen,
  onToggleHistory,
  onNewChat,
  adminAvailable,
  onOpenAdmin,
}: HeaderProps): JSX.Element {
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
      <HeaderTools
        historyOpen={historyOpen}
        onToggleHistory={onToggleHistory}
        onNewChat={onNewChat}
        adminAvailable={adminAvailable ?? null}
        {...(onOpenAdmin !== undefined ? { onOpenAdmin } : {})}
      />
    </header>
  );
}
