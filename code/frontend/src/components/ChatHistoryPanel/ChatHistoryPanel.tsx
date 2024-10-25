import React from "react";
import {
  CommandBarButton,
  ContextualMenu,
  DefaultButton,
  Dialog,
  DialogFooter,
  DialogType,
  ICommandBarStyles,
  IContextualMenuItem,
  PrimaryButton,
  Stack,
  StackItem,
  Text,
} from "@fluentui/react";

import styles from "./ChatHistoryPanel.module.css";
import { type Conversation } from "../../api";
import { ChatHistoryListItemGroups } from "../ChatHistoryListItemGroups/ChatHistoryListItemGroups";
import { segregateItems } from "../Utils/utils";

const commandBarStyle: ICommandBarStyles = {
  root: {
    padding: "0",
    display: "flex",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
};

export type ChatHistoryPanelProps = {
  onShowContextualMenu: (ev: React.MouseEvent<HTMLElement>) => void;
  showContextualMenu: boolean;
  clearingError: boolean;
  clearing: boolean;
  onHideClearAllDialog: () => void;
  onClearAllChatHistory: () => Promise<void>;
  hideClearAllDialog: boolean;
  toggleToggleSpinner: (toggler: boolean) => void;
  toggleClearAllDialog: () => void;
  onHideContextualMenu: () => void;
  setShowHistoryPanel: React.Dispatch<React.SetStateAction<boolean>>;
  fetchingChatHistory: boolean;
  handleFetchHistory: () => Promise<void>;
  onSelectConversation: (id: string) => Promise<void>;
  chatHistory: Conversation[];
  selectedConvId: string;
  onHistoryTitleChange: (id: string, newTitle: string) => void;
  onHistoryDelete: (id: string) => void;
  showLoadingMessage: boolean;
  isSavingToDB: boolean;
  showContextualPopup: boolean;
  isLoading: boolean;
  fetchingConvMessages: boolean;
};

const modalProps = {
  titleAriaId: "labelId",
  subtitleAriaId: "subTextId",
  isBlocking: true,
  styles: { main: { maxWidth: 450 } },
};

export const ChatHistoryPanel: React.FC<ChatHistoryPanelProps> = (props) => {
  const {
    onShowContextualMenu,
    showContextualMenu,
    clearingError,
    clearing,
    onHideClearAllDialog,
    onClearAllChatHistory,
    hideClearAllDialog,
    toggleToggleSpinner,
    toggleClearAllDialog,
    onHideContextualMenu,
    setShowHistoryPanel,
    fetchingChatHistory,
    handleFetchHistory,
    onSelectConversation,
    chatHistory,
    selectedConvId,
    onHistoryTitleChange,
    onHistoryDelete,
    showLoadingMessage,
    isSavingToDB,
    showContextualPopup,
    isLoading,
    fetchingConvMessages,
  } = props;

  const clearAllDialogContentProps = {
    type: DialogType.close,
    title: !clearingError
      ? "Are you sure you want to clear all chat history?"
      : "Error deleting all of chat history",
    closeButtonAriaLabel: "Close",
    subText: !clearingError
      ? "All chat history will be permanently removed."
      : "Please try again. If the problem persists, please contact the site administrator.",
  };

  const disableClearAllChatHistory =
    !chatHistory.length ||
    isLoading ||
    fetchingConvMessages ||
    fetchingChatHistory;
  const menuItems: IContextualMenuItem[] = [
    {
      key: "clearAll",
      text: "Clear all chat history",
      disabled: disableClearAllChatHistory,
      iconProps: { iconName: "Delete" },
    },
  ];
  const groupedChatHistory = segregateItems(chatHistory);
  return (
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
        <Stack horizontal className={styles.historyPanelTopRightButtons}>
          <Stack horizontal>
            <CommandBarButton
              iconProps={{ iconName: "More" }}
              title={"Clear all chat history"}
              onClick={onShowContextualMenu}
              aria-label={"clear all chat history"}
              styles={commandBarStyle}
              role="button"
              id="moreButton"
            />
            <ContextualMenu
              items={menuItems}
              hidden={!showContextualMenu}
              target={"#moreButton"}
              onItemClick={toggleClearAllDialog}
              onDismiss={onHideContextualMenu}
            />
          </Stack>

          <Stack horizontal>
            <CommandBarButton
              iconProps={{ iconName: "Cancel" }}
              title={"Hide"}
              aria-label={"hide button"}
              role="button"
              onClick={() => setShowHistoryPanel(false)}
            />
          </Stack>
        </Stack>
      </Stack>
      <Stack
        aria-label="chat history panel content"
        style={{
          display: "flex",
          height: "100%",
          padding: "1px",
        }}
      >
        <Stack className={styles.chatHistoryListContainer}>
        <ChatHistoryListItemGroups
              fetchingChatHistory={fetchingChatHistory}
              handleFetchHistory={handleFetchHistory}
              groupedChatHistory={groupedChatHistory}
              onSelectConversation={onSelectConversation}
              selectedConvId={selectedConvId}
              onHistoryTitleChange={onHistoryTitleChange}
              onHistoryDelete={onHistoryDelete}
              isGenerating={showLoadingMessage || isSavingToDB}
              toggleToggleSpinner={toggleToggleSpinner}
            />
        </Stack>
      </Stack>
      {showContextualPopup && (
        <Dialog
          hidden={hideClearAllDialog}
          onDismiss={clearing ? () => {} : onHideClearAllDialog}
          dialogContentProps={clearAllDialogContentProps}
          modalProps={modalProps}
        >
          <DialogFooter>
            {!clearingError && (
              <PrimaryButton
                onClick={onClearAllChatHistory}
                disabled={clearing}
                text="Clear All"
              />
            )}
            <DefaultButton
              onClick={onHideClearAllDialog}
              disabled={clearing}
              text={!clearingError ? "Cancel" : "Close"}
            />
          </DialogFooter>
        </Dialog>
      )}
    </section>
  );
};
