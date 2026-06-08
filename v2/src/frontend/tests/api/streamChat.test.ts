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
import { streamChat, type StreamEvent } from "../../src/api/streamChat";

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
    expect(events[0]?.channel).toBe("citation");
    expect(events[0]?.metadata).toEqual({ id: "c1", title: "Doc" });
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

  it("throws when the response is not 2xx", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([], { status: 500 }));
    await expect(collect(streamChat([]))).rejects.toThrow(/500/);
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
