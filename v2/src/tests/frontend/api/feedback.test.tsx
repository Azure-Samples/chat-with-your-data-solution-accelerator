/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest suite for the `setFeedback()` REST client. Mocks global
 * `fetch` so the unit runs offline; mirrors the
 * `tests/api/admin.test.ts` test shape.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setFeedback } from "@/api/feedback";

function noContentResponse(): Response {
  return new Response(null, { status: 204 });
}

function errorResponse(status: number, detail = "error"): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("setFeedback", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POSTs the feedback string to the per-message endpoint", async () => {
    fetchMock.mockResolvedValueOnce(noContentResponse());

    await setFeedback("msg-abc-123", "positive");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/history/messages/msg-abc-123/feedback");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
    expect(init.body).toBe(JSON.stringify({ feedback: "positive" }));
  });

  it("URL-encodes the message id so unsafe characters cannot escape the path segment", async () => {
    fetchMock.mockResolvedValueOnce(noContentResponse());

    await setFeedback("msg with/slash?and&amp", "negative");

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe(
      "/api/history/messages/msg%20with%2Fslash%3Fand%26amp/feedback",
    );
  });

  it("serializes the feedback value verbatim in the JSON body", async () => {
    fetchMock.mockResolvedValueOnce(noContentResponse());

    await setFeedback("m1", "negative: missing context");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(
      JSON.stringify({ feedback: "negative: missing context" }),
    );
  });

  it("resolves with no return value on 204 No Content", async () => {
    fetchMock.mockResolvedValueOnce(noContentResponse());

    const result = await setFeedback("m1", "positive");

    expect(result).toBeUndefined();
  });

  it("throws on 404 (unknown message id)", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(404, "message not found"));

    await expect(setFeedback("nope", "positive")).rejects.toThrow(
      /status 404/,
    );
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      errorResponse(401, "Not authenticated."),
    );

    await expect(setFeedback("m1", "positive")).rejects.toThrow(/status 401/);
  });

  it("throws on 422 (backend rejected the feedback value)", async () => {
    fetchMock.mockResolvedValueOnce(
      errorResponse(422, "feedback too long"),
    );

    await expect(setFeedback("m1", "x".repeat(100))).rejects.toThrow(
      /status 422/,
    );
  });
});
