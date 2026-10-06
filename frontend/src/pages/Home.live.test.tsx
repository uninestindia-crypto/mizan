import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderApp, routeApi } from "../components/agents/testHarness";
import { api } from "../lib/api";
import { Home } from "./Home";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const STATUS = {
  settings: { onboarding_complete: true, theme: "system" },
  index: { ready: true, latest_session: "2026-10-05", job: { state: "IDLE" } },
  download: { state: "IDLE" },
  data_folder: { scan: "IDLE" },
  lab_runs: 0,
};
const WATCH = [
  { symbol: "TCS", name: "Tata Consultancy", close: 3400, chg_1d: 0.01, spark: [1, 2, 3] },
  { symbol: "INFY", name: "Infosys", close: 1500, chg_1d: -0.02, spark: [3, 2, 1] },
];
const QUOTES_URL = "GET /api/v2/live/quotes?symbols=TCS,INFY";
const OFF = "Add an Upstox key in Settings, then Accounts and keys.";

function engine(quotes: unknown) {
  routeApi({
    "GET /api/v2/status": STATUS,
    "GET /api/v2/watchlist": WATCH,
    "GET /api/v2/paper/orders": { books: [], pending: 0 },
    "GET /api/v2/paper/mine": [],
    "GET /api/v2/paper/books": [],
    [QUOTES_URL]: quotes,
  });
}

const row = (symbol: string) => screen.getByText(symbol).closest("a") as HTMLElement;

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("live prices on the Home watchlist", () => {
  it("adds a labelled live price to each row, beside the end-of-day price, from one request", async () => {
    const when = "2026-10-06T10:15:00+05:30";
    const live = { last_price: 3501.5, change_pct: 0.5, label: "LIVE", as_of: when, source: "Upstox", message: null };
    const closed = { ...live, last_price: 1499, change_pct: -0.1, label: "LAST_CLOSE" };
    engine({ connected: true, message: null, quotes: { TCS: live, INFY: closed } });
    renderApp(<Home />);
    expect(await screen.findByText("₹3,501.50")).toBeInTheDocument();
    expect(within(row("TCS")).getByText("Live")).toBeInTheDocument();
    expect(within(row("INFY")).getByText("Last close")).toBeInTheDocument();
    expect(within(row("TCS")).getByText("₹3,400.00")).toBeInTheDocument();
    const asked = vi.mocked(api).mock.calls.filter(([path]) => String(path).startsWith("/api/v2/live/quotes"));
    expect(asked).toHaveLength(1);
  });

  it("keeps the end-of-day prices as before and says once how to connect, when live prices are off", async () => {
    engine({ connected: false, message: OFF, quotes: {} });
    renderApp(<Home />);
    expect(await screen.findByText(OFF)).toBeInTheDocument();
    expect(screen.getAllByText(OFF)).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Open Accounts and keys" })).toHaveAttribute("href", "/settings/accounts");
    expect(within(row("TCS")).getByText("₹3,400.00")).toBeInTheDocument();
    expect(within(row("INFY")).getByText("₹1,500.00")).toBeInTheDocument();
    expect(screen.queryByText("Live")).toBeNull();
  });

  it("keeps working when the live price answer never comes", async () => {
    engine(() => {
      throw new Error("offline");
    });
    renderApp(<Home />);
    expect(await screen.findByText("Tata Consultancy")).toBeInTheDocument();
    expect(within(row("TCS")).getByText("₹3,400.00")).toBeInTheDocument();
    expect(screen.queryByText("Open Accounts and keys")).toBeNull();
  });
});
