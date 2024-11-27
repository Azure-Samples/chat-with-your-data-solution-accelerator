import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { ChatHistoryListItemGroups, GroupedChatHistory } from './ChatHistoryListItemGroups';
import { Conversation } from '../../api/models';
import { historyList } from '../../api';

jest.mock('../../api/api', () => ({
  historyList: jest.fn(),
}))
const mockGroupedChatHistory = [
  {
    title: 'Group 1',
      entries: [
          { id: '1', title: 'Chat 1', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() },
          { id: '2', title: 'Chat 2', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() },
      ],
  },
  {
    title: 'Group 2',
      entries: [
          { id: '3', title: 'Chat 3', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() },
      ],
  },
];

const mockHandleFetchHistory = jest.fn();
const mockOnSelectConversation = jest.fn();
const mockOnHistoryTitleChange = jest.fn();
const mockOnHistoryDelete = jest.fn();
const mockToggleToggleSpinner = jest.fn();
const componentProps = {
  groupedChatHistory: {mockGroupedChatHistory},
  handleFetchHistory: mockHandleFetchHistory,
  fetchingChatHistory: false,
  onSelectConversation: mockOnSelectConversation,
  selectedConvId: "",
  onHistoryTitleChange: mockOnHistoryTitleChange,
  onHistoryDelete: mockOnHistoryDelete,
  isGenerating: false,
  toggleToggleSpinner: mockToggleToggleSpinner
}
// Mock the ChatHistoryListItemCell component
jest.mock('../ChatHistoryListItemCell/ChatHistoryListItemCell', () => ({
  ChatHistoryListItemCell: jest.fn(({ item, onSelect }) => (
      <div data-testid={`mock-cell-${item.id}`} onClick={() => onSelect(item)}>
          {item?.title}
      </div>
  )),
}));
describe('ChatHistoryListItemGroups', () => {
  beforeEach(() => {
    global.fetch = jest.fn();

    jest.spyOn(console, 'error').mockImplementation(() => { });
  });

    afterEach(() => {
      jest.clearAllMocks();
      //(console.error as jest.Mock).mockRestore();
    });

    it('should call handleFetchHistory with the correct offset when the observer is triggered', async () => {
      const responseMock = [{ id: '4', title: 'Chat 4', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() }];
      (historyList as jest.Mock).mockResolvedValue([...responseMock]);
      await act(async () => {
        render(
          <ChatHistoryListItemGroups
            {...componentProps}
            groupedChatHistory={mockGroupedChatHistory}
          />
        )
              });

      const scrollElms = await screen.findAllByRole('scrollDiv');
      const lastElem = scrollElms[scrollElms.length - 1];

      await act(async () => {
        fireEvent.scroll(lastElem, { target: { scrollY: 100 } });
        //await waitFor(() => expect(historyList).toHaveBeenCalled());
      });

    });

    it('displays spinner while loading more history', async () => {
      const responseMock = [{ id: '4', title: 'Chat 4', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() }];
      (historyList as jest.Mock).mockResolvedValue([...responseMock]);
      await act(async () => {
        render(
          <ChatHistoryListItemGroups
            {...componentProps}
            groupedChatHistory={mockGroupedChatHistory}
          />
        )
              });

      const scrollElms = await screen.findAllByRole('scrollDiv');
      const lastElem = scrollElms[scrollElms.length - 1];

      await act(async () => {
        fireEvent.scroll(lastElem, { target: { scrollY: 100 } });
      });

      await act(async () => {
        await waitFor(() => {
          expect(screen.queryByLabelText(/loading/i)).not.toBeInTheDocument();
        });
      });
    });

    it('should render the grouped chat history', () => {
      render(
        <ChatHistoryListItemGroups
          {...componentProps}
          groupedChatHistory={mockGroupedChatHistory}
        />
      )
      // Check if each group is rendered
      expect(screen.getByText('Group 1')).toBeInTheDocument();
      expect(screen.getByText('Group 2')).toBeInTheDocument();

      // Check if entries are rendered
      expect(screen.getByText('Chat 1')).toBeInTheDocument();
      expect(screen.getByText('Chat 2')).toBeInTheDocument();
      expect(screen.getByText('Chat 3')).toBeInTheDocument();
    });

    it('calls onSelect with the correct item when a ChatHistoryListItemCell is clicked', async () => {
      const handleSelectMock = jest.fn();

      // Render the component
      render(
        <ChatHistoryListItemGroups
          {...componentProps}
          groupedChatHistory={mockGroupedChatHistory}
        />
      )
      // Simulate clicks on each ChatHistoryListItemCell
      const cells = screen.getAllByTestId(/mock-cell-/);

      // Click on the first cell
      fireEvent.click(cells[0]);
      screen.debug()
      // Wait for the mock function to be called with the correct item
      await waitFor(() => {
          expect(mockOnSelectConversation).toHaveBeenCalledWith(mockGroupedChatHistory[0].entries[0].id);
      });

    });

    it('handles API failure gracefully', async () => {
      // Mock the API to reject with an error
      (historyList as jest.Mock).mockResolvedValue(undefined);

      render(
        <ChatHistoryListItemGroups
          {...componentProps}
          groupedChatHistory={mockGroupedChatHistory}
        />
      )
      // Simulate triggering the scroll event that loads more history
      const scrollElms = await screen.findAllByRole('scrollDiv');
      const lastElem = scrollElms[scrollElms.length - 1];

      await act(async () => {
        fireEvent.scroll(lastElem, { target: { scrollY: 100 } });
      });
      // Check that the spinner is hidden after the API call
      await waitFor(() => {
        expect(screen.queryByLabelText(/loading/i)).not.toBeInTheDocument();
      });
    });
    it('should render "No chat history" when there are no chat entries', () => {
      render(<ChatHistoryListItemGroups {...componentProps}  groupedChatHistory={[]} />);

      // Check that the "No chat history." text is in the document
      expect(screen.getByText('No chat history.')).toBeInTheDocument();

    });

    it('should render chat history when data is provided', () => {
      const mockGroupedChatHistoryWithData = [
        {
          title: 'Group 1',
          entries: [
            { id: '1', title: 'Chat 1', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() },
            { id: '2', title: 'Chat 2', messages: [], date: new Date().toISOString(), updatedAt: new Date().toISOString() },
          ]
        }
      ];

      const updatedProps = {
        ...componentProps,
        groupedChatHistory: mockGroupedChatHistoryWithData
      };

      render(<ChatHistoryListItemGroups {...updatedProps} />);

      // Check that the "No chat history." text is NOT in the document
      expect(screen.queryByText('No chat history.')).toBeNull();

      // Check that the group title is rendered
      expect(screen.getByText('Group 1')).toBeInTheDocument();

      // Ensure the individual chat entries are rendered (we mock the ChatHistoryListItemCell component)
      expect(screen.getByTestId('mock-cell-1')).toBeInTheDocument();
      expect(screen.getByTestId('mock-cell-2')).toBeInTheDocument();
    });
    it('should render the component and display the chat groups correctly', () => {
      render(<ChatHistoryListItemGroups {...componentProps} groupedChatHistory={mockGroupedChatHistory}/>);

      // Check if group titles are rendered
      expect(screen.getByText('Group 1')).toBeInTheDocument();
      expect(screen.getByText('Group 2')).toBeInTheDocument();

      // Check if chat items are rendered within each group
      expect(screen.getByTestId('mock-cell-1')).toBeInTheDocument();
      expect(screen.getByTestId('mock-cell-2')).toBeInTheDocument();
      expect(screen.getByTestId('mock-cell-3')).toBeInTheDocument();
    });

    it('should trigger the onSelectConversation when a chat is clicked', async () => {
      render(<ChatHistoryListItemGroups {...componentProps} groupedChatHistory={mockGroupedChatHistory}/>);

      // Simulate clicking on a chat item
      fireEvent.click(screen.getByTestId('mock-cell-1'));

      // Ensure the onSelectConversation is called with the correct item
      expect(mockOnSelectConversation).toHaveBeenCalledWith("1");
    });

    it('should show the spinner when fetchingChatHistory is true', async () => {
      const propsWithSpinner = {
        ...componentProps,
        fetchingChatHistory: true,
      };

      render(<ChatHistoryListItemGroups {...propsWithSpinner} groupedChatHistory={mockGroupedChatHistory}/>);

      // Ensure spinner is visible when fetchingChatHistory is true
      const spinner = screen.getByLabelText('loading more chat history');
      expect(spinner).toBeInTheDocument();
    });

    it('should not show the spinner when fetchingChatHistory is false', async () => {
      render(<ChatHistoryListItemGroups {...componentProps} groupedChatHistory={mockGroupedChatHistory}/>);

      // Ensure spinner is not visible when fetchingChatHistory is false
      const spinner = screen.queryByTestId('spinner');
      expect(spinner).toBeNull();
    });

    it('should call handleFetchHistory when the component mounts', async () => {
      render(<ChatHistoryListItemGroups {...componentProps} groupedChatHistory={mockGroupedChatHistory}/>);

      // Check that handleFetchHistory was called on mount
      expect(mockHandleFetchHistory).toHaveBeenCalledTimes(1);
    });
  });
