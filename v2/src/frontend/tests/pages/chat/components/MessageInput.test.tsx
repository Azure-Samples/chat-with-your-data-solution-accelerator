import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  ChatProvider,
  useChat,
} from "../../../../src/pages/chat/ChatContext";
import { MessageInput } from "../../../../src/pages/chat/components/MessageInput";
import { streamChat, type StreamEvent } from "../../../../src/api/streamChat";

vi.mock("../../../../src/api/streamChat", () => ({
  streamChat: vi.fn(),
}));

const streamChatMock = vi.mocked(streamChat);

function probeMessages() {
  return JSON.parse(screen.getByTestId("probe").textContent ?? "[]");
}

function Probe() {
  const { state } = useChat();
  return <div data-testid="probe">{JSON.stringify(state.messages)}</div>;
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
    const call = streamChatMock.mock.calls[0][0];
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
    const secondCall = streamChatMock.mock.calls[1][0];
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

  it("ignores citation and tool frames (out of scope for the demo)", async () => {
    streamChatMock.mockReturnValue(
      iterableOf([
        { channel: "citation", content: "", metadata: { id: "c1" } },
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

  it("disables the input and Send button while streaming, re-enables on finish", async () => {
    const def = deferredIterable();
    streamChatMock.mockReturnValue(def.iterable);
    renderInput();
    await submit("hi");

    await waitFor(() => {
      expect(getField()).toBeDisabled();
      expect(getSend()).toBeDisabled();
    });

    act(() => def.end());
    await waitFor(() => {
      expect(getField()).not.toBeDisabled();
    });
    // Send stays disabled because draft is empty after submit.
    expect(getSend()).toBeDisabled();
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
