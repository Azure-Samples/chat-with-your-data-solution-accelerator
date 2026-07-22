/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Vitest config for the v2 frontend test tree. This package is a sibling
// workspace member of cwyd-frontend; both hoist to node_modules, so a
// bare import in a spec ("@testing-library/react", the auto-injected
// "react/jsx-runtime") resolves from the shared hoisted tree with no
// per-package shims. The "@" alias points at the frontend source under
// test, matching the alias the frontend itself uses.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("../../src/frontend/src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./setup.tsx"],
    include: ["**/*.{test,spec}.{ts,tsx}"],
    css: false,
  },
});
