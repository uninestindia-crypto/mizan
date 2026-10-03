import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const outDir = fileURLToPath(new URL("../src/quant_system/server/static/app", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/",
  build: {
    outDir,
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    // The server's CSP has no data: fonts/images allowance beyond img-src, so never inline assets.
    assetsInlineLimit: 0,
    // No inline scripts: the server's CSP is script-src 'self'.
    modulePreload: { polyfill: false },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
