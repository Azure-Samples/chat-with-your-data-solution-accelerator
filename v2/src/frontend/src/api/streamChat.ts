/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
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
 */

export type StreamChannel =
  | "reasoning"
  | "tool"
  | "answer"
  | "citation"
  | "error";

const KNOWN_CHANNELS: ReadonlySet<StreamChannel> = new Set<StreamChannel>([
  "reasoning",
  "tool",
  "answer",
  "citation",
  "error",
]);

export interface StreamMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface StreamEvent {
  channel: StreamChannel;
  content: string;
  metadata: Record<string, unknown>;
}

const CONVERSATION_URL = "/api/conversation";

/**
 * Open an SSE stream against the conversation endpoint and yield typed
 * events as they arrive. The function buffers across chunk boundaries
 * so a frame split mid-line by the HTTP transport is reassembled
 * before being parsed. Frames carrying an unknown `event:` channel are
 * silently dropped — forward-compatible with new backend channels
 * added later.
 *
 * @throws Error when the response status is not 2xx.
 */
export async function* streamChat(
  messages: StreamMessage[],
): AsyncIterable<StreamEvent> {
  const response = await fetch(CONVERSATION_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ messages }),
  });

  if (!response.ok) {
    throw new Error(
      `streamChat: SSE request failed with status ${response.status}`,
    );
  }
  if (response.body === null) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
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
