import { render, screen } from '@testing-library/react';
import  Cards  from './Cards';

describe('Cards Component', () => {
  beforeEach(() => {
    render(<Cards />);
  });

  test('renders the main container', () => {
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  test('renders "Interact with Data" card correctly', () => {
    expect(screen.getByText(/Interact with Data/i)).toBeInTheDocument();
    expect(screen.getByText(/Intuitive and conversational search experience/i)).toBeInTheDocument();
    expect(screen.getByAltText(/Intract with Data/i)).toBeInTheDocument();
  });

  test('renders "Summarize Contracts" card correctly', () => {
    expect(screen.getByText(/Summarize Contracts/i)).toBeInTheDocument();
    expect(screen.getByText(/Quickly review and summarize lengthy documents/i)).toBeInTheDocument();
    expect(screen.getByAltText(/Summarize Contracts/i)).toBeInTheDocument();
  });

  test('renders "Quick Source Reference" card correctly', () => {
    expect(screen.getByText(/Quick Source Reference/i)).toBeInTheDocument();
    expect(screen.getByText(/Effortlessly retrieve and reference original documents/i)).toBeInTheDocument();
    expect(screen.getByAltText(/Source Reference/i)).toBeInTheDocument();
  });
});
