/**
 * Vitest setup: extend `expect` with `@testing-library/jest-dom`
 * matchers (`toBeInTheDocument`, `toHaveTextContent`, etc.) so every
 * test file can use them without a per-file import.
 */
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

// jsdom does not implement Element.prototype.scrollIntoView, but
// components like MessageList rely on it for auto-scroll. Provide a
// no-op stub so renders do not throw; individual tests can vi.spyOn
// to assert call shape.
if (typeof Element.prototype.scrollIntoView !== "function") {
  Element.prototype.scrollIntoView = function scrollIntoView(): void {
    /* no-op for jsdom */
  };
}

// Reset the jsdom URL to the SPA root after every test so router-driven
// specs each start from "/" instead of inheriting the previous test's
// navigation (BrowserRouter reads window.location when it mounts).
afterEach(() => {
  window.history.pushState({}, "", "/");
});
