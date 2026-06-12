/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Focused enum-contract tests for the Configuration page reducer
 * action discriminator map.
 */
import { describe, expect, expectTypeOf, it } from "vitest";

import { ConfigActionType } from "@/pages/admin/Configuration/Configuration";

describe("ConfigActionType", () => {
  it("maps every member to its canonical wire string", () => {
    expect(ConfigActionType.LoadStarted).toBe("load_started");
    expect(ConfigActionType.LoadSucceeded).toBe("load_succeeded");
    expect(ConfigActionType.LoadFailed).toBe("load_failed");
    expect(ConfigActionType.FieldChanged).toBe("field_changed");
    expect(ConfigActionType.Discard).toBe("discard");
    expect(ConfigActionType.SaveStarted).toBe("save_started");
    expect(ConfigActionType.SaveSucceeded).toBe("save_succeeded");
    expect(ConfigActionType.SaveFailed).toBe("save_failed");
    expect(ConfigActionType.ResetRequested).toBe("reset_requested");
    expect(ConfigActionType.ResetCancelled).toBe("reset_cancelled");
  });

  it("enumerates exactly the 10 known values via Object.values", () => {
    expect([...Object.values(ConfigActionType)].sort()).toEqual(
      [
        "discard",
        "field_changed",
        "load_failed",
        "load_started",
        "load_succeeded",
        "reset_cancelled",
        "reset_requested",
        "save_failed",
        "save_started",
        "save_succeeded",
      ].sort(),
    );
  });

  it("round-trips with raw wire strings", () => {
    const wire: ConfigActionType = "load_started";
    expect(wire === ConfigActionType.LoadStarted).toBe(true);
  });

  it("rejects frozen-map mutation at the type layer", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    ConfigActionType.LoadStarted = "different";
  });

  it("produces a literal-union type covering every wire string", () => {
    expectTypeOf<ConfigActionType>().toEqualTypeOf<
      | "load_started"
      | "load_succeeded"
      | "load_failed"
      | "field_changed"
      | "discard"
      | "save_started"
      | "save_succeeded"
      | "save_failed"
      | "reset_requested"
      | "reset_cancelled"
    >();
  });
});
