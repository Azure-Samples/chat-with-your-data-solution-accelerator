import React, { ReactNode } from "react";
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
  chatHistoryListData,
  citationObj,
  decodedConversationResponseWithCitations,
  historyReadAPIResponse,
} from "../../../__mocks__/SampleData";
import { HashRouter } from "react-router-dom";
import { ChatMessageContainerProps } from "../../components/ChatMessageContainer/ChatMessageContainer";
import { LayoutProps } from "../layout/Layout";
import { ChatHistoryPanelProps } from "../../components/ChatHistoryPanel/ChatHistoryPanel";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const first_question = "user question";
const data_test_ids = {
  assistant_type_section: "assistant_type_section",
  show_or_hide_chat_history_panel: "show_or_hide_chat_history_panel",
  chat_history_panel: "chat_history_panel",
  select_conversation: "select_conversation",
  select_conversation_get_history_response:
    "select_conversation_get_history_response",
  conv_messages: "conv_messages",
};
jest.mock("../../components/QuestionInput", () => ({
  QuestionInput: jest.fn((props) => {
    const { isListening, onStopClick, onMicrophoneClick } = props;
    return (
      <>
        <div
          data-testid="questionInputPrompt"
          onClick={() => props.onSend(first_question)}
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
  getFrontEndSettings: jest.fn(),
  historyList: jest.fn(),
  historyUpdate: jest.fn(),
  historyRead: jest.fn(),
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

jest.mock("./Cards_contract/Cards", () => {
  const Cards = () => (
    <div data-testid="note-list-component">Mocked Card Component</div>
  );
  return Cards;
});

jest.mock("../layout/Layout", () => {
  const Layout = (props: LayoutProps) => (
    <div>
      {props.children}
      <button
        data-testid={data_test_ids.show_or_hide_chat_history_panel}
        onClick={() => props.onSetShowHistoryPanel()}
      >
        Show / Hide Chat History Panel
      </button>
    </div>
  );
  return Layout;
});

jest.mock("../../components/AssistantTypeSection/AssistantTypeSection", () => ({
  AssistantTypeSection: (props: any) => {
    return (
      <div data-testid={data_test_ids.assistant_type_section}>
        Assistant type section component
      </div>
    );
  },
}));

jest.mock("../../components/Answer/Answer", () => ({
  Answer: (props: any) => {
    return <div>Answer component</div>;
  },
}));

jest.mock("../../components/ChatMessageContainer/ChatMessageContainer", () => ({
  ChatMessageContainer: jest.fn((props: ChatMessageContainerProps) => {
    const {
      fetchingConvMessages,
      answers,
      handleSpeech,
      activeCardIndex,
      onShowCitation,
    } = props;

    return (
      <div data-testid="chat-message-container">
        <h3>ChatMessageContainerMock</h3>
        {!fetchingConvMessages &&
          answers.map((message: any, index: number) => {
            return (
              <div
                data-testid={data_test_ids.conv_messages}
                key={message.role + index}
              >
                <p>{message.role}</p>
                <p>{message.content}</p>
              </div>
            );
          })}
        <button
          aria-label={"citation-btn"}
          onClick={() => onShowCitation(citationObj)}
        >
          Show Citation
        </button>
        <div id="chatMessagesContainer" />

        <button
          data-testid="speak-btn"
          onClick={() => handleSpeech(2, "speak")}
        >
          Speak
        </button>
        <button
          data-testid="pause-btn"
          onClick={() => handleSpeech(2, "pause")}
        >
          pause
        </button>
      </div>
    );
  }),
}));

jest.mock("../../components/CitationPanel/CitationPanel", () => ({
  CitationPanel: (props: any) => {
    return (
      <div>
        <h2>Citation Panel Component</h2>
        <div data-testid="citation-content">Citation Content</div>
      </div>
    );
  },
}));

jest.mock("../../components/ChatHistoryPanel/ChatHistoryPanel", () => ({
  ChatHistoryPanel: (props: ChatHistoryPanelProps) => {
    return (
      <>
        ChatHistoryPanel Component
        <div data-testid={data_test_ids.chat_history_panel}>
          Chat History Panel
        </div>
        {/* To simulate User selecting conversation from list */}
        <button
          data-testid={data_test_ids.select_conversation}
          onClick={() => props.onSelectConversation(chatHistoryListData[0].id)}
        >
          select conversation
        </button>
        <button
          data-testid={data_test_ids.select_conversation_get_history_response}
          onClick={() => props.onSelectConversation(chatHistoryListData[1].id)}
        >
          select conversation get response
        </button>
      </>
    );
  },
}));

const mockCallConversationApi = api.callConversationApi as jest.Mock;
const mockGetAssistantTypeApi = api.getAssistantTypeApi as jest.Mock;
const mockGetHistoryList = api.historyList as jest.Mock;
const mockHistoryUpdateApi = api.historyUpdate as jest.Mock;
const mockedMultiLingualSpeechRecognizer =
  multiLingualSpeechRecognizer as jest.Mock;
const mockHistoryRead = api.historyRead as jest.Mock;

const createFetchResponse = (ok: boolean, data: any) => {
  return {
    ok: ok,
    json: () =>
      new Promise((resolve, reject) => {
        ok ? resolve(data) : reject("Mock response: Failed to save data");
      }),
  };
};

const delayedConversationAPIcallMock = () => {
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
};

const nonDelayedConversationAPIcallMock = () => {
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
};

const initialAPICallsMocks = (
  delayConversationResponse = false,
  failUpdateAPI = false
) => {
  mockGetAssistantTypeApi.mockResolvedValueOnce({
    ai_assistant_type: "default",
  });
  (api.getFrontEndSettings as jest.Mock).mockResolvedValueOnce({
    CHAT_HISTORY_ENABLED: true,
  });
  mockGetHistoryList.mockResolvedValueOnce(chatHistoryListData);
  if (delayConversationResponse) {
    delayedConversationAPIcallMock();
  } else {
    nonDelayedConversationAPIcallMock();
  }
  const simpleUpdateResponse = {
    conversation_id: "conv_1",
    date: "2024-10-07T12:50:31.484766",
    title: "Introduction and Greeting",
  };
  mockHistoryUpdateApi.mockResolvedValueOnce(
    createFetchResponse(failUpdateAPI ? false : true, simpleUpdateResponse)
  );
  mockHistoryRead.mockResolvedValueOnce(historyReadAPIResponse);
};

describe("Chat Component", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Element.prototype.scrollIntoView = jest.fn();
    window.alert = jest.fn(); // Mock window alert
    mockGetAssistantTypeApi.mockClear();
    mockCallConversationApi.mockClear();
    mockHistoryUpdateApi.mockClear();
    mockedMultiLingualSpeechRecognizer.mockClear();
    mockHistoryRead.mockClear();
  });

  afterEach(() => {
    mockHistoryUpdateApi.mockClear();
    mockHistoryUpdateApi.mockReset();
    mockedMultiLingualSpeechRecognizer.mockReset();
    mockHistoryRead.mockReset();
  });

  test("renders the component and shows the Assistant Type section", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    await waitFor(() => {
      expect(
        screen.getByText(/Assistant type section component/i)
      ).toBeInTheDocument();
    });
  });

  // test("loads assistant type on mount", async () => {
  //   mockGetAssistantTypeApi.mockResolvedValueOnce({
  //     ai_assistant_type: "contract assistant",
  //   });
  //   initialAPICallsMocks();
  //   await act(async () => {
  //     render(
  //       <HashRouter>
  //         <Chat />
  //       </HashRouter>
  //     );
  //   });

  //   // Check for the presence of the assistant type title
  //   expect(await screen.findByText(/Contract Summarizer/i)).toBeInTheDocument();
  // });

  test("displays input field after loading", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );

    // Wait for loading
    await waitFor(() => {
      expect(screen.queryByText(/Loading.../i)).not.toBeInTheDocument();
    });
    const input = screen.getByTestId("questionInputPrompt");
    expect(input).toBeInTheDocument();
  });

  test("sends a question and displays the response", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();
  });

  test("If update API fails should throw error message", async () => {
    initialAPICallsMocks(false, true);
    const consoleErrorMock = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    await waitFor(() => {
      expect(consoleErrorMock).toHaveBeenCalledWith(
        "Error: while saving data",
        "Mock response: Failed to save data"
      );
    });

    consoleErrorMock.mockRestore();
  });

  test("clears chat when clear button is clicked", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

    const clearButton = screen.getByLabelText(/Clear session/i);

    await act(async () => {
      fireEvent.click(clearButton);
    });
    await waitFor(() => {
      expect(screen.queryByText("response from AI")).not.toBeInTheDocument();
    });
  });

  test("clears chat when clear button is in focus and Enter key triggered", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

    const clearButton = screen.getByLabelText(/Clear session/i);

    clearButton.focus();

    // Trigger the Enter key
    fireEvent.keyDown(clearButton, {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });
    await waitFor(() => {
      expect(screen.queryByText("response from AI")).not.toBeInTheDocument();
    });
  });

  test("clears chat when clear button is in focus and space key triggered", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

    const clearButton = screen.getByLabelText(/Clear session/i);

    clearButton.focus();

    // Trigger the Enter key
    fireEvent.keyDown(clearButton, {
      key: " ",
      code: "Space",
      charCode: 32,
      keyCode: 32,
    });
    await waitFor(() => {
      expect(screen.queryByText("response from AI")).not.toBeInTheDocument();
    });
  });

  test.skip("handles microphone starts speech and stops before listening speech", async () => {
    initialAPICallsMocks();

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
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Find the microphone button
    const micButton = screen.getByTestId("microphone_btn"); // Ensure the button is available
    fireEvent.click(micButton);

    // Assert that speech recognition has started
    await waitFor(() => {
      expect(screen.getByText(/Please wait.../i)).toBeInTheDocument();
    });

    // Verify that the recognizer's method was called
    expect(mockedRecognizer.startContinuousRecognitionAsync).toHaveBeenCalled();
    await delay(3000);
    // stop again
    fireEvent.click(micButton);

    expect(mockedRecognizer.stopContinuousRecognitionAsync).toHaveBeenCalled();
    expect(mockedRecognizer.close).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText(/Please wait.../i)).not.toBeInTheDocument();
    });
  });

  test("handles microphone click and starts speech and clicking on stop should stop speech recognition", async () => {
    initialAPICallsMocks();
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
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
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
    // delay(3000).then(() => {});
    expect(mockedRecognizer.stopContinuousRecognitionAsync).toHaveBeenCalled();
    expect(mockedRecognizer.close).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText(/Listening.../i)).not.toBeInTheDocument();
    }); // Check if "Listening..." is removed
  });

  test("correctly processes recognized speech", async () => {
    initialAPICallsMocks();
    const mockedRecognizer = {
      recognized: jest.fn(),
      startContinuousRecognitionAsync: jest.fn((success) => success()),
      stopContinuousRecognitionAsync: jest.fn((success) => success()),
      close: jest.fn(),
    };

    mockedMultiLingualSpeechRecognizer.mockImplementation(
      () => mockedRecognizer
    );

    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );

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
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

    const speakerButton = screen.getByTestId("speak-btn");
    await act(async () => {
      fireEvent.click(speakerButton);
    });

    const QuestionInputMicrophoneBtn = screen.getByTestId("microphone_btn");
    expect(QuestionInputMicrophoneBtn).toBeDisabled();
  });

  test("After pause speech to text Question input mic should be enabled mode", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

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

  test("Should handle onShowCitation method when citation button click", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("chat-message-container")).toBeInTheDocument();
    });

    const mockCitationBtn = await screen.findByRole("button", {
      name: /citation-btn/i,
    });

    await act(async () => {
      mockCitationBtn.click();
    });

    await waitFor(async () => {
      expect(await screen.findByTestId("citation-content")).toBeInTheDocument();
    });
  });

  test("Should handle Show Chat History panel", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });

    const answerElement = screen.getByText("response from AI");
    expect(answerElement).toBeInTheDocument();

    const showOrHidechatHistoryButton = screen.getByTestId(
      data_test_ids.show_or_hide_chat_history_panel
    );
    // SHOW
    await act(async () => {
      fireEvent.click(showOrHidechatHistoryButton);
    });

    await waitFor(async () => {
      expect(
        await screen.findByTestId(data_test_ids.chat_history_panel)
      ).toBeInTheDocument();
    });
  });

  test("Should be able to select conversation and able to get Chat History from history read API", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const {
      show_or_hide_chat_history_panel,
      chat_history_panel,
      select_conversation_get_history_response,
    } = data_test_ids;
    const showOrHidechatHistoryButton = screen.getByTestId(
      show_or_hide_chat_history_panel
    );
    // SHOW
    await act(async () => {
      fireEvent.click(showOrHidechatHistoryButton);
    });

    await waitFor(async () => {
      expect(await screen.findByTestId(chat_history_panel)).toBeInTheDocument();
    });
    const selectConversation = screen.getByTestId(
      select_conversation_get_history_response
    );
    await act(async () => {
      fireEvent.click(selectConversation);
    });
    const messages = await screen.findAllByTestId("conv_messages");
    expect(messages.length).toBeGreaterThan(1);
  });
  test("Should be able to select conversation and able to set if already messages fetched", async () => {
    initialAPICallsMocks();
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    const {
      show_or_hide_chat_history_panel,
      chat_history_panel,
      select_conversation,
    } = data_test_ids;
    const showOrHidechatHistoryButton = screen.getByTestId(
      show_or_hide_chat_history_panel
    );
    // SHOW
    await act(async () => {
      fireEvent.click(showOrHidechatHistoryButton);
    });

    await waitFor(async () => {
      expect(await screen.findByTestId(chat_history_panel)).toBeInTheDocument();
    });
    const selectConversation = screen.getByTestId(select_conversation);
    await act(async () => {
      fireEvent.click(selectConversation);
    });
  });

  // test("Should not call update API call if conversation id or no messages exists", async () => {
  //   initialAPICallsMocks();
  //   render(
  //     <HashRouter>
  //       <Chat />
  //     </HashRouter>
  //   );
  //   const submitQuestion = screen.getByTestId("questionInputPrompt");

  //   await act(async () => {
  //     fireEvent.click(submitQuestion);
  //   });
  //   const answerElement = screen.getByText("response from AI");
  //   expect(answerElement).toBeInTheDocument();
  // });

  /*
   commented test case due to chat history feature code merging
  test("displays loading message while waiting for response", async () => {
    initialAPICallsMocks(true);
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );

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
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    ); // Render the Chat component

    // Find the QuestionInput component and simulate a send action
    const questionInput = screen.getByTestId("questionInputPrompt");
    fireEvent.click(questionInput);

    // Wait for the loading state to be set and the error to be handled
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith("API request failed");
    });
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

    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );

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




  test("After pause speech to text Question input mic should be enabled mode", async () => {
    initialAPICallsMocks()

    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
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
    initialAPICallsMocks()


    // Render the Chat component
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );

    // Get the input element and submit button
    const submitButton = screen.getByTestId("questionInputPrompt");

    // Simulate user interaction
    await act(async () => {
      fireEvent.click(submitButton);
    });
    // Wait for citations to appear in the document

    await waitFor(() => {
      expect(screen.getByTestId("citation-1")).toBeInTheDocument();
      expect(screen.getByTestId("citation-2")).toBeInTheDocument();
    });
  });

  test("shows citation panel when clicked on reference", async () => {
    // Mock the API responses
    initialAPICallsMocks()

    // Render the Chat component
    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );

    // Get the input element and submit button
    const submitButton = screen.getByTestId("questionInputPrompt");

    // Simulate user interaction
    await act(async () => {
      fireEvent.click(submitButton);
    });

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

    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    const stopButton = screen.getByRole("button", { name: /stop generating/i });

    // Assertions
    expect(stopButton).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(stopButton);
    });

    expect(stopButton).not.toBeInTheDocument();
  });

  test("On focus on stop generating btn, and triggering Enter key it should hide stop generating btn", async () => {
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

    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    const stopButton = screen.getByRole("button", { name: /stop generating/i });
    // Assertions
    expect(stopButton).toBeInTheDocument();
    await act(async () => {
      stopButton.focus();
      // Trigger the Enter key
      fireEvent.keyDown(stopButton, {
        key: "Enter",
        code: "Enter",
        charCode: 13,
      });
    });

    expect(stopButton).not.toBeInTheDocument();
  });

  test("On focus on stop generating btn, and triggering Space bar key it should hide stop generating btn", async () => {
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

    render(
      <HashRouter>
        <Chat />
      </HashRouter>
    );
    // Simulate user input
    const submitQuestion = screen.getByTestId("questionInputPrompt");

    await act(async () => {
      fireEvent.click(submitQuestion);
    });
    const streamMessage = screen.getByTestId("streamendref-id");
    expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });

    const stopButton = screen.getByRole("button", { name: /stop generating/i });
    // Assertions
    expect(stopButton).toBeInTheDocument();
    await act(async () => {
      // Trigger the Enter key
      stopButton.focus();
      fireEvent.keyDown(stopButton, {
        key: " ",
        code: "Space",
        charCode: 32,
        keyCode: 32,
      });
      fireEvent.keyUp(stopButton, {
        key: " ",
        code: "Space",
        charCode: 32,
        keyCode: 32,
      });
    });

    expect(stopButton).not.toBeInTheDocument();
  });
  */
});
