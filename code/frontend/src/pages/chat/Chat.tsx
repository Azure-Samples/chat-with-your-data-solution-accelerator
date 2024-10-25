import React, { useRef, useState, useEffect } from "react";
import { Stack } from "@fluentui/react";
import { BroomRegular, SquareRegular } from "@fluentui/react-icons";
import {
  SpeechRecognizer,
  ResultReason,
} from "microsoft-cognitiveservices-speech-sdk";
import { v4 as uuidv4 } from "uuid";

import styles from "./Chat.module.css";
import { multiLingualSpeechRecognizer } from "../../util/SpeechToText";
import { useBoolean } from "@fluentui/react-hooks";
import {
  ChatMessage,
  ConversationRequest,
  callConversationApi,
  Citation,
  ChatResponse,
  getAssistantTypeApi,
  historyList,
  Conversation,
  historyUpdate,
  historyDeleteAll,
  historyRead,
  getFrontEndSettings,
} from "../../api";
import { Answer } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import Layout from "../layout/Layout";
import { AssistantTypeSection } from "../../components/AssistantTypeSection/AssistantTypeSection";
import { ChatMessageContainer } from "../../components/ChatMessageContainer/ChatMessageContainer";
import { CitationPanel } from "../../components/CitationPanel/CitationPanel";
import { ChatHistoryPanel } from "../../components/ChatHistoryPanel/ChatHistoryPanel";

const OFFSET_INCREMENT = 25;
const [ASSISTANT, TOOL, ERROR] = ["assistant", "tool", "error"];

