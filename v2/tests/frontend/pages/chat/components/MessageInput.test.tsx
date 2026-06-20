import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  ChatProvider,
  useChat,
} from "@/pages/chat/ChatContext";
import { MessageInput } from "@/pages/chat/components/MessageInput";
import { streamChat } from "@/api/streamChat";
import type { StreamEvent } from "@/models/chat";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

vi.mock("@/api/streamChat", () => ({
  streamChat: vi.fn(),
}));

vi.mock("@/hooks/useSpeechRecognition", () => ({
  useSpeechRecognition: vi.fn(),
}));

const streamChatMock = vi.mocked(streamChat);
const useSpeechRecognitionMock = vi.mocked(useSpeechRecognition);

// Default speech state — idle, no transcript, no error. Individual
// tests can override via `useSpeechRecognitionMock.mockReturnValue(...)`
// before the render call.
const defaultSpeechStub = {
  isListening: false,
  transcript: "",
  error: null,
  start: vi.fn(async () => {}),
  stop: vi.fn(async () => {}),
};

beforeEach(() => {
  useSpeechRecognitionMock.mockReturnValue({ ...defaultSpeechStub });
});

function probeMessages() {
  return JSON.parse(screen.getByTestId("probe").textContent ?? "[]");
}

function probeConversationId(): string {
  return screen.getByTestId("conversation-id-probe").textContent ?? "";
}

function Probe() {
  const { state } = useChat();
  return (
    <>
      <div data-testid="probe">{JSON.stringify(state.messages)}</div>
      <div data-testid="conversation-id-probe">
        {state.conversationId ?? "null"}
      </div>
    </>
  );
}

function renderInput() {
  return render(
    <ChatProvider>
      <MessageInput />
      <Probe />
    </ChatProvider>,
  );
}

function getField(): HTMLInputElement {
  return screen.getByLabelText(/message/i) as HTMLInputElement;
}

function getSend(): HTMLButtonElement {
  return screen.getByRole("button", { name: /send/i }) as HTMLButtonElement;
}

/** Async iterable that yields the given events in order, then completes. */
function iterableOf(events: StreamEvent[]): AsyncIterable<StreamEvent> {
  return {
    async *[Symbol.asyncIterator]() {
      for (const event of events) {
        yield event;
      }
    },
  };
}

/** Manually-driven async iterable so tests can interleave assertions. */
function deferredIterable(): {
  iterable: AsyncIterable<StreamEvent>;
  emit: (event: StreamEvent) => void;
  end: () => void;
} {
  const queue: StreamEvent[] = [];
  let resolveNext: (() => void) | null = null;
  let ended = false;

  function notify() {
    if (resolveNext !== null) {
      const fn = resolveNext;
      resolveNext = null;
      fn();
    }
  }

  const iterable: AsyncIterable<StreamEvent> = {
    async *[Symbol.asyncIterator]() {
      while (true) {
        if (queue.length > 0) {
          yield queue.shift()!;
          continue;
        }
        if (ended) return;
        await new Promise<void>((resolve) => {
          resolveNext = resolve;
        });
      }
    },
  };

  return {
    iterable,
    emit(event) {
      queue.push(event);
      notify();
    },
    end() {
      ended = true;
      notify();
    },
  };
}

async function submit(text: string) {
  fireEvent.change(getField(), { target: { value: text } });
  fireEvent.click(getSend());
}

describe("MessageInput (preserved behavior)", () => {
  beforeEach(() => {
    streamChatMock.mockReturnValue(iterableOf([]));
  });

  afterEach(() => {
    streamChatMock.mockReset();
  });

  it("disables Send when the draft is empty or whitespace", () => {
    renderInput();
    expect(getSend()).toBeDisabled();
    fireEvent.change(getField(), { target: { value: "   " } });
    expect(getSend()).toBeDisabled();
  });

  it("dispatches a user message on submit and clears the input", async () => {
    renderInput();
    const field = getField();
    await submit("hello world");

    await waitFor(() => {
      const probe = probeMessages();
      // Now expects user msg + assistant placeholder.
      expect(probe).toHaveLength(2);
      expect(probe[0]).toMatchObject({ role: "user", content: "hello world" });
      expect(probe[1]).toMatchObject({ role: "assistant" });
      expect(typeof probe[0].id).toBe("string");
      expect(probe[0].id.length).toBeGreaterThan(0);
    });
    expect(field.value).toBe("");
  });

  it("trims whitespace before dispatching", async () => {
    renderInput();
    await submit("   hi   ");
    await waitFor(() => {
      expect(probeMessages()[0].content).toBe("hi");
    });
  });

  it("does not dispatch when the form is submitted with an empty draft", () => {
    renderInput();
    fireEvent.submit(screen.getByTestId("message-input"));
    expect(probeMessages()).toEqual([]);
    expect(streamChatMock).not.toHaveBeenCalled();
  });
});

