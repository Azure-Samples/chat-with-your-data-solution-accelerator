import { render, screen, fireEvent } from "@testing-library/react";
import { QuestionInput } from "./QuestionInput";
import fetch from "isomorphic-fetch";
import userEvent from "@testing-library/user-event";

globalThis.fetch = fetch;

const mockOnSend = jest.fn();
const onStopClick = jest.fn();
const onMicrophoneClick = jest.fn();

describe("QuestionInput Component", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test("renders correctly with placeholder", () => {
    render(
      <QuestionInput
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={""}
        isListening={false}
        isRecognizing={false}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {
          throw new Error("Function not implemented.");
        }}
      />
    );

    expect(screen.getByPlaceholderText("Ask a question")).toBeInTheDocument();
  });

  test("when recognised text passed and listening is true", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={true}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {
          throw new Error("Function not implemented.");
        }}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question");

    expect(screen.getByText("recognized text")).toBeInTheDocument();
  });

  test("does not call onSend when disabled", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={true}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {
          throw new Error("Function not implemented.");
        }}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question");

    // fireEvent.change(input, { target: { value: 'Test question' } })

    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });

    expect(mockOnSend).not.toHaveBeenCalled();
  });

  //----------------

  test("call onSend when not disabled", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {
          throw new Error("Function not implemented.");
        }}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question");

    // fireEvent.change(input, { target: { value: 'Test question' } })

    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });

    expect(mockOnSend).toHaveBeenCalled();
  });

  test("does not clear question input if clearOnSend is false", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question");

    expect(screen.getByText("recognized text")).toBeInTheDocument();

    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });

    expect(input).toHaveValue("");
  });

  test("onQuestion changed for set new value", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question");

    fireEvent.change(input, { target: { value: "newvalue" } });

    expect(input).toHaveValue("newvalue");
  });

  test("onQuestion changed for set new value to be undefined", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question");

    fireEvent.change(input, { target: { value: "" } });

    expect(input).toHaveValue("");
  });

  test("microphone button is disabled", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={true}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const microphonebtn = screen.getByRole("button", {
      name: "Microphone button",
    });

    expect(microphonebtn).toBeDisabled();
  });

  test("Microphone button click onStopClick", async () => {
    userEvent.setup();
    const mockMethod = jest.fn();
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={function (): void {
          throw new Error("Function not implemented.");
        }}
        onStopClick={mockMethod}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={true}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const microphonebtn = screen.getByRole("button", {
      name: "Microphone button",
    });
    await userEvent.click(microphonebtn);

    expect(mockMethod).toHaveBeenCalled();
  });

  test("Microphone button Enter key event", async () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={onMicrophoneClick}
        onStopClick={onStopClick}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={false}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const microphonebtn = screen.getByRole("button", {
      name: "Microphone button",
    });

    microphonebtn.focus();

    // Simulate pressing the Enter key
    await userEvent.keyboard("{enter}");

    expect(onMicrophoneClick).toHaveBeenCalled();
  });

  test("Microphone button click onMicrophoneClick on other key pressed than enter and space bar", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={false}
        placeholder="Ask a question"
        onMicrophoneClick={onMicrophoneClick}
        onStopClick={onStopClick}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={false}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const microphonebtn = screen.getByRole("button", {
      name: "Microphone button",
    });

    fireEvent.keyDown(microphonebtn, { key: "A", code: "A", charCode: 65 });

    expect(onMicrophoneClick).not.toHaveBeenCalled();
  });

  test("send button disabled ", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={true}
        placeholder="Ask a question"
        onMicrophoneClick={onMicrophoneClick}
        onStopClick={onStopClick}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={false}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const sendbtn = screen.getByRole("button", { name: "Ask question button" });

    fireEvent.keyDown(sendbtn, { key: "Enter", code: "Enter", charCode: 13 });

    expect(screen.getByText("recognized text")).toBeInTheDocument();
  });

  test("send button disabled  on other key pressed than enter and space bar", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={true}
        placeholder="Ask a question"
        onMicrophoneClick={onMicrophoneClick}
        onStopClick={onStopClick}
        isSendButtonDisabled={false}
        recognizedText={"recognized text"}
        isListening={false}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const sendbtn = screen.getByRole("button", { name: "Ask question button" });

    fireEvent.keyDown(sendbtn, { key: "A", code: "A", charCode: 65 });

    expect(mockOnSend).not.toHaveBeenCalled();
  });

  test("send button enable sendregular component", () => {
    render(
      <QuestionInput
        isRecognizing={true}
        onSend={mockOnSend}
        disabled={true}
        placeholder="Ask a question"
        onMicrophoneClick={onMicrophoneClick}
        onStopClick={onStopClick}
        isSendButtonDisabled={true}
        recognizedText={"recognized text"}
        isListening={false}
        isTextToSpeachActive={false}
        setRecognizedText={function (text: string): void {}}
        clearOnSend={true}
      />
    );

    const sendregularele = screen.queryByRole("button", {
      name: /SendRegular/i,
    });

    expect(sendregularele).not.toBeInTheDocument();
  });
});
