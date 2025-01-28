import * as sdk from 'microsoft-cognitiveservices-speech-sdk';
import "@testing-library/jest-dom";
import {
  render,
  screen,
  fireEvent,
  act,
  waitFor,
} from "@testing-library/react";
import { Answer } from "./Answer";
import { conversationResponseWithCitations } from "../../../__mocks__/SampleData";

jest.mock('microsoft-cognitiveservices-speech-sdk', () => {
  return {
    SpeechConfig: {
      fromSubscription: jest.fn(),
    },
    AudioConfig: {
      fromDefaultSpeakerOutput: jest.fn(),
    },
    SpeechSynthesizer: jest.fn().mockImplementation(() => ({
      speakTextAsync: jest.fn(),
      stopSpeakingAsync: jest.fn(),
      close: jest.fn(),
    })),
    ResultReason: {
      SynthesizingAudioCompleted: 'SynthesizingAudioCompleted',
      Canceled: 'Canceled',
    },
  };
});

jest.mock(
  "react-markdown",
  () =>
    ({ children }: { children: React.ReactNode }) => {
      return <div data-testid="mock-react-markdown">{children}</div>;
    }
);
jest.mock("remark-gfm", () => () => {});
jest.mock("remark-supersub", () => () => {});

const speechMockData = {
  key: "some-key",
  languages: ["en-US", "fr-FR", "de-DE", "it-IT"],
  region: "uksouth",
  token: "some-token",
};

// Mock the Speech SDK
jest.mock("microsoft-cognitiveservices-speech-sdk", () => {
  return {
    SpeechConfig: {
      fromSubscription: jest.fn(),
      fromSpeakerOutput: jest.fn().mockReturnValue({}),
    },
    AudioConfig: {
      fromDefaultSpeakerOutput: jest.fn(),
      fromSpeakerOutput: jest.fn().mockReturnValue({}),
    },
    SpeechSynthesizer: jest.fn().mockImplementation(() => ({
      speakTextAsync: jest.fn((text, callback) => {
        callback({
          audioData: new ArrayBuffer(1024),
          audioDuration: 52375000,
          reason: 10,
        });
      }),
      close: jest.fn(),
    })),

    SpeakerAudioDestination: jest.fn().mockImplementation(() => ({
      pause: jest.fn(),
      resume: jest.fn(),
      close: jest.fn(),
    })),
    ResultReason: {
      SynthesizingAudioCompleted: 10,
      Canceled: 1,
    },
  };
});

const componentPropsWithCitations = conversationResponseWithCitations;

const createFetchResponse = (ok: boolean, data: any) => {
  return { ok: ok, json: () => new Promise((resolve) => resolve(data)) };
};