describe("MessageInput SSE wiring", () => {
  beforeEach(() => {
    streamChatMock.mockReset();
  });

  afterEach(() => {
    streamChatMock.mockReset();
  });

  it("calls streamChat with the conversation history including the new user msg", async () => {
    streamChatMock.mockReturnValue(iterableOf([]));
    renderInput();
    await submit("first question");

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(1);
    });
    const call = streamChatMock.mock.calls[0]![0];
    expect(call).toEqual([{ role: "user", content: "first question" }]);
  });

  it("appends previous turns to the streamChat payload on the second submit", async () => {
    streamChatMock.mockReturnValueOnce(
      iterableOf([{ channel: "answer", content: "ok", metadata: {} }]),
    );
    streamChatMock.mockReturnValueOnce(iterableOf([]));

    renderInput();
    await submit("first");
    await waitFor(() => {
      const probe = probeMessages();
      expect(probe).toHaveLength(2);
      expect(probe[1].streaming).toBe(false);
      expect(probe[1].content).toBe("ok");
    });

    await submit("second");
    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(2);
    });
    const secondCall = streamChatMock.mock.calls[1]![0];
    expect(secondCall).toEqual([
      { role: "user", content: "first" },
      { role: "assistant", content: "ok" },
      { role: "user", content: "second" },
    ]);
  });

  it("seeds an assistant placeholder with streaming=true and reasoning=[]", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("hi");

    await waitFor(() => {
      const probe = probeMessages();
      expect(probe).toHaveLength(2);
      expect(probe[1]).toMatchObject({
        role: "assistant",
        content: "",
        reasoning: [],
        streaming: true,
      });
    });

    act(() => def.end());
    await waitFor(() => {
      expect(probeMessages()[1].streaming).toBe(false);
    });
  });

  it("appends answer chunks into the assistant message content", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("hi");

    act(() => def.emit({ channel: "answer", content: "Hel", metadata: {} }));
    act(() => def.emit({ channel: "answer", content: "lo", metadata: {} }));
    await waitFor(() => {
      expect(probeMessages()[1].content).toBe("Hello");
    });

    act(() => def.end());
    await waitFor(() => {
      expect(probeMessages()[1].streaming).toBe(false);
    });
  });

  it("collects reasoning frames into the reasoning array", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("hi");

    act(() =>
      def.emit({ channel: "reasoning", content: "step 1", metadata: {} }),
    );
    act(() =>
      def.emit({ channel: "reasoning", content: "step 2", metadata: {} }),
    );
    await waitFor(() => {
      expect(probeMessages()[1].reasoning).toEqual(["step 1", "step 2"]);
    });

    act(() => def.end());
  });

  it("routes a placeholder reasoning frame to reasoningPlaceholder, not reasoning", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("hi");

    act(() =>
      def.emit({
        channel: "reasoning",
        content: "Searching the knowledge base for relevant sources\u2026",
        metadata: { placeholder: true },
      }),
    );
    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.reasoningPlaceholder).toBe(
        "Searching the knowledge base for relevant sources\u2026",
      );
      expect(m.reasoning).toEqual([]);
    });

    act(() =>
      def.emit({ channel: "reasoning", content: "real thinking", metadata: {} }),
    );
    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.reasoning).toEqual(["real thinking"]);
      expect(m.reasoningPlaceholder).toBe(
        "Searching the knowledge base for relevant sources\u2026",
      );
    });

    act(() => def.end());
  });

  it("ignores tool frames (out of scope for the demo)", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([
        { channel: "tool", content: "ran", metadata: {} },
        { channel: "answer", content: "done", metadata: {} },
      ]),
    );
    renderInput();
    await submit("hi");

    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.streaming).toBe(false);
      expect(m.content).toBe("done");
      expect(m.reasoning).toEqual([]);
    });
  });

  it("dispatches citation frames into the assistant message", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([
        {
          channel: "citation",
          content: "",
          metadata: {
            id: "doc-a",
            title: "Doc A",
            url: "https://example.com/a",
            snippet: "snippet a",
            score: 0.42,
            metadata: { source: "blob" },
          },
        },
        {
          channel: "citation",
          content: "",
          metadata: {
            id: "doc-b",
            title: "Doc B",
            url: "https://example.com/b",
            snippet: "snippet b",
          },
        },
        { channel: "answer", content: "done", metadata: {} },
      ]),
    );
    renderInput();
    await submit("hi");

    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.streaming).toBe(false);
      expect(m.citations).toHaveLength(2);
      expect(m.citations[0]).toEqual({
        id: "doc-a",
        title: "Doc A",
        url: "https://example.com/a",
        snippet: "snippet a",
        score: 0.42,
        metadata: { source: "blob" },
      });
      expect(m.citations[1]).toEqual({
        id: "doc-b",
        title: "Doc B",
        url: "https://example.com/b",
        snippet: "snippet b",
        score: null,
        metadata: {},
      });
    });
  });

  it("drops citation frames that arrive without an id", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([
        {
          channel: "citation",
          content: "",
          metadata: { title: "Untyped doc", url: "https://example.com/x" },
        },
        { channel: "answer", content: "done", metadata: {} },
      ]),
    );
    renderInput();
    await submit("hi");

    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.streaming).toBe(false);
      // The malformed frame was dropped, so no citations array landed.
      expect(m.citations ?? []).toEqual([]);
    });
  });

  it("surfaces an error frame as an inline error and clears streaming", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([{ channel: "error", content: "boom", metadata: {} }]),
    );
    renderInput();
    await submit("hi");

    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.error).toBe("boom");
      expect(m.streaming).toBe(false);
    });
  });

  it("surfaces a thrown fetch error as an inline error", async () => {
    streamChatMock.mockImplementation(() => {
      throw new Error("network down");
    });
    renderInput();
    await submit("hi");

    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.error).toContain("network down");
      expect(m.streaming).toBe(false);
    });
  });

  it("disables the input while streaming and swaps Send for a Cancel button", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("hi");

    await waitFor(() => {
      expect(getField()).toBeDisabled();
      // Send is hidden mid-stream; Cancel takes its place.
      expect(
        screen.queryByRole("button", { name: /^send$/i }),
      ).toBeNull();
      const cancel = screen.getByTestId(
        "message-input-cancel",
      ) as HTMLButtonElement;
      expect(cancel).toBeEnabled();
    });

    act(() => def.end());
    await waitFor(() => {
      expect(getField()).not.toBeDisabled();
    });
    // Send is back; disabled because draft is empty after submit.
    expect(getSend()).toBeDisabled();
    expect(screen.queryByTestId("message-input-cancel")).toBeNull();
  });

  it("does not re-trigger streamChat while a stream is in flight", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("first");

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(1);
    });

    // Even if the form receives a second submit (e.g. Enter key) mid-stream,
    // canSend must guard against re-entry.
    fireEvent.submit(screen.getByTestId("message-input"));
    expect(streamChatMock).toHaveBeenCalledTimes(1);

    act(() => def.end());
  });
});

