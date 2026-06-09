/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
 *
 * Vitest suite for the SSE client utility `streamChat()`. The util is
 * the only piece that talks to `POST /api/conversation` over
 * `text/event-stream`; everything in the chat UI consumes the typed
 * event stream it yields. We mock global `fetch` with a
 * `ReadableStream`-bodied `Response` so the tests exercise the real
 * SSE line parser (no network).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "@/api/streamChat";
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
    vi.restoreAllMocks();
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
    // Enqueue exactly one frame in `start`, then expose no `pull` —
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
});
