/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest assertions for the `Section` app-shell enum. Tests verify
 * member-to-string round-trip, full `Object.values` membership,
 * runtime equality with raw string literals, and the
 * back-compat `AppView` type alias so existing call sites
 * (Header / App / navigation tests) keep narrowing correctly.
 */
import { describe, expect, expectTypeOf, it } from "vitest";

import type { AppView } from "../../src/components/Header/Header";
import { Section } from "../../src/models/sections";

describe("Section", () => {
  it("exposes the 4 known members and maps each to its wire string", () => {
    expect(Section.Chat).toBe("chat");
    expect(Section.AdminIngest).toBe("admin-ingest");
    expect(Section.AdminDelete).toBe("admin-delete");
    expect(Section.AdminConfig).toBe("admin-config");
  });

  it("enumerates exactly the 4 known values via Object.values", () => {
    expect(Object.values(Section).sort()).toEqual(
      ["admin-config", "admin-delete", "admin-ingest", "chat"].sort(),
    );
  });

  it("round-trips with raw string literals", () => {
    const wire: Section = "chat";
    expect(wire === Section.Chat).toBe(true);
  });

  it("rejects frozen-map mutation at the type layer", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    Section.Chat = "different";
  });

  it("preserves the AppView back-compat alias", () => {
    expectTypeOf<AppView>().toEqualTypeOf<Section>();
    const view: AppView = Section.AdminIngest;
    expect(view).toBe("admin-ingest");
  });
});
