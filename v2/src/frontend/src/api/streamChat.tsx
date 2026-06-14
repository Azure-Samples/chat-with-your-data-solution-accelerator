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
 *
 * Cancellation: the optional `signal` honours the standard
 * `AbortController` contract. When the signal fires, the in-flight
 * `fetch()` is aborted, the underlying body stream is cancelled, any
 * pending backoff delay rejects early, and the async iterator throws
 * an `AbortError` so the caller can distinguish user-initiated cancel
 * from a network failure.
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
  /**
   * Optional `AbortSignal` for user-initiated cancellation. When it
   * fires, the in-flight request is aborted and the iterator throws
   * an `AbortError`.
   */
  signal?: AbortSignal;
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
  const signal = options.signal;

  throwIfAborted(signal);

  for (let attempt = 0; ; attempt++) {
    let yieldedAny = false;
    try {
      for await (const ev of streamChatOnce(messages, signal)) {
        yieldedAny = true;
        yield ev;
      }
      return;
    } catch (err) {
      // An abort always wins — never retry, never wrap it as a network
      // failure, even when the SDK error path bubbled up first.
      if (signal?.aborted === true || isAbortError(err)) {
        throw abortError();
      }
      const retryable = err instanceof RetryableStreamError;
      if (!retryable || yieldedAny || attempt >= maxRetries) {
        throw err;
      }
      await sleep(baseDelayMs * 2 ** attempt, signal);
    }
  }
}

async function* streamChatOnce(
  messages: StreamMessage[],
  signal: AbortSignal | undefined,
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
      ...(signal ? { signal } : {}),
    });
  } catch (cause) {
    if (isAbortError(cause)) throw cause;
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

  try {
    for (;;) {
      if (signal?.aborted === true) throw abortError();
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await raceWithSignal(reader.read(), signal);
      } catch (cause) {
        if (isAbortError(cause)) throw cause;
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
  } finally {
    // Best-effort: release the underlying body so the connection can
    // be torn down on abort or early return.
    try {
      await reader.cancel();
    } catch {
      // Ignore — cancel can reject if the stream is already closed.
    }
  }
}

function raceWithSignal<T>(
  promise: Promise<T>,
  signal: AbortSignal | undefined,
): Promise<T> {
  if (signal === undefined) return promise;
  return new Promise<T>((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError());
      return;
    }
    const onAbort = (): void => {
      reject(abortError());
    };
    signal.addEventListener("abort", onAbort, { once: true });
    promise.then(
      (value) => {
        signal.removeEventListener("abort", onAbort);
        resolve(value);
      },
      (cause: unknown) => {
        signal.removeEventListener("abort", onAbort);
        reject(cause instanceof Error ? cause : new Error(String(cause)));
      },
    );
  });
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted === true) {
      reject(abortError());
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function throwIfAborted(signal: AbortSignal | undefined): void {
  if (signal?.aborted === true) {
    throw abortError();
  }
}

function isAbortError(err: unknown): boolean {
  return (
    typeof DOMException !== "undefined" &&
    err instanceof DOMException &&
    err.name === "AbortError"
  );
}

function abortError(): DOMException {
  return new DOMException("streamChat aborted", "AbortError");
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
