import * as React from "react";
import { useEffect, useRef, useState } from "react";
import {
  DefaultButton,
  Dialog,
  DialogFooter,
  DialogType,
  IconButton,
  ITextField,
  List,
  PrimaryButton,
  Separator,
  Spinner,
  SpinnerSize,
  Stack,
  StackItem,
  Text,
  TextField,
} from "@fluentui/react";
import { useBoolean } from "@fluentui/react-hooks";

import { historyRename, historyDelete } from "../../api";
import { Conversation } from "../../api/models";
import _ from 'lodash';
import { GroupedChatHistory } from "./ChatHistoryList";

import styles from "./ChatHistoryPanel.module.css";

interface ChatHistoryListItemCellProps {
  item?: Conversation;
  onSelect: (item: Conversation | null) => void;
  selectedConvId: string;
  onHistoryTitleChange: (id: string, newTitle: string) => void;
  onHistoryDelete: (id: string) => void;
  isGenerating: boolean;
  toggleToggleSpinner: (toggler: boolean) => void;
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

export const ChatHistoryListItemCell: React.FC<
  ChatHistoryListItemCellProps
> = ({
  item,
  onSelect,
  selectedConvId,
  onHistoryTitleChange,
  onHistoryDelete,
  isGenerating,
  toggleToggleSpinner,
}) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const [edit, setEdit] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [hideDeleteDialog, { toggle: toggleDeleteDialog }] = useBoolean(true);
  const [errorDelete, setErrorDelete] = useState(false);
  const [renameLoading, setRenameLoading] = useState(false);
  const [errorRename, setErrorRename] = useState<string | undefined>(undefined);
  const [textFieldFocused, setTextFieldFocused] = useState(false);
  const textFieldRef = useRef<ITextField | null>(null);
  const isSelected = item?.id === selectedConvId;
  const dialogContentProps = {
    type: DialogType.close,
    title: "Are you sure you want to delete this item?",
    closeButtonAriaLabel: "Close",
    subText: "The history of this chat session will be permanently removed.",
  };

  const modalProps = {
    titleAriaId: "labelId",
    subtitleAriaId: "subTextId",
    isBlocking: true,
    styles: { main: { maxWidth: 450 } },
  };

  if (!item) {
    return null;
  }

  useEffect(() => {
    if (textFieldFocused && textFieldRef.current) {
      textFieldRef.current.focus();
      setTextFieldFocused(false);
    }
  }, [textFieldFocused]);

  const onDelete = async () => {
    toggleToggleSpinner(true);
    const response = await historyDelete(item.id);
    if (!response.ok) {
      setErrorDelete(true);
      setTimeout(() => {
        setErrorDelete(false);
      }, 5000);
    } else {
      onHistoryDelete(item.id);
    }
    toggleDeleteDialog();
    toggleToggleSpinner(false);
  };

  const onEdit = () => {
    setEdit(true);
    setTextFieldFocused(true);
    setEditTitle(item?.title);
  };

  const handleSelectItem = () => {
    onSelect(item);
  };

  const truncatedTitle =
    item?.title?.length > 28
      ? `${item.title.substring(0, 28)} ...`
      : item.title;

  const handleSaveEdit = async (e: any) => {
    e.preventDefault();
    if (errorRename || renameLoading || _.trim(editTitle) === "") {
      return;
    }

    if (_.trim(editTitle) === _.trim(item?.title)) {
      setEdit(false);
      setTextFieldFocused(false);
      return;
    }
    setRenameLoading(true);
    const response = await historyRename(item.id, editTitle);
    if (!response.ok) {
      setErrorRename("Error: could not rename item");
      setTimeout(() => {
        setTextFieldFocused(true);
        setErrorRename(undefined);
        if (textFieldRef.current) {
          textFieldRef.current.focus();
        }
      }, 5000);
    } else {
      setRenameLoading(false);
      setEdit(false);
      onHistoryTitleChange(item.id, editTitle);
      setEditTitle("");
    }
  };

  const chatHistoryTitleOnChange = (e: any) => {
    setEditTitle(e.target.value);
  };

  const cancelEditTitle = () => {
    setEdit(false);
    setEditTitle("");
  };

