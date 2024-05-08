import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: "../dist/static",
        emptyOutDir: true,
        sourcemap: true
    },
    server: {
        proxy: {
            "/api": {
                target: "http://127.0.0.1:5050",
                changeOrigin: true,
                secure: false
            }
        }
    }
});
