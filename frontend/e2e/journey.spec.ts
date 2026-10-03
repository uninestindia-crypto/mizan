import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test as base } from "@playwright/test";
import { mkdirSync } from "node:fs";

// One shared server and state folder: the tests below are one continuous first-time-user journey.
const fixtureData = `${process.env.QUANTOS_E2E_DIR}/fixture/data`.replace(/\//g, "\\");
const shots = "test-results/shots";

interface Problems {
  /** Declare a problem this test provokes on purpose (for example a refused request's 400). */
  expect: (pattern: RegExp) => void;
}

const test = base.extend<{ problems: Problems }>({
  problems: [
    async ({ page }, use) => {
      const seen: string[] = [];
      const expected: RegExp[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") seen.push(`console: ${msg.text()}`);
      });
      page.on("pageerror", (err) => seen.push(`pageerror: ${err.message}`));
      page.on("requestfailed", (req) => seen.push(`request failed: ${req.url()} ${req.failure()?.errorText}`));
      page.on("response", (res) => {
        if (res.status() >= 500) seen.push(`HTTP ${res.status()}: ${res.url()}`);
      });
      await use({ expect: (pattern) => void expected.push(pattern) });
      const unexpected = seen.filter((problem) => !expected.some((pattern) => pattern.test(problem)));
      expect(unexpected, "browser problems").toEqual([]);
    },
    { auto: true },
  ],
});

test.describe.configure({ mode: "serial" });

const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Main" }).getByRole("link", { name, exact: true }).click();
const shot = async (page: Page, name: string) => {
  mkdirSync(shots, { recursive: true });
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: false });
};

test("first run: welcome, style, money rules, data, then Home", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/welcome$/);
  await expect(page.getByRole("heading", { name: /Know before you risk real money/ })).toBeVisible();
  await shot(page, "01-welcome");

  const start = page.getByRole("button", { name: "Get started" });
  await expect(start).toBeDisabled();
  await page.getByRole("checkbox").check();
  await start.click();

  await expect(page.getByRole("heading", { name: "How do you invest?" })).toBeVisible();
  await page.getByRole("radio", { name: /Swing trader/ }).click();
  await shot(page, "02-style");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Set your money rules" })).toBeVisible();
  await expect(page.getByText("₹10,000", { exact: false }).first()).toBeVisible();
  await shot(page, "03-money");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Connect your market data" })).toBeVisible();
  await expect(page.getByText("Market data connected")).toHaveCount(0);
  await page.getByLabel("QuantOS data folder").fill(fixtureData);
  await page.getByRole("button", { name: "Connect and build" }).click();
  await expect(page.getByText("Market data connected")).toBeVisible({ timeout: 60_000 });
  await shot(page, "04-data");
  await page.getByRole("button", { name: "Open QuantOS" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("NIFTY 50", { exact: true })).toBeVisible();
});

test("home shows the market pulse and breadth from real index data", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Market breadth")).toBeVisible();
  await expect(page.getByText("above their 200-day average")).toBeVisible();
  await expect(page.getByText("Data to ")).toBeVisible();
  await shot(page, "05-home");
});

test("markets: screener lists stocks, presets and sorting work, row opens the stock", async ({ page }) => {
  await page.goto("/");
  await nav(page, "Markets");
  await expect(page.getByRole("heading", { name: "Markets" })).toBeVisible();
  const rows = page.getByRole("row");
  await expect(rows.filter({ hasText: "AAA" })).toBeVisible();
  await expect(rows.filter({ hasText: "BBB" })).toBeVisible();
  await page.getByRole("radio", { name: "Low volatility" }).click();
  await page.getByRole("button", { name: /Stock/ }).click();
  await page.getByPlaceholder("Filter by symbol or name").fill("alpha");
  await expect(rows.filter({ hasText: "BBB" })).toHaveCount(0);
  await shot(page, "06-markets");
  await rows.filter({ hasText: "AAA" }).click();
  await expect(page).toHaveURL(/\/stock\/AAA$/);
});

