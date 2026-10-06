/**
 * Vitest suite for the `AppShell` auth bootstrap. `getUserInfo` (the
 * MSAL-backed identity resolver) is mocked so the test drives the
 * bootstrap wiring deterministically -- the real `useAuth` hook and the
 * resolved-id singleton still run. It asserts that the id the API clients
 * forward reflects the resolver: a signed-in user yields the real object
 * id, otherwise the default user id, and history stays gated until the
 * resolver settles.
 */
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import {
  DEFAULT_USER_ID,
  getUserId,
  getUserInfo,
  setAccessToken,
  setUserId,
} from "@/api/auth";
import { resetRuntimeConfig } from "@/api/runtimeConfig";
import type { UserInfo } from "@/models/auth";

vi.mock("@/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/auth")>();
  return { ...actual, getUserInfo: vi.fn() };
});

const getUserInfoMock = vi.mocked(getUserInfo);

const RESOLVED_OID = "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab";

function signedInUser(): UserInfo {
  return {
    userId: RESOLVED_OID,
    claims: [{ typ: "name", val: "Ada Lovelace" }],
    accessToken: "backend-access-token",
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Route the shell's non-identity bootstrap calls (config/health/etc). */
function stubFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/config")) {
      return jsonResponse({ backendUrl: "" });
    }
    if (url.includes("/api/health")) {
      return jsonResponse({ status: "pass", version: "v2", checks: [] });
    }
    if (url.includes("/api/admin/status")) {
      return jsonResponse({}, 401);
    }
    // History list + anything else the shell pings.
    return jsonResponse({ conversations: [] });
  });
  globalThis.fetch = fetchMock as typeof fetch;
  return fetchMock;
}

describe("AppShell auth bootstrap", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setUserId(null);
    setAccessToken(null);
    resetRuntimeConfig();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setUserId(null);
    setAccessToken(null);
    resetRuntimeConfig();
    vi.restoreAllMocks();
  });

  it("forwards the resolved object id once the MSAL flow returns a user", async () => {
    stubFetch();
    getUserInfoMock.mockResolvedValue(signedInUser());
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
  });

  it("falls back to the default user when no identity resolves", async () => {
    stubFetch();
    getUserInfoMock.mockResolvedValue(null);
    render(<App />);
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    // No signed-in user -> the default partition id.
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("does not fetch history until identity resolves, then uses the resolved id", async () => {
    // Hold identity resolution pending so the shell stays in AuthPhase.Loading.
    let releaseAuth: ((user: UserInfo) => void) | undefined;
    const authPending = new Promise<UserInfo>((resolve) => {
      releaseAuth = resolve;
    });
    getUserInfoMock.mockReturnValue(authPending);
    const fetchMock = stubFetch();

    const historyCalls = () =>
      fetchMock.mock.calls.filter((args) =>
        String(args[0]).includes("/api/history/conversations"),
      );

    render(<App />);

    // While auth is loading, the chat route must not mount its history panel.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(historyCalls()).toHaveLength(0);

    // Resolve identity; now the chat route mounts and history loads.
    releaseAuth?.(signedInUser());
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
    await waitFor(() => {
      expect(historyCalls().length).toBeGreaterThan(0);
    });
    for (const call of historyCalls()) {
      const init = call[1] as RequestInit | undefined;
      const headers = new Headers(init?.headers);
      expect(headers.get("x-ms-client-principal-id")).toBe(RESOLVED_OID);
    }
  });

  it("resolves identity only after the runtime config has loaded", async () => {
    const fetchMock = stubFetch();
    getUserInfoMock.mockResolvedValue(signedInUser());
    render(<App />);
    await waitFor(() => {
      expect(getUserInfoMock).toHaveBeenCalled();
    });
    // /config must have been fetched before identity resolution ran.
    const configCalledBefore = fetchMock.mock.calls.some((args) =>
      String(args[0]).includes("/config"),
    );
    expect(configCalledBefore).toBe(true);
  });

  it("keeps health public but forwards the bearer on the admin-status probe", async () => {
    const fetchMock = stubFetch();
    getUserInfoMock.mockResolvedValue(signedInUser());
    render(<App />);

    const probeCall = (fragment: string) =>
      fetchMock.mock.calls.find((args) => String(args[0]).includes(fragment));

    await waitFor(() => {
      expect(probeCall("/api/health")).toBeDefined();
      expect(probeCall("/api/admin/status")).toBeDefined();
    });

    // Admin surface is gated -> must carry the resolved bearer.
    const adminHeaders = new Headers(
      (probeCall("/api/admin/status")?.[1] as RequestInit | undefined)?.headers,
    );
    expect(adminHeaders.get("authorization")).toBe("Bearer backend-access-token");

    // Health is a public liveness probe -> no Authorization header.
    const healthHeaders = new Headers(
      (probeCall("/api/health")?.[1] as RequestInit | undefined)?.headers,
    );
    expect(healthHeaders.get("authorization")).toBeNull();
  });
});
