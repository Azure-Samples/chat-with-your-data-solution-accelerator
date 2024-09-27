import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import Chat from './Chat';
import * as api from '../../api';
import { multiLingualSpeechRecognizer } from '../../util/SpeechToText';
import { Timeout } from 'microsoft-cognitiveservices-speech-sdk/distrib/lib/src/common/Timeout';
import exp from 'constants';

jest.mock('../../components/QuestionInput', () => ({
  QuestionInput: jest.fn((props) => (
      <div data-testid='questionInputPrompt' onClick={() => props.onSend("Let me know upcoming meeting scheduled")}>
       {props.placeholder}
      </div>
  )),
}));

// Mock necessary modules and functions
jest.mock('../../api', () => ({
  callConversationApi: jest.fn(),
  getAssistantTypeApi: jest.fn(),
}));
jest.mock('react-markdown', () => ({ children }: { children: React.ReactNode }) => {
  return <div data-testid="mock-react-markdown">{children}</div>;
});
jest.mock('uuid', () => ({
  v4: jest.fn(() => 'mocked-uuid'),
}));
// jest.mock("react-markdown", () => () => {})
jest.mock("remark-gfm", () => () => {})
jest.mock("rehype-raw", () => () => {})
jest.mock('../../util/SpeechToText', () => ({
  multiLingualSpeechRecognizer: jest.fn(),
}));
jest.mock('../../components/Answer', () => ({
  Answer: (props: any) => {
    // console.log("AnswerProps", props);
    return <div data-testid='answerInputPrompt' >
      <div data-testid='answer-response'>{props.answer.answer}</div>
    </div>
  }
}));


jest.mock('./Cards_contract/Cards', () => ({
  Cards: (props: any) => <div>Card Component</div>
}));

const mockedMultiLingualSpeechRecognizer = multiLingualSpeechRecognizer as jest.Mock;
const mockCallConversationApi = api.callConversationApi as jest.Mock;
const mockGetAssistantTypeApi = api.getAssistantTypeApi as jest.Mock;

describe('Chat Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Element.prototype.scrollIntoView = jest.fn();
    // chatMessageStreamEnd
  });

  test('renders the component and shows the empty state', async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });

    render(<Chat />);
await waitFor(()=>{
  expect(screen.getByText(/Start chatting/i)).toBeInTheDocument();
  expect(screen.getByText(/This chatbot is configured to answer your questions/i)).toBeInTheDocument();
})
});

test('loads assistant type on mount', async () => {
  mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'contract assistant' });
  await act(async () => {
    render(
      <Chat/>
    );
  });

  // Wait for loading to finish
  // await waitFor(() => {
  //     expect(screen.queryByText(/Loading.../i)).not.toBeInTheDocument();
  // });


  // Check for the presence of the assistant type title
  expect(await screen.findByText(/Contract Summarizer/i)).toBeInTheDocument();
});


test('displays input field after loading', async () => {
  mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'contract assistant' });

  render(<Chat/>);

  // Wait for loading to finish
  await waitFor(() => {
      expect(screen.queryByText(/Loading.../i)).not.toBeInTheDocument();
  });
  // screen.debug()
   const input = await screen.getByTestId("questionInputPrompt");
  // Question Component
  expect(input).toBeInTheDocument()
  //  // Simulate user input
});



