/**
 * Pillar: Stable Core
 * Phase: 5 (frontend — user identity)
 *
 * Vitest suite for the `AppShell` auth bootstrap. Drives the whole shell
 * through a URL-routed `fetch` mock (no module stubs) so the real
 * `useAuth` hook + `getUserInfo` run, and asserts the resolved-id
 * singleton the API clients forward reflects the `/.auth/me` lookup and
 * the `auth_enforced` flag carried on the `/api/health` payload. When
 * auth is enforced and `/.auth/me` returns no principal, the shell
 * renders the `<AuthBlocked>` screen in place of the routed view.
 */
import { render, screen, waitFor } from "@testing-library/react";
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
 * Route the shell's bootstrap calls by URL. `authEnforced` rides the
 * health payload; `signedIn` toggles whether `/.auth/me` returns a
 * principal (200) or no identity provider (401).
 */
function stubFetch({
  authEnforced,
  signedIn,
}: {
  authEnforced: boolean;
  signedIn: boolean;
}): void {
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
        auth_enforced: authEnforced,
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
    stubFetch({ authEnforced: false, signedIn: true });
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
  });

  it("forwards the resolved object id even when auth is enforced", async () => {
    stubFetch({ authEnforced: true, signedIn: true });
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
  });

  it("falls back to the default user when not signed in and auth is not enforced", async () => {
    stubFetch({ authEnforced: false, signedIn: false });
    render(<App />);
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    // No principal + not enforced -> the default partition id.
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("forwards the default user when auth is enforced but no principal resolves", async () => {
    stubFetch({ authEnforced: true, signedIn: false });
    render(<App />);
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });
    // Blocked sessions never forward a bogus id; the shell makes no
    // user-scoped calls while blocked (asserted via the UI at F11).
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("queries the Easy Auth /.auth/me endpoint on the SPA origin", async () => {
    stubFetch({ authEnforced: false, signedIn: true });
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

  it("renders the blocked screen when auth is enforced but no principal resolves", async () => {
    stubFetch({ authEnforced: true, signedIn: false });
    render(<App />);
    expect(await screen.findByTestId("auth-blocked")).toBeInTheDocument();
  });

  it("keeps the blocked screen hidden once a principal resolves under enforcement", async () => {
    stubFetch({ authEnforced: true, signedIn: true });
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(RESOLVED_OID);
    });
    expect(screen.queryByTestId("auth-blocked")).toBeNull();
  });

  it("keeps the blocked screen hidden when auth is not enforced and no principal resolves", async () => {
    stubFetch({ authEnforced: false, signedIn: false });
    render(<App />);
    await waitFor(() => {
      expect(getUserId()).toBe(DEFAULT_USER_ID);
    });
    expect(screen.queryByTestId("auth-blocked")).toBeNull();
  });
});