describe("MessageInput cancel button", () => {
  beforeEach(() => {
    streamChatMock.mockReset();
  });

  afterEach(() => {
    streamChatMock.mockReset();
  });

  function getCancel(): HTMLButtonElement {
    return screen.getByTestId(
      "message-input-cancel",
    ) as HTMLButtonElement;
  }

  it("forwards a fresh AbortSignal on every submit", async () => {
    streamChatMock.mockReturnValueOnce(
      iterableOf([{ channel: "answer", content: "a", metadata: {} }]),
    );
    streamChatMock.mockReturnValueOnce(
      iterableOf([{ channel: "answer", content: "b", metadata: {} }]),
    );

    renderInput();
    await submit("first");
    await waitFor(() => {
      expect(probeMessages()[1].streaming).toBe(false);
    });

    await submit("second");
    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(2);
    });

    const firstOpts = streamChatMock.mock.calls[0]![1];
    const secondOpts = streamChatMock.mock.calls[1]![1];
    expect(firstOpts?.signal).toBeInstanceOf(AbortSignal);
    expect(secondOpts?.signal).toBeInstanceOf(AbortSignal);
    expect(firstOpts?.signal).not.toBe(secondOpts?.signal);
  });

  it("aborts the in-flight stream when Cancel is clicked", async () => {
    const def = deferredIterable();
    let capturedSignal: AbortSignal | undefined;
    streamChatMock.mockImplementation((_msgs, opts) => {
      capturedSignal = opts?.signal;
      return def.iterable;
    });

    renderInput();
    await submit("hi");
    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(1);
    });
    expect(capturedSignal?.aborted).toBe(false);

    fireEvent.click(getCancel());
    expect(capturedSignal?.aborted).toBe(true);

    // Simulate streamChat reacting to the abort by throwing AbortError,
    // matching the real implementation's contract.
    act(() => {
      def.end();
    });
  });

  it("treats AbortError as a clean stop (no error toast, partial content kept)", async () => {
    streamChatMock.mockImplementation(() => ({
      async *[Symbol.asyncIterator]() {
        yield { channel: "answer", content: "partial", metadata: {} };
        throw new DOMException("streamChat aborted", "AbortError");
      },
    }));

    renderInput();
    await submit("hi");

    await waitFor(() => {
      const m = probeMessages()[1];
      expect(m.streaming).toBe(false);
      expect(m.content).toBe("partial");
      expect(m.error ?? null).toBeNull();
    });
  });
});

