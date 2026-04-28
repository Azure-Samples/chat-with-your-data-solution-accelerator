/**
 * Pillar: Stable Core
 * Phase: 1
 *
 * Vitest setup: extend `expect` with `@testing-library/jest-dom`
 * matchers (`toBeInTheDocument`, `toHaveTextContent`, etc.) so every
 * test file can use them without a per-file import.
 */
import "@testing-library/jest-dom/vitest";
