/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
 *
 * Vitest suite for `fetchConversation()` — the seam that loads one
 * persisted conversation from `GET /api/history/conversations/{id}` and
 * maps the stored `MessageRecord[]` onto the frontend `ChatMessage[]`
 * transcript, rehydrating each assistant turn's persisted citations from
 * `metadata.citations`. Global `fetch` is mocked so the tests exercise
 * the real URL building + role filter + citation narrowing (no network).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchConversation } from "@/api/conversationHistory";

function jsonResponse(body: unknown, { status = 200 }: { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("fetchConversation", () => {
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

  it("GETs the conversation detail route with the encoded id and JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ messages: [] }));
    await fetchConversation("conv 7/ab");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/history/conversations/conv%207%2Fab");
    expect(init.method).toBe("GET");
    const headers = init.headers as Record<string, string>;
    expect(headers["Accept"]).toBe("application/json");
  });

  it("prepends VITE_BACKEND_URL to the detail route when set", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://backend.example.com");
    fetchMock.mockResolvedValueOnce(jsonResponse({ messages: [] }));
    await fetchConversation("conv-1");
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "https://backend.example.com/api/history/conversations/conv-1",
    );
  });

  it("returns the resolved conversationId alongside the mapped messages", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        messages: [
          { id: "m1", role: "user", content: "hi", metadata: {} },
          { id: "m2", role: "assistant", content: "hello", metadata: {} },
        ],
      }),
    );
    const loaded = await fetchConversation("conv-9");
    expect(loaded.conversationId).toBe("conv-9");
    expect(loaded.messages).toEqual([
      { id: "m1", role: "user", content: "hi" },
      { id: "m2", role: "assistant", content: "hello" },
    ]);
  });

  it("rehydrates assistant citations from metadata.citations", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        messages: [
          {
            id: "m2",
            role: "assistant",
            content: "grounded answer [doc1]",
            metadata: {
              citations: [
                {
                  id: "src-1",
                  title: "Doc One",
                  url: "https://example.com/d1",
                  snippet: "a snippet",
                  score: 0.87,
                  metadata: { page: 3 },
                },
              ],
            },
          },
        ],
      }),
    );
    const loaded = await fetchConversation("conv-1");
    expect(loaded.messages).toEqual([
      {
        id: "m2",
        role: "assistant",
        content: "grounded answer [doc1]",
        citations: [
          {
            id: "src-1",
            title: "Doc One",
            url: "https://example.com/d1",
            snippet: "a snippet",
            score: 0.87,
            metadata: { page: 3 },
          },
        ],
      },
    ]);
  });

  it("omits the citations key when an assistant message persisted none", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        messages: [
          { id: "m2", role: "assistant", content: "no sources", metadata: {} },
        ],
      }),
    );
    const loaded = await fetchConversation("conv-1");
    expect(loaded.messages[0]).not.toHaveProperty("citations");
  });

  it("drops system and tool messages from the rehydrated transcript", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        messages: [
          { id: "s1", role: "system", content: "you are…", metadata: {} },
          { id: "m1", role: "user", content: "hi", metadata: {} },
          { id: "t1", role: "tool", content: "{}", metadata: {} },
          { id: "m2", role: "assistant", content: "hello", metadata: {} },
        ],
      }),
    );
    const loaded = await fetchConversation("conv-1");
    expect(loaded.messages.map((m) => m.id)).toEqual(["m1", "m2"]);
  });

  it("drops a malformed persisted citation that lacks a non-empty id", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        messages: [
          {
            id: "m2",
            role: "assistant",
            content: "answer",
            metadata: {
              citations: [
                { id: "", title: "empty id" },
                { title: "missing id" },
                { id: "good", title: "kept" },
              ],
            },
          },
        ],
      }),
    );
    const loaded = await fetchConversation("conv-1");
    expect(loaded.messages[0]?.citations).toEqual([
      { id: "good", title: "kept", url: "", snippet: "", score: null, metadata: {} },
    ]);
  });

  it("coerces a non-numeric or non-finite citation score to null", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        messages: [
          {
            id: "m2",
            role: "assistant",
            content: "answer",
            metadata: {
              citations: [{ id: "s1", score: "high" }],
            },
          },
        ],
      }),
    );
    const loaded = await fetchConversation("conv-1");
    expect(loaded.messages[0]?.citations?.[0]?.score).toBeNull();
  });

  it("tolerates a message with no metadata field", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ messages: [{ id: "m1", role: "user", content: "hi" }] }),
    );
    const loaded = await fetchConversation("conv-1");
    expect(loaded.messages).toEqual([{ id: "m1", role: "user", content: "hi" }]);
  });

  it("returns an empty transcript when the detail has no messages array", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}));
    const loaded = await fetchConversation("conv-1");
    expect(loaded).toEqual({ conversationId: "conv-1", messages: [] });
  });

  it("throws with the status when the response is not ok", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "not found" }, { status: 404 }));
    await expect(fetchConversation("missing")).rejects.toThrow(
      "fetchConversation: request failed with status 404",
    );
  });
});
