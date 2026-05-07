import { describe, expect, it } from "vitest";
import { act, render, screen } from "@testing-library/react";
import {
  ChatProvider,
  useChat,
  type ChatMessage,
} from "../../../../src/pages/chat/ChatContext";
import { MessageList } from "../../../../src/pages/chat/components/MessageList";

const m1: ChatMessage = { id: "1", role: "user", content: "hello" };
const m2: ChatMessage = { id: "2", role: "assistant", content: "hi back" };
const mWithReasoning: ChatMessage = {
  id: "3",
  role: "assistant",
  content: "answer body",
  reasoning: ["thinking step 1", "thinking step 2"],
};
const mWithError: ChatMessage = {
  id: "4",
  role: "assistant",
  content: "",
  error: "stream blew up",
};
const mWithEmptyReasoning: ChatMessage = {
  id: "5",
  role: "assistant",
  content: "no reasoning here",
  reasoning: [],
};

function Seed({ messages }: { messages: ChatMessage[] }) {
  const { dispatch } = useChat();
  (Seed as unknown as { _dispatch?: typeof dispatch })._dispatch = dispatch;
  void messages;
  return null;
}

describe("MessageList", () => {
  it("shows empty state when no messages", () => {
    render(
      <ChatProvider>
        <MessageList />
      </ChatProvider>,
    );
    expect(screen.getByTestId("message-list-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("message-list")).toBeNull();
  });

  it("renders one <li> per message in dispatch order", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m1 });
      dispatch({ type: "add", message: m2 });
    });

    const list = screen.getByTestId("message-list");
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("hello");
    expect(items[1].textContent).toContain("hi back");
  });

  it("tags each <li> with its role for styling hooks", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m1 });
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.getByTestId("message-1").getAttribute("data-role")).toBe("user");
    expect(screen.getByTestId("message-2").getAttribute("data-role")).toBe(
      "assistant",
    );
  });

  it("renders a collapsed reasoning <details> panel when reasoning entries exist", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithReasoning });
    });

    const details = screen.getByTestId("message-3-reasoning");
    expect(details.tagName.toLowerCase()).toBe("details");
    expect((details as HTMLDetailsElement).open).toBe(false);
    const summary = details.querySelector("summary");
    expect(summary?.textContent).toBe("\u25B8 Show reasoning");
  });

  it("lists every reasoning entry inside the panel", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithReasoning });
    });

    const details = screen.getByTestId("message-3-reasoning");
    const items = details.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("thinking step 1");
    expect(items[1].textContent).toBe("thinking step 2");
  });

  it("does not render a reasoning panel when reasoning is absent", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.queryByTestId("message-2-reasoning")).toBeNull();
  });

  it("does not render a reasoning panel when reasoning is an empty array", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithEmptyReasoning });
    });

    expect(screen.queryByTestId("message-5-reasoning")).toBeNull();
  });

  it("renders an inline error notice when message.error is set", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithError });
    });

    const notice = screen.getByTestId("message-4-error");
    expect(notice.getAttribute("role")).toBe("alert");
    expect(notice.textContent).toContain("stream blew up");
  });

  it("does not render an error notice when message.error is unset", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.queryByTestId("message-2-error")).toBeNull();
  });
});
