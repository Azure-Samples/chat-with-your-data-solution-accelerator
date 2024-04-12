import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const envDir = process.env.VITE_ENV_DIR;

// https://vitejs.dev/config/
export default defineConfig({
    envDir: envDir,
    plugins: [react()],
    build: {
        outDir: "../dist/static",
        emptyOutDir: true,
        sourcemap: true
    },
    server: {
        proxy: {
            "/api": {
                target: "http://127.0.0.1:5000",
                changeOrigin: true,
                secure: false
            }
        }
    }
});
