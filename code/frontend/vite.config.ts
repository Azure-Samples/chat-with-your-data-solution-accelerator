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
                target: "https://rsta4xey-test-website-6eg6fe2yksguu.azurewebsites.net",
                changeOrigin: true,
                secure: false
            }
        }
    }
});
