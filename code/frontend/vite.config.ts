import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  console.log("mode: ", mode);
  const { VITE_API_URL } = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    build: {
      outDir: "build",
      emptyOutDir: true,
      sourcemap: false,
    },
    publicDir: "public",
    server: {
      proxy: {
        "/api": {
          target: VITE_API_URL,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
