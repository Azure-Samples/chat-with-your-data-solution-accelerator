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
    expect(citationsListContainer.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  test("Should be able click Chevron to get citation list", async () => {
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
    const chevronIcon = screen.getByTestId("chevron-icon");
    await act(async () => {
      fireEvent.click(chevronIcon);
    });
    const citationsListContainer = screen.getByTestId("citations-container");
    expect(citationsListContainer.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });
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
});