test("stock: chart, statistics, costs, watchlist and add-to-portfolio", async ({ page }) => {
  await page.goto("/stock/AAA");
  await expect(page.getByRole("heading", { name: "AAA", exact: true })).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();
  await expect(page.getByText("Round-trip charges")).toBeVisible();
  await expect(page.getByText("Corporate actions")).toBeVisible();
  await shot(page, "07-stock");

  await page.getByRole("button", { name: "Watch", exact: true }).click();
  await expect(page.getByRole("button", { name: "Watching" })).toBeVisible();

  await page.getByRole("button", { name: "Add to portfolio" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Quantity").fill("50");
  await dialog.getByLabel("Average price").fill("110.5");
  await dialog.getByLabel("Bought on").fill("2020-08-03");
  await dialog.getByRole("button", { name: "Add holding" }).click();
  await expect(dialog).toBeHidden();
});

test("stock with a demerger explains why history is not comparable", async ({ page }) => {
  await page.goto("/stock/BBB");
  await expect(page.getByText(/not comparable/).first()).toBeVisible();
  await expect(page.getByText(/Only the \d+-session refresh is used/)).toBeVisible();
  await shot(page, "08-stock-demerger");
});

test("lab: run buy and hold, get a verdict, then a refused test is explained", async ({ page, problems }) => {
  problems.expect(/status of 400/);
  await page.goto("/");
  await nav(page, "Strategy Lab");
  await expect(page.getByRole("heading", { name: "Choose a strategy to test" })).toBeVisible();
  await shot(page, "09-lab");
  await page.getByRole("button", { name: /Buy and hold/ }).click();

  const box = page.getByRole("combobox");
  await box.fill("AAA");
  await page.getByRole("option", { name: /AAA/ }).click();
  await page.getByRole("button", { name: "Run test" }).click();

  const verdict = page.getByRole("region", { name: "Verdict" });
  await expect(verdict).toBeVisible({ timeout: 30_000 });
  await expect(verdict).toContainText(/Chance the edge is real|No probability shown/);
  await expect(page.getByText("Growth of")).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();
  await expect(page.getByText("How this was tested")).toBeVisible();
  await shot(page, "10-lab-result");

  await page.goto("/lab/new/buy_hold?symbols=DDD");
  await page.getByRole("button", { name: "Run test" }).click();
  await expect(page.getByText("The lab refused this test")).toBeVisible();
  await expect(page.getByText(/demerger/i).first()).toBeVisible();
  await shot(page, "11-lab-refused");
});

test("portfolio: holding is valued and compared with NIFTY", async ({ page }) => {
  await page.goto("/portfolio");
  await expect(page.getByRole("link", { name: "AAA" })).toBeVisible();
  await expect(page.getByText("Versus NIFTY")).toBeVisible();
  await expect(page.getByText("Allocation")).toBeVisible();
  await shot(page, "12-portfolio");
});

test("paper trading page explains itself when no books exist here", async ({ page }) => {
  await page.goto("/paper");
  await expect(page.getByRole("heading", { name: "Paper trading" })).toBeVisible();
  await expect(page.getByText("How to read these numbers")).toBeVisible();
  await shot(page, "13-paper");
});

test("tools: cost calculator, position size and options payoff", async ({ page }) => {
  await page.goto("/tools");
  await expect(page).toHaveURL(/\/tools\/costs$/);
  await expect(page.getByText("Profit after charges")).toBeVisible();
  await expect(page.getByText("Securities transaction tax (STT)").first()).toBeVisible();
  await shot(page, "14-tools-costs");

  await page.getByRole("link", { name: "Position size" }).click();
  await expect(page.getByText("Loss if stopped out")).toBeVisible();
  await shot(page, "15-tools-size");

  await page.getByRole("link", { name: "Options payoff" }).click();
  await expect(page.getByText("Position Greeks today")).toBeVisible();
  await expect(page.getByRole("img", { name: /Profit and loss by underlying price/ })).toBeVisible();
  await shot(page, "16-tools-options");
});

test("settings: every section opens", async ({ page }) => {
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/settings\/profile$/);
  for (const [link, text] of [
    ["Broker charges", "Your broker's charges"],
    ["Market data", "Data folder"],
    ["Accounts & keys", "Upstox API key"],
    ["AI assistants", "Codex CLI"],
    ["About", "Open-source software"],
  ] as const) {
    await page.getByRole("navigation", { name: "Settings" }).getByRole("link", { name: link }).click();
    await expect(page.getByText(text).first()).toBeVisible();
  }
  await shot(page, "17-settings-about");
});

test("search palette finds a stock with the keyboard", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Market breadth")).toBeVisible();
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder(/Search a stock/).fill("alp");
  await page.getByRole("option", { name: /AAA/ }).click();
  await expect(page).toHaveURL(/\/stock\/AAA$/);
});

test("dark theme applies everywhere and survives a reload", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await shot(page, "20-home-dark");
  await page.goto("/stock/AAA");
  await expect(page.locator("canvas").first()).toBeVisible();
  await shot(page, "21-stock-dark");
  await page.goto("/lab");
  await shot(page, "22-lab-dark");
  await page.goto("/markets");
  await expect(page.getByRole("row").filter({ hasText: "AAA" })).toBeVisible();
  await shot(page, "23-markets-dark");
});

test("a narrow window still has navigation and no horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 900 });
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Markets" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await shot(page, "24-narrow");
});

// ---------------------------------------------------------------------------- accessibility

const PAGES = [
  ["home", "/"],
  ["markets", "/markets"],
  ["stock", "/stock/AAA"],
  ["stock with data break", "/stock/BBB"],
  ["lab", "/lab"],
  ["lab setup", "/lab/new/momentum"],
  ["portfolio", "/portfolio"],
  ["paper", "/paper"],
  ["cost tool", "/tools/costs"],
  ["size tool", "/tools/position-size"],
  ["options tool", "/tools/options"],
  ["settings profile", "/settings/profile"],
  ["settings data", "/settings/data"],
  ["settings accounts", "/settings/accounts"],
  ["settings about", "/settings/about"],
] as const;

for (const theme of ["light", "dark"] as const) {
  test(`accessibility (axe, WCAG 2 AA) in ${theme} theme`, async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Market breadth")).toBeVisible();
    await page.getByRole("radio", { name: theme === "dark" ? "Dark" : "Light" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const failures: string[] = [];
    for (const [name, path] of PAGES) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(400); // let the fade-in animation finish before measuring contrast
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      for (const v of results.violations) {
        failures.push(`${name}: ${v.id} (${v.impact}) x${v.nodes.length} — ${v.help} — e.g. ${v.nodes[0]?.target.join(" ")} :: ${v.nodes[0]?.failureSummary?.split("\n")[1] ?? ""}`);
      }
    }
    expect(failures, "accessibility violations").toEqual([]);
  });
}