test('sends a question and displays the response', async () => {
  // Mock the assistant type API response
  mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });

  // Mock the conversation API response
  mockCallConversationApi.mockResolvedValueOnce({
    body: {
      getReader: jest.fn().mockReturnValue({
        read: jest.fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(JSON.stringify({
              choices: [{
                messages: [{ role: 'assistant', content: 'response from AI' }]
              }]
            })),
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
  const answerElement =  screen.getByTestId("answer-response");
  // Question Component
  expect(answerElement.textContent).toEqual("response from AI")

});

  test('displays loading message while waiting for response', async () => {
    mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });
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

  test.only('should handle API failure correctly', async () => {
    const mockError = new Error('API request failed');
    mockCallConversationApi.mockRejectedValueOnce(mockError); // Simulate API failure

    render(<Chat />); // Render the Chat component

    // Find the QuestionInput component and simulate a send action
    const questionInput = screen.getByTestId('questionInputPrompt');
    fireEvent.click(questionInput);

    // Wait for the loading state to be set and the error to be handled
    await waitFor(() => {
      expect(api.callConversationApi).toHaveBeenCalledTimes(1); // Ensure the API was called

      // Use regex to match the error message
      expect(screen.getByText(/API request failed/i)).toBeInTheDocument();
    });
  });



//   test('clears chat when clear button is clicked', async () => {
//     mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });
//     mockCallConversationApi.mockResolvedValueOnce({
//       body: {
//         getReader: jest.fn().mockReturnValue({
//           read: jest.fn().mockResolvedValueOnce({
//             done: false,
//             value: new TextEncoder().encode(JSON.stringify({ choices: [{ messages: [{ role: 'assistant', content: 'This is a response' }] }] })),
//           }),
//         }),
//       },
//     });

//     render(<Chat />);

//     // Simulate user input
//   const submitQuestion = screen.getByTestId("questionInputPrompt");

//   // await fireEvent.change(await input, { target: { value: 'What is AI?' } });
//   await act(async () => {
//     fireEvent.click(submitQuestion);
//   });
//   const streamMessage = screen.getByTestId("streamendref-id");
//   expect(streamMessage.scrollIntoView).toHaveBeenCalledWith({
//     behavior: "smooth",
//   });

//   // screen.debug()
//   const answerElement =  screen.getByTestId("answer-response");

// await waitFor(()=>{ expect(answerElement.textContent).toEqual("response from AI")});
//     const clearButton = screen.getByLabelText(/Clear session/i);
//     await act(async () => {
//       fireEvent.click(clearButton);
//     });
//       expect(screen.getByTestId("answer-response")).not.toBeInTheDocument();
//   });

  // test('handles microphone click and starts speech recognition', async () => {
  //   mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });
  //   mockedMultiLingualSpeechRecognizer.mockImplementation(() => ({
  //     recognized: jest.fn(),
  //     startContinuousRecognitionAsync: jest.fn((success) => success()),
  //     stopContinuousRecognitionAsync: jest.fn((success) => success()),
  //   }));

  //   render(<Chat />);

  //   const micButton = screen.getByLabelText(/Microphone/i); // Adjust the aria-label in the QuestionInput component
  //   fireEvent.click(micButton);

  //   expect(screen.getByText(/Listening.../i)).toBeInTheDocument();
  // });

  // test('updates recognized text correctly', async () => {
  //   mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });
  //   const recognizedText = 'This is recognized text';

  //   render(<Chat />);
  //   const input = screen.getByPlaceholderText(/Type a new question.../i) as HTMLInputElement;

  //   // Simulate the speech recognition output
  //   fireEvent.change(input, { target: { value: recognizedText } });

  //   expect(input.value).toBe(recognizedText);
  // });

  // test('updates text-to-speech state correctly', async () => {
  //   mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });

  //   render(<Chat />);

  //   const speakButton = screen.getByLabelText(/speak/i); // Ensure this label matches your button's aria-label
  //   fireEvent.click(speakButton);

  //   // Assuming that your component reflects the TTS state visually, e.g., showing "Speaking..." or similar
  //   await waitFor(() => {
  //     expect(screen.getByText(/Speaking.../i)).toBeInTheDocument(); // Adjust based on actual output in the component
  //   });
  // });

  // test('shows citations when available', async () => {
  //   mockGetAssistantTypeApi.mockResolvedValueOnce({ ai_assistant_type: 'default' });
  //   mockCallConversationApi.mockResolvedValueOnce({
  //     body: {
  //       getReader: jest.fn().mockReturnValue({
  //         read: jest.fn().mockResolvedValueOnce({
  //           done: false,
  //           value: new TextEncoder().encode(JSON.stringify({
  //             choices: [{ messages: [{ role: 'tool', content: JSON.stringify({ citations: ['Citation 1', 'Citation 2'] }) }] }] }
  //           )),
  //         }),
  //       }),
  //     },
  //   });

  //   render(<Chat />);

  //   const input = screen.getByPlaceholderText(/Type a new question.../i);
  //   fireEvent.change(input, { target: { value: 'What is AI?' } });
  //   fireEvent.keyPress(input, { key: 'Enter', code: 'Enter' });

  //   await waitFor(() => {
  //     expect(screen.getByText(/Citation 1/i)).toBeInTheDocument();
  //     expect(screen.getByText(/Citation 2/i)).toBeInTheDocument();
  //   });
  // });
});
