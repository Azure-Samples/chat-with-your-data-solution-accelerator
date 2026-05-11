/**
 * Pillar: Stable Core
 * Phase: 4 (frontend polish — MACAE re-skin)
 *
 * Backwards-compatible alias for the old `<AppHeader>` symbol. The
 * actual implementation now lives in `components/Header/Header.tsx`
 * (Coral / MACAE-faithful). This module re-exports it under the legacy
 * name so callers (App.tsx, future imports) don't need to change in
 * lock-step with the rename. Slated for inline removal in U8 cleanup.
 */
export { Header as AppHeader } from "../Header/Header";
export type { HeaderProps as AppHeaderProps } from "../Header/Header";