  const handleKeyPressEdit = (e: any) => {
    if (e.key === "Enter") {
      return handleSaveEdit(e);
    }
    if (e.key === "Escape") {
      cancelEditTitle();
      return;
    }
  };
  const onClickDelete = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    toggleDeleteDialog();
  };
  const isButtonDisabled = isGenerating && isSelected;
  return (
    <Stack
      key={item.id}
      tabIndex={0}
      aria-label="chat history item"
      className={styles.itemCell}
      onClick={() => handleSelectItem()}
      onKeyDown={(e) =>
        e.key === "Enter" || e.key === " " ? handleSelectItem() : null
      }
      verticalAlign="center"
      // horizontal
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      styles={{
        root: {
          backgroundColor: isSelected ? "#e6e6e6" : "transparent",
        },
      }}
    >
      {edit ? (
        <>
          <Stack.Item style={{ width: "100%" }}>
            <form
              aria-label="edit title form"
              onSubmit={(e) => handleSaveEdit(e)}
              style={{ padding: "5px 0px" }}
            >
              <Stack horizontal verticalAlign={"start"}>
                <Stack.Item>
                  <TextField
                    componentRef={textFieldRef}
                    autoFocus={textFieldFocused}
                    value={editTitle}
                    placeholder={item.title}
                    onChange={chatHistoryTitleOnChange}
                    onKeyDown={handleKeyPressEdit}
                    errorMessage={errorRename}
                    disabled={errorRename ? true : false}
                  />
                </Stack.Item>
                {_.trim(editTitle) && (
                  <Stack.Item>
                    <Stack
                      aria-label="action button group"
                      horizontal
                      verticalAlign={"center"}
                    >
                      <IconButton
                        role="button"
                        disabled={errorRename !== undefined}
                        onKeyDown={(e) =>
                          e.key === " " || e.key === "Enter"
                            ? handleSaveEdit(e)
                            : null
                        }
                        onClick={(e) => handleSaveEdit(e)}
                        aria-label="confirm new title"
                        iconProps={{ iconName: "CheckMark" }}
                        styles={{ root: { color: "green", marginLeft: "5px" } }}
                      />
                      <IconButton
                        role="button"
                        disabled={errorRename !== undefined}
                        onKeyDown={(e) =>
                          e.key === " " || e.key === "Enter"
                            ? cancelEditTitle()
                            : null
                        }
                        onClick={() => cancelEditTitle()}
                        aria-label="cancel edit title"
                        iconProps={{ iconName: "Cancel" }}
                        styles={{ root: { color: "red", marginLeft: "5px" } }}
                      />
                    </Stack>
                  </Stack.Item>
                )}
              </Stack>
              {errorRename && (
                <Text
                  role="alert"
                  aria-label={errorRename}
                  style={{
                    fontSize: 12,
                    fontWeight: 400,
                    color: "rgb(164,38,44)",
                  }}
                >
                  {errorRename}
                </Text>
              )}
            </form>
          </Stack.Item>
        </>
      ) : (
        <>
          <Stack horizontal verticalAlign={"center"} style={{ width: "100%" }}>
            <div className={styles.chatTitle}>{truncatedTitle}</div>
            {(isSelected || isHovered) && (
              <Stack horizontal horizontalAlign="end">
                <IconButton
                  className={styles.itemButton}
                  disabled={isButtonDisabled}
                  iconProps={{ iconName: "Delete" }}
                  title="Delete"
                  onClick={onClickDelete}
                  onKeyDown={(e) =>
                    e.key === " " ? toggleDeleteDialog() : null
                  }
                />
                <IconButton
                  className={styles.itemButton}
                  disabled={isButtonDisabled}
                  iconProps={{ iconName: "Edit" }}
                  title="Edit"
                  onClick={onEdit}
                  onKeyDown={(e) => (e.key === " " ? onEdit() : null)}
                />
              </Stack>
            )}
          </Stack>
        </>
      )}
      {errorDelete && (
        <Text
          styles={{
            root: { color: "red", marginTop: 5, fontSize: 14 },
          }}
        >
          Error: could not delete item
        </Text>
      )}
      <Dialog
        hidden={hideDeleteDialog}
        onDismiss={toggleDeleteDialog}
        dialogContentProps={dialogContentProps}
        modalProps={modalProps}
      >
        <DialogFooter>
          <PrimaryButton onClick={onDelete} text="Delete" />
          <DefaultButton onClick={toggleDeleteDialog} text="Cancel" />
        </DialogFooter>
      </Dialog>
    </Stack>
  );
};

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
      <div id="chatHistoryListItemObserver" ref={observerTarget} />
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
