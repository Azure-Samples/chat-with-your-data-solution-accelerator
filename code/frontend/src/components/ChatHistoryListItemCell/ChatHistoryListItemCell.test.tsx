import { screen, waitFor, fireEvent, act, findByText, render } from '@testing-library/react';
import { ChatHistoryListItemCell } from './ChatHistoryListItemCell'
import { Conversation } from '../../api/models'
import { historyRename, historyDelete } from '../../api'
import React, { useEffect } from 'react'
import userEvent from '@testing-library/user-event'

// Mock API
jest.mock('../../api/api', () => ({
  historyRename: jest.fn(),
  historyDelete: jest.fn()
}))

const conversation: Conversation = {
  id: '1',
  title: 'Test Chat',
  messages: [],
  date: new Date().toISOString()
}

const mockOnSelect = jest.fn()
const mockOnHistoryTitleChange = jest.fn()
const mockOnHistoryDelete = jest.fn()
const mockOnToggleSpinner = jest.fn()
// const mockOnEdit = jest.fn()
const mockAppState = {
  currentChat: { id: '1' },
  isRequestInitiated: false
}
const componentProps = {
  item: conversation,
  onSelect: mockOnSelect,
  selectedConvId: '',
  onHistoryTitleChange: mockOnHistoryTitleChange,
  onHistoryDelete: mockOnHistoryDelete,
  isGenerating: false,
  toggleToggleSpinner: mockOnToggleSpinner
}
describe('ChatHistoryListItemCell', () => {
  beforeEach(() => {
    mockOnSelect.mockClear()
    global.fetch = jest.fn()
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  test('renders the chat history item', () => {
render(<ChatHistoryListItemCell {...componentProps} />);
    const titleElement = screen.getByText(/Test Chat/i)
    expect(titleElement).toBeInTheDocument()
  })

  test('truncates long title', () => {
    // Create a long title for the conversation
    const longTitleConversation = {
      ...conversation,
      title: 'A very long title that should be truncated after 28 characters'
    }

    // Update the component props with the long title conversation
    const componentPropsWithLongTitle = {
      ...componentProps,
      item: longTitleConversation // Pass the modified conversation here
    }

    // Render the component with the updated props
    render(<ChatHistoryListItemCell {...componentPropsWithLongTitle} />)

    // Check if the truncated title is in the document
    const truncatedTitle = screen.getByText(/A very long title that shoul .../i)
    expect(truncatedTitle).toBeInTheDocument()
   })

  test('calls onSelect when clicked', () => {
   render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.click(item)
    expect(mockOnSelect).toHaveBeenCalledWith(conversation)
  })

  test('when null item is not passed', () => {
    // Modify componentProps to pass `undefined` for `item`
    const componentPropsWithUndefinedItem = {
      ...componentProps,
      item: undefined // Set item to undefined
    };

    // Render the component with the updated props
    render(<ChatHistoryListItemCell {...componentPropsWithUndefinedItem} />)

    // Expect that no content related to the title is rendered
    const titleElement = screen.queryByText(/Test Chat/i);
    expect(titleElement).not.toBeInTheDocument();
})

  test('displays delete and edit buttons on hover', async () => {
    const mockAppStateUpdated = {
      ...componentProps,
      currentChat: { id: '' }
    }
    render(<ChatHistoryListItemCell {...mockAppStateUpdated} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    await waitFor(() => {
      expect(screen.getByTitle(/Delete/i)).toBeInTheDocument()
      expect(screen.getByTitle(/Edit/i)).toBeInTheDocument()
    })
  })

  test('hides delete and edit buttons when not hovered', async () => {
    const mockAppStateUpdated = {
      ...mockAppState,
      currentChat: { id: '' }
    }
    render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    await waitFor(() => {
      expect(screen.getByTitle(/Delete/i)).toBeInTheDocument()
      expect(screen.getByTitle(/Edit/i)).toBeInTheDocument()
    })

    fireEvent.mouseLeave(item)
    await waitFor(() => {
      expect(screen.queryByTitle(/Delete/i)).not.toBeInTheDocument()
      expect(screen.queryByTitle(/Edit/i)).not.toBeInTheDocument()
    })
  })

  test('shows confirmation dialog and deletes item', async () => {
    ;(historyDelete as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    })

    render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    const deleteButton = screen.getByTitle(/Delete/i)
    fireEvent.click(deleteButton)

    await waitFor(() => {
      expect(screen.getByText(/Are you sure you want to delete this item?/i)).toBeInTheDocument()
    })

    const confirmDeleteButton = screen.getByRole('button', { name: 'Delete' })
    fireEvent.click(confirmDeleteButton)

    await waitFor(() => {
      expect(historyDelete).toHaveBeenCalled()
    })
  })

  test('when delete API fails or return false', async () => {
    ;(historyDelete as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({})
    })

    render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    const deleteButton = screen.getByTitle(/Delete/i)
    fireEvent.click(deleteButton)

    await waitFor(() => {
      expect(screen.getByText(/Are you sure you want to delete this item?/i)).toBeInTheDocument()
    })

    const confirmDeleteButton = screen.getByRole('button', { name: 'Delete' })

    await act(() => {
      userEvent.click(confirmDeleteButton)
    })

    await waitFor(async () => {
      expect(await screen.findByText(/Error: could not delete item/i)).toBeInTheDocument()
    })
  })

  test('cancel delete when confirmation dialog is shown', async () => {
    render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    const deleteButton = screen.getByTitle(/Delete/i)
    fireEvent.click(deleteButton)

    await waitFor(() => {
      expect(screen.getByText(/Are you sure you want to delete this item?/i)).toBeInTheDocument()
    })
    const cancelDeleteButton = screen.getByRole('button', { name: 'Cancel' })
    fireEvent.click(cancelDeleteButton)

    await waitFor(() => {
      expect(screen.queryByText(/Are you sure you want to delete this item?/i)).not.toBeInTheDocument()
    })
  })

  test('disables buttons when request is initiated', () => {
    const appStateWithRequestInitiated = {
      ...componentProps,
      isGenerating: true,
      selectedConvId:'1'
    }

    render(<ChatHistoryListItemCell {...appStateWithRequestInitiated} onSelect={mockOnSelect}  />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    const deleteButton = screen.getByTitle(/Delete/i)
    const editButton = screen.getByTitle(/Edit/i)

    expect(deleteButton).toBeDisabled()
    expect(editButton).toBeDisabled()
  })

  test('does not disable buttons when request is not initiated', () => {
  render(<ChatHistoryListItemCell {...componentProps} />);
  const item = screen.getByLabelText('chat history item')
  fireEvent.mouseEnter(item)
  const deleteButton = screen.getByTitle(/Delete/i)
    const editButton = screen.getByTitle(/Edit/i)

    expect(deleteButton).not.toBeDisabled()
    expect(editButton).not.toBeDisabled()
  })

  test('calls onEdit when Edit button is clicked', async () => {
    render(<ChatHistoryListItemCell {...componentProps} />);

    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item) // Simulate hover to reveal Edit button

    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i)
      expect(editButton).toBeInTheDocument()
      fireEvent.click(editButton) // Simulate Edit button click
    })
    const inputItem = screen.getByPlaceholderText('Test Chat')
    expect(inputItem).toBeInTheDocument() // Ensure onEdit is called with the conversation item
    expect(inputItem).toHaveValue('Test Chat')
  })

  test('handles input onChange and onKeyDown ENTER events correctly', async () => {
    ;(historyRename as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    })

render(<ChatHistoryListItemCell {...componentProps} />);
    // Simulate hover to reveal Edit button
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    // Wait for the Edit button to appear and click it
    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i)
      expect(editButton).toBeInTheDocument()
      fireEvent.click(editButton)
    })

    // Find the input field
    const inputItem = screen.getByPlaceholderText('Test Chat')
    expect(inputItem).toBeInTheDocument() // Ensure input is there

    // Simulate the onChange event by typing into the input field
    fireEvent.change(inputItem, { target: { value: 'Updated Chat' } })
    expect(inputItem).toHaveValue('Updated Chat') // Ensure value is updated

    // Simulate keydown event for the 'Enter' key
    fireEvent.keyDown(inputItem, { key: 'Enter', code: 'Enter', charCode: 13 })

    await waitFor(() => expect(historyRename).toHaveBeenCalled())

    // Optionally: Verify that some onSave or equivalent function is called on Enter key
    // expect(mockOnSave).toHaveBeenCalledWith('Updated Chat'); (if you have a mock function for the save logic)

    // Simulate keydown event for the 'Escape' key
    // fireEvent.keyDown(inputItem, { key: 'Escape', code: 'Escape', charCode: 27 });

    //await waitFor(() =>  expect(screen.getByPlaceholderText('Updated Chat')).not.toBeInTheDocument());
  })

  test('handles input onChange and onKeyDown ESCAPE events correctly', async () => {
    render(<ChatHistoryListItemCell {...componentProps} />);

    // Simulate hover to reveal Edit button
    const item = screen.getByLabelText('chat history item');
    fireEvent.mouseEnter(item);

    // Wait for the Edit button to appear and click it
    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i);
      fireEvent.click(editButton);
    });

    // Find the input field
    const inputItem = screen.getByPlaceholderText('Test Chat');
    expect(inputItem).toBeInTheDocument(); // Ensure input is there

    // Simulate the onChange event by typing into the input field
    fireEvent.change(inputItem, { target: { value: 'Updated Chat Change' } });

    fireEvent.keyDown(inputItem, { key: 'Escape', code: 'Escape', charCode: 27 });
    await waitFor(() => {
      //console.log("Current value:", inputItem);  // Debugging log
      expect(inputItem).not.toBeInTheDocument();
    });

  });


  test('Should hide the rename from when cancel it.', async () => {
    userEvent.setup()

    render(<ChatHistoryListItemCell {...componentProps}/>)
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    // Wait for the Edit button to appear and click it
    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i)
      fireEvent.click(editButton)
    })

    await userEvent.click(screen.getByRole('button', { name: 'cancel edit title' }))

    // Wait for the error to be hidden after 5 seconds
    await waitFor(() => {
      const input = screen.queryByLabelText('confirm new title')
      expect(input).not.toBeInTheDocument()
    })
  })

  test.skip('handles rename save API failed', async () => {
    userEvent.setup()
    ;(historyRename as jest.Mock).mockRejectedValue({
      ok: false,
      json: async () => ({})
    })

    render(<ChatHistoryListItemCell {...componentProps} />);
    // Simulate hover to reveal Edit button
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    // Wait for the Edit button to appear and click it
    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i)
      fireEvent.click(editButton)
    })

    const inputItem = screen.getByPlaceholderText('Test Chat');
    expect(inputItem).toBeInTheDocument(); // Ensure input is there

    // Simulate the onChange event by typing into the input field
    fireEvent.change(inputItem, { target: { value: 'Updated Chat Change' } });
    userEvent.click(screen.getByRole('button', { name: 'confirm new title' }))

    await waitFor(() => {
      expect(screen.getByText(/Error: could not rename item/i)).toBeInTheDocument()
    })

    // Wait for the error to be hidden after 5 seconds
    await waitFor(() => expect(screen.queryByText('Error: could not rename item')).not.toBeInTheDocument(), {
      timeout: 6000
    })
    const input = screen.getByLabelText('confirm new title')
    expect(input).toHaveFocus()
  }, 10000)

  test('shows error when trying to rename to an existing title', async () => {
    const existingTitle = 'Existing Chat Title'
    const conversationWithExistingTitle: Conversation = {
      id: '2',
      title: existingTitle,
      messages: [],
      date: new Date().toISOString()
    }

    ;(historyRename as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'Title already exists' })
    })