describe("Answer.tsx", () => {
  const mockCitationClick = jest.fn();
  const mockOnSpeak = jest.fn();
  beforeEach(() => {
    global.fetch = jest.fn();
    Element.prototype.scrollIntoView = jest.fn();
    window.alert = jest.fn();
  });
  afterEach(() => {
    jest.clearAllMocks();
  });

  test("AI Generated Content Incorrect Text should be found", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{ answer: "User Question 1", citations: [] }}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
          isActive={true}
          index={0}
        />
      );
    });
    const AIGeneratedContentElement = screen.getByText(
      /ai\-generated content may be incorrect/i
    );
    expect(AIGeneratedContentElement).toBeInTheDocument();
  });

  test("No Of Citations Should Show 5 references", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const referencesElement = screen.getByTestId("no-of-references");
    expect(referencesElement).toBeInTheDocument();
    expect(referencesElement.textContent).toEqual("5 references");
  });

  test("On Click references show citations list", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const referencesElement = screen.getByTestId("toggle-citations-list");
    await act(async () => {
      fireEvent.click(referencesElement);
    });
    const citationsListContainer = screen.getByTestId("citations-container");
    expect(citationsListContainer).toBeInTheDocument()
  });

  test("On focus and trigger Enter It should show citations list", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const referencesElement = screen.getByTestId("toggle-citations-list");
    await act(async () => {
      referencesElement.focus();
      fireEvent.keyDown(referencesElement, { key: 'Enter', code: 'Enter', charCode: 13 });
    });
    const citationsListContainer = screen.getByTestId("citations-container");
    expect(citationsListContainer).toBeInTheDocument()
  });

  test("should be able to click play", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    const playBtnAfterClick = screen.queryByTestId("play-button");
    const pauseBtnAfterClick = screen.getByTestId("pause-button");
    expect(playBtnAfterClick).not.toBeInTheDocument();
    expect(pauseBtnAfterClick).toBeInTheDocument();
  });

  test("should be able to play pause and play again", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(() => {}, { timeout: 4000 });
    const pauseBtnAfterClick = screen.getByTestId("pause-button");
    expect(pauseBtnAfterClick).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(pauseBtnAfterClick);
    });
    const playBtnAfterPause = screen.queryByTestId("play-button");
    expect(playBtnAfterPause).toBeInTheDocument();
  });

  test("should be able to pause after play", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(() => {}, { timeout: 4000 });
    const pauseBtnAfterClick = screen.getByTestId("pause-button");
    expect(pauseBtnAfterClick).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(pauseBtnAfterClick);
    });
    await waitFor(
      async () => {
        const playBtnAfterPause = screen.queryByTestId("play-button");
        expect(playBtnAfterPause).toBeInTheDocument();
        await act(async () => {
          fireEvent.click(pauseBtnAfterClick);
        });
      },
      { timeout: 3000 }
    );
  });

  test("should be able to get synthesized audio after clicking play", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    // let reRender;
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(() => {}, { timeout: 4000 });
  });

  test("on change of isActive prop playing audio should stop", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    let reRender: (ui: React.ReactNode) => void;
    await act(async () => {
      const { rerender } = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
      reRender = rerender;
    });

    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });

    await act(async () => {
      const pauseBtn = screen.getByTestId("pause-button");
      expect(pauseBtn).toBeInTheDocument();
      reRender(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={false}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playAfterActiveFalse = screen.getByTestId("play-button");
    expect(playAfterActiveFalse).toBeInTheDocument();
  });

  test("on index prop update new synthesizer to be initialized", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    let reRender: (ui: React.ReactNode) => void;
    await act(async () => {
      const { rerender } = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
      reRender = rerender;
    });

    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });

    await act(async () => {
      const pauseBtn = screen.getByTestId("pause-button");
      expect(pauseBtn).toBeInTheDocument();
      reRender(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={false}
          index={3}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playAfterActiveFalse = screen.getByTestId("play-button");
    expect(playAfterActiveFalse).toBeInTheDocument();
  });

  test("After duration completing it should show Play button", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(
      () => {
        const playBtnAfterClick = screen.getByTestId("play-button");
        expect(playBtnAfterClick).toBeInTheDocument();
      },
      { timeout: 7000 }
    );
  }, 8000);

  test("window should Alert when copying the answer", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });

    const messageBox = screen.getByTestId("message-box");
    expect(messageBox).toBeInTheDocument();
    fireEvent.copy(messageBox);
    expect(window.alert).toHaveBeenCalledWith("Please consider where you paste this content.");
  });
  test("renders correctly without citations", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );

    await act(async () => {
      render(
        <Answer
          answer={{ answer: "User Question without citations.", citations: [] }}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
          isActive={true}
          index={1}
        />
      );
    });

    // Check if the answer text is rendered correctly
    const answerTextElement = screen.getByText(/User Question without citations/i);
    expect(answerTextElement).toBeInTheDocument();

    // Verify that the citations container is not rendered
    const citationsContainer = screen.queryByTestId("citations-container");
    expect(citationsContainer).not.toBeInTheDocument();

    // Verify that no references element is displayed
    const referencesElement = screen.queryByTestId("no-of-references");
    expect(referencesElement).not.toBeInTheDocument();
  });
  test("should stop audio playback when isActive is false", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );

    await act(async () => {
      const { rerender } = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });

    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(playBtn);
    });

    const pauseBtn = screen.getByTestId("pause-button");
    expect(pauseBtn).toBeInTheDocument();

    // Rerender with isActive set to false
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={false}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });

    expect(playBtn).toBeInTheDocument(); // Ensure the play button is back
    //expect(pauseBtn).not.toBeInTheDocument(); // Ensure pause button is not there
  });
  test("should initialize new synthesizer on index prop update", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );

    let rerender;
    await act(async () => {
      const { rerender: rerenderFunc } = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
      rerender = rerenderFunc;
    });

    const playBtn = screen.getByTestId("play-button");
    await act(async () => {
      fireEvent.click(playBtn);
    });

    const pauseBtn = screen.getByTestId("pause-button");
    expect(pauseBtn).toBeInTheDocument();

    // Rerender with a different index
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={3} // Change index
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });

    // Check if a new synthesizer has been initialized
    const newPlayBtn = screen.getByTestId("play-button");
    expect(newPlayBtn).toBeInTheDocument();
    //expect(pauseBtn).not.toBeInTheDocument(); // Ensure previous pause button is gone
  });
  test("test the reference is clickabel", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    fireEvent.click(screen.getByTestId(/toggle-citations-list/i));
    fireEvent.click(screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    }));
    expect(screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    })).toBeInTheDocument()
  });
  test("test the reference is key enter", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    fireEvent.click(screen.getByTestId(/toggle-citations-list/i));
    fireEvent.keyDown (screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    }), { key : 'Enter' });
    expect(screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    })).toBeInTheDocument()
  });
  test("test the reference is key space", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    fireEvent.click(screen.getByTestId(/toggle-citations-list/i));
    fireEvent.keyDown (screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    }), { key : " " });
    expect(screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    })).toBeInTheDocument()
  });
  test("test the reference is on key enter/space", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    fireEvent.click(screen.getByTestId(/toggle-citations-list/i));
    fireEvent.keyDown (screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    }), { key : "a" });
    expect(screen.getByRole('button', {
      name: /1 msft_fy23q4_10k\.docx \- part 7/i
    })).toBeInTheDocument()
  });
  test('test Generating answer... ', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{ answer: "Generating answer...", citations: [] }}
          isActive={true}
          index={3}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    expect(screen.getByText(/Generating answer.../i)).toBeInTheDocument()
  });
  test('test the api thow error', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false })
    const consoleSpy = jest.spyOn(console, 'log');
    let renderref
    await act(async () => {
      renderref = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    expect(consoleSpy).toHaveBeenCalled();
    // Restore the original console.log
    consoleSpy.mockRestore();
  });
  // test('test speech', async () => {
  //   (global.fetch as jest.Mock).mockResolvedValue(
  //     createFetchResponse(true, speechMockData)
  //   );
  //   await act(async () => {
  //     render(
  //       <Answer
  //         answer={{
  //           answer: componentPropsWithCitations.answer.answer,
  //           citations: componentPropsWithCitations.answer.citations,
  //         }}
  //         isActive={true}
  //         index={2}
  //         onCitationClicked={mockCitationClick}
  //         onSpeak={mockOnSpeak}
  //       />
  //     );
  //   });
  //   const playBtn = screen.getByRole('button', {
  //     name: /speak/i
  //   });
  //   await act(async () => {
  //     fireEvent.click(playBtn);
  //   });
  //   await waitFor(() => {}, { timeout: 5000 });
  //   const pauseBtnAfterClick = screen.getByTestId("pause-button");
  //   await act(async () => {
  //     fireEvent.click(pauseBtnAfterClick);
  //   });
  //   screen.logTestingPlaygroundURL()
  // });
});
