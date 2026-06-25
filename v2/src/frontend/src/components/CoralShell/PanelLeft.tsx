/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — reference-architecture re-skin)
 *
 * Left navigation panel primitive. Mirrors the reference architecture's
 * `commonComponents/components/Layout/PanelLeft`: a vertical column
 * docked on the left edge of the `<CoralShellRow>`, raised above the
 * recessed shell background by `--colorNeutralBackground1` plus a
 * `--colorNeutralStroke2` right-edge separator.
 *
 * Pure layout primitive: no business logic. The grid cell in
 * `<ChatPage>` controls width + visibility (the panel is collapsed by
 * setting the grid column to 0px), so this component itself just fills
 * 100% of its cell. Renders an `<aside>` so it counts as a
 * `complementary` landmark for assistive tech.
 */
import { type HTMLAttributes, type JSX, type ReactNode } from "react";
import styles from "./CoralShell.module.css";

export interface PanelLeftProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

export function PanelLeft({
  children,
  className,
  ...rest
}: PanelLeftProps): JSX.Element {
  const composed =
    className === undefined || className === ""
      ? (styles.panelLeft ?? "")
      : `${styles.panelLeft ?? ""} ${className}`;
  return (
    <aside className={composed} data-coral-panel="left" {...rest}>
      {children}
    </aside>
  );
}
