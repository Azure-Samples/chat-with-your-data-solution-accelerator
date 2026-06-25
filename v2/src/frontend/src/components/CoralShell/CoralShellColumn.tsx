/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — reference-architecture re-skin)
 *
 * Outer Coral shell column. Mirrors the reference architecture's
 * `commonComponents/components/Layout/CoralShellColumn`: a full-viewport
 * vertical flex stack that hosts `<Header>` at the top plus a single
 * `<CoralShellRow>` filling the remaining space. Provides the recessed
 * shell background (`--colorNeutralBackground3`) so child panels with
 * `--colorNeutralBackground1` read as raised cards.
 *
 * Pure layout primitive: no business logic, no theme knowledge (Fluent
 * tokens are inherited via `<FluentProvider>` on `<App>`). Custom
 * `className` is appended after the base class so callers can layer
 * extra styling without losing the shell defaults.
 */
import { type HTMLAttributes, type JSX, type ReactNode } from "react";
import styles from "./CoralShell.module.css";

export interface CoralShellColumnProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CoralShellColumn({
  children,
  className,
  ...rest
}: CoralShellColumnProps): JSX.Element {
  const composed =
    className === undefined || className === ""
      ? (styles.column ?? "")
      : `${styles.column ?? ""} ${className}`;
  return (
    <div className={composed} data-coral-shell="column" {...rest}>
      {children}
    </div>
  );
}
