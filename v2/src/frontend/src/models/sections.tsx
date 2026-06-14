/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * App-shell `Section` enum — the closed set of primary pages the SPA
 * can render — plus the `SectionPath` URL map and `pathToSection`
 * reverse lookup binding each section to its browser route. `Section`
 * uses the `as const` + literal-union pattern; its members are the
 * wire strings behind the `data-testid="nav-<section>"` selectors and
 * the `aria-current` page markers in the navigation header.
 */

export const Section = Object.freeze({
  Chat: "chat",
  AdminIngest: "admin-ingest",
  AdminDelete: "admin-delete",
  AdminConfig: "admin-config",
} as const);
export type Section = (typeof Section)[keyof typeof Section];

/** Browser route each `Section` maps to (Chat is the SPA root). */
export const SectionPath: Record<Section, string> = {
  [Section.Chat]: "/",
  [Section.AdminIngest]: "/admin/ingest",
  [Section.AdminDelete]: "/admin/delete",
  [Section.AdminConfig]: "/admin/config",
};

/**
 * Reverse of `SectionPath`: resolve a router pathname to its
 * `Section`. Unknown or partial paths fall back to `Section.Chat`,
 * matching the SPA's catch-all redirect to the root route.
 */
export function pathToSection(pathname: string): Section {
  const entries = Object.entries(SectionPath) as [Section, string][];
  const match = entries.find(([, path]) => path === pathname);
  return match ? match[0] : Section.Chat;
}
