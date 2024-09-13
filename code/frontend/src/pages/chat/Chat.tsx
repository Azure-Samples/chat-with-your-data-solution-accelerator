import React, { useRef, useState, useEffect, useCallback } from "react";
import {
  CommandBarButton,
  ContextualMenu,
  DefaultButton,
  Dialog,
  DialogFooter,
  IContextualMenuItem,
  Separator,
  Spinner,
  SpinnerSize,
  Stack,
  StackItem,
  Text,
} from "@fluentui/react";
import {
  BroomRegular,
  DismissRegular,
  SquareRegular,
} from "@fluentui/react-icons";
import {
  SpeechRecognizer,
  ResultReason,
} from "microsoft-cognitiveservices-speech-sdk";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { v4 as uuidv4 } from "uuid";

import styles from "./Chat.module.css";
import Azure from "../../assets/Azure.svg";
import { multiLingualSpeechRecognizer } from "../../util/SpeechToText";

import {
  ChatMessage,
  ConversationRequest,
  callConversationApi,
  Citation,
  ToolMessageContent,
  ChatResponse,
  getAssistantTypeApi,
  historyList,
  Conversation,
  historyUpdate,
} from "../../api";
import { Answer } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import Cards from "./Cards_contract/Cards";
import Layout from "../layout/Layout";
import HistoryPanel from "../../components/HistoryPanel/HistoryPanel";
import ChatHistoryList from "./ChatHistoryList";

const OFFSET_INCREMENT = 25;
const [ASSISTANT, TOOL, ERROR] = ["assistant", "tool", "error"];

