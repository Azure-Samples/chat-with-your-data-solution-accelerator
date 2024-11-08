import { render, screen, fireEvent } from '@testing-library/react';
import { ChatHistoryListItemGroups } from './ChatHistoryListItemGroups';

describe('ChatHistoryListItemGroups', () => {
  const mockFetchHistory = jest.fn();
  const mockSelectConversation = jest.fn();
  const mockTitleChange = jest.fn();
  const mockDeleteHistory = jest.fn();
  const mockToggleSpinner = jest.fn();

  const groupedChatHistory = [
    {
      title: 'January',
      entries: [
        { id: '1', content: 'Hello' },
        { id: '2', content: 'World' },
      ],
    },
    {
      title: 'February',
      entries: [],
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders no chat history message when there are no entries', () => {
    render(
      <ChatHistoryListItemGroups
        fetchingChatHistory={false}
        handleFetchHistory={mockFetchHistory}
        groupedChatHistory={[]}
        onSelectConversation={mockSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockTitleChange}
        onHistoryDelete={mockDeleteHistory}
        isGenerating={false}
        toggleToggleSpinner={mockToggleSpinner}
      />
    );

    expect(screen.getByText('No chat history.')).toBeInTheDocument();
  });

  test('renders chat history groups and items', () => {
    render(
        <ChatHistoryListItemGroups
        fetchingChatHistory={false}
        handleFetchHistory={mockFetchHistory}
        groupedChatHistory={[]}
        onSelectConversation={mockSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockTitleChange}
        onHistoryDelete={mockDeleteHistory}
        isGenerating={false}
        toggleToggleSpinner={mockToggleSpinner}
      />
    );

    expect(screen.getByText('January')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('World')).toBeInTheDocument();
    expect(screen.queryByText('February')).toBeInTheDocument();
  });

  test('calls onSelectConversation when a conversation is selected', () => {
    render(
      <ChatHistoryListItemGroups
            fetchingChatHistory={false}
            handleFetchHistory={mockFetchHistory}
            onSelectConversation={mockSelectConversation}
            selectedConvId=""
            onHistoryTitleChange={mockTitleChange}
            onHistoryDelete={mockDeleteHistory}
            isGenerating={false}
            toggleToggleSpinner={mockToggleSpinner} groupedChatHistory={[]}      />
    );

    const helloItem = screen.getByText('Hello');
    fireEvent.click(helloItem);

    expect(mockSelectConversation).toHaveBeenCalledWith('1');
  });

  test('shows spinner when fetching chat history', () => {
    render(
        <ChatHistoryListItemGroups
        fetchingChatHistory={false}
        handleFetchHistory={mockFetchHistory}
        groupedChatHistory={[]}
        onSelectConversation={mockSelectConversation}
        selectedConvId=""
        onHistoryTitleChange={mockTitleChange}
        onHistoryDelete={mockDeleteHistory}
        isGenerating={false}
        toggleToggleSpinner={mockToggleSpinner}
      />
    );

    expect(screen.getByLabelText('loading more chat history')).toBeInTheDocument();
  });
});
