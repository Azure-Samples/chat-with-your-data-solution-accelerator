/**
 * Pillar: Stable Core
 * Phase: 4 (S1 / SPEECH-MVP)
 *
 * Vitest suite for the `getSpeechConfig()` REST client. Mocks global
 * `fetch` with a JSON body so the unit test runs offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getSpeechConfig } from "@/api/speech";
import { DEFAULT_USER_ID, setUserId } from "@/api/auth";
import { loadRuntimeConfig, resetRuntimeConfig } from "@/api/runtimeConfig";

function jsonResponse(body: unknown, { status = 200 }: { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("getSpeechConfig", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    resetRuntimeConfig();
    // getSpeechConfig forwards the shared auth singleton; reset it.
    setUserId(null);
  });

  it("GETs /api/speech with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        token: "spch-token",
        region: "eastus2",
        languages: ["en-US", "fr-FR"],
      }),
    );

    await getSpeechConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/speech");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("prepends VITE_BACKEND_URL to the speech route when set (split-host deploy)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        token: "spch-token",
        region: "eastus2",
        languages: ["en-US"],
      }),
    );
    vi.stubEnv("VITE_BACKEND_URL", "https://backend.example.com");

    await getSpeechConfig();

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("https://backend.example.com/api/speech");
  });

  it("prefers the runtime /config backendUrl over the env fallback", async () => {
    // The runtime origin from /config must win over build-time
    // VITE_BACKEND_URL so the deployed split-host SPA mints its Speech
    // token from the backend Container App resolved at boot.
    vi.stubEnv("VITE_BACKEND_URL", "https://build-time.example.com");
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/config") {
        return jsonResponse({ backendUrl: "https://runtime.example.com" });
      }
      return jsonResponse({
        token: "spch-token",
        region: "eastus2",
        languages: ["en-US"],
      });
    });

    await loadRuntimeConfig();
    await getSpeechConfig();

    const speechCall = fetchMock.mock.calls.find(
      ([callUrl]) => callUrl === "https://runtime.example.com/api/speech",
    );
    expect(speechCall).toBeDefined();
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        token: "spch-token",
        region: "eastus2",
        languages: ["en-US", "fr-FR", "de-DE", "it-IT"],
      }),
    );

    const result = await getSpeechConfig();

    expect(result).toEqual({
      token: "spch-token",
      region: "eastus2",
      languages: ["en-US", "fr-FR", "de-DE", "it-IT"],
    });
  });

  it("throws on non-2xx status (e.g. 503 when speech is not configured)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Speech service not configured." }, { status: 503 }),
    );

    await expect(getSpeechConfig()).rejects.toThrow(/status 503/);
  });

  it("throws on 502 (token mint failure)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Speech token mint failed." }, { status: 502 }),
    );

    await expect(getSpeechConfig()).rejects.toThrow(/status 502/);
  });

  it("forwards the default principal id header when no user is resolved", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ token: "spch-token", region: "eastus2", languages: ["en-US"] }),
    );

    await getSpeechConfig();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["x-ms-client-principal-id"]).toBe(DEFAULT_USER_ID);
  });

  it("forwards the resolved principal id header once a user is set", async () => {
    setUserId("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ token: "spch-token", region: "eastus2", languages: ["en-US"] }),
    );

    await getSpeechConfig();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["x-ms-client-principal-id"]).toBe(
      "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
    );
  });
});
