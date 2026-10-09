import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { dateTime } from "../lib/format";
import { callsTo, deferred, renderApp, routeApi } from "./agents/testHarness";
import { BrokerAccountCard } from "./BrokerAccountCard";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const FETCHED = "2026-10-06T10:30:00+05:30";
const SNAPSHOT_URL = "GET /api/v2/broker/snapshot";
const REFRESH_URL = "POST /api/v2/broker/refresh";

const TCS = {
  symbol: "TCS",
  exchange: "NSE",
  isin: null,
  quantity: 10,
  t1_quantity: 0,
  average_price: 3400,
  last_price: 3500.5,
  close_price: 3480,
  value: 35005,
  invested: 34000,
  pnl: 1005,
  pnl_pct: 2.96,
  today: 205,
  weight_pct: 54.02,
};
const INFY = { ...TCS, symbol: "INFY", quantity: 20, average_price: 1500, last_price: 1490, value: 29800, invested: 30000, pnl: -200, pnl_pct: -0.67, today: -100, weight_pct: 45.98, t1_quantity: 3 };

const FIGURES = {
  broker: "upstox",
  connected: true,
  view_only: true,
  label: "From your Upstox account. View only.",
  fetched_at: FETCHED,
  freshness: "UP_TO_DATE",
  message: null,
  totals: { value: 64805, invested: 64000, pnl: 805, pnl_pct: 1.26, today: 105, arriving_value: 4470, arriving_note: "Bought recently, arriving in your demat (3 shares)." },
  cash: { available: 12000.5, in_use: 3000 },
  holdings: [TCS, INFY],
  positions: [{ symbol: "INFY", exchange: "NSE", product: "Intraday", quantity: -5, closed: false, average_price: 1500, last_price: 1490, pnl: 50, realised: 0, unrealised: 50 }],
  warnings: ["TCS is 54% of your holdings (above 25%)."],
  skipped: { holdings: 0, positions: 0 },
  notes: [],
};
const NOTHING = { ...FIGURES, connected: false, fetched_at: null, freshness: "NONE", totals: null, cash: null, holdings: [], positions: [], warnings: [], message: "To see your Upstox account here, open Settings, then Broker view, and follow the three steps." };

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("Portfolio, the Upstox account card", () => {
  it("before anything is connected, shows the engine's message and a link to the one place that fixes it", async () => {
    routeApi({ [SNAPSHOT_URL]: NOTHING });
    renderApp(<BrokerAccountCard />);
    expect(await screen.findByText(/follow the three steps/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Broker view" })).toHaveAttribute("href", "/settings/broker");
    expect(screen.queryByText("Value of holdings")).toBeNull();
  });

  it("shows the account with the time it was fetched, in more than one place, and says it is view only", async () => {
    routeApi({ [SNAPSHOT_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    expect(await screen.findByText("From your Upstox account")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`View only · Updated ${dateTime(FETCHED).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`))).toBeInTheDocument();
    expect(screen.getAllByText(dateTime(FETCHED)).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Up to date").length).toBeGreaterThan(0);
    expect(screen.getByText("₹64,805")).toBeInTheDocument();
    expect(screen.getByText("₹12,001")).toBeInTheDocument();
  });

  it("lists each holding with its quantity, price, value, gain and share, and the recently bought shares apart", async () => {
    routeApi({ [SNAPSHOT_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    const table = await screen.findByRole("table", { name: "Holdings in your Upstox account" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]!).getByText("TCS")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("₹35,005")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("54.0%")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("3 arriving")).toBeInTheDocument();
    expect(screen.getByText("Bought recently, arriving in your demat (3 shares).")).toBeInTheDocument();
  });

  it("lists open positions in words and the concentration warning", async () => {
    routeApi({ [SNAPSHOT_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    const table = await screen.findByRole("table", { name: "Open positions in your Upstox account" });
    expect(within(table).getByText("Intraday")).toBeInTheDocument();
    expect(screen.getByText("TCS is 54% of your holdings (above 25%).")).toBeInTheDocument();
  });

  it("announces rows that could not be read", async () => {
    routeApi({ [SNAPSHOT_URL]: { ...FIGURES, skipped: { holdings: 1, positions: 0 }, notes: ["1 holding could not be read and was not shown."] } });
    renderApp(<BrokerAccountCard />);
    expect(await screen.findByText("1 holding could not be read and was not shown.")).toBeInTheDocument();
  });

  it("after the sign-in ends, keeps the figures with their time and names the click, without asking Upstox", async () => {
    const ended = { ...FIGURES, connected: false, freshness: "OLDER", message: "Your Upstox sign-in has ended for today (Upstox ends it at 3:30 am). Open Settings, then Broker view, and click Connect Upstox." };
    routeApi({ [SNAPSHOT_URL]: ended });
    renderApp(<BrokerAccountCard />);
    expect(await screen.findByText(/Your Upstox sign-in has ended for today/)).toBeInTheDocument();
    expect(screen.getAllByText("Older").length).toBeGreaterThan(0);
    expect(screen.getAllByText(dateTime(FETCHED)).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
    expect(callsTo("POST", "/api/v2/broker/refresh")).toHaveLength(0);
  });

  it("refreshes once by itself when the figures are old and the sign-in is still good", async () => {
    routeApi({ [SNAPSHOT_URL]: { ...FIGURES, freshness: "OLDER" }, [REFRESH_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    await waitFor(() => expect(callsTo("POST", "/api/v2/broker/refresh")).toHaveLength(1));
    expect(await screen.findAllByText("Up to date")).not.toHaveLength(0);
    expect(callsTo("POST", "/api/v2/broker/refresh")).toHaveLength(1);
  });

  it("does not refresh when the figures are already up to date", async () => {
    routeApi({ [SNAPSHOT_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    await screen.findByText("From your Upstox account");
    expect(callsTo("POST", "/api/v2/broker/refresh")).toHaveLength(0);
  });

  it("refreshes when asked", async () => {
    routeApi({ [SNAPSHOT_URL]: FIGURES, [REFRESH_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    fireEvent.click(await screen.findByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/broker/refresh")).toHaveLength(1));
  });

  it("while the first figures are being fetched after connecting, says so instead of 'not connected'", async () => {
    const gate = deferred<unknown>();
    routeApi({ [SNAPSHOT_URL]: { ...NOTHING, connected: true, message: null }, [REFRESH_URL]: () => gate.promise });
    renderApp(<BrokerAccountCard />);
    expect(await screen.findByText("Fetching your account from Upstox…")).toBeInTheDocument();
    expect(screen.queryByText("Not connected")).toBeNull();
    gate.resolve(FIGURES);
    expect(await screen.findByText("Value of holdings")).toBeInTheDocument();
  });

  it("has no button that could trade", async () => {
    routeApi({ [SNAPSHOT_URL]: FIGURES });
    renderApp(<BrokerAccountCard />);
    await screen.findByText("From your Upstox account");
    const names = screen.getAllByRole("button").map((b) => b.textContent ?? "");
    expect(names.filter((name) => /\b(buy|sell|place|exit|convert|order|trade|square)\b/i.test(name))).toEqual([]);
  });

  it("shows a calm message if the figures cannot load", async () => {
    vi.mocked(api).mockRejectedValue(new Error("offline"));
    renderApp(<BrokerAccountCard />);
    expect(await screen.findByText("Your broker account could not load")).toBeInTheDocument();
  });
});
