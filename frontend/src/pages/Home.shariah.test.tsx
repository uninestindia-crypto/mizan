import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
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
import { Home } from "./Home";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const WATCH = [
  { symbol: "TCS", name: "Tata Consultancy", close: 3400, chg_1d: 0.01, spark: [1, 2, 3] },
  { symbol: "INFY", name: "Infosys", close: 1500, chg_1d: -0.02, spark: [3, 2, 1] },
];
const MOVER = { close: 100, chg_1d: 0.03 };
const OVERVIEW = {
  latest_session: "2026-10-05",
  benchmark: null,
  breadth: {
    universe: "liquid",
    asof: "2026-10-05",
    count: 1,
    above_200dma: 1,
    above_200dma_pct: 0.5,
    advancers: 1,
    decliners: 1,
    unchanged: 0,
    stale: 0,
  },
  gainers: [{ symbol: "AAA", name: "Alpha", ...MOVER }, { symbol: "BBB", name: "Beta", ...MOVER }],
  losers: [],
};
const QUOTES = { connected: false, message: "Add an Upstox key in Settings, then Accounts and keys.", quotes: {} };

function engine(shariah: boolean) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    "GET /api/v2/watchlist": WATCH,
    "GET /api/v2/market/overview": OVERVIEW,
    "GET /api/v2/portfolio": { holdings: [], totals: null, warnings: [], nifty: null },
    "GET /api/v2/paper/orders": { books: [], pending: 0 },
    "GET /api/v2/paper/mine": [],
    "GET /api/v2/paper/books": [],
    "GET /api/v2/live/quotes?symbols=TCS,INFY": QUOTES,
    [statusUrl("INFY", "TCS")]: statuses({ TCS: COMPLIANT_ROW, INFY: NON_COMPLIANT_ROW }),
    [statusUrl("AAA", "BBB")]: statuses({ AAA: COMPLIANT_ROW, BBB: NON_COMPLIANT_ROW }),
  });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
});
afterEach(cleanup);

async function card(title: string) {
  const heading = await screen.findByRole("heading", { name: title });
  return within(heading.closest("section") as HTMLElement);
}

describe("Home in Shariah mode", () => {
  it("lists only the compliant stocks on the watchlist, with a badge, and says how many are hidden", async () => {
    engine(true);
    renderPage(<Home />);
    const watchlist = await card("Watchlist");
    expect(await watchlist.findByText(/Showing only Shariah-compliant stocks\. 1 hidden\./)).toBeInTheDocument();
    expect(watchlist.getByText("TCS")).toBeInTheDocument();
    expect(watchlist.queryByText("INFY")).toBeNull();
    expect(watchlist.getByText("Compliant")).toBeInTheDocument();
  });

  it("shows the hidden stock, labelled, when asked, and hides it again", async () => {
    engine(true);
    renderPage(<Home />);
    const watchlist = await card("Watchlist");
    fireEvent.click(await watchlist.findByRole("button", { name: "Show them" }));
    expect(watchlist.getByText("INFY")).toBeInTheDocument();
    expect(watchlist.getByText("Not compliant")).toBeInTheDocument();
    fireEvent.click(watchlist.getByRole("button", { name: "Hide them again" }));
    expect(watchlist.queryByText("INFY")).toBeNull();
  });

  it("still asks for live prices for every watched stock, so nothing about the list itself changes", async () => {
    engine(true);
    renderPage(<Home />);
    await (await card("Watchlist")).findByText(/1 hidden/);
    const asked = vi.mocked(api).mock.calls.map(([p]) => String(p));
    expect(asked).toContain("/api/v2/live/quotes?symbols=TCS,INFY");
  });

  it("filters the biggest moves the same way", async () => {
    engine(true);
    renderPage(<Home />);
    const moves = await card("Biggest moves");
    await moves.findByText(/Showing only Shariah-compliant stocks\. 1 hidden\./);
    expect(moves.getByText("AAA")).toBeInTheDocument();
    expect(moves.queryByText("BBB")).toBeNull();
  });

  it("says how many stocks are screened from company filings when the engine can say", async () => {
    engine(true);
    renderPage(<Home />);
    await (await card("Watchlist")).findByText(/1 hidden/);
    const asked = () => vi.mocked(api).mock.calls.map(([path]) => String(path));
    await waitFor(() => expect(asked()).toContain("/api/v2/shariah/filings/coverage"));
  });
});

describe("Home in Institutional mode", () => {
  it("lists every stock and shows no note", async () => {
    engine(false);
    renderPage(<Home />);
    const watchlist = await card("Watchlist");
    expect(await watchlist.findByText("INFY")).toBeInTheDocument();
    expect(watchlist.getByText("TCS")).toBeInTheDocument();
    expect(screen.queryByText(/Showing only Shariah-compliant/)).toBeNull();
    expect(screen.queryByText("Compliant")).toBeNull();
  });
});
