import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import Chat from "./Chat";
import * as api from "../../api";
import { multiLingualSpeechRecognizer } from "../../util/SpeechToText";
import {
  AIResponseContent,
  citationObj,
  decodedConversationResponseWithCitations,
} from "../../../__mocks__/SampleData";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

jest.mock("../../components/QuestionInput", () => ({
  QuestionInput: jest.fn((props) => {
    console.log("QuestionInput props", props);
    const { isListening, onStopClick, onMicrophoneClick } = props;
    return (
      <>
        <div
          data-testid="questionInputPrompt"
          onClick={() => props.onSend("Let me know upcoming meeting scheduled")}
        >
          {props.placeholder}
          <div data-testid="recognized_text">{props.recognizedText}</div>
        </div>
        <button
          data-testid="microphone_btn"
          onClick={isListening ? onStopClick : onMicrophoneClick}
          disabled={props.isTextToSpeachActive}
        >
          Microphone button
        </button>
      </>
    );
  }),
}));

// Mock necessary modules and functions
jest.mock("../../api", () => ({
  callConversationApi: jest.fn(),
  getAssistantTypeApi: jest.fn(),
}));
jest.mock(
  "react-markdown",
  () =>
    ({ children }: { children: React.ReactNode }) => {
      return <div data-testid="mock-react-markdown">{children}</div>;
    }
);
jest.mock("uuid", () => ({
  v4: jest.fn(() => "mocked-uuid"),
}));
jest.mock("remark-gfm", () => () => {});
jest.mock("rehype-raw", () => () => {});
jest.mock("../../util/SpeechToText", () => ({
  multiLingualSpeechRecognizer: jest.fn(),
}));
jest.mock("../../components/Answer", () => ({
  Answer: (props: any) => {
    console.log("AnswerProps", props);
    return (
      <div data-testid="answerInputPrompt">
        <div data-testid="answer-response">{props.answer.answer}</div>
        {/* onSpeak(index, 'speak'); */}
        <button
          data-testid="speak-btn"
          onClick={() => props.onSpeak(props.index, "speak")}
        >
          Speak
        </button>
        <button
          data-testid="pause-btn"
          onClick={() => props.onSpeak(props.index, "pause")}
        >
          Speak
        </button>
        {props.answer.citations.map((_citationObj: any, index: number) => (
          <div data-testid={`citation-${index}`} key={index}>
            citation-{index}
          </div>
        ))}
        <button
          data-testid="mocked-view-citation-btn"
          onClick={() => props.onCitationClicked(citationObj)}
        >
          Click Citation
        </button>
      </div>
    );
  },
}));

jest.mock("./Cards_contract/Cards", () => {
  const Cards = () => (
    <div data-testid="note-list-component">Mocked Card Component</div>
  );
  return Cards;
});

const mockedMultiLingualSpeechRecognizer =
  multiLingualSpeechRecognizer as jest.Mock;
const mockCallConversationApi = api.callConversationApi as jest.Mock;
const mockGetAssistantTypeApi = api.getAssistantTypeApi as jest.Mock;

