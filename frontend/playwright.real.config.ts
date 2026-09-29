import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// Manual check against the user's real market data (slow: builds the full index). Not part of CI.
const here = fileURLToPath(new URL(".", import.meta.url));
process.env.QUANTOS_E2E_DIR = `${here}test-results/real-app`.replaceAll("\\", "/");
process.env.QUANTOS_E2E_PORT = "8771";
const python = process.env.QUANTOS_PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e/real",
  timeout: 900_000,
  expect: { timeout: 60_000 },
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results/real-artifacts",
  use: { baseURL: "http://127.0.0.1:8771", channel: "msedge", viewport: { width: 1360, height: 860 } },
  webServer: {
    command: `"${python}" e2e/serve_real.py`,
    url: "http://127.0.0.1:8771/api/v2/status",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
