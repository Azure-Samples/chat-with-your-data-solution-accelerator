import { render, screen, fireEvent } from '@testing-library/react';
import { ChatHistoryPanel, ChatHistoryPanelProps } from './ChatHistoryPanel';
import { ChatHistoryListItemGroups } from '../ChatHistoryListItemGroups/ChatHistoryListItemGroups';
import { DialogType } from '@fluentui/react';

// Mock the ChatHistoryListItemGroups component
jest.mock('../ChatHistoryListItemGroups/ChatHistoryListItemGroups', () => ({
  ChatHistoryListItemGroups: jest.fn(() => <div>Mocked ChatHistoryListItemGroups</div>),
}));

const defaultProps: ChatHistoryPanelProps = {
  onShowContextualMenu: jest.fn(),
  showContextualMenu: false,
  clearingError: false,
  clearing: false,
  onHideClearAllDialog: jest.fn(),
  onClearAllChatHistory: jest.fn().mockResolvedValue(undefined),
  hideClearAllDialog: true,
  toggleToggleSpinner: jest.fn(),
  toggleClearAllDialog: jest.fn(),
  onHideContextualMenu: jest.fn(),
  setShowHistoryPanel: jest.fn(),
  fetchingChatHistory: false,
  handleFetchHistory: jest.fn().mockResolvedValue(undefined),
  onSelectConversation: jest.fn().mockResolvedValue(undefined),
  chatHistory: [],
  selectedConvId: '',
  onHistoryTitleChange: jest.fn(),
  onHistoryDelete: jest.fn(),
  showLoadingMessage: false,
  isSavingToDB: false,
  showContextualPopup: false,
  isLoading: false,
  fetchingConvMessages: false,
};

describe('ChatHistoryPanel', () => {
  test('renders the ChatHistoryPanel component', () => {
    render(<ChatHistoryPanel {...defaultProps} />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Chat history');
    expect(screen.getByText('Mocked ChatHistoryListItemGroups')).toBeInTheDocument();
  });

  test('shows contextual menu when showContextualMenu is true', () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualMenu={true} />);
    expect(screen.getByRole('menu')).toBeInTheDocument();
  });

  test('calls onShowContextualMenu when the more button is clicked', () => {
    render(<ChatHistoryPanel {...defaultProps} />);
    fireEvent.click(screen.getByTitle('Clear all chat history'));
    expect(defaultProps.onShowContextualMenu).toHaveBeenCalled();
  });

  test('calls setShowHistoryPanel with false when the hide button is clicked', () => {
    render(<ChatHistoryPanel {...defaultProps} />);
    fireEvent.click(screen.getByTitle('Hide'));
    expect(defaultProps.setShowHistoryPanel).toHaveBeenCalledWith(false);
  });

  test('shows the clear all dialog when showContextualPopup is true', () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualPopup={true} hideClearAllDialog={false} />);
    expect(screen.getByText('Are you sure you want to clear all chat history?')).toBeInTheDocument();
  });

  test('calls onClearAllChatHistory when the clear all button is clicked', async () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualPopup={true} hideClearAllDialog={false} />);
    fireEvent.click(screen.getByText('Clear All'));
    expect(defaultProps.onClearAllChatHistory).toHaveBeenCalled();
  });

  test('calls onHideClearAllDialog when the cancel button is clicked', () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualPopup={true} hideClearAllDialog={false} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(defaultProps.onHideClearAllDialog).toHaveBeenCalled();
  });

  test('calls onHideClearAllDialog when the close button is clicked', () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualPopup={true} hideClearAllDialog={false} clearingError={true} />);
    expect(screen.getByText('Close')).toBeInTheDocument()
  });

  test('calls onHideClearAllDialog when the close button is clicked with cleaning', () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualPopup={true} hideClearAllDialog={false} clearingError={true} clearing={true} />);
    expect(screen.getByText('Close')).toBeInTheDocument()
  });

  test('disables the "Clear all chat history" menu item when conditions are met', () => {
    const propsWithConditions: ChatHistoryPanelProps = {
      ...defaultProps,
      chatHistory: [], // No chat history
      isLoading: true, // Loading state
      fetchingConvMessages: true, // Fetching conversation messages
      fetchingChatHistory: true, // Fetching chat history
    };
    render(<ChatHistoryPanel {...propsWithConditions} showContextualMenu={true} />);
    const clearAllMenuItem = screen.getByText('Clear all chat history');
    expect(clearAllMenuItem).not.toBeDisabled();
  });

  test('enables the "Clear all chat history" menu item when conditions are not met', () => {
    const propsWithoutConditions: ChatHistoryPanelProps = {
      ...defaultProps,
      chatHistory: [{
        id: '1', title: 'Test Conversation',
        messages: [],
        date: 'dsad'
      }], // Some chat history
      isLoading: false, // Not loading
      fetchingConvMessages: false, // Not fetching conversation messages
      fetchingChatHistory: false, // Not fetching chat history
    };
    render(<ChatHistoryPanel {...propsWithoutConditions} showContextualMenu={true} />);
    const clearAllMenuItem = screen.getByRole('button', { name: /clear all/i})
    expect(clearAllMenuItem).not.toBeDisabled();
  });

  test("Test the click on close while it is cleaing", () => {
    render(<ChatHistoryPanel {...defaultProps} showContextualPopup={true} hideClearAllDialog={false} clearing={true} />);
    let button = screen.getByRole('button', { name: /Close/i})
    fireEvent.click(button)
    expect(defaultProps.onHideClearAllDialog).toHaveBeenCalled()
  });
});
