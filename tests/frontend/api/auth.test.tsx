/**
 * Vitest suite for `getUserInfo()` -- the seam that resolves the signed-in
 * user and a backend access token through the browser-side MSAL flow. The
 * `api/msal` and `api/runtimeConfig` modules are mocked so the tests drive
 * the resolution branches (no provider, mid-redirect, resolved) without a
 * real Entra round trip.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { IPublicClientApplication } from "@azure/msal-browser";
import {
  authHeaders,
  DEFAULT_USER_ID,
  getAccessToken,
  getUserId,
  getUserInfo,
  setAccessToken,
  setUserId,
  userIdHeaders,
} from "@/api/auth";
import { getMsalApp, resolveAuthWith } from "@/api/msal";
import { getAuthConfig } from "@/api/runtimeConfig";

vi.mock("@/api/msal", () => ({
  getMsalApp: vi.fn(),
  resolveAuthWith: vi.fn(),
}));
vi.mock("@/api/runtimeConfig", () => ({
  getAuthConfig: vi.fn(),
}));

const getMsalAppMock = vi.mocked(getMsalApp);
const resolveAuthWithMock = vi.mocked(resolveAuthWith);
const getAuthConfigMock = vi.mocked(getAuthConfig);

const FAKE_APP = {} as IPublicClientApplication;

describe("getUserInfo", () => {
  beforeEach(() => {
    getAuthConfigMock.mockReturnValue({
      clientId: "client-123",
      authority: "https://login.microsoftonline.com/tenant-456",
      apiScope: "api://client-123/user_impersonation",
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when no identity provider is configured (local dev)", async () => {
    getMsalAppMock.mockResolvedValueOnce(null);
    expect(await getUserInfo()).toBeNull();
    expect(resolveAuthWithMock).not.toHaveBeenCalled();
  });

  it("returns null while the browser is mid-redirect (no token yet)", async () => {
    getMsalAppMock.mockResolvedValueOnce(FAKE_APP);
    resolveAuthWithMock.mockResolvedValueOnce(null);
    expect(await getUserInfo()).toBeNull();
  });

  it("maps the resolved auth onto UserInfo", async () => {
    getMsalAppMock.mockResolvedValueOnce(FAKE_APP);
    resolveAuthWithMock.mockResolvedValueOnce({
      userId: "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
      accessToken: "backend-access-token",
      claims: [{ typ: "name", val: "Ada Lovelace" }],
    });

    const info = await getUserInfo();

    expect(info).toEqual({
      userId: "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
      claims: [{ typ: "name", val: "Ada Lovelace" }],
      accessToken: "backend-access-token",
    });
  });

  it("acquires the token for the configured scope from the runtime config", async () => {
    getMsalAppMock.mockResolvedValueOnce(FAKE_APP);
    resolveAuthWithMock.mockResolvedValueOnce({
      userId: "oid-1",
      accessToken: "tok",
      claims: [],
    });

    await getUserInfo();

    expect(resolveAuthWithMock).toHaveBeenCalledWith(FAKE_APP, [
      "api://client-123/user_impersonation",
    ]);
  });

  it("defaults to OIDC scopes when no apiScope is configured", async () => {
    getAuthConfigMock.mockReturnValue({
      clientId: "client-123",
      authority: "https://login.microsoftonline.com/tenant-456",
      apiScope: "",
    });
    getMsalAppMock.mockResolvedValueOnce(FAKE_APP);
    resolveAuthWithMock.mockResolvedValueOnce({
      userId: "oid-1",
      accessToken: "tok",
      claims: [],
    });

    await getUserInfo();

    expect(resolveAuthWithMock).toHaveBeenCalledWith(FAKE_APP, [
      "openid",
      "profile",
    ]);
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

describe("backend bearer token store + authHeaders", () => {
  afterEach(() => {
    // Module-level `currentAccessToken` is shared across tests; reset it.
    setAccessToken(null);
  });

  it("getAccessToken returns null before any token is set", () => {
    expect(getAccessToken()).toBeNull();
  });

  it("authHeaders is empty when no token is resolved (local dev)", () => {
    expect(authHeaders()).toEqual({});
  });

  it("authHeaders forwards a Bearer token once set", () => {
    setAccessToken("backend-jwt");
    expect(getAccessToken()).toBe("backend-jwt");
    expect(authHeaders()).toEqual({ Authorization: "Bearer backend-jwt" });
  });

  it("setAccessToken(null) clears the token back to empty headers", () => {
    setAccessToken("backend-jwt");
    setAccessToken(null);
    expect(authHeaders()).toEqual({});
  });
});
