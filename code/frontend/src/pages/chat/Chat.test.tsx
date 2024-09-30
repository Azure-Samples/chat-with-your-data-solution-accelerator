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


jest.mock("../../components/QuestionInput", () => ({
  QuestionInput: jest.fn((props) => {
    // console.log(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", props);
    return (
      <div
        data-testid="questionInputPrompt"
        onClick={() => props.onSend("Let me know upcoming meeting scheduled")}
      >
        {props.placeholder}
        <div
          data-testid="microphone_btn"
          onClick={() => props.onMicrophoneClick()}
        >
          Microphone button
        </div>
        <div data-testid="recognise_txt">{props.recognizedText} </div>
      </div>
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
// jest.mock("react-markdown", () => () => {})
jest.mock("remark-gfm", () => () => {});
jest.mock("rehype-raw", () => () => {});
jest.mock("../../util/SpeechToText", () => ({
  multiLingualSpeechRecognizer: jest.fn(),
}));
jest.mock("../../components/Answer", () => ({
  Answer: (props: any) => {
    // console.log("AnswerProps", props);
    return (
      <div data-testid="answerInputPrompt">
        <div data-testid="answer-response">{props.answer.answer}</div>
      </div>
    );
  },
}));

// jest.mock("./Cards_contract/Cards", () => ({
//   Cards: (props: any) => {
//     console.log("Card Props", props);
//     return <div>Card Component</div>;
//   },
// }));

jest.mock('./Cards_contract/Cards', () => {
  const Cards = () => (
    <div data-testid='note-list-component'>Mocked Card Component</div>
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
    // chatMessageStreamEnd
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

    // Wait for loading to finish
    // await waitFor(() => {
    //     expect(screen.queryByText(/Loading.../i)).not.toBeInTheDocument();
    // });

    // Check for the presence of the assistant type title
    expect(await screen.findByText(/Contract Summarizer/i)).toBeInTheDocument();
  });

  test("displays input field after loading", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "contract assistant",
    });

    render(<Chat />);

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText(/Loading.../i)).not.toBeInTheDocument();
    });
    // screen.debug()
    const input = await screen.getByTestId("questionInputPrompt");
    // Question Component
    expect(input).toBeInTheDocument();
    //  // Simulate user input
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
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    // await fireEvent.change(await input, { target: { value: 'What is AI?' } });
    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    // screen.debug()
    const answerElement = screen.getByTestId("answer-response");
    // Question Component
    expect(answerElement.textContent).toEqual("response from AI");
  });

  test("displays loading message while waiting for response", async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce(new Promise(() => {})); // Keep it pending

    render(<Chat />);

    const input = screen.getByTestId("questionInputPrompt");
    // await fireEvent.change(await input, { target: { value: 'What is AI?' } });
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
    window.alert = jest.fn(); // Mock window alert
    // mockResponse = { body: { getReader: () => ({ read: jest.fn().mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(JSON.stringify({ error: "An error occurred" })) }).mockResolvedValueOnce({ done: true }), }), }, };
    render(<Chat />); // Render the Chat component

    // Find the QuestionInput component and simulate a send action
    const questionInput = screen.getByTestId("questionInputPrompt");
    fireEvent.click(questionInput);

    // Wait for the loading state to be set and the error to be handled
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith("API request failed");
    });

    // await waitFor(() => {
    //   //expect(mockCallConversationApi).toHaveBeenCalledTimes(1); // Ensure the API was called

    //   // Use regex to match the error message
    //   expect(mockCallConversationApi).toThrow("API request failed");
    // });
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

    // await fireEvent.change(await input, { target: { value: 'What is AI?' } });
    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    // screen.debug()
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

  test("handles microphone click and starts speech recognition", async () => {
    // Mock the API response
    mockCallConversationApi.mockResolvedValueOnce({
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
    // screen.debug()

    // Verify that the recognizer's method was called
    expect(mockedRecognizer.startContinuousRecognitionAsync).toHaveBeenCalled();
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

  // test('correctly processes recognized speech', async () => {
  //   const mockedRecognizer = {
  //     recognized: jest.fn(),
  //     startContinuousRecognitionAsync: jest.fn((success) => success()),
  //     stopContinuousRecognitionAsync: jest.fn((success) => success()),
  //     close: jest.fn(),
  //   };

  //   mockedMultiLingualSpeechRecognizer.mockImplementation(() => mockedRecognizer);

  //   render(<Chat />);

  //   const micButton = screen.getByTestId("microphone_btn");

  //   // Start recognition
  //   fireEvent.click(micButton);

  //   // Simulate recognized speech
  //   act(() => {
  //     mockedRecognizer.recognized(null, {
  //       result: {
  //         reason: 3,
  //         text: 'Hello, how can I help you?',
  //       },
  //     });
  //   });

  //   // Verify that the recognized text is set
  //   await waitFor(() => {
  //     const recognisedTxt = screen.getByTestId('recognise_txt');
  //     //expect(recognisedTxt.textContent).toEqual('Hello, how can I help you?');
  //   });
  // });

  // test('handles recognition errors gracefully', async () => {
  //   const mockedRecognizer = {
  //     recognized: jest.fn(),
  //     startContinuousRecognitionAsync: jest.fn((success) => success()),
  //     stopContinuousRecognitionAsync: jest.fn((success) => success()),
  //     close: jest.fn(),
  //   };

  //   mockedMultiLingualSpeechRecognizer.mockImplementation(() => mockedRecognizer);

  //   render(<Chat />);

  //   const micButton = await screen.findByLabelText(/Microphone/i);

  //   // Start recognition
  //   fireEvent.click(micButton);

  //   // Simulate an error during recognition
  //   act(() => {
  //     mockedRecognizer.recognized(null, {
  //       result: {
  //         reason: 'Error',
  //       },
  //     });
  //   });

  //   // Check if the appropriate error handling occurs (e.g., alert or message)
  // expect(window.alert).toHaveBeenCalledWith('An error occurred during speech recognition.');
  //});
  test("shows citations when available", async () => {
    // Mock the API responses
    mockGetAssistantTypeApi.mockResolvedValueOnce({
      ai_assistant_type: "default",
    });
    mockCallConversationApi.mockResolvedValueOnce({
      body: {
        getReader: jest.fn().mockReturnValue({
          read: jest.fn().mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(
              JSON.stringify({
                choices: [
                  {
                    messages: [
                      {
                        role: "tool",
                        content: JSON.stringify({
                          citations: ["Citation 1", "Citation 2"],
                        }),
                      },
                    ],
                  },
                ],
              })
            ),
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
    // screen.debug();
    // Wait for citations to appear in the document
    expect(screen.getByText(/Citation 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Citation 2/i)).toBeInTheDocument();

  });
});
