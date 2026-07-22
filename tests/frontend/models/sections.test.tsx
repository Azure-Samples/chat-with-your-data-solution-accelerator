/**
 * Vitest assertions for the `Section` app-shell enum. Tests verify
 * member-to-string round-trip, full `Object.values` membership,
 * runtime equality with raw string literals, and the
 * back-compat `AppView` type alias so existing call sites
 * (Header / App / navigation tests) keep narrowing correctly.
 */
import { describe, expect, expectTypeOf, it } from "vitest";

import type { AppView } from "@/components/Header/Header";
import { Section, SectionPath, pathToSection } from "@/models/sections";

describe("Section", () => {
  it("exposes the 4 known members and maps each to its wire string", () => {
    expect(Section.Chat).toBe("chat");
    expect(Section.AdminIngest).toBe("admin-ingest");
    expect(Section.AdminDelete).toBe("admin-delete");
    expect(Section.AdminConfig).toBe("admin-config");
  });

  it("enumerates exactly the 4 known values via Object.values", () => {
    expect(Object.values(Section).sort()).toEqual(
      [
        "admin-config",
        "admin-delete",
        "admin-ingest",
        "chat",
      ].sort(),
    );
  });

  it("round-trips with raw string literals", () => {
    const wire: Section = "chat";
    expect(wire === Section.Chat).toBe(true);
  });

  it("rejects map mutation at the type layer and at runtime", () => {
    expect(() => {
      // @ts-expect-error -- `as const` maps must be readonly at compile time.
      Section.Chat = "different";
    }).toThrow(TypeError);
  });

  it("preserves the AppView back-compat alias", () => {
    expectTypeOf<AppView>().toEqualTypeOf<Section>();
    const view: AppView = Section.AdminIngest;
    expect(view).toBe("admin-ingest");
  });
});

describe("SectionPath", () => {
  it("maps every Section member to its browser route", () => {
    expect(SectionPath[Section.Chat]).toBe("/");
    expect(SectionPath[Section.AdminIngest]).toBe("/admin/ingest");
    expect(SectionPath[Section.AdminDelete]).toBe("/admin/delete");
    expect(SectionPath[Section.AdminConfig]).toBe("/admin/config");
  });

  it("covers exactly the 4 Section members", () => {
    expect(Object.keys(SectionPath).sort()).toEqual(
      Object.values(Section).sort(),
    );
  });
});

describe("pathToSection", () => {
  it("maps each known route back to its Section", () => {
    expect(pathToSection("/")).toBe(Section.Chat);
    expect(pathToSection("/admin/ingest")).toBe(Section.AdminIngest);
    expect(pathToSection("/admin/delete")).toBe(Section.AdminDelete);
    expect(pathToSection("/admin/config")).toBe(Section.AdminConfig);
  });

  it("defaults unknown or partial paths to Chat", () => {
    expect(pathToSection("/nope")).toBe(Section.Chat);
    expect(pathToSection("/admin")).toBe(Section.Chat);
    expect(pathToSection("/admin/ingest/extra")).toBe(Section.Chat);
  });

  it("round-trips every Section through its route", () => {
    for (const section of Object.values(Section)) {
      expect(pathToSection(SectionPath[section])).toBe(section);
    }
  });
});
