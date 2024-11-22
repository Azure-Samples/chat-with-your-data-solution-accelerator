import React from "react";
import { render, screen,fireEvent } from "@testing-library/react";
import { ChatMessageContainer, ChatMessageContainerProps } from "./ChatMessageContainer";
//import { Spinner } from "@fluentui/react";
import { Answer } from "../../components/Answer";

jest.mock("@fluentui/react", () => ({
    Spinner: jest.fn(() => <div data-testid="spinner" />),
    SpinnerSize: {
      medium: "medium",
    },
  }));

jest.mock("../../components/Answer", () => ({
    Answer: jest.fn((props: any) => <div data-testid="answer-component">
        <p>{props.answer.answer}</p>
        <span>Mock Answer Component</span>
        {props.answer.answer  == 'Generating answer...' ?
        <button onClick={() => props.onCitationClicked()}>Mock Citation Loading</button>        :
        <button onClick={() => props.onCitationClicked({ title: 'Test Citation' })}>Mock Citation</button>
        }
        
    </div>)
}));

const mockProps: ChatMessageContainerProps = {
  fetchingConvMessages: false,
  answers: [],
  activeCardIndex: null,
  handleSpeech: jest.fn(),
  onShowCitation: jest.fn(),
};

describe("ChatMessageContainer", () => {
    beforeEach(() => {
        global.fetch = jest.fn();
        jest.spyOn(console, 'error').mockImplementation(() => { });
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

  it("renders spinner when fetchingConvMessages is true", () => {
    render(
      <ChatMessageContainer
        {...mockProps}
        fetchingConvMessages={true}
      />
    );
    expect(screen.getByTestId("spinner")).toBeInTheDocument();
  });

  it("does not render spinner when fetchingConvMessages is false", () => {
    render(
      <ChatMessageContainer
        {...mockProps}
        fetchingConvMessages={false}
      />
    );
    expect(screen.queryByTestId("spinner")).not.toBeInTheDocument();
  });

  it("renders user message when role is USER", () => {
    const userMessage = { role: "user", content: "Hello" ,  id: '1', date: new Date().toDateString()};
    render(
      <ChatMessageContainer
        {...mockProps}
        answers={[userMessage]}
      />
    );
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("renders assistant message using Answer component", () => {

    const messages = [
        { role: "user", content: "User message" , id: '1', date: new Date().toDateString() },
        { role: "assistant", content: "Assistant response" , id: '2', date: new Date().toDateString() },
    ]
    render(
      <ChatMessageContainer
        {...mockProps}
        answers={messages}
      />
    );
    expect(screen.getByTestId("answer-component")).toBeInTheDocument();
  });

  it("renders error message using Answer component with fallback content", () => {
    const errorMessage = { role: "error", content: "An error occurred" ,id: '3', date: new Date().toDateString() };
    render(
      <ChatMessageContainer
        {...mockProps}
        answers={[errorMessage]}
      />
    );
    expect(screen.getByTestId("answer-component")).toBeInTheDocument();
  });

  it("calls handleSpeech and onShowCitation when Answer props are triggered", () => {
    const messages = [
        { role: "user", content: "User message" , id: '1', date: new Date().toDateString() },
        { role: "assistant", content: "Assistant response" , id: '2', date: new Date().toDateString() },
    ]
    const handleSpeechMock = jest.fn();
    const onShowCitationMock = jest.fn();

    render(
      <ChatMessageContainer
        {...mockProps}
        answers={messages}
        handleSpeech={handleSpeechMock}
        onShowCitation={onShowCitationMock}
      />
    );
    expect(Answer).toHaveBeenCalledTimes(1);
    // expect(Answer).toHaveBeenCalledWith(
    //   expect.objectContaining({
    //     onSpeak: handleSpeechMock,
    //     onCitationClicked: onShowCitationMock,
    //   }),
    //   expect.anything()
    // );
  });

  it("parses citations correctly for TOOL messages", () => {
    const toolMessage = { role: "tool", content: JSON.stringify({ citations: ["Citation1"] }) , id: '1', date: new Date().toDateString() };
    const assistantMessage = { role: "assistant", content: "Assistant's response" , id: '2', date: new Date().toDateString() };

    render(
      <ChatMessageContainer
        {...mockProps}
        answers={[toolMessage, assistantMessage]}
      />
    );

    expect(Answer).toHaveBeenCalledWith(
      expect.objectContaining({
        answer: expect.objectContaining({
          citations: ["Citation1"],
        }),
      }),
      expect.anything()
    );
  });

  it("handles malformed TOOL message content gracefully", () => {
    const toolMessage = { role: "tool", content: "Invalid JSON" , id: '1', date: new Date().toDateString() };
    const assistantMessage = { role: "assistant", content: "Assistant's response" , id: '2', date: new Date().toDateString() };

    render(
      <ChatMessageContainer
        {...mockProps}
        answers={[toolMessage, assistantMessage]}
      />
    );

    expect(Answer).toHaveBeenCalledWith(
      expect.objectContaining({
        answer: expect.objectContaining({
          citations: [],
        }),
      }),
      expect.anything()
    );
  });

  it("renders multiple messages in the correct order", () => {
    const messages = [
      { role: "user", content: "User message" , id: '1', date: new Date().toDateString() },
      { role: "assistant", content: "Assistant response" , id: '2', date: new Date().toDateString() },
      { role: "error", content: "An error occurred",id: '3', date: new Date().toDateString() },
    ];

    render(
      <ChatMessageContainer
        {...mockProps}
        answers={messages}
      />
    );

    expect(screen.getByText("User message")).toBeInTheDocument();
    expect(screen.getByText(/Sorry, an error occurred. Try refreshing the conversation or waiting a few minutes. If the issue persists, contact your system administrator. Error: An error occurred/i)).toBeInTheDocument();
  });

  it("handles empty answers array gracefully", () => {
    render(
      <ChatMessageContainer
        {...mockProps}
        answers={[]}
      />
    );

    expect(screen.queryByText("User message")).not.toBeInTheDocument();
    expect(screen.queryByTestId("answer-component")).not.toBeInTheDocument();
  });

  it('calls onShowCitation when a citation is clicked', () => {
    const messages = [
        { role: "user", content: "User message" , id: '1', date: new Date().toDateString() },
        { role: "assistant", content: "Assistant response" , id: '2', date: new Date().toDateString() },
    ];
     render(
        <ChatMessageContainer
          {...mockProps}
          answers={messages}
        />
      );
    // Simulate a citation click
    const citationButton = screen.getByText('Mock Citation');
    fireEvent.click(citationButton);

    // Check if onShowCitation is called with the correct argument
    expect(mockProps.onShowCitation).toHaveBeenCalledWith({ title: 'Test Citation' });
});
});
