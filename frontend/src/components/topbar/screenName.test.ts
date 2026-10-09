import { describe, expect, it } from "vitest";
import { type ScreenName, screenName } from "./screenName";

const SETTINGS = { label: "Settings", to: "/settings/profile" };
const LAB = { label: "Strategy Lab", to: "/lab" };
const PAPER = { label: "Paper trading", to: "/paper" };
const TOOLS = { label: "Tools", to: "/tools/costs" };

describe("the name of the screen", () => {
  const CASES: [string, ScreenName][] = [
    ["/", { title: "Home" }],
    ["/markets", { title: "Markets" }],
    ["/stock/TCS", { title: "TCS", parent: { label: "Markets", to: "/markets" } }],
    ["/stock/m%26m", { title: "M&M", parent: { label: "Markets", to: "/markets" } }],
    ["/lab", { title: "Strategy Lab" }],
    ["/lab/new/buy_hold", { title: "New test", parent: LAB }],
    ["/lab/runs/abc123", { title: "Test result", parent: LAB }],
    ["/portfolio", { title: "Portfolio" }],
    ["/paper", { title: "Paper trading" }],
    ["/paper/new", { title: "New paper book", parent: PAPER }],
    ["/paper/2f269931b483", { title: "Paper book", parent: PAPER }],
    ["/agents", { title: "Agents" }],
    ["/shariah", { title: "Mizan Shariah" }],
    ["/tools/costs", { title: "Trade costs", parent: TOOLS }],
    ["/tools/position-size", { title: "Position size", parent: TOOLS }],
    ["/tools/agents", { title: "AI apps", parent: TOOLS }],
    ["/settings/profile", { title: "Profile & money rules", parent: SETTINGS }],
    ["/settings/ai", { title: "AI assistants", parent: SETTINGS }],
    ["/settings/about", { title: "About", parent: SETTINGS }],
    ["/settings/ai/", { title: "AI assistants", parent: SETTINGS }],
  ];

  it.each(CASES)("%s", (path, expected) => {
    expect(screenName(path)).toEqual(expected);
  });

  const ROWS_1 = [
    ["/settings/something-new", "Settings"],
    ["/tools/something-new", "Tools"],
    ["/lab/something-new", "Strategy Lab"],
  ];

  it.each(ROWS_1)("%s, an unknown part, falls back to the name of its group: %s", (path, title) => {
    expect(screenName(path)).toEqual({ title });
  });

  it("says so when the page does not exist", () => {
    expect(screenName("/nowhere")).toEqual({ title: "Page not found" });
  });

  it("does not throw on a broken address piece", () => {
    expect(screenName("/stock/%E0%A4%A").title).toBe("%E0%A4%A");
  });
});

describe("a path piece that is also the name of something built in", () => {
  const PATHS = ["/settings/constructor", "/tools/__proto__", "/constructor", "/lab/toString"];

  it.each(PATHS)("%s does not break the bar", (path) => {
    expect(typeof screenName(path).title).toBe("string");
  });
});