const Chat = () => {
  const lastQuestionRef = useRef<string>("");
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showLoadingMessage, setShowLoadingMessage] = useState<boolean>(false);

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
  const [showHistoryBtn, setShowHistoryBtn] = useState(true);
  const [showHistoryPanel, setShowHistoryPanel] = useState(true);
  const [fetchingChatHistory, setFetchingChatHistory] = useState(false);
  const [offset, setOffset] = useState<number>(0);
  const firstRender = useRef(true);
  const observerTarget = useRef(null);
  const [observerCounter, setObserverCounter] = useState(0);
  const [showContextualMenu, setShowContextualMenu] = React.useState(false);
  const [chatHistory, setChatHistory] = useState<Conversation[]>([]);
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [selectedConvId, setSelectedConvId] = useState<string>("");

  const saveToDB = async (messages: ChatMessage[], convId: string) => {
    if (!convId || !messages.length) {
      return;
    }
    const isNewConversation = !selectedConvId;
    await historyUpdate(messages, convId)
      .then(async (res) => {
        if (!res.ok) {
          let errorMessage =
            "Answers can't be saved at this time.";
          let errorChatMsg: ChatMessage = {
            id: uuidv4(), // TODO need to update to uuid() from react-uuid
            role: ERROR,
            content: errorMessage,
            date: new Date().toISOString(),
          };
          if (!messages) {
            let err: Error = {
              ...new Error(),
              message: "Failure fetching current chat state.",
            };
            throw err;
          }
          setAnswers([...messages, errorChatMsg]);
        }
        let responseJson = await res.json();
        console.log("update response", res, responseJson);
        if (isNewConversation && responseJson?.success) {
          const metaData = responseJson?.data;
          const newConversation = {
            id: metaData?.conversation_id,
            title: metaData?.title,
            messages: messages,
            date: metaData?.date,
          };
          // updatedAt?: string;
          setChatHistory((prevHistory) => [newConversation, ...prevHistory]);
          setSelectedConvId(metaData?.conversation_id);
        }
        return res as Response;
      })
      .catch((err) => {
        console.error("Error: while saving data", err);
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
          console.log(">>> reading from response");
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
        saveToDB(updatedMessages, conversationId);
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

  const stopSpeechRecognition = () => {
    if (isRecognizing) {
      // console.log("Stopping continuous recognition...");
      if (recognizerRef.current) {
        recognizerRef.current.stopContinuousRecognitionAsync(() => {
          // console.log("Speech recognition stopped.");
          recognizerRef.current?.close();
        });
      }
      setIsRecognizing(false);
      setRecognizedText("");
      setSendButtonDisabled(false);
      setIsListening(false);
    }
  };

  const onMicrophoneClick = async () => {
    // clear the previous text
    setUserMessage("");
    setRecognizedText("");
    if (!isRecognizing) {
      setSendButtonDisabled(true);
      await startSpeechRecognition();
    } else {
      stopSpeechRecognition();
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
        const result = await getAssistantTypeApi();
        if (result) {
          setAssistantType(result.ai_assistant_type);
        }
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

  const parseCitationFromMessage = (message: ChatMessage) => {
    if (message.role === "tool") {
      try {
        const toolMessage = JSON.parse(message.content) as ToolMessageContent;
        return toolMessage.citations;
      } catch {
        return [];
      }
    }
    return [];
  };

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

  const getMessagesByconvId = (id: string) => {
    const conv = chatHistory.find((obj) => String(obj.id) === String(id));
    if (conv) {
      return conv.messages;
    }
    return [];
  };

  const onSelectConversation = (id: string) => {
    console.log("selected conv id in chat", id);
    const messages = getMessagesByconvId(id);
    setAnswers(messages);
    setSelectedConvId(id);
  };

  const onHistoryTitleChange = (id: string, newTitle: string) => {
    const tempChatHistory = [...chatHistory];
    const conv = tempChatHistory.find((obj) => obj.id === id);
    if (conv) {
      conv.title = newTitle;
      setChatHistory(tempChatHistory);
    }
  };

  const onHistoryDelete = (id: string) => {
    // remove seleted id
    const tempChatHistory = [...chatHistory];
    tempChatHistory.splice(
      tempChatHistory.findIndex((a) => a.id === id),
      1
    );
    setChatHistory(tempChatHistory);
  };

  const handleFetchHistory = async () => {
    if (fetchingChatHistory || !hasMoreRecords) {
      return;
    }
    setFetchingChatHistory(true);
    await historyList(offset).then((response) => {
      console.log("HL response", response);
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

  const menuItems: IContextualMenuItem[] = [
    {
      key: "clearAll",
      text: "Clear all chat history",
      disabled: isLoading,
      iconProps: { iconName: "Delete" },
    },
  ];

  // const onShowContextualMenu = useCallback(
  //   (ev: React.MouseEvent<HTMLElement>) => {
  //     ev.preventDefault(); // don't navigate
  //     setShowContextualMenu(true);
  //   },
  //   []
  // );
  console.log("answers", answers, lastQuestionRef);
  return (
    <Layout
      showHistoryBtn={showHistoryBtn}
      onSetShowHistoryPanel={onSetShowHistoryPanel}
      showHistoryPanel={showHistoryPanel}
    >
      <div className={styles.container}>
        <Stack horizontal className={styles.chatRoot}>
          <div
            className={`${styles.chatContainer} ${styles.MobileChatContainer}`}
          >
            {!lastQuestionRef.current && answers.length === 0 ? (
              <Stack className={styles.chatEmptyState}>
                <img
                  src={Azure}
                  className={styles.chatIcon}
                  aria-hidden="true"
                  alt="Azure AI logo"
                />
                {assistantType === "contract assistant" ? (
                  <>
                    <h1 className={styles.chatEmptyStateTitle}>
                      Contract Summarizer
                    </h1>
                    <h2 className={styles.chatEmptyStateSubtitle}>
                      AI-Powered assistant for simplified summarization
                    </h2>
                    <Cards />
                  </>
                ) : assistantType === "default" ? (
                  <>
                    <h1 className={styles.chatEmptyStateTitle}>
                      Start chatting
                    </h1>
                    <h2 className={styles.chatEmptyStateSubtitle}>
                      This chatbot is configured to answer your questions
                    </h2>
                  </>
                ) : (
                  <div className={styles.loadingContainer}>
                    <div className={styles.loadingIcon}></div>
                    <p>Loading...</p>
                  </div>
                )}
              </Stack>
            ) : (
              <div
                className={styles.chatMessageStream}
                style={{ marginBottom: isLoading ? "40px" : "0px" }}
              >
                {answers.map((answer, index) => (
                  <React.Fragment key={`${answer?.role}-${index}`}>
                    {answer.role === "user" ? (
                      <div
                        className={styles.chatMessageUser}
                        key={`${answer?.role}-${index}`}
                      >
                        <div className={styles.chatMessageUserMessage}>
                          {answer.content}
                        </div>
                      </div>
                    ) : answer.role === "assistant" ||
                      answer.role === "error" ? (
                      <div
                        className={styles.chatMessageGpt}
                        key={`${answer?.role}-${index}`}
                      >
                        <Answer
                          answer={{
                            answer:
                              answer.role === "assistant"
                                ? answer.content
                                : "Sorry, an error occurred. Try refreshing the conversation or waiting a few minutes. If the issue persists, contact your system administrator. Error: " +
                                  answer.content,
                            citations:
                              answer.role === "assistant"
                                ? parseCitationFromMessage(answers[index - 1])
                                : [],
                          }}
                          onSpeak={handleSpeech}
                          isActive={activeCardIndex === index}
                          onCitationClicked={(c) => onShowCitation(c)}
                          index={index}
                        />
                      </div>
                    ) : null}
                  </React.Fragment>
                ))}
                {showLoadingMessage && (
                  <React.Fragment key="generating-answer">
                    <div className={styles.chatMessageUser}>
                      <div className={styles.chatMessageUserMessage}>
                        {lastQuestionRef.current}
                      </div>
                    </div>
                    <div className={styles.chatMessageGpt}>
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
                )}
                <div ref={chatMessageStreamEnd} />
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
          {answers.length > 0 && isCitationPanelOpen && activeCitation && (
            <Stack.Item
              className={`${styles.citationPanel} ${styles.mobileStyles}`}
            >
              <Stack
                horizontal
                className={styles.citationPanelHeaderContainer}
                horizontalAlign="space-between"
                verticalAlign="center"
              >
                <span className={styles.citationPanelHeader}>Citations</span>
                <DismissRegular
                  className={styles.citationPanelDismiss}
                  onClick={() => setIsCitationPanelOpen(false)}
                />
              </Stack>
              <h5
                className={`${styles.citationPanelTitle} ${styles.mobileCitationPanelTitle}`}
              >
                {activeCitation[2]}
              </h5>
              <div
                className={`${styles.citationPanelDisclaimer} ${styles.mobileCitationPanelDisclaimer}`}
              >
                Tables, images, and other special formatting not shown in this
                preview. Please follow the link to review the original document.
              </div>
              <ReactMarkdown
                className={`${styles.citationPanelContent} ${styles.mobileCitationPanelContent}`}
                children={activeCitation[0]}
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
              />
            </Stack.Item>
          )}

          {showHistoryPanel && (
            <section
              className={styles.historyContainer}
              data-is-scrollable
              aria-label={"chat history panel"}
            >
              <Stack
                horizontal
                horizontalAlign="space-between"
                verticalAlign="center"
                wrap
                aria-label="chat history header"
                className="mt-8"
              >
                <StackItem>
                  <Text
                    role="heading"
                    aria-level={2}
                    style={{
                      alignSelf: "center",
                      fontWeight: "600",
                      fontSize: "18px",
                      marginRight: "auto",
                      paddingLeft: "20px",
                    }}
                  >
                    Chat history
                  </Text>
                </StackItem>
                <Stack verticalAlign="start">
                  <Stack
                    horizontal
                    // styles={commandBarButtonStyle}
                  >
                    {/* <CommandBarButton
                      iconProps={{ iconName: "More" }}
                      title={"Clear all chat history"}
                      aria-label={"clear all chat history"}
                      role="button"
                      id="moreButton"
                      onClick={onShowContextualMenu}
                      // styles={commandBarStyle}
                    />
                    <ContextualMenu
                      target={"#moreButton"}
                      items={menuItems}
                      // hidden={!showContextualMenu}
                      // onItemClick={toggleClearAllDialog}
                      // onDismiss={onHideContextualMenu}
                    /> */}
                    <CommandBarButton
                      iconProps={{ iconName: "Cancel" }}
                      title={"Hide"}
                      aria-label={"hide button"}
                      role="button"
                      onClick={() => setShowHistoryPanel(false)}
                      // styles={commandBarStyle}
                    />
                  </Stack>
                </Stack>
              </Stack>
              <Stack
                aria-label="chat history panel content"
                style={{
                  display: "flex",
                  flexGrow: 1,
                  flexDirection: "column",
                  flexWrap: "wrap",
                  padding: "1px",
                }}
              >
                <Stack className={styles.chatHistoryListContainer}>
                  {showHistoryPanel && (
                    <ChatHistoryList
                      fetchingChatHistory={fetchingChatHistory}
                      handleFetchHistory={handleFetchHistory}
                      chatHistory={chatHistory}
                      onSelectConversation={onSelectConversation}
                      selectedConvId={selectedConvId}
                      onHistoryTitleChange={onHistoryTitleChange}
                      onHistoryDelete={onHistoryDelete}
                    />
                  )}
                  {/* appStateContext?.state.chatHistoryLoadingState ===
                    ChatHistoryLoadingState.Fail &&
                    appStateContext?.state.isCosmosDBAvailable */}
                  {/* {true && (
                    <>
                      <Stack>
                        <Stack
                          horizontalAlign="center"
                          verticalAlign="center"
                          style={{ width: "100%", marginTop: 10 }}
                        >
                          <StackItem>
                            <Text
                              style={{
                                alignSelf: "center",
                                fontWeight: "400",
                                fontSize: 16,
                              }}
                            >
                              <span>Error loading chat history</span>
                            </Text>
                          </StackItem>
                          <StackItem>
                            <Text
                              style={{
                                alignSelf: "center",
                                fontWeight: "400",
                                fontSize: 14,
                              }}
                            >
                              <span>
                                Chat history can't be saved at this time
                              </span>
                            </Text>
                          </StackItem>
                        </Stack>
                      </Stack>
                    </>
                  )} */}
                  {/* appStateContext?.state.chatHistoryLoadingState ===
                    ChatHistoryLoadingState.Loading && */}
                  {/* {fetchingChatHistory && (
                    <>
                      <Stack
                        horizontal
                        horizontalAlign="center"
                        verticalAlign="center"
                        style={{ width: "100%", marginTop: 10, gap: 8 }}
                      >
                        <StackItem>
                          <Spinner size={SpinnerSize.medium} />
                        </StackItem>
                        <StackItem>
                          <span style={{ whiteSpace: "pre-wrap" }}>
                            Loading chat history
                          </span>
                        </StackItem>
                      </Stack>
                    </>
                  )} */}
                </Stack>
              </Stack>
              <Dialog
              // hidden={hideClearAllDialog}
              // onDismiss={clearing ? () => {} : onHideClearAllDialog}
              // dialogContentProps={clearAllDialogContentProps}
              // modalProps={modalProps}
              >
                <DialogFooter>
                  {/* {!clearingError && (
                    <PrimaryButton
                      onClick={onClearAllChatHistory}
                      disabled={clearing}
                      text="Clear All"
                    />
                  )} */}
                  <DefaultButton
                  // onClick={onHideClearAllDialog}
                  // disabled={clearing}
                  // text={!clearingError ? "Cancel" : "Close"}
                  />
                </DialogFooter>
              </Dialog>
            </section>
          )}
        </Stack>
      </div>
    </Layout>
  );
};

export default Chat;