describe("MessageInput conversation-id wiring", () => {
  beforeEach(() => {
    streamChatMock.mockReset();
  });

  afterEach(() => {
    streamChatMock.mockReset();
  });

  it("sends conversationId: null to streamChat on a fresh chat", async () => {
    streamChatMock.mockReturnValue(iterableOf([]));
    renderInput();
    await submit("first question");

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(1);
    });
    const opts = streamChatMock.mock.calls[0]![1];
    expect(opts?.conversationId).toBeNull();
  });

  it("records the backend conversation id from the onConversationId callback", async () => {
    streamChatMock.mockImplementation((_msgs, opts) => ({
      async *[Symbol.asyncIterator]() {
        yield { channel: "answer", content: "hi", metadata: {} };
        opts?.onConversationId?.("conv-7");
      },
    }));

    renderInput();
    expect(probeConversationId()).toBe("null");
    await submit("hello");

    await waitFor(() => {
      expect(probeConversationId()).toBe("conv-7");
    });
  });

  it("continues the same conversation on the next submit", async () => {
    streamChatMock.mockImplementationOnce((_msgs, opts) => ({
      async *[Symbol.asyncIterator]() {
        yield { channel: "answer", content: "first", metadata: {} };
        opts?.onConversationId?.("conv-9");
      },
    }));
    streamChatMock.mockReturnValueOnce(iterableOf([]));

    renderInput();
    await submit("first");
    await waitFor(() => {
      expect(probeMessages()[1].streaming).toBe(false);
    });
    await waitFor(() => {
      expect(probeConversationId()).toBe("conv-9");
    });

    await submit("second");
    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(2);
    });
    // The id recorded from the first stream is re-sent so the backend
    // appends the second turn to the same conversation.
    expect(streamChatMock.mock.calls[1]![1]?.conversationId).toBe("conv-9");
  });

  it("starts a fresh conversation (conversationId: null) after a reset", async () => {
    streamChatMock.mockImplementationOnce((_msgs, opts) => ({
      async *[Symbol.asyncIterator]() {
        yield { channel: "answer", content: "hi", metadata: {} };
        opts?.onConversationId?.("conv-3");
      },
    }));
    streamChatMock.mockReturnValueOnce(iterableOf([]));

    renderInput();
    await submit("first");
    await waitFor(() => {
      expect(probeConversationId()).toBe("conv-3");
    });

    fireEvent.click(screen.getByTestId("message-input-clear"));
    await waitFor(() => {
      expect(probeConversationId()).toBe("null");
    });

    await submit("second");
    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(2);
    });
    expect(streamChatMock.mock.calls[1]![1]?.conversationId).toBeNull();
  });
});

