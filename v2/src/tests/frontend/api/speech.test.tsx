/**
 * Pillar: Stable Core
 * Phase: 4 (S1 / SPEECH-MVP)
 *
 * Vitest suite for the `getSpeechConfig()` REST client. Mocks global
 * `fetch` with a JSON body so the unit test runs offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getSpeechConfig } from "@/api/speech";

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
    vi.restoreAllMocks();
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
});
