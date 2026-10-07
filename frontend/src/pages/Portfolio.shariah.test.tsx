import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { routeApi } from "../components/agents/testHarness";
import { forgetHiddenChoices } from "../components/mode/hiddenChoice";
import {
  COMPLIANT_ROW,
  NON_COMPLIANT_ROW,
  renderPage,
  statuses,
  statusFor,
  statusUrl,
} from "../components/mode/modeKit";
import { api } from "../lib/api";
import Portfolio from "./Portfolio";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const HOLDING = {
  quantity: 10,
  avg_price: 100,
  buy_date: "2026-01-02",
  note: "",
  cost: 1000,
  close: 120,
  value: 1200,
  pnl: 200,
  pnl_pct: 0.2,
};
const PORTFOLIO = {
  holdings: [
    { id: 1, symbol: "TCS", ...HOLDING },
    { id: 2, symbol: "INFY", ...HOLDING },
  ],
  totals: { value: 2400, cost: 2000, pnl: 400, pnl_pct: 0.2, day_change: 10, exit_charges: 30 },
  warnings: [],
  nifty: null,
};

function engine(shariah: boolean) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    "GET /api/v2/portfolio": PORTFOLIO,
    [statusUrl("INFY", "TCS")]: statuses({ TCS: COMPLIANT_ROW, INFY: NON_COMPLIANT_ROW }),
  });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
});
afterEach(cleanup);

const table = async () => within(await screen.findByRole("table"));

describe("Portfolio holdings in Shariah mode", () => {
  it("lists the compliant holdings, labels them, and says the totals still include the hidden ones", async () => {
    engine(true);
    renderPage(<Portfolio />);
    await screen.findByText(/Showing only Shariah-compliant stocks\. 1 hidden\./);
    const rows = await table();
    expect(rows.getByRole("link", { name: "TCS" })).toBeInTheDocument();
    expect(rows.queryByRole("link", { name: "INFY" })).toBeNull();
    expect(rows.getByRole("link", { name: /Compliant/ })).toHaveAttribute("href", "/stock/TCS#shariah-proof");
    expect(screen.getByText("The totals above still include them.")).toBeInTheDocument();
  });

  it("shows every holding on request, each with its label", async () => {
    engine(true);
    renderPage(<Portfolio />);
    fireEvent.click(await screen.findByRole("button", { name: "Show them" }));
    const rows = await table();
    expect(rows.getByRole("link", { name: "INFY" })).toBeInTheDocument();
    expect(rows.getByRole("link", { name: /Not compliant/ })).toBeInTheDocument();
  });
});

describe("Portfolio holdings in Institutional mode", () => {
  it("lists every holding with no label", async () => {
    engine(false);
    renderPage(<Portfolio />);
    const rows = await table();
    expect(rows.getByRole("link", { name: "INFY" })).toBeInTheDocument();
    expect(rows.getByRole("link", { name: "TCS" })).toBeInTheDocument();
    expect(screen.queryByText("Compliant")).toBeNull();
  });
});
