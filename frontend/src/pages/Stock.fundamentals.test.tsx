import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, routeApi } from "../components/agents/testHarness";
import { COMPANY_FRESH } from "../components/fundamentals/fundamentalsFixtures";
import { renderPage, statusFor } from "../components/mode/modeKit";
import { ACCOUNT_LIST } from "../components/portfolio/portfolioKit";
import { api } from "../lib/api";
import Stock from "./Stock";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});
vi.mock("../components/charts", () => ({ PriceChart: () => null, Sparkline: () => null }));

const PROFILE = {
  info: {
    name: "Example Software",
    is_etf: false,
    first_date: "2016-01-01",
    last_date: "2026-10-05",
    sessions: 2500,
    snapshot: { close: 3400, chg_1d: 0.01, asof: "2026-10-05", high_52w: 4000, low_52w: 3000, turnover_cr: 900 },
  },
  stats: { ret_1m: 0, ret_6m: 0, ret_1y: 0, ret_5y: 0, vol_1y: 0.2, max_drawdown_1y: -0.1, beta_1y: 1 },
  actions: [],
  flags: [],
  in_watchlist: false,
};
const EMPTY_BARS = { dates: [], open: [], high: [], low: [], close: [], volume: [] };
const QUOTES_OFF = { connected: false, message: "Add an Upstox key in Settings.", quotes: {} };

function engine(more: Record<string, unknown> = {}) {
  routeApi({
    "GET /api/v2/status": statusFor(false),
    "GET /api/v2/stocks/TCS": PROFILE,
    "GET /api/v2/market/bars/TCS": EMPTY_BARS,
    "POST /api/v2/tools/costs": { charges: 120, breakeven_move_pct: 0.003 },
    "GET /api/v2/live/quotes?symbols=TCS": QUOTES_OFF,
    "GET /api/v2/fundamentals/TCS": COMPANY_FRESH,
    "GET /api/v2/accounts": ACCOUNT_LIST,
    "POST /api/v2/portfolio/holdings": {},
    ...more,
  });
}

const show = () =>
  renderPage(
    <Routes>
      <Route path="/stock/:symbol" element={<Stock />} />
    </Routes>,
    "/stock/TCS",
  );

beforeEach(() => {
  vi.mocked(api).mockReset();
  localStorage.clear();
});
afterEach(cleanup);

describe("a stock's page", () => {
  it("has a section with the results from the company's own filings", async () => {
    engine();
    show();
    const title = "Results from the company's own filings";
    expect(await screen.findByRole("heading", { level: 2, name: title })).toBeInTheDocument();
    expect(await screen.findByText(COMPANY_FRESH.scorecard.header)).toBeInTheDocument();
  });
});

describe("Add to portfolio on a stock's page", () => {
  const openForm = async () => {
    fireEvent.click(await screen.findByRole("button", { name: "Add to portfolio" }));
    return within(await screen.findByRole("dialog", { name: "Add a holding" }));
  };

  it("offers the accounts, starting on the first one", async () => {
    engine();
    show();
    const form = await openForm();
    expect(await form.findByLabelText("Account")).toHaveValue("1");
    expect(form.getByLabelText("Average price")).toHaveValue("3400");
  });

  it("starts on the account last viewed in the Portfolio", async () => {
    localStorage.setItem("quantos.portfolio.account", "2");
    engine();
    show();
    const form = await openForm();
    expect(await form.findByLabelText("Account")).toHaveValue("2");
  });

  it("keeps the stock fixed: no search and no Change", async () => {
    engine();
    show();
    const form = await openForm();
    await form.findByLabelText("Account");
    expect(form.queryByRole("button", { name: "Change" })).toBeNull();
    expect(form.queryByRole("combobox", { name: /Search/ })).toBeNull();
  });

  it("files the purchase in the account that was picked", async () => {
    engine();
    show();
    const form = await openForm();
    fireEvent.change(await form.findByLabelText("Account"), { target: { value: "3" } });
    fireEvent.change(form.getByLabelText("Quantity"), { target: { value: "5" } });
    fireEvent.click(form.getByRole("button", { name: "Add holding" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/portfolio/holdings")).toHaveLength(1));
    const sent = callsTo("POST", "/api/v2/portfolio/holdings")[0];
    expect(sent).toMatchObject({ symbol: "TCS", quantity: 5, account_id: 3 });
  });
});
