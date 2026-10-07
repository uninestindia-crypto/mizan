import { cleanup, screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderApp, routeApi } from "../components/agents/testHarness";
import { TooltipProvider } from "../components/ui";
import { api } from "../lib/api";
import Stock from "./Stock";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});
vi.mock("../components/charts", () => ({ PriceChart: () => null, Sparkline: () => null }));

const STATUS = {
  settings: { onboarding_complete: true, theme: "system" },
  index: { ready: true, latest_session: "2026-10-05", job: { state: "IDLE" } },
  download: { state: "IDLE" },
  data_folder: { scan: "IDLE" },
};
const PROFILE = {
  info: {
    name: "Tata Consultancy",
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
const LIVE_URL = "GET /api/v2/live/quotes?symbols=TCS";
const OFF = "Add an Upstox key in Settings, then Accounts and keys.";

function engine(quotes: unknown) {
  routeApi({
    "GET /api/v2/status": STATUS,
    "GET /api/v2/stocks/TCS": PROFILE,
    "GET /api/v2/market/bars/TCS": { dates: [], open: [], high: [], low: [], close: [], volume: [] },
    "POST /api/v2/tools/costs": { charges: 120, breakeven_move_pct: 0.003 },
    [LIVE_URL]: quotes,
  });
}

const page = (
  <TooltipProvider>
    <Routes>
      <Route path="/stock/:symbol" element={<Stock />} />
    </Routes>
  </TooltipProvider>
);
const show = () => renderApp(page, undefined, "/stock/TCS");

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the live price in the Stock page header", () => {
  it("shows the labelled live price under the end-of-day price, which stays as it was", async () => {
    const when = "2026-10-06T10:15:00+05:30";
    const live = { last_price: 3501.5, change_pct: 0.5, label: "DELAYED", as_of: when, source: "Upstox" };
    engine({ connected: true, message: null, quotes: { TCS: { ...live, message: null } } });
    show();
    expect(await screen.findByText("Delayed")).toBeInTheDocument();
    expect(screen.getByText("₹3,501.50")).toBeInTheDocument();
    expect(screen.getByText("As of 6 Oct, 10:15 am India time, from Upstox")).toBeInTheDocument();
    expect(screen.getByText("₹3,400.00")).toBeInTheDocument();
  });

  it("shows the end-of-day price and one way to connect when live prices are off", async () => {
    engine({ connected: false, message: OFF, quotes: {} });
    show();
    expect(await screen.findByText(OFF)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Accounts and keys" })).toHaveAttribute("href", "/settings/accounts");
    expect(screen.getByText("₹3,400.00")).toBeInTheDocument();
  });
});
