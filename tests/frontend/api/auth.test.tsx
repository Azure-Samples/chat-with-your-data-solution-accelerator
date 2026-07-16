/**
 * Vitest suite for `getUserInfo()` -- the seam that resolves the signed-in
 * user from Easy Auth `/.auth/me` and narrows the principal to its Entra
 * object-identifier claim. Global `fetch` is mocked so the tests exercise
 * the real URL (always the SPA-origin `/.auth/me`, never the backend),
 * the claim extraction, and the graceful `null` fallbacks (no network).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_USER_ID,
  getUserId,
  getUserInfo,
  setUserId,
  userIdHeaders,
} from "@/api/auth";
import type { AuthMeResponse } from "@/models/auth";

const OBJECT_ID_CLAIM =
  "http://schemas.microsoft.com/identity/claims/objectidentifier";

function jsonResponse(
  body: unknown,
  { status = 200 }: { status?: number } = {},
) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function principal(objectId: string): AuthMeResponse {
  return {
    user_id: "user@contoso.example.com",
    provider_name: "aad",
    user_claims: [
      { typ: "name", val: "Ada Lovelace" },
      { typ: OBJECT_ID_CLAIM, val: objectId },
    ],
  };
}

describe("getUserInfo", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("GETs the SPA-origin /.auth/me endpoint", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([principal("oid-1")]));
    await getUserInfo();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("/.auth/me");
  });

  it("never prefixes VITE_BACKEND_URL (auth is the SPA's own origin)", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://backend.example.com");
    fetchMock.mockResolvedValueOnce(jsonResponse([principal("oid-1")]));
    await getUserInfo();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("/.auth/me");
  });

  it("resolves the object-identifier claim as the userId", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([principal("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab")]),
    );
    const info = await getUserInfo();
    expect(info?.userId).toBe("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
  });

  it("preserves every claim on the resolved UserInfo", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([principal("oid-9")]));
    const info = await getUserInfo();
    expect(info?.claims).toEqual([
      { typ: "name", val: "Ada Lovelace" },
      { typ: OBJECT_ID_CLAIM, val: "oid-9" },
    ]);
  });

  it("returns null when /.auth/me responds not-ok (no identity provider)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, { status: 401 }));
    expect(await getUserInfo()).toBeNull();
  });

  it("returns null when the principal array is empty", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([]));
    expect(await getUserInfo()).toBeNull();
  });

  it("falls back to user_id when no object-identifier claim is present", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        {
          user_id: "user@contoso.example.com",
          provider_name: "aad",
          user_claims: [{ typ: "name", val: "Ada Lovelace" }],
        },
      ]),
    );
    expect(await getUserInfo()).toEqual({
      userId: "user@contoso.example.com",
      claims: [{ typ: "name", val: "Ada Lovelace" }],
    });
  });

  it("returns null when fetch rejects (network error)", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));
    expect(await getUserInfo()).toBeNull();
  });
});

describe("resolved-id store + header builder", () => {
  afterEach(() => {
    // Module-level `currentUserId` is shared across tests; reset it.
    setUserId(null);
  });

  it("exposes the all-zeros default user id", () => {
    expect(DEFAULT_USER_ID).toBe("00000000-0000-0000-0000-000000000000");
  });

  it("getUserId falls back to the default before any user is set", () => {
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("getUserId returns the resolved id once set", () => {
    setUserId("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
    expect(getUserId()).toBe("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
  });

  it("setUserId(null) clears the override back to the default", () => {
    setUserId("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
    setUserId(null);
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("userIdHeaders forwards the default id when no user is resolved", () => {
    expect(userIdHeaders()).toEqual({
      "x-ms-client-principal-id": DEFAULT_USER_ID,
    });
  });

  it("userIdHeaders forwards the resolved id once set", () => {
    setUserId("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
    expect(userIdHeaders()).toEqual({
      "x-ms-client-principal-id": "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
    });
  });
});
