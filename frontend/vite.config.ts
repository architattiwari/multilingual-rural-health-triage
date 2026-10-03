import { defineConfig } from "vitest/config";

// In development the API runs on :8000. In production a reverse proxy serves both from one origin.
export default defineConfig({
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  build: { target: "es2020", sourcemap: false, cssCodeSplit: false },
  test: { environment: "jsdom", include: ["tests/**/*.test.ts"] },
});
