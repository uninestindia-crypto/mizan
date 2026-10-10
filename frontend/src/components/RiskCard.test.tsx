import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { renderApp, routeApi } from "./agents/testHarness";
import { RiskCard } from "./RiskCard";
import { TooltipProvider } from "./ui";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const NOTE = "Based on how these holdings moved day to day over the sessions shown. It describes the past and is not a forecast: a calm year says little about a bad one.";
const PORTFOLIO = "GET /api/v2/portfolio/risk";
const BROKER = "GET /api/v2/broker/risk";

const RISK = {
  available: true,
  message: null,
  window: { sessions: 252, from: "2025-10-01", to: "2026-10-06", days_left_out: 0 },
  volatility_pct: 18.4,
  effective_bets: 2.3,
  diversification: { holdings: 5, average_correlation: 0.42 },
  shrinkage: 0.21,
  holdings: [
    { symbol: "TCS", money_pct: 40, risk_pct: 52.5, volatility_pct: 24.1 },
    { symbol: "INFY", money_pct: 35, risk_pct: 30, volatility_pct: 22 },
    { symbol: "ITC", money_pct: 25, risk_pct: 17.5, volatility_pct: 17 },
  ],
  left_out: [],
  note: NOTE,
};
const NOTHING = { ...RISK, available: false, message: "There are no holdings to look at yet.", window: null, volatility_pct: null, effective_bets: null, diversification: null, shrinkage: null, holdings: [] };

function show(source: "portfolio" | "broker" = "portfolio", account = "all") {
  return renderApp(
    <TooltipProvider>
      <RiskCard source={source} account={account} />
    </TooltipProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("How your holdings move together", () => {
  it("says the typical yearly swing, how many independent holdings the portfolio behaves like, and how closely they move", async () => {
    routeApi({ [PORTFOLIO]: RISK });
    show();
    expect(await screen.findByText("18.4%")).toBeInTheDocument();
    expect(screen.getByText("2.3 holdings")).toBeInTheDocument();
    expect(screen.getByText("of the 5 you own")).toBeInTheDocument();
    expect(screen.getByText("0.42")).toBeInTheDocument();
    expect(screen.getByText("1 is in lockstep, 0 is unrelated")).toBeInTheDocument();
  });

  it("puts each holding's share of the money next to its share of the risk and calls out the one with more risk than size", async () => {
    routeApi({ [PORTFOLIO]: RISK });
    show();
    const table = await screen.findByRole("table", { name: "Each holding's share of the money and of the risk" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(4);
    expect(within(rows[1]!).getByText("TCS")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("40.0%")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("52.5%")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("More risk than its size")).toBeInTheDocument();
    expect(within(rows[2]!).queryByText("More risk than its size")).toBeNull();
  });

  it("always says it describes the past, and gives the window in words", async () => {
    routeApi({ [PORTFOLIO]: RISK });
    show();
    expect(await screen.findByText(NOTE)).toBeInTheDocument();
    expect(screen.getByText(/The last 252 sessions/)).toBeInTheDocument();
    expect(screen.getByText(/describes the past, not a forecast/)).toBeInTheDocument();
  });

  it("names what was left out and why, and the days left out for a known break in the data", async () => {
    routeApi({
      [PORTFOLIO]: {
        ...RISK,
        window: { ...RISK.window, days_left_out: 2 },
        left_out: [{ symbol: "NEWLY", reason: "Only 21 sessions of price history, so it was left out." }],
      },
    });
    show();
    expect(await screen.findByText(/Left out: NEWLY\. Only 21 sessions of price history/)).toBeInTheDocument();
    expect(screen.getByText(/2 days with a known break in the price data were left out/)).toBeInTheDocument();
  });

  it("with a single holding it does not show the closeness figure", async () => {
    routeApi({ [PORTFOLIO]: { ...RISK, effective_bets: 1, diversification: { holdings: 1, average_correlation: null }, holdings: [{ symbol: "TCS", money_pct: 100, risk_pct: 100, volatility_pct: 24 }] } });
    show();
    expect(await screen.findByText("1 holding")).toBeInTheDocument();
    expect(screen.queryByText("How closely they move together")).toBeNull();
  });

  it("when there is nothing to describe, shows the engine's message and no numbers", async () => {
    routeApi({ [PORTFOLIO]: NOTHING });
    show();
    expect(await screen.findByText("There are no holdings to look at yet.")).toBeInTheDocument();
    expect(screen.queryByText("Typical yearly swing")).toBeNull();
  });

  it("asks the broker's route when it is the broker's holdings", async () => {
    routeApi({ [BROKER]: RISK });
    show("broker");
    expect(await screen.findByText("18.4%")).toBeInTheDocument();
    const asked = vi.mocked(api).mock.calls.map(([path]) => String(path));
    expect(asked).toEqual(["/api/v2/broker/risk"]);
  });

  it("asks for one account's holdings when one account is in view, and the plain address for all of them", async () => {
    routeApi({ "GET /api/v2/portfolio/risk?account=3": RISK });
    show("portfolio", "3");
    expect(await screen.findByText("18.4%")).toBeInTheDocument();
    expect(vi.mocked(api).mock.calls.map(([path]) => String(path))).toEqual(["/api/v2/portfolio/risk?account=3"]);
  });

  it("shows a calm message if the answer cannot load, not an error page", async () => {
    vi.mocked(api).mockRejectedValue(new Error("offline"));
    show();
    expect(await screen.findByText("How your holdings move together could not load")).toBeInTheDocument();
  });

  it("uses no developer's word and no advice", async () => {
    routeApi({ [PORTFOLIO]: RISK });
    const { container } = show();
    await screen.findByText("18.4%");
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\b(volatility|correlation|covariance|API|JSON|token|backend)\b/i);
    expect(text).not.toMatch(/\b(buy|sell|should|recommend)\b/i);
  });
});
