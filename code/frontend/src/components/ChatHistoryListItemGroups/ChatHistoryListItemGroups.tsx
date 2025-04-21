import * as React from "react";
import { useEffect, useRef } from "react";
import {
  List,
  Separator,
  Spinner,
  SpinnerSize,
  Stack,
  StackItem,
  Text,
} from "@fluentui/react";
import { Conversation } from "../../api/models";
import _ from "lodash";
import styles from "./ChatHistoryListItemGroups.module.css";
import { ChatHistoryListItemCell } from "../ChatHistoryListItemCell/ChatHistoryListItemCell";

export interface GroupedChatHistory {
  title: string;
  entries: Conversation[];
}
interface ChatHistoryListItemGroupsProps {
  fetchingChatHistory: boolean;
  handleFetchHistory: () => Promise<void>;
  groupedChatHistory: GroupedChatHistory[];
  onSelectConversation: (id: string) => void;
  selectedConvId: string;
  onHistoryTitleChange: (id: string, newTitle: string) => void;
  onHistoryDelete: (id: string) => void;
  isGenerating: boolean;
  toggleToggleSpinner: (toggler: boolean) => void;
}

export const ChatHistoryListItemGroups: React.FC<
  ChatHistoryListItemGroupsProps
> = ({
  groupedChatHistory,
  handleFetchHistory,
  fetchingChatHistory,
  onSelectConversation,
  selectedConvId,
  onHistoryTitleChange,
  onHistoryDelete,
  isGenerating,
  toggleToggleSpinner,
}) => {
  const observerTarget = useRef(null);
  const handleSelectHistory = (item?: Conversation) => {
    if (typeof item === "object") {
      onSelectConversation(item?.id);
    }
  };

  const onRenderCell = (item?: Conversation) => {
    return (
      <ChatHistoryListItemCell
        item={item}
        onSelect={() => handleSelectHistory(item)}
        selectedConvId={selectedConvId}
        key={item?.id}
        onHistoryTitleChange={onHistoryTitleChange}
        onHistoryDelete={onHistoryDelete}
        isGenerating={isGenerating}
        toggleToggleSpinner={toggleToggleSpinner}
      />
    );
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          handleFetchHistory();
        }
      },
      { threshold: 1 }
    );

    if (observerTarget.current) observer.observe(observerTarget.current);

    return () => {
      if (observerTarget.current) observer.unobserve(observerTarget.current);
    };
  }, [observerTarget.current]);

  const allConversationsLength = groupedChatHistory.reduce(
    (previousValue, currentValue) =>
      previousValue + currentValue.entries.length,
    0
  );

  if (!fetchingChatHistory && allConversationsLength === 0) {
    return (
      <Stack
        horizontal
        horizontalAlign="center"
        verticalAlign="center"
        style={{ width: "100%", marginTop: 10 }}
      >
        <StackItem>
          <Text
            style={{ alignSelf: "center", fontWeight: "400", fontSize: 14 }}
          >
            <span>No chat history.</span>
          </Text>
        </StackItem>
      </Stack>
    );
  }

  return (
    <div
      id="historyListContainer"
      className={styles.listContainer}
      data-is-scrollable
    >
      {groupedChatHistory.map(
        (group, index) =>
          group.entries.length > 0 && (
            <Stack
              horizontalAlign="start"
              verticalAlign="center"
              key={`GROUP-${group.title}-${index}`}
              className={styles.chatGroup}
              aria-label={`chat history group: ${group.title}`}
            >
              <Stack aria-label={group.title} className={styles.chatMonth}>
                {group.title}
              </Stack>
              <List
                aria-label={`chat history list`}
                items={group.entries}
                onRenderCell={onRenderCell}
                className={styles.chatList}
              />
            </Stack>
          )
      )}
      <div role="scrollDiv" id="chatHistoryListItemObserver" ref={observerTarget} />
      <Separator
        styles={{
          root: {
            width: "100%",
            padding: "0px",
            height: "2px",
            position: "relative",
            "::before": {
              backgroundColor: "#d6d6d6",
            },
          },
        }}
      />
      {Boolean(fetchingChatHistory) && (
        <div className={styles.spinnerContainer}>
          <Spinner
            size={SpinnerSize.small}
            aria-label="loading more chat history"
            className={styles.spinner}
          />
        </div>
      )}
    </div>
  );
};
