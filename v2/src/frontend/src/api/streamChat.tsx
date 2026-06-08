/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half) +
 *        7 (Testing + Documentation — SSE resilience: retry-with-backoff
 *           on transient connection failures)
 *
 * SSE client utility for `POST /api/conversation`. The backend emits
 * Server-Sent Events on the locked channel set defined in
 * `backend/core/types.py::OrchestratorChannel` (ADR 0007):
 *
 *     event: <channel>\n
 *     data:  {"content": "...", "metadata": {...}}\n\n
 *
 * `streamChat()` returns an async iterator of typed events so the
 * chat UI can fan-out into the right surfaces (answer text, the
 * collapsible reasoning panel, citations, error notice). This module
 * is a pure utility: no React imports, no DOM.
 *
 * Resilience: a transient connection failure that happens before any
 * event has been yielded — `fetch()` rejecting with a network error,
 * or the server responding with a 5xx — is retried with exponential
 * backoff up to `maxRetries` additional attempts (default 2; total
 * up to 3 attempts). 4xx responses are non-retryable and bubble up
 * immediately. Failures that happen AFTER the first event has been
 * yielded are surfaced to the caller as a thrown error rather than
 * silently re-invoking the LLM, since the in-flight assistant turn
 * is already partially visible to the user and a fresh attempt would
 * either duplicate output or stitch together two unrelated answers.
 */
import { StreamChannel } from "@/models/chat";
import type { StreamEvent, StreamMessage } from "@/models/chat";

const KNOWN_CHANNELS: ReadonlySet<StreamChannel> = new Set(
  Object.values(StreamChannel),
);

const CONVERSATION_URL = "/api/conversation";
const DEFAULT_MAX_RETRIES = 2;
const DEFAULT_BASE_DELAY_MS = 500;

export interface StreamChatOptions {
  /**
   * Number of additional attempts after the first one when a retryable
   * failure surfaces before any event is yielded. `maxRetries: 0`
   * disables retry. Default 2 → up to 3 total attempts.
   */
  maxRetries?: number;
  /**
   * Base backoff in milliseconds. The delay before attempt `n` is
   * `baseDelayMs * 2 ** n` (so 500 / 1000 / 2000 / ... with the
   * default). Default 500.
   */
  baseDelayMs?: number;
}

/** Connection-class failure: safe to retry if nothing has been yielded yet. */
class RetryableStreamError extends Error {}
/** Permanent failure (e.g. 4xx): never retry. */
class NonRetryableStreamError extends Error {}

/**
 * Open an SSE stream against the conversation endpoint and yield typed
 * events as they arrive. The function buffers across chunk boundaries
 * so a frame split mid-line by the HTTP transport is reassembled
 * before being parsed. Frames carrying an unknown `event:` channel are
 * silently dropped — forward-compatible with new backend channels
 * added later.
 *
 * @throws Error when a non-retryable response (4xx) is returned, when
 *   the retry budget is exhausted on a retryable failure, or when the
 *   connection drops after the first event has already been yielded.
 */
export async function* streamChat(
  messages: StreamMessage[],
  options: StreamChatOptions = {},
): AsyncIterable<StreamEvent> {
  const maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
  const baseDelayMs = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;

  for (let attempt = 0; ; attempt++) {
    let yieldedAny = false;
    try {
      for await (const ev of streamChatOnce(messages)) {
        yieldedAny = true;
        yield ev;
      }
      return;
    } catch (err) {
      const retryable = err instanceof RetryableStreamError;
      if (!retryable || yieldedAny || attempt >= maxRetries) {
        throw err;
      }
      await sleep(baseDelayMs * 2 ** attempt);
    }
  }
}

async function* streamChatOnce(
  messages: StreamMessage[],
): AsyncIterable<StreamEvent> {
  let response: Response;
  try {
    response = await fetch(CONVERSATION_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ messages }),
    });
  } catch (cause) {
    throw new RetryableStreamError(
      `streamChat: SSE request failed before reaching the server (${describeCause(cause)})`,
    );
  }

  if (!response.ok) {
    const ErrCtor =
      response.status >= 500 ? RetryableStreamError : NonRetryableStreamError;
    throw new ErrCtor(
      `streamChat: SSE request failed with status ${String(response.status)}`,
    );
  }

  if (response.body === null) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    let chunk: ReadableStreamReadResult<Uint8Array>;
    try {
      chunk = await reader.read();
    } catch (cause) {
      throw new RetryableStreamError(
        `streamChat: SSE stream interrupted (${describeCause(cause)})`,
      );
    }
    const { done, value } = chunk;
    if (done) {
      // Flush any trailing bytes through the decoder so multibyte
      // characters that straddle the final chunk boundary are emitted.
      buffer += decoder.decode();
      if (buffer.length > 0) {
        const trailing = parseFrame(buffer);
        if (trailing !== null) {
          yield trailing;
        }
      }
      return;
    }
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line (`\n\n`). Anything left
    // in `buffer` after the last separator is a partial frame and is
    // carried over to the next read.
    let separator = buffer.indexOf("\n\n");
    while (separator !== -1) {
      const frame = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const event = parseFrame(frame);
      if (event !== null) {
        yield event;
      }
      separator = buffer.indexOf("\n\n");
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function describeCause(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

interface ParsedPayload {
  content?: unknown;
  metadata?: unknown;
}

function parseFrame(frame: string): StreamEvent | null {
  let channel: string | null = null;
  const dataLines: string[] = [];

  for (const rawLine of frame.split("\n")) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line.length === 0 || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      channel = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (channel === null || !KNOWN_CHANNELS.has(channel as StreamChannel)) {
    return null;
  }
  if (dataLines.length === 0) {
    return null;
  }

  const dataText = dataLines.join("\n");
  let payload: ParsedPayload;
  try {
    payload = JSON.parse(dataText) as ParsedPayload;
  } catch {
    return null;
  }

  const content = typeof payload.content === "string" ? payload.content : "";
  const metadata =
    payload.metadata !== null &&
    typeof payload.metadata === "object" &&
    !Array.isArray(payload.metadata)
      ? (payload.metadata as Record<string, unknown>)
      : {};

  return {
    channel: channel as StreamChannel,
    content,
    metadata,
  };
}
