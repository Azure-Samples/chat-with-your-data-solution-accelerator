/**
 * Enum-contract tests for the frontend theme discriminator.
 */
import { describe, expect, expectTypeOf, it } from "vitest";

import { Theme } from "@/theme/themeContext";

describe("Theme", () => {
  it("maps every member to its canonical wire string", () => {
    expect(Theme.Light).toBe("light");
    expect(Theme.Dark).toBe("dark");
  });

  it("enumerates exactly the 2 known values via Object.values", () => {
    expect([...Object.values(Theme)].sort()).toEqual([
      "dark",
      "light",
    ]);
  });

  it("round-trips with raw wire strings", () => {
    const wire: Theme = "light";
    expect(wire === Theme.Light).toBe(true);
  });

  it("rejects frozen-map mutation at the type layer", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    Theme.Light = "different";
  });

  it("produces a literal-union type covering every wire string", () => {
    expectTypeOf<Theme>().toEqualTypeOf<"light" | "dark">();
  });
});