const Chat = () => {
  const lastQuestionRef = useRef<string>("");
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showLoadingMessage, setShowLoadingMessage] = useState<boolean>(false);
  const [isAssistantAPILoading, setIsAssistantAPILoading] = useState(false);
  const [isSendButtonDisabled, setSendButtonDisabled] = useState(false);
  const [activeCitation, setActiveCitation] =
    useState<
      [
        content: string,
        id: string,
        title: string,
        filepath: string,
        url: string,
        metadata: string,
      ]
    >();
  const [isCitationPanelOpen, setIsCitationPanelOpen] =
    useState<boolean>(false);
  const [answers, setAnswers] = useState<ChatMessage[]>([]);
  const [toggleSpinner, setToggleSpinner] = React.useState(false);
  const [showContextualMenu, setShowContextualMenu] = React.useState(false);
  const [showContextualPopup, setShowContextualPopup] = React.useState(false);
  const abortFuncs = useRef([] as AbortController[]);
  const [conversationId, setConversationId] = useState<string>(uuidv4());
  const [userMessage, setUserMessage] = useState("");
  const [recognizedText, setRecognizedText] = useState<string>("");
  const [isRecognizing, setIsRecognizing] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognizerRef = useRef<SpeechRecognizer | null>(null);
  const [assistantType, setAssistantType] = useState("");
  const [activeCardIndex, setActiveCardIndex] = useState<number | null>(null);
  const [isTextToSpeachActive, setIsTextToSpeachActive] = useState(false);
  const [showHistoryBtn, setShowHistoryBtn] = useState(false);
  const [showHistoryPanel, setShowHistoryPanel] = useState(false);
  const [fetchingChatHistory, setFetchingChatHistory] = useState(false);
  const [offset, setOffset] = useState<number>(0);
  const [chatHistory, setChatHistory] = useState<Conversation[]>([]);
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [selectedConvId, setSelectedConvId] = useState<string>("");
  const [hideClearAllDialog, { toggle: toggleClearAllDialog }] =
    useBoolean(true);
  const [clearing, setClearing] = React.useState(false);
  const [clearingError, setClearingError] = React.useState(false);
  const [fetchingConvMessages, setFetchingConvMessages] = React.useState(false);
  const [isSavingToDB, setIsSavingToDB] = React.useState(false);
  const [isInitialAPItriggered, setIsInitialAPItriggered] = useState(false);

  const saveToDB = async (messages: ChatMessage[], convId: string) => {
    if (!convId || !messages.length) {
      return;
    }
    const isNewConversation = !selectedConvId;
    setIsSavingToDB(true);
    await historyUpdate(messages, convId)
      .then(async (res) => {
        if (!res.ok) {
          let errorMessage = "Answers can't be saved at this time.";
          let errorChatMsg: ChatMessage = {
            id: uuidv4(),
            role: ERROR,
            content: errorMessage,
            date: new Date().toISOString(),
          };
          if (!messages) {
            setAnswers([...messages, errorChatMsg]);
            let err: Error = {
              ...new Error(),
              message: "Failure fetching current chat state.",
            };
            throw err;
          }
        }
        let responseJson = await res.json();
        if (isNewConversation && responseJson?.success) {
          const metaData = responseJson?.data;
          const newConversation = {
            id: metaData?.conversation_id,
            title: metaData?.title,
            messages: messages,
            date: metaData?.date,
          };
          setChatHistory((prevHistory) => [newConversation, ...prevHistory]);
          setSelectedConvId(metaData?.conversation_id);
        } else if (responseJson?.success) {
          setMessagesByConvId(convId, messages);
        }
        setIsSavingToDB(false);
        return res as Response;
      })
      .catch((err) => {
        console.error("Error: while saving data", err);
        setIsSavingToDB(false);
      });
  };

  const makeApiRequest = async (question: string) => {
    lastQuestionRef.current = question;

    setIsLoading(true);
    setShowLoadingMessage(true);
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const userMessage: ChatMessage = {
      role: "user",
      content: recognizedText || question,
      id: uuidv4(),
      date: new Date().toISOString(),
    };

    const request: ConversationRequest = {
      id: selectedConvId || conversationId,
      messages: [...answers, userMessage].filter(
        (messageObj) => messageObj.role !== ERROR
      ),
    };
    let result = {} as ChatResponse;
    try {
      const response = await callConversationApi(
        request,
        abortController.signal
      );
      if (response?.body) {
        const reader = response.body.getReader();
        let runningText = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          var text = new TextDecoder("utf-8").decode(value);
          const objects = text.split("\n");
          objects.forEach((obj) => {
            try {
              runningText += obj;
              result = JSON.parse(runningText);
              setShowLoadingMessage(false);
              if (result.error) {
                setAnswers([
                  ...answers,
                  userMessage,
                  {
                    role: "error",
                    content: result.error,
                    id: "",
                    date: "",
                  },
                ]);
              } else {
                setAnswers([
                  ...answers,
                  userMessage,
                  ...result.choices[0].messages,
                ]);
              }
              runningText = "";
            } catch {}
          });
        }
        const updatedMessages = [
          ...answers,
          userMessage,
          ...result.choices[0].messages,
        ];
        setAnswers(updatedMessages);
        saveToDB(updatedMessages, selectedConvId || conversationId);
      }
    } catch (e) {
      if (!abortController.signal.aborted) {
        if (e instanceof Error) {
          alert(e.message);
        } else {
          alert(
            "An error occurred. Please try again. If the problem persists, please contact the site administrator."
          );
        }
      }
      setAnswers([...answers, userMessage]);
    } finally {
      setIsLoading(false);
      setShowLoadingMessage(false);
      abortFuncs.current = abortFuncs.current.filter(
        (a) => a !== abortController
      );
    }

    return abortController.abort();
  };
  // Buffer to store recognized text
  let recognizedTextBuffer = "";
  let currentSentence = "";

  const startSpeechRecognition = async () => {
    if (!isRecognizing) {
      setIsRecognizing(true);
      recognizerRef.current = await multiLingualSpeechRecognizer(); // Store the recognizer in the ref

      recognizerRef.current.recognized = (s, e) => {
        if (e.result.reason === ResultReason.RecognizedSpeech) {
          let recognizedText = e.result.text.trim();
          // Append current sentence to buffer if it's not empty
          if (currentSentence) {
            recognizedTextBuffer += ` ${currentSentence.trim()}`;
            currentSentence = "";
          }
          // Start new sentence
          currentSentence += ` ${recognizedText}`;
          //set text in textarea
          setUserMessage((recognizedTextBuffer + currentSentence).trim());
          setRecognizedText((recognizedTextBuffer + currentSentence).trim());
        }
      };

      recognizerRef.current.startContinuousRecognitionAsync(
        () => {
          setIsRecognizing(true);
          setIsListening(true);
        },
        (error) => {
          console.error(`Error starting recognition: ${error}`);
        }
      );
    }
  };

  const stopSpeechRecognition = (e: React.KeyboardEvent | React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isRecognizing) {
      if (recognizerRef.current) {
        recognizerRef.current.stopContinuousRecognitionAsync(() => {
          recognizerRef.current?.close();
        });
      }
      setIsRecognizing(false);
      setRecognizedText("");
      setSendButtonDisabled(false);
      setIsListening(false);
    }
  };

  const onMicrophoneClick = async (
    e: React.KeyboardEvent | React.MouseEvent
  ) => {
    // clear the previous text
    e.preventDefault();
    e.stopPropagation();
    setUserMessage("");
    setRecognizedText("");
    if (!isRecognizing) {
      setSendButtonDisabled(true);
      await startSpeechRecognition();
    } else {
      if (recognizerRef.current) {
        recognizerRef.current.stopContinuousRecognitionAsync(() => {
          recognizerRef.current?.close();
        });
      }
      setIsRecognizing(false);
      setSendButtonDisabled(false);
      setIsListening(false);
      setRecognizedText(userMessage);
    }
  };

  const clearChat = () => {
    lastQuestionRef.current = "";
    setActiveCitation(undefined);
    setAnswers([]);
    setConversationId(uuidv4());
    setSelectedConvId("");
  };

  const stopGenerating = () => {
    abortFuncs.current.forEach((a) => a.abort());
    setShowLoadingMessage(false);
    setIsLoading(false);
  };

  useEffect(() => {
    chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" });
    const fetchAssistantType = async () => {
      try {
        setIsAssistantAPILoading(true);
        const result = await getAssistantTypeApi();
        if (result) {
          setAssistantType(result.ai_assistant_type);
        }
        setIsAssistantAPILoading(false);
        return result;
      } catch (error) {
        console.error("Error fetching assistant type:", error);
      }
    };
    fetchAssistantType();
  }, [showLoadingMessage]);

  const onShowCitation = (citation: Citation) => {
    setActiveCitation([
      citation.content,
      citation.id,
      citation.title ?? "",
      citation.filepath ?? "",
      "",
      "",
    ]);
    setIsCitationPanelOpen(true);
    setShowHistoryPanel(false);
  };

  const onClearAllChatHistory = async () => {
    toggleToggleSpinner(true);
    setClearing(true);
    const response = await historyDeleteAll();
    if (!response.ok) {
      setClearingError(true);
    } else {
      setChatHistory([]);
      toggleClearAllDialog();
      setShowContextualPopup(false);
      setAnswers([]);
      setSelectedConvId("");
    }
    setClearing(false);
    toggleToggleSpinner(false);
  };

  const onHideClearAllDialog = () => {
    toggleClearAllDialog();
    setTimeout(() => {
      setClearingError(false);
    }, 2000);
  };

  const onShowContextualMenu = React.useCallback(
    (ev: React.MouseEvent<HTMLElement>) => {
      ev.preventDefault(); // don't navigate
      setShowContextualMenu(true);
      setShowContextualPopup(true);
    },
    []
  );

  const onHideContextualMenu = React.useCallback(
    () => setShowContextualMenu(false),
    []
  );

  const handleSpeech = (index: number, status: string) => {
    if (status != "pause") setActiveCardIndex(index);
    setIsTextToSpeachActive(status == "speak" ? true : false);
  };
  const onSetShowHistoryPanel = () => {
    if (!showHistoryPanel) {
      setIsCitationPanelOpen(false);
    }
    setShowHistoryPanel((prevState) => !prevState);
  };

  const getMessagesByConvId = (id: string) => {
    const conv = chatHistory.find((obj) => String(obj.id) === String(id));
    if (conv) {
      return conv?.messages || [];
    }
    return [];
  };

  const setMessagesByConvId = (id: string, messagesList: ChatMessage[]) => {
    const tempHistory = [...chatHistory];
    const matchedIndex = tempHistory.findIndex(
      (obj) => String(obj.id) === String(id)
    );
    if (matchedIndex > -1) {
      tempHistory[matchedIndex].messages = messagesList;
    }
  };

  const onSelectConversation = async (id: string) => {
    if (!id) {
      console.error("No conversation Id found");
      return;
    }
    const messages = getMessagesByConvId(id);
    if (messages.length === 0) {
      setFetchingConvMessages(true);
      const responseMessages = await historyRead(id);
      setAnswers(responseMessages);
      setMessagesByConvId(id, responseMessages);
      setFetchingConvMessages(false);
    } else {
      setAnswers(messages);
    }
    setSelectedConvId(id);
  };

  useEffect(() => {
    chatMessageStreamEnd.current?.scrollIntoView({ behavior: "instant" });
  }, [selectedConvId]);

  const onHistoryTitleChange = (id: string, newTitle: string) => {
    const tempChatHistory = [...chatHistory];
    const index = tempChatHistory.findIndex((obj) => obj.id === id);
    if (index > -1) {
      tempChatHistory[index].title = newTitle;
      setChatHistory(tempChatHistory);
    }
  };

  const toggleToggleSpinner = (toggler: boolean) => {
    setToggleSpinner(toggler);
  };

  useEffect(() => {
    setIsInitialAPItriggered(true);
  }, []);

  useEffect(() => {
    if (isInitialAPItriggered) {
      (async () => {
        const response = await getFrontEndSettings();
        if (response.CHAT_HISTORY_ENABLED) {
          handleFetchHistory();
          setShowHistoryBtn(true);
        }
      })();
    }
  }, [isInitialAPItriggered]);

  const onHistoryDelete = (id: string) => {
    const tempChatHistory = [...chatHistory];
    tempChatHistory.splice(
      tempChatHistory.findIndex((a) => a.id === id),
      1
    );
    setChatHistory(tempChatHistory);
    if (id === selectedConvId) {
      lastQuestionRef.current = "";
      setActiveCitation(undefined);
      setAnswers([]);
      setSelectedConvId("");
    }
  };

  const handleFetchHistory = async () => {
    if (fetchingChatHistory || !hasMoreRecords) {
      return;
    }
    setFetchingChatHistory(true);
    await historyList(offset).then((response) => {
      if (Array.isArray(response)) {
        setChatHistory((prevData) => [...prevData, ...response]);
        if (response.length === OFFSET_INCREMENT) {
          setOffset((offset) => (offset += OFFSET_INCREMENT));
          // Stopping offset increment if there were no records
        } else if (response.length < OFFSET_INCREMENT) {
          setHasMoreRecords(false);
        }
      } else {
        setChatHistory([]);
      }
      setFetchingChatHistory(false);
      return response;
    });
  };

  const loadingMessageBlock = () => {
    return (
      <React.Fragment key="generating-answer">
        <div className={styles.chatMessageUser}>
          <div className={styles.chatMessageUserMessage}>
            {lastQuestionRef.current}
          </div>
        </div>
        <div className={styles.chatMessageGpt} data-testid="generatingAnswer">
          <Answer
            answer={{
              answer: "Generating answer...",
              citations: [],
            }}
            onCitationClicked={() => null}
            index={0}
          />
        </div>
      </React.Fragment>
    );
  };
  const showAssistantTypeSection =
    !fetchingConvMessages && !lastQuestionRef.current && answers.length === 0;
  const showCitationPanel =
    answers.length > 0 && isCitationPanelOpen && activeCitation;
  return (
    <Layout
      toggleSpinner={toggleSpinner}
      showHistoryBtn={showHistoryBtn}
      onSetShowHistoryPanel={onSetShowHistoryPanel}
      showHistoryPanel={showHistoryPanel}
    >
      <div className={styles.container}>
        <Stack horizontal className={styles.chatRoot}>
          <div
            className={`${styles.chatContainer} ${styles.MobileChatContainer}`}
          >
            {showAssistantTypeSection ? (
              <AssistantTypeSection
                assistantType={assistantType}
                isAssistantAPILoading={isAssistantAPILoading}
              />
            ) : (
              <div
                className={styles.chatMessageStream}
                style={{ marginBottom: isLoading ? "40px" : "0px" }}
              >
                <ChatMessageContainer
                  activeCardIndex={activeCardIndex}
                  answers={answers}
                  fetchingConvMessages={fetchingConvMessages}
                  handleSpeech={handleSpeech}
                  onShowCitation={onShowCitation}
                />
                {showLoadingMessage && loadingMessageBlock()}
                <div data-testid="streamendref-id" ref={chatMessageStreamEnd} />
              </div>
            )}
            <div>
              {isRecognizing && !isListening && <p>Please wait...</p>}{" "}
              {isListening && <p>Listening...</p>}{" "}
            </div>

            <Stack horizontal className={styles.chatInput}>
              {isLoading && (
                <Stack
                  horizontal
                  className={styles.stopGeneratingContainer}
                  role="button"
                  aria-label="Stop generating"
                  tabIndex={0}
                  onClick={stopGenerating}
                  onKeyDown={(e) =>
                    e.key === "Enter" || e.key === " " ? stopGenerating() : null
                  }
                >
                  <SquareRegular
                    className={styles.stopGeneratingIcon}
                    aria-hidden="true"
                  />
                  <span
                    className={styles.stopGeneratingText}
                    aria-hidden="true"
                  >
                    Stop generating
                  </span>
                </Stack>
              )}
              <BroomRegular
                className={`${styles.clearChatBroom} ${styles.mobileclearChatBroom}`}
                style={{
                  background:
                    isLoading || answers.length === 0
                      ? "#BDBDBD"
                      : "radial-gradient(109.81% 107.82% at 100.1% 90.19%, #0F6CBD 33.63%, #2D87C3 70.31%, #8DDDD8 100%)",
                  cursor: isLoading || answers.length === 0 ? "" : "pointer",
                }}
                onClick={clearChat}
                onKeyDown={(e) =>
                  e.key === "Enter" || e.key === " " ? clearChat() : null
                }
                aria-label="Clear session"
                role="button"
                tabIndex={0}
              />
              <QuestionInput
                clearOnSend
                placeholder="Type a new question..."
                disabled={isLoading}
                onSend={(question) => makeApiRequest(question)}
                recognizedText={recognizedText}
                isSendButtonDisabled={isSendButtonDisabled}
                onMicrophoneClick={onMicrophoneClick}
                onStopClick={stopSpeechRecognition}
                isListening={isListening}
                isRecognizing={isRecognizing}
                setRecognizedText={setRecognizedText}
                isTextToSpeachActive={isTextToSpeachActive}
              />
            </Stack>
          </div>
          {showCitationPanel && (
            <CitationPanel
              activeCitation={activeCitation}
              setIsCitationPanelOpen={setIsCitationPanelOpen}
            />
          )}

          {showHistoryPanel && (
            <ChatHistoryPanel
              chatHistory={chatHistory}
              clearing={clearing}
              clearingError={clearingError}
              fetchingChatHistory={fetchingChatHistory}
              fetchingConvMessages={fetchingConvMessages}
              handleFetchHistory={handleFetchHistory}
              hideClearAllDialog={hideClearAllDialog}
              isLoading={isLoading}
              isSavingToDB={isSavingToDB}
              onClearAllChatHistory={onClearAllChatHistory}
              onHideClearAllDialog={onHideClearAllDialog}
              onHideContextualMenu={onHideContextualMenu}
              onHistoryDelete={onHistoryDelete}
              onHistoryTitleChange={onHistoryTitleChange}
              onSelectConversation={onSelectConversation}
              onShowContextualMenu={onShowContextualMenu}
              selectedConvId={selectedConvId}
              setShowHistoryPanel={setShowHistoryPanel}
              showContextualMenu={showContextualMenu}
              showContextualPopup={showContextualPopup}
              showLoadingMessage={showLoadingMessage}
              toggleClearAllDialog={toggleClearAllDialog}
              toggleToggleSpinner={toggleToggleSpinner}
            />
          )}
        </Stack>
      </div>
    </Layout>
  );
};

export default Chat;
