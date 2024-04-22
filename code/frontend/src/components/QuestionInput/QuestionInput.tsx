import React, { useState, useEffect } from "react";
import { Stack, TextField } from "@fluentui/react";
import {
  SendRegular,
  MicFilled,
  DeleteFilled,
  SendFilled,
  MicRecordRegular,
} from "@fluentui/react-icons";
import Send from "../../assets/Send.svg";
// import MicrophoneIcon from "../../assets/mic-outline.svg";
import styles from "./QuestionInput.module.css";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMicrophone } from "@fortawesome/free-solid-svg-icons";
interface Props {
  onSend: (question: string) => void;
  onMicrophoneClick: () => void;
  onStopClick: () => void;
  onClearChat: () => void;
  disabled: boolean;
  placeholder?: string;
  clearOnSend?: boolean;
  recognizedText: string;
  isListening: boolean;
  isRecognizing: boolean;
  isThreadActive: boolean;
  setRecognizedText: (text: string) => void;
}

export const QuestionInput = ({
  onSend,
  onMicrophoneClick,
  onStopClick,
  onClearChat,
  disabled,
  placeholder,
  clearOnSend,
  recognizedText,
  isListening,
  isRecognizing,
  isThreadActive,
  setRecognizedText,
}: Props) => {
  const [question, setQuestion] = useState<string>("");
  const [liveRecognizedText, setLiveRecognizedText] = useState<string>("");
  const [microphoneIconActive, setMicrophoneIconActive] =
    useState<boolean>(false);

  useEffect(() => {
    if (isRecognizing) {
      setLiveRecognizedText(recognizedText);
      setMicrophoneIconActive(true); // Set microphone icon to active (blue)
    } else {
      setMicrophoneIconActive(false); // Set microphone icon to inactive
    }
  }, [recognizedText, isRecognizing]);
  const sendQuestion = () => {
    if (disabled || (!question.trim() && !liveRecognizedText.trim())) {
      return;
    }

    const textToSend = question || liveRecognizedText;

    onSend(textToSend);

    if (clearOnSend) {
      setQuestion("");
      setLiveRecognizedText("");
      setRecognizedText(""); // Clear recognizedText
    }
  };

  const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendQuestion();
    }
  };

  const clearChat = () => {
    onClearChat();
  };

  const onQuestionChange = (
    _ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
    newValue?: string
  ) => {
    setQuestion(newValue || "");
    setLiveRecognizedText(newValue || ""); // Update liveRecognizedText when edited
  };

  const sendQuestionDisabled = disabled || !question.trim();

  return (
    <Stack horizontal className={`${styles.questionInputContainer} ${!isThreadActive ? '' : styles.chatThreadActive}`}>
      <div className={styles.topSearchInput}>
        {/* Text Input Field */}
        <TextField
          className={styles.questionInputTextArea}
          placeholder={placeholder}
          multiline
          resizable={false}
          borderless
          value={question || liveRecognizedText}
          onChange={(e, newValue) => {
            if (newValue !== undefined) {
              onQuestionChange(e, newValue);
              setRecognizedText(newValue);
            }
          }}
          onKeyDown={onEnterPress}
        />

        {/* Send Button */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Ask question button"
          onClick={sendQuestion}
          onKeyDown={(e) =>
            e.key === "Enter" || e.key === " " ? sendQuestion() : null
          }
          className={styles.questionInputSendButtonContainer}
        >
          {disabled ? (
            <SendRegular className={styles.questionInputSendButtonDisabled} />
          ) : (
            <SendFilled className={styles.questionInputSendButton} />
          )}
        </div>
      </div>

      <div className={styles.chatAdditionalControls}>
        <div className={styles.chatAdditionalControlsInner}>
          {/* Microphone Icon */}
          <div
            className={styles.questionInputMicrophone}
            onClick={isListening ? onStopClick : onMicrophoneClick}
            onKeyDown={(e) =>
              e.key === "Enter" || e.key === " "
                ? isListening
                  ? onStopClick()
                  : onMicrophoneClick()
                : null
            }
            role="button"
            tabIndex={0}
            aria-label="Microphone button"
          >
            {microphoneIconActive ? (
              <MicRecordRegular className={styles.micIconRecordingOn} />
            ) : (
              <MicFilled className={styles.micIconRecordingOff} />
            )}
          </div>

          {/* Clear chat option */}
          <div
            className={styles.clearChatButton}
            onClick={clearChat}
            onKeyDown={(e) =>
              e.key === "Enter" || e.key === " " ? clearChat() : null
            }
          >
            <DeleteFilled className={styles.clearChatIcon} />
            <span>Clear Chat</span>
          </div>
        </div>
      </div>
    </Stack>
  );
};
