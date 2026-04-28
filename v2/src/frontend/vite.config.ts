/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pillar: Stable Core
// Phase: 1
//
// Bare Vite scaffold for the v2 frontend. Backend URL is read at
// runtime from `import.meta.env.VITE_BACKEND_URL` so the same build
// boots against local docker-compose and against deployed Container
// Apps without a rebuild.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.{test,spec}.{ts,tsx}"],
    css: false,
  },
});
