/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * App-shell `Section` enum — the closed set of primary pages the
 * SPA can render. Follows the `as const` + literal-union pattern
 * documented in [.github/instructions/v2-frontend.instructions.md]
 * (Enums section). Members are the wire strings used by the
 * page registry (`services/app/pageRegistry.tsx` — landing in a
 * later unit) and by the `data-testid="nav-<section>"` selectors
 * already pinned by [tests/AppNavigation.test.tsx]; rename a
 * value here only with a coordinated test update.
 */

export const Section = {
  Chat: "chat",
  AdminIngest: "admin-ingest",
  AdminDelete: "admin-delete",
  AdminConfig: "admin-config",
} as const;
export type Section = (typeof Section)[keyof typeof Section];
