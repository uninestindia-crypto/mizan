// Attach to the running native QuantOS window (WebView2 debugging port) and report what it shows.
//   node e2e/native/probe.mjs [port] [screenshot.png]
import { chromium } from "@playwright/test";

const port = process.argv[2] ?? "9222";
const out = process.argv[3];
const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
const page = browser.contexts()[0]?.pages().find((p) => p.url().startsWith("http://127.0.0.1"));
if (!page) throw new Error("No QuantOS page found in the native window");
await page.waitForLoadState("networkidle");
const metrics = await page.evaluate(() => ({
  url: location.href,
  title: document.title,
  inner: [window.innerWidth, window.innerHeight],
  outer: [window.outerWidth, window.outerHeight],
  screen: [screen.width, screen.height],
  avail: [screen.availWidth, screen.availHeight],
  dpr: window.devicePixelRatio,
  theme: document.documentElement.dataset.theme,
  navLinks: [...document.querySelectorAll('nav[aria-label="Main"] a')].map((a) => a.textContent?.trim()),
  hasHorizontalScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
}));
console.log(JSON.stringify(metrics, null, 2));
if (out) await page.screenshot({ path: out });
await browser.close();
