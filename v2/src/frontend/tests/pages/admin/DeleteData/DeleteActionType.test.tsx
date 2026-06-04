/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Focused enum-contract tests for the DeleteData page reducer action
 * discriminator map.
 */
import { describe, expect, expectTypeOf, it } from "vitest";

import { DeleteActionType } from "@/pages/admin/DeleteData/DeleteData";

describe("DeleteActionType", () => {
  it("maps every member to its canonical wire string", () => {
    expect(DeleteActionType.ListStarted).toBe("list_started");
    expect(DeleteActionType.ListSucceeded).toBe("list_succeeded");
    expect(DeleteActionType.ListFailed).toBe("list_failed");
    expect(DeleteActionType.ToggleSelected).toBe("toggle_selected");
    expect(DeleteActionType.SelectAll).toBe("select_all");
    expect(DeleteActionType.ConfirmOpen).toBe("confirm_open");
    expect(DeleteActionType.ConfirmClose).toBe("confirm_close");
    expect(DeleteActionType.DeleteStarted).toBe("delete_started");
    expect(DeleteActionType.DeleteSucceeded).toBe("delete_succeeded");
    expect(DeleteActionType.DeleteFailed).toBe("delete_failed");
  });

  it("enumerates exactly the 10 known values via Object.values", () => {
    expect([...Object.values(DeleteActionType)].sort()).toEqual(
      [
        "confirm_close",
        "confirm_open",
        "delete_failed",
        "delete_started",
        "delete_succeeded",
        "list_failed",
        "list_started",
        "list_succeeded",
        "select_all",
        "toggle_selected",
      ].sort(),
    );
  });

  it("round-trips with raw wire strings", () => {
    const wire: DeleteActionType = "list_started";
    expect(wire === DeleteActionType.ListStarted).toBe(true);
  });

  it("rejects frozen-map mutation at the type layer", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    DeleteActionType.ListStarted = "different";
  });

  it("produces a literal-union type covering every wire string", () => {
    expectTypeOf<DeleteActionType>().toEqualTypeOf<
      | "list_started"
      | "list_succeeded"
      | "list_failed"
      | "toggle_selected"
      | "select_all"
      | "confirm_open"
      | "confirm_close"
      | "delete_started"
      | "delete_succeeded"
      | "delete_failed"
    >();
  });
});
