/**
 * Vitest suite for the SSE client utility `streamChat()`. The util is
 * the only piece that talks to `POST /api/conversation` over
 * `text/event-stream`; everything in the chat UI consumes the typed
 * event stream it yields. We mock global `fetch` with a
 * `ReadableStream`-bodied `Response` so the tests exercise the real
 * SSE line parser (no network).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "@/api/streamChat";
import { DEFAULT_USER_ID, setUserId } from "@/api/auth";
import { loadRuntimeConfig, resetRuntimeConfig } from "@/api/runtimeConfig";
import type { StreamEvent } from "@/models/chat";

const enc = new TextEncoder();

function sseResponse(chunks: string[], { status = 200 }: { status?: number } = {}) {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(enc.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "Content-Type": "text/event-stream" },
  });
}

async function collect(stream: AsyncIterable<StreamEvent>): Promise<StreamEvent[]> {
  const out: StreamEvent[] = [];
  for await (const ev of stream) {
    out.push(ev);
  }
  return out;
}

describe("streamChat", () => {
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
    // `streamChat` forwards the shared auth singleton; reset it.
    setUserId(null);
  });

  it("posts the messages payload to /api/conversation with SSE Accept header", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    await collect(
      streamChat([{ role: "user", content: "hello" }]),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/conversation");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Accept"]).toBe("text/event-stream");
    expect(JSON.parse(init.body as string)).toEqual({
      messages: [{ role: "user", content: "hello" }],
    });
  });

  it("forwards the default principal id header when no user is resolved", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    await collect(streamChat([{ role: "user", content: "hello" }]));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["x-ms-client-principal-id"]).toBe(DEFAULT_USER_ID);
  });

  it("forwards the resolved principal id header once a user is set", async () => {
    setUserId("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    await collect(streamChat([{ role: "user", content: "hello" }]));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["x-ms-client-principal-id"]).toBe(
      "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
    );
  });

  it("yields a single answer event from one well-formed SSE frame", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: answer\ndata: {"content":"hi","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(streamChat([]));
    expect(events).toEqual([
      { channel: "answer", content: "hi", metadata: {} },
    ]);
  });

  it("yields multiple events from a concatenated stream", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: reasoning\ndata: {"content":"thinking","metadata":{}}\n\n' +
          'event: answer\ndata: {"content":"done","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(streamChat([]));
    expect(events).toEqual([
      { channel: "reasoning", content: "thinking", metadata: {} },
      { channel: "answer", content: "done", metadata: {} },
    ]);
  });

  it("buffers across chunk boundaries that split a single SSE frame", async () => {
    // Frame is split in the middle of the data line across two reads.
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: answer\ndata: {"conte',
        'nt":"split","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(streamChat([]));
    expect(events).toEqual([
      { channel: "answer", content: "split", metadata: {} },
    ]);
  });

  it("preserves metadata fields on citation events", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: citation\ndata: {"content":"","metadata":{"id":"c1","title":"Doc"}}\n\n',
      ]),
    );
    const events = await collect(streamChat([]));
    expect(events).toHaveLength(1);
    expect(events[0]!.channel).toBe("citation");
    expect(events[0]!.metadata).toEqual({ id: "c1", title: "Doc" });
  });

  it("yields error events without throwing", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: error\ndata: {"content":"boom","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(streamChat([]));
    expect(events).toEqual([
      { channel: "error", content: "boom", metadata: {} },
    ]);
  });

  it("throws immediately on a 4xx response without retrying", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([], { status: 400 }));
    await expect(
      collect(streamChat([], { maxRetries: 2, baseDelayMs: 1 })),
    ).rejects.toThrow(/400/);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("surfaces the backend JSON error body (message + reason + status) on a non-OK response", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "Orchestrator 'agent_framework' is not available here.",
          reason: "orchestrator_requires_azure_search",
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );
    let caught: unknown;
    try {
      await collect(streamChat([], { maxRetries: 2, baseDelayMs: 1 }));
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(Error);
    const error = caught as Error & { status?: number; reason?: string };
    expect(error.message).toBe(
      "Orchestrator 'agent_framework' is not available here.",
    );
    expect(error.status).toBe(409);
    expect(error.reason).toBe("orchestrator_requires_azure_search");
    // 409 is a 4xx -> non-retryable -> exactly one fetch.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to a generic status message when the error body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("<html>502 Bad Gateway</html>", {
        status: 502,
        headers: { "Content-Type": "text/html" },
      }),
    );
    await expect(
      collect(streamChat([], { maxRetries: 0 })),
    ).rejects.toThrow(/SSE request failed with status 502/);
  });

  it("retries on a network error from fetch() and succeeds on the next attempt", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: answer\ndata: {"content":"ok-after-retry","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(
      streamChat([], { maxRetries: 2, baseDelayMs: 1 }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(events).toEqual([
      { channel: "answer", content: "ok-after-retry", metadata: {} },
    ]);
  });

  it("retries on a 5xx response and succeeds on the next attempt", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([], { status: 503 }));
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: answer\ndata: {"content":"ok-after-503","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(
      streamChat([], { maxRetries: 2, baseDelayMs: 1 }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(events).toEqual([
      { channel: "answer", content: "ok-after-503", metadata: {} },
    ]);
  });

  it("throws after exhausting the retry budget on repeated network errors", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(
      collect(streamChat([], { maxRetries: 2, baseDelayMs: 1 })),
    ).rejects.toThrow(/Failed to fetch|SSE request failed/);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not retry once the stream has started yielding events", async () => {
    // First attempt: deliver one frame then error the underlying stream.
    let pulls = 0;
    const droppingStream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (pulls === 0) {
          controller.enqueue(
            enc.encode(
              'event: answer\ndata: {"content":"partial","metadata":{}}\n\n',
            ),
          );
          pulls += 1;
        } else {
          controller.error(new Error("connection reset"));
        }
      },
    });
    fetchMock.mockResolvedValueOnce(
      new Response(droppingStream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const seen: StreamEvent[] = [];
    await expect(
      (async () => {
        for await (const ev of streamChat([], {
          maxRetries: 2,
          baseDelayMs: 1,
        })) {
          seen.push(ev);
        }
      })(),
    ).rejects.toThrow(/connection reset|interrupted/);
    expect(seen).toEqual([
      { channel: "answer", content: "partial", metadata: {} },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("honors maxRetries: 0 by performing a single attempt", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(
      collect(streamChat([], { maxRetries: 0, baseDelayMs: 1 })),
    ).rejects.toThrow(/Failed to fetch|SSE request failed/);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("forwards the AbortSignal to fetch()", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    const controller = new AbortController();
    await collect(streamChat([], { signal: controller.signal }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBe(controller.signal);
  });

  it("aborts mid-stream when the AbortSignal fires", async () => {
    // Enqueue exactly one frame in `start`, then expose no `pull` --
    // the reader's second `read()` call hangs forever until the signal
    // races it down via `streamChat`'s signal-aware read wrapper.
    let cancelled = false;
    const hangingStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          enc.encode(
            'event: answer\ndata: {"content":"hi","metadata":{}}\n\n',
          ),
        );
      },
      cancel() {
        cancelled = true;
      },
    });
    fetchMock.mockResolvedValueOnce(
      new Response(hangingStream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const controller = new AbortController();
    const seen: StreamEvent[] = [];
    const drained = (async () => {
      for await (const ev of streamChat([], { signal: controller.signal })) {
        seen.push(ev);
        if (seen.length === 1) {
          controller.abort();
        }
      }
    })();

    await expect(drained).rejects.toThrow(/abort|cancel/i);
    expect(seen).toEqual([
      { channel: "answer", content: "hi", metadata: {} },
    ]);
    expect(cancelled).toBe(true);
  });

  it("aborts during backoff delay between retry attempts", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    // The second attempt should never run because the signal fires
    // before the backoff timer elapses.
    fetchMock.mockResolvedValue(
      sseResponse([
        'event: answer\ndata: {"content":"should-not-arrive","metadata":{}}\n\n',
      ]),
    );

    const controller = new AbortController();
    const drained = collect(
      streamChat([], {
        maxRetries: 5,
        baseDelayMs: 10_000,
        signal: controller.signal,
      }),
    );
    // Let the first attempt's rejection surface and the backoff begin.
    await new Promise((resolve) => setTimeout(resolve, 10));
    controller.abort();

    await expect(drained).rejects.toThrow(/abort|cancel/i);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects synchronously when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(
      collect(streamChat([], { signal: controller.signal })),
    ).rejects.toThrow(/abort|cancel/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ignores frames with unknown channels (defensive forward-compat)", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: futureChannel\ndata: {"content":"x","metadata":{}}\n\n' +
          'event: answer\ndata: {"content":"ok","metadata":{}}\n\n',
      ]),
    );
    const events = await collect(streamChat([]));
    expect(events).toEqual([
      { channel: "answer", content: "ok", metadata: {} },
    ]);
  });

  it("sends conversation_id in the POST body when conversationId is provided", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    await collect(
      streamChat([{ role: "user", content: "hi" }], {
        conversationId: "conv-42",
      }),
    );
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      messages: [{ role: "user", content: "hi" }],
      conversation_id: "conv-42",
    });
  });

  it("omits conversation_id from the body when conversationId is null", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    await collect(
      streamChat([{ role: "user", content: "hi" }], { conversationId: null }),
    );
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body).toEqual({ messages: [{ role: "user", content: "hi" }] });
    expect("conversation_id" in body).toBe(false);
  });

  it("invokes onConversationId with the id from the terminal conversation frame", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: answer\ndata: {"content":"hello","metadata":{}}\n\n',
        'event: conversation\ndata: {"conversation_id":"conv-new"}\n\n',
      ]),
    );
    const ids: string[] = [];
    const events = await collect(
      streamChat([], {
        onConversationId: (id) => {
          ids.push(id);
        },
      }),
    );
    // The conversation frame is a transport-control event, never yielded
    // as a StreamEvent (Hard Rule #6 channel lock).
    expect(events).toEqual([
      { channel: "answer", content: "hello", metadata: {} },
    ]);
    expect(ids).toEqual(["conv-new"]);
  });

  it("drops the terminal conversation frame from the event stream", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: answer\ndata: {"content":"done","metadata":{}}\n\n',
        'event: conversation\ndata: {"conversation_id":"conv-x"}\n\n',
      ]),
    );
    // No onConversationId callback supplied -- the frame is still dropped.
    const events = await collect(streamChat([]));
    expect(events).toEqual([
      { channel: "answer", content: "done", metadata: {} },
    ]);
  });

  it("ignores a conversation frame with a missing or empty id", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: conversation\ndata: {"conversation_id":""}\n\n' +
          "event: conversation\ndata: {}\n\n",
      ]),
    );
    const ids: string[] = [];
    const events = await collect(
      streamChat([], {
        onConversationId: (id) => {
          ids.push(id);
        },
      }),
    );
    expect(events).toEqual([]);
    expect(ids).toEqual([]);
  });

  it("buffers a conversation frame split across chunk boundaries", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: conversation\ndata: {"conversa',
        'tion_id":"conv-split"}\n\n',
      ]),
    );
    const ids: string[] = [];
    await collect(
      streamChat([], {
        onConversationId: (id) => {
          ids.push(id);
        },
      }),
    );
    expect(ids).toEqual(["conv-split"]);
  });

  it("prepends VITE_BACKEND_URL to the conversation request URL", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://backend.example.com");
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    await collect(streamChat([]));
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://backend.example.com/api/conversation");
  });

  it("prefers the runtime /config backendUrl over the env fallback", async () => {
    // The runtime origin from /config must win over build-time
    // VITE_BACKEND_URL so the deployed split-host SPA streams from the
    // backend Container App resolved at boot.
    vi.stubEnv("VITE_BACKEND_URL", "https://build-time.example.com");
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/config") {
        return new Response(
          JSON.stringify({ backendUrl: "https://runtime.example.com" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return sseResponse([]);
    });
    await loadRuntimeConfig();
    await collect(streamChat([]));
    const conversationCall = fetchMock.mock.calls.find(
      ([callUrl]) => callUrl === "https://runtime.example.com/api/conversation",
    );
    expect(conversationCall).toBeDefined();
  });
});
