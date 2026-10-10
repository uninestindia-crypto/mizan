import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, routeApi } from "../components/agents/testHarness";
import {
  COMPLIANT_ROW,
  NON_COMPLIANT_ROW,
  renderPage,
  statuses,
  statusFor,
  statusUrl,
} from "../components/mode/modeKit";
import { PROOF_URL } from "../components/proof/proofKit";
import { rawProof } from "../components/proof/proofFixtures";
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

const QUOTES_OFF = { connected: false, message: "Add an Upstox key in Settings, then Accounts and keys.", quotes: {} };
const EMPTY_BARS = { dates: [], open: [], high: [], low: [], close: [], volume: [] };

function engine(shariah: boolean, row = NON_COMPLIANT_ROW) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    "GET /api/v2/stocks/TCS": PROFILE,
    "GET /api/v2/market/bars/TCS": EMPTY_BARS,
    "POST /api/v2/tools/costs": { charges: 120, breakeven_move_pct: 0.003 },
    "GET /api/v2/live/quotes?symbols=TCS": QUOTES_OFF,
    "POST /api/v2/watchlist": ["TCS"],
    "GET /api/v2/watchlist": [],
    [statusUrl("TCS")]: statuses({ TCS: row }),
    [PROOF_URL]: rawProof("ratio_fail"),
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
});
afterEach(cleanup);

describe("a stock's page in Shariah mode", () => {
  it("opens with the Shariah proof before the chart and the statistics", async () => {
    engine(true);
    show();
    const proof = await screen.findByRole("heading", { level: 2, name: "Shariah screening" });
    const stats = await screen.findByRole("heading", { name: "Statistics" });
    expect(proof.compareDocumentPosition(stats) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(await screen.findByRole("group", { name: "Verdict" })).toHaveTextContent("Not compliant");
  });

  it("still shows the stock, whatever its result", async () => {
    engine(true);
    show();
    expect(await screen.findByRole("heading", { name: "TCS" })).toBeInTheDocument();
    expect(await screen.findByText("₹3,400.00")).toBeInTheDocument();
  });

  it("asks before watching a stock that is not compliant, and watches nothing until the person agrees", async () => {
    engine(true);
    show();
    await screen.findByRole("group", { name: "Verdict" });
    await waitFor(() => expect(callsTo("GET", statusUrl("TCS").slice(4))).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("TCS is not Shariah-compliant (Debt is over the limit). Add it anyway?");
    expect(callsTo("POST", "/api/v2/watchlist")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Add anyway" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/watchlist")).toEqual([{ symbol: "TCS" }]));
  });

  it("watches a compliant stock without asking", async () => {
    engine(true, COMPLIANT_ROW);
    show();
    await screen.findByRole("group", { name: "Verdict" });
    await waitFor(() => expect(callsTo("GET", statusUrl("TCS").slice(4))).toHaveLength(1));
    fireEvent.click(await screen.findByRole("button", { name: "Watch" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/watchlist")).toEqual([{ symbol: "TCS" }]));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("a stock's page in Institutional mode", () => {
  it("has a folded Shariah screening section, and watches without asking", async () => {
    engine(false);
    show();
    expect(await screen.findByRole("button", { name: "Shariah screening" })).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(await screen.findByRole("button", { name: "Watch" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/watchlist")).toEqual([{ symbol: "TCS" }]));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(callsTo("GET", "/api/v2/shariah/stocks/TCS/proof")).toHaveLength(0);
  });
});
