import { render, screen, fireEvent } from '@testing-library/react';
import { ChatHistoryListItemGroups, GroupedChatHistory } from './ChatHistoryListItemGroups';
import { Conversation } from '../../api/models';

const mockGroupedChatHistory: GroupedChatHistory[] = [
  {
    title: 'Group 1',
    entries: [
      { id: '1', title: 'Conversation 1' } as Conversation,
      { id: '2', title: 'Conversation 2' } as Conversation,
    ],
  },
  {
    title: 'Group 2',
    entries: [
      { id: '3', title: 'Conversation 3' } as Conversation,
    ],
  },
];

const mockHandleFetchHistory = jest.fn();
const mockOnSelectConversation = jest.fn();
const mockOnHistoryTitleChange = jest.fn();
const mockOnHistoryDelete = jest.fn();
const mockToggleToggleSpinner = jest.fn();

describe('ChatHistoryListItemGroups', () => {
  test('renders No chat history when there are no conversations', () => {
    render(
      <ChatHistoryListItemGroups
        groupedChatHistory={[]}
        handleFetchHistory={mockHandleFetchHistory}
        fetchingChatHistory={false}
        onSelectConversation={mockOnSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockOnHistoryTitleChange}
        onHistoryDelete={mockOnHistoryDelete}
        isGenerating={false}
        toggleToggleSpinner={mockToggleToggleSpinner}
      />
    );

    expect(screen.getByText('No chat history.')).toBeInTheDocument();
  });

  test('renders chat history groups and conversations', () => {
    render(
      <ChatHistoryListItemGroups
        groupedChatHistory={mockGroupedChatHistory}
        handleFetchHistory={mockHandleFetchHistory}
        fetchingChatHistory={false}
        onSelectConversation={mockOnSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockOnHistoryTitleChange}
        onHistoryDelete={mockOnHistoryDelete}
        isGenerating={false}
        toggleToggleSpinner={mockToggleToggleSpinner}
      />
    );

    expect(screen.getByText('Group 1')).toBeInTheDocument();
    expect(screen.getByText('Group 2')).toBeInTheDocument();
    expect(screen.getByText('Conversation 1')).toBeInTheDocument();
    expect(screen.getByText('Conversation 2')).toBeInTheDocument();
    expect(screen.getByText('Conversation 3')).toBeInTheDocument();
  });

  test('calls handleFetchHistory when observer target is intersecting', () => {
    render(
      <ChatHistoryListItemGroups
        groupedChatHistory={mockGroupedChatHistory}
        handleFetchHistory={mockHandleFetchHistory}
        fetchingChatHistory={false}
        onSelectConversation={mockOnSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockOnHistoryTitleChange}
        onHistoryDelete={mockOnHistoryDelete}
        isGenerating={false}
        toggleToggleSpinner={mockToggleToggleSpinner}
      />
    );

    // Simulate intersection observer callback
    fireEvent.scroll(window, { target: { scrollY: 1000 } });
    expect(mockHandleFetchHistory).toHaveBeenCalled();
  });

  test('calls onSelectConversation when a conversation is clicked', () => {
    render(
      <ChatHistoryListItemGroups
        groupedChatHistory={mockGroupedChatHistory}
        handleFetchHistory={mockHandleFetchHistory}
        fetchingChatHistory={false}
        onSelectConversation={mockOnSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockOnHistoryTitleChange}
        onHistoryDelete={mockOnHistoryDelete}
        isGenerating={false}
        toggleToggleSpinner={mockToggleToggleSpinner}
      />
    );

    fireEvent.click(screen.getByText('Conversation 1'));
    expect(mockOnSelectConversation).toHaveBeenCalledWith('1');
  });
});
