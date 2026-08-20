/**
 * Vitest suite for the `AppShell` auth bootstrap. Drives the whole shell
 * through a URL-routed `fetch` mock (no module stubs) so the real
 * `useAuth` hook + `getUserInfo` run, and asserts the resolved-id
 * singleton the API clients forward reflects the Easy Auth `/.auth/me`
 * lookup: a principal yields the real object id, otherwise the default
 * user id.
 */
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import { DEFAULT_USER_ID, getUserId, setUserId } from "@/api/auth";

const RESOLVED_OID = "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab";
const OBJECT_ID_CLAIM =
  "http://schemas.microsoft.com/identity/claims/objectidentifier";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** A signed-in `/.auth/me` principal carrying the Entra object id. */
function principalPayload() {
  return [
    {
      user_id: "user@contoso.example.com",
      provider_name: "aad",
      user_claims: [{ typ: OBJECT_ID_CLAIM, val: RESOLVED_OID }],
    },
  ];
}

/**
 * Route the shell's bootstrap calls by URL. `signedIn` toggles whether
 * `/.auth/me` returns a principal (200) or no identity provider (401).
 */
function stubFetch({ signedIn }: { signedIn: boolean }): void {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/.auth/me")) {
      return signedIn
        ? jsonResponse(principalPayload())
        : jsonResponse({}, 401);
    }
    if (url.includes("/api/health")) {
      return jsonResponse({
        status: "pass",
        version: "v2",
        checks: [],
      });
    }
    if (url.includes("/api/admin/status")) {
      return jsonResponse({}, 401);
    }
    // History list + anything else the shell pings.
    return jsonResponse({ conversations: [] });
  });
  globalThis.fetch = fetchMock as typeof fetch;
}

describe("AppShell auth bootstrap", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setUserId(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setUserId(null);
    vi.restoreAllMocks();
  });

  it("forwards the resolved object id once /.auth/me returns a principal", async () => {
    stubFetch({ signedIn: true });
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
  });

  it("falls back to the default user when no principal resolves", async () => {
    stubFetch({ signedIn: false });
    render(<App />);
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    // No principal -> the default partition id.
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("does not fetch history until /.auth/me resolves, then uses the resolved id", async () => {
    // Hold /.auth/me pending so the shell stays in AuthPhase.Loading.
    let releaseAuthMe: (() => void) | undefined;
    const authMePending = new Promise<void>((resolve) => {
      releaseAuthMe = resolve;
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/.auth/me")) {
        await authMePending;
        return jsonResponse(principalPayload());
      }
      if (url.includes("/api/health")) {
        return jsonResponse({ status: "pass", version: "v2", checks: [] });
      }
      if (url.includes("/api/admin/status")) {
        return jsonResponse({}, 401);
      }
      return jsonResponse([]);
    });
    globalThis.fetch = fetchMock as typeof fetch;

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
    releaseAuthMe?.();
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

  it("queries the Easy Auth /.auth/me endpoint on the SPA origin", async () => {
    stubFetch({ signedIn: true });
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
    const calledAuthMe = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
      .calls.length;
    expect(calledAuthMe).toBeGreaterThan(0);
    const authMeCall = (
      globalThis.fetch as ReturnType<typeof vi.fn>
    ).mock.calls.find((args) => String(args[0]).includes("/.auth/me"));
    expect(authMeCall).toBeDefined();
    // Resolved off the SPA origin, never prefixed with the backend URL.
    expect(String(authMeCall?.[0])).toBe("/.auth/me");
  });
});
