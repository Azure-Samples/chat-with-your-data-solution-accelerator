/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — reference-architecture re-skin)
 *
 * Inner Coral shell row. Mirrors the reference architecture's
 * `commonComponents/components/Layout/CoralShellRow`: a horizontal flex
 * container that fills the remaining vertical space inside a
 * `<CoralShellColumn>` and hosts the PanelLeft + content (+ optional
 * PanelRight) sections side-by-side.
 *
 * Pure layout primitive: no business logic. `min-height: 0` (set in the
 * CSS module) is the standard flexbox escape hatch so a scrollable
 * descendant like `<MessageList>` actually scrolls instead of growing
 * the row.
 */
import { type HTMLAttributes, type JSX, type ReactNode } from "react";
import styles from "./CoralShell.module.css";

export interface CoralShellRowProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CoralShellRow({
  children,
  className,
  ...rest
}: CoralShellRowProps): JSX.Element {
  const composed =
    className === undefined || className === ""
      ? (styles.row ?? "")
      : `${styles.row ?? ""} ${className}`;
  return (
    <div className={composed} data-coral-shell="row" {...rest}>
      {children}
    </div>
  );
}
