import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Bare Vite scaffold for the v2 frontend. Backend URL is read at
// runtime from `import.meta.env.VITE_BACKEND_URL` so the same build
// boots against local docker-compose and against deployed Container
// Apps without a rebuild.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5273,
    host: true,
    // Local dev convenience: proxy /api/* to the host-run FastAPI backend
    // so streamChat() can keep using same-origin relative URLs and dodge
    // CORS entirely. Container Apps deploys serve frontend + backend
    // behind the same hostname so the relative URL also works there;
    // this proxy is purely a dev affordance.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
