import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatMessageContainer } from "./ChatMessageContainer";
import { Answer } from "../../components/Answer";

jest.mock("../../components/Answer", () => ({
  Answer: jest.fn(() => <div data-testid="answer-component">Answer</div>),
}));

describe("ChatMessageContainer", () => {
  const mockOnShowCitation = jest.fn();
  const mockHandleSpeech = jest.fn();

  const defaultProps = {
    fetchingConvMessages: false,
    answers: [],
    activeCardIndex: null,
    handleSpeech: mockHandleSpeech,
    onShowCitation: mockOnShowCitation,
  };

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders the spinner when fetchingConvMessages is true", () => {
    render(
      <ChatMessageContainer
        {...defaultProps}
        fetchingConvMessages={true}
      />
    );
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders user messages correctly", () => {
    const answers = [
      { role: "user", content: "Hello", id: "1", date: new Date().toISOString() },
    ];
    render(<ChatMessageContainer {...defaultProps} answers={answers} />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.queryByTestId("answer-component")).not.toBeInTheDocument();
  });

  it("renders assistant messages correctly", () => {
    const answers = [
      {
        role: "assistant",
        content: "Hi there!",
        id: "1",
        date: new Date().toISOString(),
      },
    ];
    render(<ChatMessageContainer {...defaultProps} answers={answers} />);

    expect(screen.getByTestId("answer-component")).toBeInTheDocument();
    expect(Answer).toHaveBeenCalledWith(
      expect.objectContaining({
        answer: {
          answer: "Hi there!",
          citations: [],
        },
        onSpeak: mockHandleSpeech,
        isActive: false,
        onCitationClicked: mockOnShowCitation,
        index: 0,
      }),
      expect.anything()
    );
  });

  it("renders error messages correctly", () => {
    const answers = [
      {
        role: "error",
        content: "Some error occurred",
        id: "1",
        date: new Date().toISOString(),
      },
    ];
    render(<ChatMessageContainer {...defaultProps} answers={answers} />);

    expect(screen.getByTestId("answer-component")).toBeInTheDocument();
    expect(Answer).toHaveBeenCalledWith(
      expect.objectContaining({
        answer: {
          answer:
            "Sorry, an error occurred. Try refreshing the conversation or waiting a few minutes. If the issue persists, contact your system administrator. Error: Some error occurred",
          citations: [],
        },
        onSpeak: mockHandleSpeech,
        isActive: false,
        onCitationClicked: mockOnShowCitation,
        index: 0,
      }),
      expect.anything()
    );
  });

//   it("calls onShowCitation when a citation is clicked", async () => {
//     const user = userEvent.setup();
//     const answers = [
//       {
//         role: "assistant",
//         content: "Hi there!",
//         id: "1",
//         date: new Date().toISOString(),
//       },
//     ];
//     render(<ChatMessageContainer {...defaultProps} answers={answers} />);

//     const citationCallback = Answer.mock.calls[0][0].onCitationClicked;
//     await user.click(screen.getByTestId("answer-component"));
//     citationCallback({ id: "citation-1" });

//     expect(mockOnShowCitation).toHaveBeenCalledWith({ id: "citation-1" });
//   });

//   it("triggers handleSpeech when the onSpeak prop is used", () => {
//     const answers = [
//       {
//         role: "assistant",
//         content: "Hi there!",
//         id: "1",
//         date: new Date().toISOString(),
//       },
//     ];
//     render(<ChatMessageContainer {...defaultProps} answers={answers} />);

//     const speechCallback = Answer.mock.calls[0][0].onSpeak;
//     speechCallback();
//     expect(mockHandleSpeech).toHaveBeenCalled();
//   });
});
