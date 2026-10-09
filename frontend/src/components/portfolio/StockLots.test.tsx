import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Portfolio from "../../pages/Portfolio";
import { api } from "../../lib/api";
import { POSITIONS_LOTS } from "../fundamentals/fundamentalsFixtures";
import { ADVICE } from "../fundamentals/fundamentalsKit";
import { forgetHiddenChoices } from "../mode/hiddenChoice";
import { ACCOUNT_LINES, EVERYTHING, engine, renderAt } from "./portfolioKit";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const NOTE = "Holding periods are shown as facts. Check current tax rules or ask an adviser.";
const WITH_LOTS = { ...EVERYTHING, positions: POSITIONS_LOTS };
const ONE_ACCOUNT = { ...WITH_LOTS, accounts: [ACCOUNT_LINES[0]] };

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
  localStorage.clear();
});
afterEach(cleanup);

async function openTcs(answer: unknown) {
  engine({ "GET /api/v2/portfolio": answer });
  renderAt(<Portfolio />);
  fireEvent.click(await screen.findByRole("button", { name: "Show which accounts hold TCS" }));
  return within(screen.getByRole("list", { name: "Purchases of TCS" }));
}

describe("the purchases under a stock", () => {
  it("lists each purchase, oldest first, with the day and the shares", async () => {
    const lots = await openTcs(WITH_LOTS);
    const items = lots.getAllByRole("listitem").map((li) => li.textContent);
    expect(items[0]).toContain("5 shares bought 29 Feb 2024 in Asha's Zerodha");
    expect(items[1]).toContain("10 shares bought 1 Aug 2025 in My account");
    expect(items[2]).toContain("4 shares bought 9 Oct 2026 in Asha's Zerodha");
  });

  it("says how many days each has been held", async () => {
    const lots = await openTcs(WITH_LOTS);
    expect(lots.getByText(/Held for 953 days/)).toBeInTheDocument();
    expect(lots.getByText(/Held for 0 days/)).toBeInTheDocument();
  });

  it("says a purchase held longer than 12 months is held more than 12 months", async () => {
    const lots = await openTcs(WITH_LOTS);
    expect(lots.getAllByText(/held more than 12 months/)).toHaveLength(2);
  });

  it("says from which date a newer purchase counts as more than 12 months", async () => {
    const lots = await openTcs(WITH_LOTS);
    expect(lots.getByText(/counts as more than 12 months from 9 Oct 2027/)).toBeInTheDocument();
  });

  it("shows the engine's sentence about holding periods exactly as sent", async () => {
    await openTcs(WITH_LOTS);
    expect(screen.getByText(NOTE)).toBeInTheDocument();
  });

  it("says nothing about tax amounts or rates of its own", async () => {
    const lots = await openTcs(WITH_LOTS);
    const text = lots.getAllByRole("listitem").map((li) => li.textContent).join(" ");
    expect(text).not.toMatch(/tax|rate|%|₹/i);
    expect(text).not.toMatch(ADVICE);
  });

  it("opens for someone with one account too, to show the purchases but no list of accounts", async () => {
    const lots = await openTcs(ONE_ACCOUNT);
    expect(lots.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.queryByRole("list", { name: "Accounts holding TCS" })).toBeNull();
    expect(lots.queryByText(/ in My account/)).toBeNull();
  });
});

describe("a stock with no purchases listed", () => {
  it("does not open for someone with one account", async () => {
    engine({ "GET /api/v2/portfolio": { ...EVERYTHING, accounts: [ACCOUNT_LINES[0]] } });
    renderAt(<Portfolio />);
    await screen.findByRole("table", { name: "Holdings by stock" });
    expect(screen.queryByRole("button", { name: /which accounts hold/ })).toBeNull();
  });
});