describe("Chat Component", () => {
  const mockSetIsCitationPanelOpen = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    Element.prototype.scrollIntoView = jest.fn();
    window.alert = jest.fn(); // Mock window alert
  });

  test("renders the component and shows the empty state", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });

    render(<Chat />);
    await waitFor(() => {
      expect(screen.getByText(/Start chatting/i)).toBeInTheDocument();
      expect(
        screen.getByText(/This chatbot is configured to answer your questions/i)
      ).toBeInTheDocument();
    });
  });

  test("loads assistant type on mount", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "contract assistant",
    });
    await act(async () => {
      render(<Chat />);
    });

    // Check for the presence of the assistant type title
    expect(await screen.findByText(/Contract Summarizer/i)).toBeInTheDocument();
  });

  test("displays input field after loading", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "contract assistant",
    });

    render(<Chat />);

    // Wait for loading
    await waitFor(() => {
      expect(screen.queryByText(/Loading.../i)).not.toBeInTheDocument();
    });
    const input = screen.getByTestId("questionInputPrompt");
    expect(input).toBeInTheDocument();
  });

  test("sends a question and displays the response", async () => {
    // Mock the assistant type API response
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });

    // Mock the conversation API response
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify({
                  choices: [
                    {
                      messages: [
                        { role: "assistant", content: "response from AI" },
                      ],
                    },
                  ],
                })
              ),
            })
            .mockResolvedValueOnce({ done: true }), // Mark the stream as done
        }),
      },
    });

    render(<Chat />);
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    const answerElement = screen.getByTestId("answer-response");
    expect(answerElement.textContent).toEqual("response from AI");
  });

  test("displays loading message while waiting for response", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce(new Promise(() => {}));

    render(<Chat />);

    const input = screen.getByTestId("questionInputPrompt");
    await act(async () => {
      fireEvent.click(input);
    });
    // Wait for the loading message to appear
    const streamMessage = await screen.findByTestId("generatingAnswer");

    // Check if the generating answer message is in the document
    expect(streamMessage).toBeInTheDocument();

    // Optionally, if you want to check if scrollIntoView was called
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });
  });

  test("should handle API failure correctly", async () => {
    const mockError = new Error("API request failed");
    mockCallConversationApi.mockRejectedValueOnce(mockError); // Simulate API failure
    render(<Chat />); // Render the Chat component

    // Find the QuestionInput component and simulate a send action
    const questionInput = screen.getByTestId("questionInputPrompt");
    fireEvent.click(questionInput);

    // Wait for the loading state to be set and the error to be handled
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith("API request failed");
    });
  });

  test("clears chat when clear button is clicked", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify({
                  choices: [
                    {
                      messages: [
                        { role: "assistant", content: "response from AI" },
                      ],
                    },
                  ],
                })
              ),
            })
            .mockResolvedValueOnce({ done: true }), // Mark the stream as done
        }),
      },
    });

    render(<Chat />);
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    const answerElement = await screen.findByTestId("answer-response");

    await waitFor(() => {
      expect(answerElement.textContent).toEqual("response from AI");
    });

    const clearButton = screen.getByLabelText(/Clear session/i);

    await act(async () => {
      fireEvent.click(clearButton);
    });
    await waitFor(() => {
      expect(screen.queryByTestId("answer-response")).not.toBeInTheDocument();
    });
  });

  test("clears chat when clear button is in focus and Enter key triggered", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify({
                  choices: [
                    {
                      messages: [
                        { role: "assistant", content: "response from AI" },
                      ],
                    },
                  ],
                })
              ),
            })
            .mockResolvedValueOnce({ done: true }), // Mark the stream as done
        }),
      },
    });

    render(<Chat />);
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    const answerElement = await screen.findByTestId("answer-response");

    await waitFor(() => {
      expect(answerElement.textContent).toEqual("response from AI");
    });

    const clearButton = screen.getByLabelText(/Clear session/i);

    await act(async () => {
      // fireEvent.click(clearButton);

      clearButton.focus();

      // Trigger the Enter key
      fireEvent.keyDown(clearButton, { key: 'Enter', code: 'Enter', charCode: 13 });
    });
    await waitFor(() => {
      expect(screen.queryByTestId("answer-response")).not.toBeInTheDocument();
    });
  });

  test("handles microphone click and starts speech recognition", async () => {
    // Mock the API response
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });

    // Mock the speech recognizer implementation
    const mockedRecognizer = {
      recognized: jest.fn(),
      startContinuousRecognitionAsync: jest.fn((success) => success()),
      stopContinuousRecognitionAsync: jest.fn((success) => success()),
      close: jest.fn(),
    };

    mockedMultiLingualSpeechRecognizer.mockImplementation(
      () => mockedRecognizer
    );

    // Render the Chat component
    render(<Chat />);
    // Find the microphone button
    const micButton = screen.getByTestId("microphone_btn"); // Ensure the button is available
    fireEvent.click(micButton);

    // Assert that speech recognition has started
    await waitFor(() => {
      expect(screen.getByText(/Listening.../i)).toBeInTheDocument();
    });

    // Verify that the recognizer's method was called
    expect(mockedRecognizer.startContinuousRecognitionAsync).toHaveBeenCalled();
    // stop again
    fireEvent.click(micButton);
  });

  test("handles stopping speech recognition when microphone is clicked again", async () => {
    const mockedRecognizer = {
      recognized: jest.fn(),
      startContinuousRecognitionAsync: jest.fn((success) => success()),
      stopContinuousRecognitionAsync: jest.fn((success) => success()),
      close: jest.fn(),
    };

    mockedMultiLingualSpeechRecognizer.mockImplementation(
      () => mockedRecognizer
    );

    render(<Chat />);

    const micButton = screen.getByTestId("microphone_btn");

    // Start recognition
    fireEvent.click(micButton);
    await waitFor(() => {
      expect(screen.getByText(/Listening.../i)).toBeInTheDocument();
    });
    expect(mockedRecognizer.startContinuousRecognitionAsync).toHaveBeenCalled();

    // Stop recognition
    fireEvent.click(micButton);
    expect(mockedRecognizer.stopContinuousRecognitionAsync).toHaveBeenCalled();
    expect(mockedRecognizer.close).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText(/Listening.../i)).not.toBeInTheDocument();
    }); // Check if "Listening..." is removed
  });

  test("correctly processes recognized speech", async () => {
    const mockedRecognizer = {
      recognized: jest.fn(),
      startContinuousRecognitionAsync: jest.fn((success) => success()),
      stopContinuousRecognitionAsync: jest.fn((success) => success()),
      close: jest.fn(),
    };

    mockedMultiLingualSpeechRecognizer.mockImplementation(
      () => mockedRecognizer
    );

    render(<Chat />);

    const micButton = screen.getByTestId("microphone_btn");

    // click mic button
    fireEvent.click(micButton);
    // initiate continuous recognization
    await waitFor(() => {
      // once listening availble
      expect(screen.queryByText(/Listening.../i)).not.toBeInTheDocument();

      // Simulate recognized speech

      fireEvent.click(micButton);
    });
    expect(mockedRecognizer.startContinuousRecognitionAsync).toHaveBeenCalled();
    act(() => {
      // let rec = mockedMultiLingualSpeechRecognizer();
      mockedRecognizer.recognized(null, {
        result: {
          reason: 3,
          text: "Hello AI",
        },
      });
      mockedRecognizer.recognized(null, {
        result: {
          reason: 3,
          text: "Explain me Microsoft AI in detail",
        },
      });
    });

    // Verify that the recognized text is set
    await waitFor(() => {
      const recognizedTextElement = screen.getByTestId("recognized_text");
      expect(
        screen.queryByText(/Hello AI Explain me Microsoft AI in detail/i)
      ).toBeInTheDocument();
      expect(recognizedTextElement.textContent).toEqual(
        "Hello AI Explain me Microsoft AI in detail"
      );
    });
  });

  test("while speaking response text speech recognizing mic to be disabled", async () => {
    // Mock the assistant type API response
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    // Mock the conversation API response
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify({
                  choices: [
                    {
                      messages: [
                        { role: "assistant", content: AIResponseContent },
                      ],
                    },
                  ],
                })
              ),
            })
            .mockResolvedValueOnce({ done: true }), // Mark the stream as done
        }),
      },
    });

    render(<Chat />);
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByTestId("answer-response");
    // Question Component
    expect(answerElement.textContent).toEqual(AIResponseContent);

    const speakerButton = screen.getByTestId("speak-btn");
    await act(async () => {
      fireEvent.click(speakerButton);
    });
    const QuestionInputMicrophoneBtn = screen.getByTestId("microphone_btn");
    expect(QuestionInputMicrophoneBtn).toBeDisabled();
  });

  test("After pause speech to text Question input mic should be enabled mode", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });

    // Mock the conversation API response
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify({
                  choices: [
                    {
                      messages: [
                        { role: "assistant", content: AIResponseContent },
                      ],
                    },
                  ],
                })
              ),
            })
            .mockResolvedValueOnce({ done: true }), // Mark the stream as done
        }),
      },
    });

    render(<Chat />);
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByTestId("answer-response");

    expect(answerElement.textContent).toEqual(AIResponseContent);

    const speakerButton = screen.getByTestId("speak-btn");
    await act(async () => {
      fireEvent.click(speakerButton);
    });
    const pauseButton = screen.getByTestId("pause-btn");

    await act(async () => {
      fireEvent.click(pauseButton);
    });
    const QuestionInputMicrophoneBtn = screen.getByTestId("microphone_btn");
    expect(QuestionInputMicrophoneBtn).not.toBeDisabled();
  });
  test("shows citations list when available", async () => {
    // Mock the API responses
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify(decodedConversationResponseWithCitations)
              ),
            })
            .mockResolvedValueOnce({
              done: true,
              value: new TextEncoder().encode(JSON.stringify({})),
            }),
        }),
      },
    });

    // Render the Chat component
    render(<Chat />);

    // Get the input element and submit button
    const submitButton = screen.getByTestId("questionInputPrompt");

    // Simulate user interaction
    await act(async () => {
      fireEvent.click(submitButton);
    });
    // Wait for citations to appear in the document

    screen.debug();

    await waitFor(() => {
      expect(screen.getByTestId("citation-1")).toBeInTheDocument();
      expect(screen.getByTestId("citation-2")).toBeInTheDocument();
    });
  });

  test("shows citation panel when clicked on reference", async () => {
    // Mock the API responses
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                JSON.stringify(decodedConversationResponseWithCitations)
              ),
            })
            .mockResolvedValueOnce({
              done: true,
              value: new TextEncoder().encode(JSON.stringify({})),
            }),
        }),
      },
    });

    // Render the Chat component
    render(<Chat />);

    // Get the input element and submit button
    const submitButton = screen.getByTestId("questionInputPrompt");

    // Simulate user interaction
    await act(async () => {
      fireEvent.click(submitButton);
    });
    screen.debug();

    const citationReferenceElement = screen.getByTestId(
      "mocked-view-citation-btn"
    );

    await act(async () => {
      fireEvent.click(citationReferenceElement);
    });

    await waitFor(() => {
      const citationPanelHeaderElement = screen.getByTestId(
        "citation-panel-header"
      );
      expect(citationPanelHeaderElement).toBeInTheDocument();

      const citationPanelDisclaimerElement = screen.getByTestId(
        "citation-panel-disclaimer"
      );
      expect(citationPanelDisclaimerElement).toBeInTheDocument();

      const citationMarkdownContent = screen.getByTestId("mock-react-markdown");
      expect(citationMarkdownContent).toBeInTheDocument();
    });
  });

  test("On click of stop generating btn, it should hide stop generating btn", async () => {
    // Mock the assistant type API response
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });

    // Mock the conversation API response
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest
            .fn()
            .mockResolvedValueOnce(
              delay(5000).then(() => ({
                done: false,
                value: new TextEncoder().encode(
                  JSON.stringify(decodedConversationResponseWithCitations)
                ),
              }))
            )
            .mockResolvedValueOnce({
              done: true,
              value: new TextEncoder().encode(JSON.stringify({})),
            }),
        }),
      },
    });

    render(<Chat />);
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    screen.debug();
    const stopButton = screen.getByRole("button", { name: /stop generating/i });

    // Assertions
    expect(stopButton).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(stopButton);
    });

    expect(stopButton).not.toBeInTheDocument();
  });
});
