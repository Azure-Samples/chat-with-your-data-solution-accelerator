import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import {
  ChatProvider,
  useChat,
} from "../../../../src/pages/chat/ChatContext";
import { MessageInput } from "../../../../src/pages/chat/components/MessageInput";

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

describe("MessageInput", () => {
  it("disables Send when the draft is empty or whitespace", () => {
    renderInput();
    expect(getSend()).toBeDisabled();
    fireEvent.change(getField(), { target: { value: "   " } });
    expect(getSend()).toBeDisabled();
  });

  it("dispatches a user message on submit and clears the input", () => {
    renderInput();
    const field = getField();
    fireEvent.change(field, { target: { value: "hello world" } });
    fireEvent.click(getSend());

    const probe = JSON.parse(screen.getByTestId("probe").textContent || "[]");
    expect(probe).toHaveLength(1);
    expect(probe[0]).toMatchObject({ role: "user", content: "hello world" });
    expect(typeof probe[0].id).toBe("string");
    expect(probe[0].id.length).toBeGreaterThan(0);
    expect(field.value).toBe("");
  });

  it("trims whitespace before dispatching", () => {
    renderInput();
    fireEvent.change(getField(), { target: { value: "   hi   " } });
    fireEvent.click(getSend());
    const probe = JSON.parse(screen.getByTestId("probe").textContent || "[]");
    expect(probe[0].content).toBe("hi");
  });

  it("does not dispatch when the form is submitted with an empty draft", () => {
    renderInput();
    fireEvent.submit(screen.getByTestId("message-input"));
    expect(screen.getByTestId("probe").textContent).toBe("[]");
  });
});
