import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const here = fileURLToPath(new URL(".", import.meta.url));
const e2eDir = `${here}test-results/e2e-app`.replace(/\\/g, "/");
const port = 8770;
process.env.QUANTOS_E2E_DIR = e2eDir;
process.env.QUANTOS_E2E_PORT = String(port);

const python = process.env.QUANTOS_PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e",
  // The real-data check has its own config (playwright.real.config.ts); it needs the user's data.
  testIgnore: "**/real/**",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  outputDir: "test-results/artifacts",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel: "msedge",
    viewport: { width: 1360, height: 860 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${python}" e2e/serve.py`,
    url: `http://127.0.0.1:${port}/api/v2/status`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
