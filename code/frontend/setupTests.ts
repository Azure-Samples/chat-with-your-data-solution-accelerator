import "@testing-library/jest-dom";
const { TextDecoder, TextEncoder } = require('node:util')

import { initializeIcons } from "@fluentui/react/lib/Icons";
initializeIcons();
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock IntersectionObserver
class IntersectionObserverMock {
  callback: IntersectionObserverCallback;
  options: IntersectionObserverInit;

  root: Element | null = null; // Required property
  rootMargin: string = '0px'; // Required property
  thresholds: number[] = [0]; // Required property

  constructor(callback: IntersectionObserverCallback, options: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
  }

  observe = jest.fn((target: Element) => {
    // Simulate intersection with an observer instance
    this.callback([{ isIntersecting: true }] as IntersectionObserverEntry[], this as IntersectionObserver);
  });

  unobserve = jest.fn();
  disconnect = jest.fn(); // Required method
  takeRecords = jest.fn(); // Required method
}

// Store the original IntersectionObserver
const originalIntersectionObserver = window.IntersectionObserver;

beforeAll(() => {
  window.IntersectionObserver = IntersectionObserverMock as any;
});

afterAll(() => {
  // Restore the original IntersectionObserver
  window.IntersectionObserver = originalIntersectionObserver;
});

