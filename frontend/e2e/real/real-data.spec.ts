import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

const REAL = process.env.QUANTOS_REAL_DATA ?? "D:/quant_system/data";
const shots = "test-results/real-shots";
test.describe.configure({ mode: "serial" });
const shot = async (page: import("@playwright/test").Page, name: string) => {
  mkdirSync(shots, { recursive: true });
  await page.screenshot({ path: `${shots}/${name}.png` });
};

test("connect the real data folder and build the full index", async ({ page }) => {
  const started = Date.now();
  await page.goto("/");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Get started" }).click();
  await page.getByRole("radio", { name: /Investor/ }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("QuantOS data folder").fill(REAL);
  await page.getByRole("button", { name: "Connect and build" }).click();
  await expect(page.getByText("Market data connected")).toBeVisible({ timeout: 400_000 });
  console.log(`index build via UI: ${((Date.now() - started) / 1000).toFixed(0)} s`);
  await shot(page, "01-connected");
  await page.getByRole("button", { name: "Open QuantOS" }).click();
  await expect(page.getByText("Market breadth")).toBeVisible();
  await page.waitForTimeout(600);
  await shot(page, "02-home");
});

test("screener over the whole market stays fast", async ({ page }) => {
  await page.goto("/markets");
  await page.getByRole("radio", { name: "All listed" }).click();
  await expect(page.getByText(/^\d[\d,]* shown\./)).toBeVisible({ timeout: 30_000 });
  const t = Date.now();
  await page.getByRole("button", { name: /^1Y/ }).click();
  await expect(page.getByRole("columnheader", { name: /1Y/ })).toHaveAttribute("aria-sort", /ascending|descending/);
  console.log(`re-sort of the full market: ${Date.now() - t} ms`);
  await page.getByRole("radio", { name: "Near 52-week high" }).click();
  await page.waitForTimeout(500);
  await shot(page, "03-markets-all");
});

test("real stock pages: a normal one and one with a demerger", async ({ page }) => {
  await page.goto("/stock/INFY");
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.waitForTimeout(700);
  await shot(page, "04-stock-infy");
  await page.goto("/stock/HEG");
  await expect(page.getByText(/not comparable/).first()).toBeVisible();
  await shot(page, "05-stock-heg");
  await page.goto("/stock/SPLPETRO");
  await page.waitForTimeout(700);
  await shot(page, "06-stock-splpetro");
});

test("real Strategy Lab: trend on a stock, momentum on a universe", async ({ page }) => {
  await page.goto("/lab/new/trend?symbols=TATASTEEL,RELIANCE,HDFCBANK");
  const started = Date.now();
  await page.getByRole("button", { name: "Run test" }).click();
  // RELIANCE demerged Jio Financial on 2023-07-20: the lab must refuse and offer a one-click fix.
  await expect(page.getByText(/RELIANCE had a demerger on 2023-07-20/)).toBeVisible();
  await shot(page, "06b-lab-refused-real");
  await page.getByRole("button", { name: "Remove RELIANCE and run" }).click();
  await expect(page.getByRole("region", { name: "Verdict" })).toBeVisible({ timeout: 120_000 });
  console.log(`trend lab run: ${Date.now() - started} ms`);
  await page.waitForTimeout(800);
  await shot(page, "07-lab-trend");

  await page.goto("/lab/new/momentum");
  const t = Date.now();
  await page.getByRole("button", { name: "Run test" }).click();
  await expect(page.getByRole("region", { name: "Verdict" })).toBeVisible({ timeout: 180_000 });
  console.log(`momentum universe lab run: ${Date.now() - t} ms`);
  await page.waitForTimeout(800);
  await shot(page, "08-lab-momentum");
  await page.getByText("How this was tested").click();
  await shot(page, "09-lab-momentum-assumptions");
});

test("real portfolio and tools", async ({ page }) => {
  await page.goto("/portfolio");
  for (const [symbol, qty, price, date] of [
    ["INFY", "40", "1500", "2024-01-15"],
    ["TCS", "10", "3800", "2024-02-10"],
    ["ITC", "300", "420", "2023-11-01"],
  ]) {
    await page.getByRole("button", { name: /Add (holding|your first holding)/ }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("combobox").fill(symbol!);
    await dialog.getByRole("option", { name: new RegExp(`^${symbol}`) }).first().click();
    await dialog.getByLabel("Quantity").fill(qty!);
    await dialog.getByLabel("Average price").fill(price!);
    await dialog.getByLabel("Bought on").fill(date!);
    await dialog.getByRole("button", { name: "Add holding" }).click();
    await expect(dialog).toBeHidden();
  }
  await expect(page.getByText("Versus NIFTY")).toBeVisible();
  await page.waitForTimeout(700);
  await shot(page, "10-portfolio");
  await page.goto("/tools/options");
  await page.waitForTimeout(900);
  await shot(page, "11-options");
});