describe("MessageInput clear-conversation button", () => {
  beforeEach(() => {
    streamChatMock.mockReset();
  });

  afterEach(() => {
    streamChatMock.mockReset();
  });

  function getClear(): HTMLButtonElement {
    return screen.getByTestId(
      "message-input-clear",
    ) as HTMLButtonElement;
  }

  it("renders a clear-conversation button that is disabled while the transcript is empty", () => {
    streamChatMock.mockReturnValue(iterableOf([]));
    renderInput();
    const clear = getClear();
    expect(clear.getAttribute("aria-label")).toMatch(/new conversation/i);
    expect(clear).toBeDisabled();
  });

  it("enables Clear once at least one message has landed in the transcript", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([{ channel: "answer", content: "hi", metadata: {} }]),
    );
    renderInput();
    await submit("hello");
    await waitFor(() => {
      expect(probeMessages()).toHaveLength(2);
    });
    expect(getClear()).toBeEnabled();
  });

  it("clears the transcript when clicked", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([{ channel: "answer", content: "hi", metadata: {} }]),
    );
    renderInput();
    await submit("hello");
    await waitFor(() => {
      expect(probeMessages()).toHaveLength(2);
    });

    fireEvent.click(getClear());
    await waitFor(() => {
      expect(probeMessages()).toEqual([]);
    });
    expect(getClear()).toBeDisabled();
  });

  it("is disabled while a stream is in flight (even with prior messages)", async () => {
    // First submit completes so the transcript has content.
    streamChatMock.mockReturnValueOnce(
      iterableOf([{ channel: "answer", content: "hi", metadata: {} }]),
    );
    // Second submit hangs so we can observe the streaming state.
    const def = deferredIterable();
    streamChatMock.mockReturnValueOnce(def.iterable);

    renderInput();
    await submit("first");
    await waitFor(() => {
      expect(probeMessages()).toHaveLength(2);
    });
    expect(getClear()).toBeEnabled();

    await submit("second");
    await waitFor(() => {
      expect(getClear()).toBeDisabled();
    });

    act(() => def.end());
  });
});

describe("MessageInput mic button (S1 / SPEECH-MVP)", () => {
  beforeEach(() => {
    streamChatMock.mockReturnValue(iterableOf([]));
  });

  afterEach(() => {
    streamChatMock.mockReset();
  });

  function getMic(): HTMLButtonElement {
    return screen.getByTestId("message-input-mic") as HTMLButtonElement;
  }

  it("renders an idle mic button (aria-pressed=false) by default", () => {
    renderInput();
    const mic = getMic();
    expect(mic).toBeEnabled();
    expect(mic.getAttribute("aria-pressed")).toBe("false");
    expect(mic.getAttribute("aria-label")).toMatch(/start dictation/i);
  });

  it("calls hook.start() when the mic is clicked while idle", async () => {
    const start = vi.fn(async () => {});
    useSpeechRecognitionMock.mockReturnValue({
      ...defaultSpeechStub,
      start,
    });

    renderInput();
    fireEvent.click(getMic());
    await waitFor(() => {
      expect(start).toHaveBeenCalledTimes(1);
    });
  });

  it("flips to aria-pressed=true and calls hook.stop() while listening", async () => {
    const stop = vi.fn(async () => {});
    useSpeechRecognitionMock.mockReturnValue({
      ...defaultSpeechStub,
      isListening: true,
      stop,
    });

    renderInput();
    const mic = getMic();
    expect(mic.getAttribute("aria-pressed")).toBe("true");
    expect(mic.getAttribute("aria-label")).toMatch(/stop dictation/i);
    expect(getField()).toBeDisabled();

    fireEvent.click(mic);
    await waitFor(() => {
      expect(stop).toHaveBeenCalledTimes(1);
    });
  });

  it("streams the transcript into the draft input while listening", () => {
    useSpeechRecognitionMock.mockReturnValue({
      ...defaultSpeechStub,
      isListening: true,
      transcript: "hello world",
    });

    renderInput();
    expect(getField().value).toBe("hello world");
  });

  it("disables the mic button when the hook reports an error", () => {
    useSpeechRecognitionMock.mockReturnValue({
      ...defaultSpeechStub,
      error: "mic permission denied",
    });

    renderInput();
    const mic = getMic();
    expect(mic).toBeDisabled();
    expect(mic.getAttribute("aria-label")).toMatch(/permission denied/i);
  });

  it("disables Send while listening even when the draft is non-empty", () => {
    useSpeechRecognitionMock.mockReturnValue({
      ...defaultSpeechStub,
      isListening: true,
      transcript: "something to send",
    });

    renderInput();
    expect(getField().value).toBe("something to send");
    expect(getSend()).toBeDisabled();
  });
});
