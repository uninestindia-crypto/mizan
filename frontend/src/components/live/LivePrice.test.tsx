import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { type LiveQuote, type LiveQuotes, useLiveQuotes } from "../../lib/live";
import { renderApp, routeApi } from "../agents/testHarness";
import { LiveChip, LiveConnectNote, LivePrice } from "./LivePrice";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const quote = (over: Partial<LiveQuote> = {}): LiveQuote => ({
  last_price: 3500.5,
  change_pct: 0.42,
  label: "LIVE",
  as_of: "2026-10-06T10:15:00+05:30",
  source: "Upstox",
  message: null,
  ...over,
});

const connected = (quotes: Record<string, LiveQuote>): LiveQuotes => ({ connected: true, message: null, quotes });
const OFF = "Add an Upstox key in Settings, then Accounts and keys.";
const notConnected: LiveQuotes = { connected: false, message: OFF, quotes: {} };
const URL_ONE = "GET /api/v2/live/quotes?symbols=TCS";

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("one live price", () => {
  it("shows the price with its label, the change in words, and where and when it came from", async () => {
    routeApi({ [URL_ONE]: connected({ TCS: quote() }) });
    renderApp(<LivePrice symbol="TCS" />);
    expect(await screen.findByText("Live")).toBeInTheDocument();
    expect(screen.getByText("₹3,500.50")).toBeInTheDocument();
    expect(screen.getByText("+0.42%")).toBeInTheDocument();
    expect(screen.getByText("up")).toBeInTheDocument();
    expect(screen.getByText("As of 6 Oct, 10:15 am India time, from Upstox")).toBeInTheDocument();
  });

  it("never shows a price without its plain-word label", async () => {
    for (const [label, words] of [["DELAYED", "Delayed"], ["LAST_CLOSE", "Last close"]] as const) {
      routeApi({ [URL_ONE]: connected({ TCS: quote({ label }) }) });
      const view = renderApp(<LivePrice symbol="TCS" />);
      expect(await screen.findByText(words)).toBeInTheDocument();
      expect(screen.getByText("₹3,500.50")).toBeInTheDocument();
      view.unmount();
    }
  });

  it("says a fall in words as well as with a sign", async () => {
    routeApi({ [URL_ONE]: connected({ TCS: quote({ change_pct: -1.25 }) }) });
    renderApp(<LivePrice symbol="TCS" />);
    expect(await screen.findByText("−1.25%")).toBeInTheDocument();
    expect(screen.getByText("down")).toBeInTheDocument();
  });

  it("shows Not available and the reason, and no price, when there is none", async () => {
    const none = { last_price: null, change_pct: null, as_of: null };
    const unavailable = quote({ ...none, label: "UNAVAILABLE", message: "No price." });
    routeApi({ [URL_ONE]: connected({ TCS: unavailable }) });
    renderApp(<LivePrice symbol="TCS" />);
    expect(await screen.findByText("Not available")).toBeInTheDocument();
    expect(screen.getByText("No price.")).toBeInTheDocument();
    expect(screen.queryByText(/₹/)).toBeNull();
  });

  it("shows Not available when a price comes with a label the app does not know", async () => {
    routeApi({ [URL_ONE]: connected({ TCS: quote({ label: "STALE" as never }) }) });
    renderApp(<LivePrice symbol="TCS" />);
    expect(await screen.findByText("Not available")).toBeInTheDocument();
    expect(screen.queryByText("₹3,500.50")).toBeNull();
  });
});

describe("when live prices are not connected", () => {
  it("shows the message once, with a button to Accounts and keys, and no price", async () => {
    routeApi({ [URL_ONE]: notConnected });
    renderApp(<LivePrice symbol="TCS" />);
    expect(await screen.findByText(OFF)).toBeInTheDocument();
    expect(screen.getAllByText(OFF)).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Open Accounts and keys" })).toHaveAttribute("href", "/settings/accounts");
    expect(screen.queryByText(/₹/)).toBeNull();
  });

  it("still names the next click when the engine sent no words", async () => {
    routeApi({ [URL_ONE]: { connected: false, message: null, quotes: {} } });
    renderApp(<LivePrice symbol="TCS" />);
    expect(await screen.findByText(/Open Settings, then Accounts and keys/)).toBeInTheDocument();
  });

  it("shows nothing at all, and does not break the page, when the engine cannot be reached", async () => {
    routeApi({ [URL_ONE]: () => { throw new Error("offline"); } });
    const { container } = renderApp(<LivePrice symbol="TCS" />);
    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(container.querySelector("[role=status]")).toBeNull();
    expect(screen.queryByText(/₹/)).toBeNull();
  });
});

function Watchlist({ symbols }: { symbols: string[] }) {
  const live = useLiveQuotes(symbols);
  return (
    <div>
      <LiveConnectNote quotes={live.data} />
      {symbols.map((symbol) => (
        <div key={symbol} data-testid={symbol}>
          {symbol}
          <LiveChip symbol={symbol} quotes={live.data} />
        </div>
      ))}
    </div>
  );
}

describe("prices for a whole list", () => {
  it("asks once for the whole list and puts a labelled price on each row", async () => {
    const url = "GET /api/v2/live/quotes?symbols=TCS,INFY";
    routeApi({ [url]: connected({ TCS: quote(), INFY: quote({ label: "LAST_CLOSE", last_price: 1500 }) }) });
    renderApp(<Watchlist symbols={["TCS", "INFY", "tcs"]} />);
    expect(await screen.findByText("₹1,500.00")).toBeInTheDocument();
    expect(vi.mocked(api)).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("TCS")).toHaveTextContent("Live");
    expect(screen.getByTestId("INFY")).toHaveTextContent("Last close");
  });

  it("says the problem once, not once per row, when live prices are not connected", async () => {
    routeApi({ "GET /api/v2/live/quotes?symbols=TCS,INFY": notConnected });
    renderApp(<Watchlist symbols={["TCS", "INFY"]} />);
    expect(await screen.findByText(OFF)).toBeInTheDocument();
    expect(screen.getAllByText(OFF)).toHaveLength(1);
    expect(screen.getByTestId("TCS")).toHaveTextContent(/^TCS$/);
    expect(screen.getByTestId("INFY")).toHaveTextContent(/^INFY$/);
  });

  it("asks nothing for an empty list", async () => {
    routeApi({});
    renderApp(<Watchlist symbols={[]} />);
    await new Promise((done) => setTimeout(done, 50));
    expect(api).not.toHaveBeenCalled();
  });
});
