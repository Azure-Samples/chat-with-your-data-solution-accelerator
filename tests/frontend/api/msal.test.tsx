/**
 * Vitest suite for the browser-side MSAL seam. The interactive redirect
 * flows cannot run in jsdom, so `resolveAuthWith` is exercised against a
 * hand-rolled fake `IPublicClientApplication` that records the calls the
 * seam makes (silent acquire, login redirect, interactive acquire). The
 * pure `buildMsalConfig` mapping and the no-client-id guards run directly.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  AccountInfo,
  AuthenticationResult,
  IPublicClientApplication,
} from "@azure/msal-browser";
import {
  buildMsalConfig,
  getMsalApp,
  resolveAuthWith,
} from "@/api/msal";
import type { AuthRuntimeConfig } from "@/api/runtimeConfig";

const POPULATED: AuthRuntimeConfig = {
  clientId: "client-123",
  authority: "https://login.microsoftonline.com/tenant-456",
  apiScope: "api://client-123/user_impersonation",
};

function account(oid: string): AccountInfo {
  return {
    homeAccountId: `${oid}.tenant`,
    environment: "login.microsoftonline.com",
    tenantId: "tenant-456",
    username: "ada@contoso.example.com",
    localAccountId: oid,
    idTokenClaims: { oid, name: "Ada Lovelace" },
  } as AccountInfo;
}

interface FakeAppCalls {
  loginRedirect: number;
  acquireTokenRedirect: number;
}

function fakeApp(
  overrides: Partial<IPublicClientApplication>,
  calls: FakeAppCalls,
): IPublicClientApplication {
  return {
    handleRedirectPromise: vi.fn(async () => null),
    getActiveAccount: vi.fn(() => null),
    getAllAccounts: vi.fn(() => []),
    setActiveAccount: vi.fn(),
    loginRedirect: vi.fn(async () => {
      calls.loginRedirect += 1;
    }),
    acquireTokenRedirect: vi.fn(async () => {
      calls.acquireTokenRedirect += 1;
    }),
    ...overrides,
  } as unknown as IPublicClientApplication;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("buildMsalConfig", () => {
  it("returns null when the client id is empty", () => {
    expect(
      buildMsalConfig({ clientId: "", authority: "", apiScope: "" }),
    ).toBeNull();
  });

  it("maps a populated runtime config onto an MSAL configuration", () => {
    const config = buildMsalConfig(POPULATED);
    expect(config).not.toBeNull();
    expect(config?.auth.clientId).toBe("client-123");
    expect(config?.auth.authority).toBe(
      "https://login.microsoftonline.com/tenant-456",
    );
    expect(config?.auth.redirectUri).toBe(window.location.origin);
  });
});

describe("getMsalApp", () => {
  it("returns null when no client id is configured (local dev)", async () => {
    const app = await getMsalApp({ clientId: "", authority: "", apiScope: "" });
    expect(app).toBeNull();
  });
});

describe("resolveAuthWith", () => {
  it("returns the oid and ID token from a silent acquisition", async () => {
    const calls: FakeAppCalls = { loginRedirect: 0, acquireTokenRedirect: 0 };
    const result = {
      idToken: "backend-id-token",
      accessToken: "unused-access-token",
      account: account("oid-9"),
    } as AuthenticationResult;
    const app = fakeApp(
      {
        getAllAccounts: vi.fn(() => [account("oid-9")]),
        acquireTokenSilent: vi.fn(async () => result),
      },
      calls,
    );

    const resolved = await resolveAuthWith(app, ["openid", "profile"]);

    expect(resolved).toEqual({
      userId: "oid-9",
      accessToken: "backend-id-token",
      claims: [
        { typ: "oid", val: "oid-9" },
        { typ: "name", val: "Ada Lovelace" },
      ],
    });
    expect(calls.loginRedirect).toBe(0);
  });

  it("triggers a login redirect and returns null when no account exists", async () => {
    const calls: FakeAppCalls = { loginRedirect: 0, acquireTokenRedirect: 0 };
    const app = fakeApp({}, calls);

    const resolved = await resolveAuthWith(app, ["openid", "profile"]);

    expect(resolved).toBeNull();
    expect(calls.loginRedirect).toBe(1);
  });

  it("falls back to an interactive redirect when silent acquire fails", async () => {
    const calls: FakeAppCalls = { loginRedirect: 0, acquireTokenRedirect: 0 };
    const app = fakeApp(
      {
        getAllAccounts: vi.fn(() => [account("oid-x")]),
        acquireTokenSilent: vi.fn(async () => {
          throw new Error("interaction_required");
        }),
      },
      calls,
    );

    const resolved = await resolveAuthWith(app, ["openid", "profile"]);

    expect(resolved).toBeNull();
    expect(calls.acquireTokenRedirect).toBe(1);
  });
});
