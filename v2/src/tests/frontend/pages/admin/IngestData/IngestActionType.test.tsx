/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest assertions for the `IngestActionType` enum that
 * discriminates the IngestData page reducer's action union. Tests
 * verify member-to-string round-trip, full `Object.values`
 * membership, runtime equality with raw wire strings, the
 * `as const` read-only contract, and the literal-union type.
 */
import { describe, expect, expectTypeOf, it } from "vitest";

import { IngestActionType } from "@/pages/admin/IngestData/IngestData";

describe("IngestActionType", () => {
  it("maps every member to its canonical wire string", () => {
    expect(IngestActionType.UploadQueued).toBe("upload_queued");
    expect(IngestActionType.UploadStarted).toBe("upload_started");
    expect(IngestActionType.UploadSuccess).toBe("upload_success");
    expect(IngestActionType.UploadFailed).toBe("upload_failed");
    expect(IngestActionType.UrlAdded).toBe("url_added");
    expect(IngestActionType.UrlStarted).toBe("url_started");
    expect(IngestActionType.UrlSuccess).toBe("url_success");
    expect(IngestActionType.UrlFailed).toBe("url_failed");
    expect(IngestActionType.ReprocessOpen).toBe("reprocess_open");
    expect(IngestActionType.ReprocessClose).toBe("reprocess_close");
    expect(IngestActionType.ReprocessStarted).toBe("reprocess_started");
    expect(IngestActionType.ReprocessSuccess).toBe("reprocess_success");
    expect(IngestActionType.ReprocessFailed).toBe("reprocess_failed");
  });

  it("enumerates exactly the 13 known values via Object.values", () => {
    expect([...Object.values(IngestActionType)].sort()).toEqual(
      [
        "reprocess_close",
        "reprocess_failed",
        "reprocess_open",
        "reprocess_started",
        "reprocess_success",
        "upload_failed",
        "upload_queued",
        "upload_started",
        "upload_success",
        "url_added",
        "url_failed",
        "url_started",
        "url_success",
      ].sort(),
    );
  });

  it("round-trips with raw wire strings", () => {
    const wire: IngestActionType = "upload_queued";
    expect(wire === IngestActionType.UploadQueued).toBe(true);
  });

  it("rejects frozen-map mutation at the type layer", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    IngestActionType.UploadQueued = "different";
  });

  it("produces a literal-union type covering every wire string", () => {
    expectTypeOf<IngestActionType>().toEqualTypeOf<
      | "upload_queued"
      | "upload_started"
      | "upload_success"
      | "upload_failed"
      | "url_added"
      | "url_started"
      | "url_success"
      | "url_failed"
      | "reprocess_open"
      | "reprocess_close"
      | "reprocess_started"
      | "reprocess_success"
      | "reprocess_failed"
    >();
  });
});
