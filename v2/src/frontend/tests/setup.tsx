/**
 * Pillar: Stable Core
 * Phase: 1
 *
 * Vitest setup: extend `expect` with `@testing-library/jest-dom`
 * matchers (`toBeInTheDocument`, `toHaveTextContent`, etc.) so every
 * test file can use them without a per-file import.
 */
import "@testing-library/jest-dom/vitest";

// jsdom does not implement Element.prototype.scrollIntoView, but
// components like MessageList rely on it for auto-scroll. Provide a
// no-op stub so renders do not throw; individual tests can vi.spyOn
// to assert call shape.
if (typeof Element.prototype.scrollIntoView !== "function") {
  Element.prototype.scrollIntoView = function scrollIntoView(): void {
    /* no-op for jsdom */
  };
}
