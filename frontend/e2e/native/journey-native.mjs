// Drive the installed QuantOS native window (WebView2 debugging port) through a real first-run journey.
//   QUANTOS_DEBUG_PORT=9377 quantos-studio.exe   then   node e2e/native/journey-native.mjs [port] [dataFolder]
import { mkdirSync } from "node:fs";
import { chromium, expect } from "@playwright/test";

const port = process.argv[2] ?? "9377";
const dataFolder = process.argv[3] ?? "D:/quant_system/data";
const shots = "test-results/native-shots";
mkdirSync(shots, { recursive: true });

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
const page = browser.contexts()[0]?.pages().find((p) => p.url().startsWith("http://127.0.0.1"));
if (!page) throw new Error("No QuantOS page found in the native window");
const problems = [];
page.on("console", (m) => m.type() === "error" && problems.push(`console: ${m.text()}`));
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
const shot = (name) => page.screenshot({ path: `${shots}/${name}.png` });
const step = (text) => console.log(`- ${text}`);
const started = Date.now();

step("first run opens the welcome screen");
await expect(page.getByRole("heading", { name: /Know before you risk real money/ })).toBeVisible();
await page.getByRole("checkbox").check();
await page.getByRole("button", { name: "Get started" }).click();
await page.getByRole("radio", { name: /Investor/ }).click();
await page.getByRole("button", { name: "Continue" }).click();
await page.getByRole("button", { name: "Continue" }).click();

step("connect the real data folder and build the index");
await page.getByLabel("QuantOS data folder").fill(dataFolder);
await page.getByRole("button", { name: "Connect and build" }).click();
await expect(page.getByText("Market data connected")).toBeVisible({ timeout: 400_000 });
console.log(`  index built in ${((Date.now() - started) / 1000).toFixed(0)} s`);
await page.getByRole("button", { name: "Open QuantOS" }).click();
await expect(page.getByText("Market breadth")).toBeVisible();
await page.waitForTimeout(600);
await shot("01-home");

step("markets screener");
await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Markets", exact: true }).click();
await expect(page.getByRole("row").filter({ hasText: "RELIANCE" }).first()).toBeVisible();
await shot("02-markets");

step("stock page with chart");
await page.goto(`${page.url().split("/").slice(0, 3).join("/")}/stock/INFY`);
await expect(page.locator("canvas").first()).toBeVisible();
await page.waitForTimeout(700);
await shot("03-stock");

step("strategy lab run on real data");
await page.goto(`${page.url().split("/").slice(0, 3).join("/")}/lab/new/trend?symbols=TATASTEEL,HDFCBANK`);
await page.getByRole("button", { name: "Run test" }).click();
await expect(page.getByRole("region", { name: "Verdict" })).toBeVisible({ timeout: 120_000 });
await page.waitForTimeout(800);
await shot("04-lab");

step("cost tool");
await page.goto(`${page.url().split("/").slice(0, 3).join("/")}/tools/costs`);
await expect(page.getByText("Profit after charges")).toBeVisible();

step("settings shows the AI assistants detected on this PC");
await page.goto(`${page.url().split("/").slice(0, 3).join("/")}/settings/ai`);
await expect(page.getByText("Codex CLI")).toBeVisible();
await shot("05-settings-ai");

await browser.close();
if (problems.length) {
  console.log("PROBLEMS:\n" + problems.join("\n"));
  process.exit(1);
}
console.log(`native journey passed in ${((Date.now() - started) / 1000).toFixed(0)} s with no console errors`);
