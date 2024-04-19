import { useRef, useState, useEffect, MouseEvent } from "react";
import { Stack } from "@fluentui/react";
import {
  BroomRegular,
  DismissRegular,
  RecordStopFilled,
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
  customConversationApi,
  Citation,
  ToolMessageContent,
  ChatResponse,
  CitationMetadata,
} from "../../api";
import { Answer } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import { Sidebar } from "../../components/Sidebar";
import { Avatar, Spinner } from "@fluentui/react-components";
import moment from "moment";


const Chat = () => {
  const lastQuestionRef = useRef<string>("");
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showLoadingMessage, setShowLoadingMessage] = useState<boolean>(false);
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
  const makeApiRequest = async (question: string) => {
    lastQuestionRef.current = question;

    setIsLoading(true);
    setShowLoadingMessage(true);
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const userMessage: ChatMessage = {
      role: "user",
      content: recognizedText || question,
    };

    const request: ConversationRequest = {
      id: conversationId,
      messages: [...answers, userMessage],
    };

    let result = {} as ChatResponse;
    try {
      const response = await customConversationApi(
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
                  { role: "error", content: result.error },
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
        setAnswers([...answers, userMessage, ...result.choices[0].messages]);
      }
    } catch (e) {
      if (!abortController.signal.aborted) {
        console.error(result);
        alert(
          "An error occurred. Please try again. If the problem persists, please contact the site administrator."
        );
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

  const startSpeechRecognition = async () => {
    if (!isRecognizing) {
      setIsRecognizing(true);

      recognizerRef.current = await multiLingualSpeechRecognizer(); // Store the recognizer in the ref

      recognizerRef.current.recognized = (s, e) => {
        if (e.result.reason === ResultReason.RecognizedSpeech) {
          const recognized = e.result.text;
          setUserMessage(recognized);
          setRecognizedText(recognized);
        }
      };

      recognizerRef.current.startContinuousRecognitionAsync(() => {
        setIsRecognizing(true);
        setIsListening(true);
      });
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
      setIsListening(false);
    }
  };

  const onMicrophoneClick = async () => {
    if (!isRecognizing) {
      // console.log("Starting speech recognition...");
      await startSpeechRecognition();
    } else {
      // console.log("Stopping speech recognition...");
      stopSpeechRecognition();
      setRecognizedText(userMessage);
    }
  };

  // moved clear chat into child component per design, triggered here
  const onClearChat = () => {
    clearChat();
  };

  const clearChat = () => {
    lastQuestionRef.current = "";
    setActiveCitation(undefined);
    setAnswers([]);
    setConversationId(uuidv4());
  };

  const stopGenerating = () => {
    abortFuncs.current.forEach((a) => a.abort());
    setShowLoadingMessage(false);
    setIsLoading(false);
  };

  useEffect(
    () => chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" }),
    [showLoadingMessage]
  );

  const onShowCitation = (citation: Citation, isKeyPressed: boolean) => {
    // console.log('citation: ', citation);
    // console.log('moment: ', moment().calendar());

    // const metaDataObj = citation.metadata as unknown as CitationMetadata;

    setActiveCitation([
      citation.content,
      citation.id,
      citation.title ?? "",
      citation.filepath ?? "",
      "",
      "",
    ]);

    // console.log('isKeyPressed: ', isKeyPressed);

    if (isKeyPressed) {
      setIsCitationPanelOpen(true);
    } else {
      // console.log(citation?.metadata?.original_url);
      window.open(citation?.metadata?.original_url, '_blank');
    }
  };

  const onCitationHover = (e: MouseEvent, citation: Citation) => {
    // console.log('HOVERED!!!!!!!!!');
    // console.log(e, citation);
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

  return (
    <div className={styles.container}>
      {/* <Sidebar /> */}
      <Stack horizontal className={styles.chatRoot}>
        <div
          className={`${styles.chatContainer} ${styles.MobileChatContainer}`}
        >
          {!lastQuestionRef.current ? (
            <Stack className={styles.chatEmptyState}>
              {/* <img src="../../src/assets/logo_blue.webp" className={styles.chatIcon} aria-hidden="true" /> */}
              <h6 className={styles.chatHomeText03}>Let's explore together</h6>
              <h5 className={styles.chatHomeText02}>Let's explore together</h5>
              <h3 className={styles.chatHomeText01}>Let's explore together</h3>
            </Stack>
          ) : (
            <div
              className={styles.chatMessageStream}
              style={{ marginBottom: isLoading ? "40px" : "0px" }}
            >
              <div className={styles.chatMessageStreamInner}>
                {answers.map((answer, index) => (
                  <div key={index}>
                    {answer.role === "user" ? (
                      <div className={`${styles.chatMessageUser}`} key={index}>
                        <Avatar image={{ src: '../../eddie-hoover-user-avatar.png'}} aria-label="Guest" className={styles.chatAvatar}/>
                        <div className={styles.chatMessageUserMessage}>
                          {answer.content}
                        </div>
                        <div className={` ${styles.timeStamp}`}>
                          <div>{moment().calendar()}</div>
                        </div>
                      </div>
                    ) : answer.role === "assistant" ||
                      answer.role === "error" ? (
                      <div className={`${styles.chatMessageGpt} ${styles.answerShowing}`} key={index}>
                        <Avatar image={{ src: '../../pronto-avatar-anim-close.gif'}} aria-label="Guest" className={styles.chatAvatar}/>
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
                          onCitationClicked={(c, isKeyPressed) => onShowCitation(c, isKeyPressed)}
                          // onCitationHover={(e, c) => onCitationHover(e, c)}
                          index={index}
                        />
                      </div>
                    ) : null}
                  </div>
                ))}
                {showLoadingMessage && (
                  <>
                    <div className={styles.chatMessageUser}>
                      <Avatar image={{ src: '../../eddie-hoover-user-avatar.png'}} aria-label="Guest" className={styles.chatAvatar}/>
                      <div className={styles.chatMessageUserMessage}>
                        {lastQuestionRef.current}
                      </div>
                    </div>
                    <div className={styles.chatMessageGpt}>
                      <Avatar image={{ src: '../../pronto-avatar-anim-close.gif'}} aria-label="Guest" className={styles.chatAvatar}/>
                      <Answer
                        answer={{
                          answer: "Generating Answer... AI-generated content may be incorrect",
                          citations: [],
                        }}
                        onCitationClicked={() => null}
                        index={0}
                      />
                      <Spinner size="extra-small" className={styles.thinkingSpinner} labelPosition="after" label="Thinking..." />
                    </div>
                  </>
                )}
                <div ref={chatMessageStreamEnd} />
              </div>
            </div>
          )}
          <div>
            {isRecognizing && !isListening && <p>Please wait...</p>}{" "}
            {isListening && <p>Listening...</p>}{" "}
          </div>

          <Stack horizontal className={`${styles.chatInput} ${!lastQuestionRef.current ? '' : styles.chatThreadActive}`}>
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
                <RecordStopFilled
                  className={styles.stopGeneratingIcon}
                  aria-hidden="true"
                />
                <span className={styles.stopGeneratingText} aria-hidden="true">
                  Stop Pronto
                </span>
              </Stack>
            )}
            {/* <BroomRegular
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
            /> */}
            <QuestionInput
              clearOnSend
              placeholder="Ask anything..."
              disabled={isLoading}
              onSend={(question) => makeApiRequest(question)}
              recognizedText={recognizedText}
              onMicrophoneClick={onMicrophoneClick}
              onStopClick={stopSpeechRecognition}
              isListening={isListening}
              isRecognizing={isRecognizing}
              setRecognizedText={setRecognizedText}
              onClearChat={onClearChat}
              isThreadActive={!(!lastQuestionRef.current)}
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
            <ReactMarkdown
              className={`${styles.citationPanelContent} ${styles.mobileCitationPanelContent}`}
              children={activeCitation[0]}
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
            />
          </Stack.Item>
        )}
      </Stack>
      <div className={`${styles.bgPatternImgContainer}`}>
        <img
          src="../../Airbus_CarbonGrid.png"
          className={styles.bgPatternImg}
          aria-hidden="true"
        />
      </div>
    </div>
  );
};

export default Chat;