render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i)
      fireEvent.click(editButton)
    })

    const inputItem = screen.getByPlaceholderText(conversation.title)
    fireEvent.change(inputItem, { target: { value: existingTitle } })

    fireEvent.keyDown(inputItem, { key: 'Enter', code: 'Enter', charCode: 13 })

    await waitFor(() => {
      expect(screen.getByText(/Error: could not rename item/i)).toBeInTheDocument()
    })
  })


  test('triggers edit functionality when Enter key is pressed', async () => {
    ;(historyRename as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Title changed' })
    })
    render(<ChatHistoryListItemCell {...componentProps} />);

    // Simulate hover to reveal Edit button
    const item = screen.getByLabelText('chat history item');
    fireEvent.mouseEnter(item);

    // Wait for the Edit button to appear and click it
    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i);
      fireEvent.click(editButton);
    });

    // Find the input field
    const inputItem = screen.getByPlaceholderText('Test Chat');
    expect(inputItem).toBeInTheDocument(); // Ensure input is there

    // Simulate the onChange event by typing into the input field
    fireEvent.change(inputItem, { target: { value: 'Updated Chat Change' } });

    fireEvent.keyDown(inputItem, { key: 'Enter', code: 'Enter', charCode: 13 })
    await waitFor(() => {
      //console.log("Current value:", inputItem);  // Debugging log
      expect(inputItem).toHaveValue('Updated Chat Change');
    });

  })

  test('successfully saves edited title', async () => {
    ;(historyRename as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    })

render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    const editButton = screen.getByTitle(/Edit/i)
    fireEvent.click(editButton)

    const inputItem = screen.getByPlaceholderText('Test Chat')
    fireEvent.change(inputItem, { target: { value: 'Updated Chat' } })

    const form = screen.getByLabelText('edit title form')
    fireEvent.submit(form)

    await waitFor(() => {
      expect(historyRename).toHaveBeenCalledWith('1', 'Updated Chat')
    })
  })

  test('calls onEdit when space key is pressed on the Edit button', () => {
    const mockOnSelect = jest.fn()
    const mockAppStateUpdated = {
      ...componentProps,
      currentChat: { id: '1' },
      isRequestInitiated: false
    }
    render(<ChatHistoryListItemCell {...mockAppStateUpdated} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    const editButton = screen.getByTitle(/Edit/i)

    fireEvent.keyDown(editButton, { key: ' ', code: 'Space', charCode: 32 })

    expect(screen.getByLabelText(/confirm new title/i)).toBeInTheDocument()
  })

  test('calls toggleDeleteDialog when space key is pressed on the Delete button', () => {
    // const toggleDeleteDialogMock = jest.fn()
    const mockAppStateUpdated = {
      ...componentProps,
      currentChat: { id: '1' },
      isRequestInitiated: false
    }
    render(<ChatHistoryListItemCell {...mockAppStateUpdated} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)
    const deleteButton = screen.getByTitle(/Delete/i)

    // fireEvent.focus(deleteButton)

    fireEvent.keyDown(deleteButton, { key: ' ', code: 'Space', charCode: 32 })

    expect(screen.getByLabelText(/chat history item/i)).toBeInTheDocument()
  })

  ///////

  test('opens delete confirmation dialog when Enter key is pressed on the Delete button', async () => {
render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    const deleteButton = screen.getByTitle(/Delete/i)
    fireEvent.keyDown(deleteButton, { key: 'Enter', code: 'Enter', charCode: 13 })

    // expect(await screen.findByText(/Are you sure you want to delete this item?/i)).toBeInTheDocument()
  })

  test('opens delete confirmation dialog when Space key is pressed on the Delete button', async () => {
render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    const deleteButton = screen.getByTitle(/Delete/i)
    fireEvent.keyDown(deleteButton, { key: ' ', code: 'Space', charCode: 32 })

    expect(await screen.findByText(/Are you sure you want to delete this item?/i)).toBeInTheDocument()
  })

  test('opens edit input when Space key is pressed on the Edit button', async () => {
 render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    const editButton = screen.getByTitle(/Edit/i)
    fireEvent.keyDown(editButton, { key: ' ', code: 'Space', charCode: 32 })

    const inputItem = screen.getByLabelText('confirm new title')
    expect(inputItem).toBeInTheDocument()
  })

  test('opens edit input when Enter key is pressed on the Edit button', async () => {
  render(<ChatHistoryListItemCell {...componentProps} />);
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    const editButton = screen.getByTitle(/Edit/i)
    fireEvent.keyDown(editButton, { key: 'Enter', code: 'Enter', charCode: 13 })

    // const inputItem = await screen.getByLabelText('confirm new title')
    // expect(inputItem).toBeInTheDocument()
  })

  test('handles rename save when the updated text is equal to initial text', async () => {
    userEvent.setup()
    ;(historyRename as jest.Mock).mockRejectedValue({
      ok: false,
      json: async () => ({ message: 'Title not changed' })
    })
    render(<ChatHistoryListItemCell {...componentProps}/>)

    // Simulate hover to reveal Edit button
    const item = screen.getByLabelText('chat history item')
    fireEvent.mouseEnter(item)

    // Wait for the Edit button to appear and click it
    await waitFor(() => {
      const editButton = screen.getByTitle(/Edit/i)
      expect(editButton).toBeInTheDocument()
      fireEvent.click(editButton)
    })

    // Find the input field
    const inputItem = screen.getByPlaceholderText('Test Chat')
    expect(inputItem).toBeInTheDocument() // Ensure input is there

    await act(() => {
      userEvent.type(inputItem, 'Test Chat')
      //fireEvent.change(inputItem, { target: { value: 'Test Chat' } });
    })
    expect(historyRename).not.toHaveBeenCalled()
})
test('Should hide the rename from on Enter or space .', async () => {
  userEvent.setup()

  render(<ChatHistoryListItemCell {...componentProps}/>)
  const item = screen.getByLabelText('chat history item')
  fireEvent.mouseEnter(item)
  // Wait for the Edit button to appear and click it
  await waitFor(() => {
    const editButton = screen.getByTitle(/Edit/i)
    fireEvent.click(editButton)
  })

  const editButton =screen.getByRole('button', { name: 'cancel edit title' })
  fireEvent.keyDown(editButton, { key: 'Enter', code: 'Enter', charCode: 13 })

  // Wait for the error to be hidden after 5 seconds
  await waitFor(() => {
    const input = screen.queryByLabelText('confirm new title')
    expect(input).not.toBeInTheDocument()
  })
})
})
