import React, { Fragment } from "react";
import { Spinner, SpinnerSize } from "@fluentui/react";
import { Answer } from "../../components/Answer";
import styles from "./ChatMessageContainer.module.css";
import {
  type ToolMessageContent,
  type ChatMessage,
  type Citation,
} from "../../api";

const [ASSISTANT, TOOL, ERROR, USER] = ["assistant", "tool", "error", "user"];

export type ChatMessageContainerProps = {
  fetchingConvMessages: boolean;
  answers: ChatMessage[];
  activeCardIndex: number | null;
  handleSpeech: any;
  onShowCitation: (citedDocument: Citation) => void;
};

const parseCitationFromMessage = (message: ChatMessage) => {
  if (message.role === TOOL) {
    try {
      const toolMessage = JSON.parse(message.content) as ToolMessageContent;
      return toolMessage.citations;
    } catch {
      return [];
    }
  }
  return [];
};

export const ChatMessageContainer: React.FC<ChatMessageContainerProps> = (
  props
) => {
  const {
    fetchingConvMessages,
    answers,
    handleSpeech,
    activeCardIndex,
    onShowCitation,
  } = props;
  return (
    <Fragment>
      {fetchingConvMessages && (
        <div className={styles.fetchMessagesSpinner}>
          <Spinner size={SpinnerSize.medium} />
        </div>
      )}
      {!fetchingConvMessages &&
        answers.map((answer, index) => (
          <React.Fragment key={`${answer?.role}-${index}`}>
            {answer.role === USER ? (
              <div
                className={styles.chatMessageUser}
                key={`${answer?.role}-${index}`}
              >
                <div className={styles.chatMessageUserMessage}>
                  {answer.content}
                </div>
              </div>
            ) : answer.role === ASSISTANT || answer.role === ERROR ? (
              <div
                className={styles.chatMessageGpt}
                key={`${answer?.role}-${index}`}
              >
                <Answer
                  answer={{
                    answer:
                      answer.role === ASSISTANT
                        ? answer.content
                        : "Sorry, an error occurred. Try refreshing the conversation or waiting a few minutes. If the issue persists, contact your system administrator. Error: " +
                          answer.content,
                    citations:
                      answer.role === ASSISTANT
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
    </Fragment>
  );
};
