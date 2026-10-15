/**
 * Vitest suite for `fetchDocumentObjectUrl` -- the authenticated bridge
 * that pulls a backend-gated `/api/files/<name>` blob with the forwarded
 * bearer + principal id and hands back an object URL. Global `fetch` and
 * `URL.createObjectURL` are stubbed so the test runs offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchDocumentObjectUrl } from "@/api/files";
import { setAccessToken, setUserId } from "@/api/auth";
import { resetRuntimeConfig } from "@/api/runtimeConfig";

const RESOLVED_OID = "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab";

let originalCreateObjectURL: typeof URL.createObjectURL | undefined;

beforeEach(() => {
  resetRuntimeConfig();
  originalCreateObjectURL = URL.createObjectURL;
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setAccessToken(null);
  setUserId(null);
  resetRuntimeConfig();
  if (originalCreateObjectURL) {
    URL.createObjectURL = originalCreateObjectURL;
  }
});

/** Find the fetch call that targeted the `/api/files/` route. */
function fileCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.find((args) =>
    String(args[0]).includes("/api/files/"),
  );
}

describe("fetchDocumentObjectUrl", () => {
  it("fetches with the bearer + principal id and returns an object URL", async () => {
    setAccessToken("backend-token");
    setUserId(RESOLVED_OID);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/config")) {
        return new Response("{}", { status: 200 });
      }
      return new Response(new Blob(["%PDF"], { type: "application/pdf" }), {
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const objectUrl = await fetchDocumentObjectUrl("Benefit Options.pdf");

    expect(objectUrl).toBe("blob:mock-url");
    const call = fileCall(fetchMock);
    expect(call).toBeDefined();
    expect(String(call?.[0])).toContain("/api/files/Benefit%20Options.pdf");
    const headers = new Headers((call?.[1] as RequestInit | undefined)?.headers);
    expect(headers.get("authorization")).toBe("Bearer backend-token");
    expect(headers.get("x-ms-client-principal-id")).toBe(RESOLVED_OID);
  });

  it("throws on a non-2xx response", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/config")) {
        return new Response("{}", { status: 200 });
      }
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchDocumentObjectUrl("missing.pdf")).rejects.toThrow(/404/);
  });
});
