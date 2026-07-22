/**
 * Vitest assertions for the shared admin/page status enums. Each
 * enum is an `as const` map; the tests verify member-to-string
 * round-trip, full membership via `Object.values`, and runtime
 * equality with bare string literals (the TS counterpart to a
 * Python `StrEnum` so wire payloads + reducer dispatch continue
 * to interop without `as` casts).
 */
import { describe, expect, it } from "vitest";

import {
  LoadStatus,
  ReprocessStatus,
  RowDeleteStatus,
  SaveStatus,
  SubmitStatus,
  UploadStatus,
} from "@/models/status";

describe("LoadStatus", () => {
  it("exposes the 3 known members and maps each to its string value", () => {
    expect(LoadStatus.Loading).toBe("loading");
    expect(LoadStatus.Loaded).toBe("loaded");
    expect(LoadStatus.Failed).toBe("failed");
  });

  it("enumerates exactly the 3 known values via Object.values", () => {
    expect(Object.values(LoadStatus).sort()).toEqual(
      ["failed", "loaded", "loading"].sort(),
    );
  });

  it("round-trips with raw string literals", () => {
    const wire: LoadStatus = "loading";
    expect(wire === LoadStatus.Loading).toBe(true);
  });
});

describe("SaveStatus", () => {
  it("exposes the 4 known members and maps each to its string value", () => {
    expect(SaveStatus.Idle).toBe("idle");
    expect(SaveStatus.Saving).toBe("saving");
    expect(SaveStatus.Success).toBe("success");
    expect(SaveStatus.Failed).toBe("failed");
  });

  it("enumerates exactly the 4 known values via Object.values", () => {
    expect(Object.values(SaveStatus).sort()).toEqual(
      ["failed", "idle", "saving", "success"].sort(),
    );
  });
});

describe("UploadStatus", () => {
  it("exposes the 4 known members and maps each to its string value", () => {
    expect(UploadStatus.Pending).toBe("pending");
    expect(UploadStatus.Uploading).toBe("uploading");
    expect(UploadStatus.Success).toBe("success");
    expect(UploadStatus.Failed).toBe("failed");
  });

  it("enumerates exactly the 4 known values via Object.values", () => {
    expect(Object.values(UploadStatus).sort()).toEqual(
      ["failed", "pending", "success", "uploading"].sort(),
    );
  });
});

describe("SubmitStatus", () => {
  it("exposes the 4 known members and maps each to its string value", () => {
    expect(SubmitStatus.Pending).toBe("pending");
    expect(SubmitStatus.Submitting).toBe("submitting");
    expect(SubmitStatus.Success).toBe("success");
    expect(SubmitStatus.Failed).toBe("failed");
  });

  it("enumerates exactly the 4 known values via Object.values", () => {
    expect(Object.values(SubmitStatus).sort()).toEqual(
      ["failed", "pending", "submitting", "success"].sort(),
    );
  });
});

describe("ReprocessStatus", () => {
  it("exposes the 5 known members and maps each to its string value", () => {
    expect(ReprocessStatus.Idle).toBe("idle");
    expect(ReprocessStatus.Confirming).toBe("confirming");
    expect(ReprocessStatus.Running).toBe("running");
    expect(ReprocessStatus.Success).toBe("success");
    expect(ReprocessStatus.Failed).toBe("failed");
  });

  it("enumerates exactly the 5 known values via Object.values", () => {
    expect(Object.values(ReprocessStatus).sort()).toEqual(
      ["confirming", "failed", "idle", "running", "success"].sort(),
    );
  });
});

describe("RowDeleteStatus", () => {
  it("exposes the 3 known members and maps each to its string value", () => {
    expect(RowDeleteStatus.Idle).toBe("idle");
    expect(RowDeleteStatus.Deleting).toBe("deleting");
    expect(RowDeleteStatus.Failed).toBe("failed");
  });

  it("enumerates exactly the 3 known values via Object.values", () => {
    expect(Object.values(RowDeleteStatus).sort()).toEqual(
      ["deleting", "failed", "idle"].sort(),
    );
  });
});

describe("Cross-enum invariants", () => {
  it("frozen `as const` maps reject mutation at the type layer", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    LoadStatus.Loading = "different";
  });

  it("widens to the literal-union type without `as` casts", () => {
    const accept = (status: LoadStatus): LoadStatus => status;
    expect(accept(LoadStatus.Loaded)).toBe("loaded");
    expect(accept("failed")).toBe("failed");
  });
});
