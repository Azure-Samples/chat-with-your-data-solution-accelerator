import { render, screen } from '@testing-library/react';
import SpinnerComponent from './Spinner';
import { Spinner } from '@fluentui/react';

// Mock the Fluent UI Spinner component
jest.mock('@fluentui/react', () => ({
  ...jest.requireActual('@fluentui/react'),
  Spinner: jest.fn(() => <div data-testid="fluent-spinner" />),
}));

describe('SpinnerComponent', () => {
  test('does not render the spinner when loading is false', () => {
    render(<SpinnerComponent loading={false} />);

    // Spinner should not be in the document
    const spinnerContainer = screen.queryByTestId('spinnerContainer');
    expect(spinnerContainer).not.toBeInTheDocument();
  });

  test('renders the spinner when loading is true', () => {
    render(<SpinnerComponent loading={true} />);

    // Spinner should be in the document
    const spinnerContainer = screen.getByTestId('spinnerContainer');
    expect(spinnerContainer).toBeInTheDocument();
  });

  test('renders the spinner with the provided label', () => {
    const label = 'Loading...';
    render(<SpinnerComponent loading={true} label={label} />);

    // Spinner should be in the document with the provided label
    expect(Spinner).toHaveBeenCalledWith(
      expect.objectContaining({ label }),
      expect.anything()
    );
  });

  test('renders the spinner without a label when label is not provided', () => {
    render(<SpinnerComponent loading={true} />);

    // Spinner should be called without a label
    expect(Spinner).toHaveBeenCalledWith(
      expect.objectContaining({ label: undefined }),
      expect.anything()
    );
  });

  test('spinner has the correct custom styles', () => {
    render(<SpinnerComponent loading={true} />);

    // Spinner should be called with custom styles
    expect(Spinner).toHaveBeenCalledWith(
      expect.objectContaining({
        styles: expect.objectContaining({
          label: {
            fontSize: '20px',
            color: 'rgb(91 184 255)',
            fontWeight: 600,
          },
        }),
      }),
      expect.anything()
    );
  });
});
