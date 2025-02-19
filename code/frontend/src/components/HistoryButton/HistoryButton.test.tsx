import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryButton } from './HistoryButton';
import '@testing-library/jest-dom';

// Mocking Fluent UI's DefaultButton to focus on the functionality of the HistoryButton component
jest.mock('@fluentui/react', () => ({
  DefaultButton: ({ text, iconProps, onClick, className }: any) => (
    <button className={className} onClick={onClick}>
      {iconProps?.iconName && <span className="icon">{iconProps.iconName}</span>}
      {text}
    </button>
  ),
}));

describe('HistoryButton', () => {
  it('renders the button with the correct text', () => {
    render(<HistoryButton onClick={() => {}} text="View History" />);

    const button = screen.getByText('View History');
    expect(button).toBeInTheDocument();
  });

  it('renders the History icon', () => {
    render(<HistoryButton onClick={() => {}} text="View History" />);

    const icon = screen.getByText('History'); // Icon is represented as text in the mock
    expect(icon).toBeInTheDocument();
  });

  it('calls the onClick function when clicked', () => {
    const handleClick = jest.fn();
    render(<HistoryButton onClick={handleClick} text="View History" />);

    const button = screen.getByText('View History');
    fireEvent.click(button);

    // Check that the onClick function was called
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('applies the correct className from styles', () => {
    render(<HistoryButton onClick={() => {}} text="View History" />);

    const button = screen.getByText('View History');
    // Check if the class name is applied correctly (mocked value for styles.historyButtonRoot)
    expect(button).toHaveClass('historyButtonRoot');
  });

  it('renders correctly when text is undefined', () => {
    render(<HistoryButton onClick={() => {}} text={undefined} />);

    const button = screen.queryByText(/View History/);
    // Ensure no text is rendered when `text` is undefined
    expect(button).toBeNull();
  });
});
