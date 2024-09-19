import React, { useState, useEffect } from "react";
import { Stack, TextField } from "@fluentui/react";
import { SendRegular } from "@fluentui/react-icons";
import Send from "../../assets/Send.svg";
import MicrophoneIcon from "../../assets/mic-outline.svg";
import styles from "./QuestionInput.module.css";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMicrophone } from "@fortawesome/free-solid-svg-icons";
interface Props {
  onSend: (question: string) => void;
  onMicrophoneClick: (e: React.KeyboardEvent | React.MouseEvent) => void;
  onStopClick: (e: React.KeyboardEvent | React.MouseEvent) => void;
  disabled: boolean;
  isSendButtonDisabled: boolean;
  placeholder?: string;
  clearOnSend?: boolean;
  recognizedText: string;
  isListening: boolean;
  isRecognizing: boolean;
  isTextToSpeachActive: boolean;
  setRecognizedText: (text: string) => void;
}

export const QuestionInput = ({
  onSend,
  onMicrophoneClick,
  onStopClick,
  disabled,
  isSendButtonDisabled,
  placeholder,
  clearOnSend,
  recognizedText,
  isListening,
  isRecognizing,
  setRecognizedText,
  isTextToSpeachActive,
}: Props) => {
  const [question, setQuestion] = useState<string>("");
  const [liveRecognizedText, setLiveRecognizedText] = useState<string>("");
  const [microphoneIconActive, setMicrophoneIconActive] =
    useState<boolean>(false);
  const [isMicrophoneDisabled, setIsMicrophoneDisabled] = useState(false);
  const [isTextAreaDisabled, setIsTextAreaDisabled] = useState(false);
  useEffect(() => {
    if (isRecognizing) {
      setLiveRecognizedText(recognizedText);
      setIsTextAreaDisabled(true);
      setMicrophoneIconActive(true); // Set microphone icon to active (blue)
    } else {
      setIsTextAreaDisabled(false);
      setMicrophoneIconActive(false); // Set microphone icon to inactive
    }
  }, [recognizedText, isRecognizing]);
  useEffect(() => {
    setIsMicrophoneDisabled(isTextToSpeachActive);
  }, [isTextToSpeachActive]);
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

  const onQuestionChange = (
    _ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
    newValue?: string
  ) => {
    setQuestion(newValue || "");
    setLiveRecognizedText(newValue || ""); // Update liveRecognizedText when edited
  };

  const sendQuestionDisabled = disabled || !question.trim();

  return (
    <Stack horizontal className={styles.questionInputContainer}>
      {/* Text Input Field */}
      <TextField
        style={{ backgroundColor: "white" }}
        disabled={isTextAreaDisabled}
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
      <div className={styles.microphoneAndSendContainer}>
        {/* Microphone Icon */}
        <button
          type="button"
          disabled={isMicrophoneDisabled ? true : false}
          className={styles.questionInputMicrophone}
          onClick={
            isListening ? (e) => onStopClick(e) : (e) => onMicrophoneClick(e)
          }
          onKeyDown={(e) =>
            e.key === "Enter" || e.key === " "
              ? isListening
                ? () => onStopClick(e)
                : () => onMicrophoneClick(e)
              : null
          }
          role="button"
          tabIndex={0}
          aria-label="Microphone button"
        >
          {microphoneIconActive || isMicrophoneDisabled ? (
            <FontAwesomeIcon
              icon={faMicrophone}
              className={styles.microphoneIconActive}
              style={{ color: isMicrophoneDisabled ? "lightgray" : "blue" }}
            />
          ) : (
            <img
              src={MicrophoneIcon}
              className={styles.microphoneIcon}
              alt="Microphone"
            />
          )}
        </button>

        {/* Send Button */}
        {isSendButtonDisabled ? (
          <SendRegular className={styles.SendButtonDisabled} />
        ) : (
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
              <img
                src={Send}
                className={styles.questionInputSendButton}
                alt="Send"
              />
            )}
          </div>
        )}
      </div>
    </Stack>
  );
};
