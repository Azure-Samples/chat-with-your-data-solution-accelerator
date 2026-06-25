/**
 * Pillar: Stable Core
 * Phase: 1 (Frontend → App Service build-from-source)
 *
 * Vitest suite for the runtime backend-URL seam. Mocks global `fetch`
 * so the unit test runs offline and stubs `VITE_BACKEND_URL` to exercise
 * the build-time fallback path.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getBackendUrl,
  loadRuntimeConfig,
  resetRuntimeConfig,
} from "@/api/runtimeConfig";

function jsonResponse(body: unknown, { status = 200 }: { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("runtimeConfig", () => {
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
  });

  it("falls back to VITE_BACKEND_URL before /config loads", () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://env.example.com");

    expect(getBackendUrl()).toBe("https://env.example.com");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns an empty string when neither cache nor env is set", () => {
    vi.stubEnv("VITE_BACKEND_URL", "");

    expect(getBackendUrl()).toBe("");
  });

  it("fetches /config and caches backendUrl", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ backendUrl: "https://backend.example.com" }),
    );

    await loadRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/config");
    expect(getBackendUrl()).toBe("https://backend.example.com");
  });

  it("lets the runtime /config value override the env fallback", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://env.example.com");
    fetchMock.mockResolvedValue(
      jsonResponse({ backendUrl: "https://runtime.example.com" }),
    );

    await loadRuntimeConfig();

    expect(getBackendUrl()).toBe("https://runtime.example.com");
  });

  it("is idempotent across concurrent and repeat calls", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ backendUrl: "https://backend.example.com" }),
    );

    await Promise.all([loadRuntimeConfig(), loadRuntimeConfig()]);
    await loadRuntimeConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to env when the /config fetch rejects", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://env.example.com");
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    await loadRuntimeConfig();

    expect(getBackendUrl()).toBe("https://env.example.com");
  });

  it("ignores a non-ok /config response", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "");
    fetchMock.mockResolvedValue(jsonResponse({}, { status: 500 }));

    await loadRuntimeConfig();

    expect(getBackendUrl()).toBe("");
  });

  it("resetRuntimeConfig clears the cached value", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://env.example.com");
    fetchMock.mockResolvedValue(
      jsonResponse({ backendUrl: "https://runtime.example.com" }),
    );

    await loadRuntimeConfig();
    expect(getBackendUrl()).toBe("https://runtime.example.com");

    resetRuntimeConfig();

    expect(getBackendUrl()).toBe("https://env.example.com");
  });
});
