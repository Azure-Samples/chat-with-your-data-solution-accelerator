import React from "react";
import { Stack } from "@fluentui/react";
import Azure from "../../assets/Azure.svg";
import Cards from "../../pages/chat/Cards_contract/Cards";
import styles from "./AssistantTypeSection.module.css";

type AssistantTypeSectionProps = {
  assistantType: string;
  isAssistantAPILoading: boolean;
};

enum assistantTypes {
  default = "default",
  contractAssistant = "contract assistant",
}

export const AssistantTypeSection: React.FC<AssistantTypeSectionProps> = ({
  assistantType,
  isAssistantAPILoading,
}) => {
  return (
    <Stack className={styles.chatEmptyState}>
      <img
        src={Azure}
        className={styles.chatIcon}
        aria-hidden="true"
        alt="Chat with your data"
      />
      {assistantType === assistantTypes.contractAssistant ? (
        <>
          <h1 className={styles.chatEmptyStateTitle}>Contract Summarizer</h1>
          <h2 className={styles.chatEmptyStateSubtitle}>
            AI-Powered assistant for simplified summarization
          </h2>
          <Cards />
        </>
      ) : assistantType === assistantTypes.default ? (
        <>
          <h1 className={styles.chatEmptyStateTitle}>
            Chat with your
            <span className={styles.dataText}>&nbsp;Data</span>
          </h1>
          <h2 className={styles.chatEmptyStateSubtitle}>
            This chatbot is configured to answer your questions
          </h2>
        </>
      ) : null}
      {isAssistantAPILoading && (
        <div className={styles.loadingContainer}>
          <div className={styles.loadingIcon}></div>
          <p>Loading...</p>
        </div>
      )}
    </Stack>
  );
};
