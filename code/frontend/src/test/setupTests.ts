import '@testing-library/jest-dom'; // For jest-dom matchers like toBeInTheDocument
import { initializeIcons } from '@fluentui/react/lib/Icons';

initializeIcons();

import { server } from '../../__mocks__/server';

// Establish API mocking before all tests
beforeAll(() => server.listen());

// Reset any request handlers that are declared in a test
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished
afterAll(() => server.close());
