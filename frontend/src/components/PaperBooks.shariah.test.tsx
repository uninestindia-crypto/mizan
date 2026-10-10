import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import type { OrdersFreshness, PaperPosition, PaperQueuedOrder } from "../lib/types";
import { routeApi } from "./agents/testHarness";
import {
  COMPLIANT_ROW,
  NON_COMPLIANT_ROW,
  NOT_SCREENED_ROW,
  renderPage,
  statuses,
  statusFor,
  statusUrl,
} from "./mode/modeKit";
import { OrderTicket } from "./OrderTicket";
import { PaperPositionsCard } from "./PaperPositions";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const BASE = {
  quantity: 10,
  average_price: 3000,
  last_close: 3100,
  market_value: 31000,
  unrealized_pnl: 1000,
  weight: 0.4,
};
const POSITIONS: PaperPosition[] = [
  { ...BASE, symbol: "TCS" },
  { ...BASE, symbol: "INFY" },
  { ...BASE, symbol: "ITC" },
];
const CURRENT: OrdersFreshness = {
  state: "CURRENT",
  as_of: "2026-10-06",
  expected_session: "2026-10-07",
  sessions_missed: 0,
  message: "",
};
const QUEUED: PaperQueuedOrder[] = [
  { side: "BUY", symbol: "TCS", quantity: 10, reference_price: 3100 },
  { side: "SELL", symbol: "INFY", quantity: 5, reference_price: 1450 },
];
const TICKET = {
  orders: CURRENT,
  queued: QUEUED,
  bookName: "XS Monthly",
  bookCapital: 1000000,
  slippageBps: 5,
  bookId: "b1",
  placements: [],
};
const MIXED = { TCS: COMPLIANT_ROW, INFY: NON_COMPLIANT_ROW, ITC: NOT_SCREENED_ROW };
const SENTENCE = "The book keeps them because it follows its own rule; QuantOS shows you the status so you can decide.";

function engine(shariah: boolean, symbols: string[], answer: unknown) {
  routeApi({ "GET /api/v2/status": statusFor(shariah), [statusUrl(...symbols)]: answer });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("a paper book's holdings in Shariah mode", () => {
  it("keeps every holding, labels each one, and says plainly how many are not compliant", async () => {
    engine(true, ["INFY", "ITC", "TCS"], statuses(MIXED));
    renderPage(<PaperPositionsCard positions={POSITIONS} bookName="XS Monthly" />);
    expect(await screen.findByText(/1 of these stocks is not Shariah-compliant\./)).toBeInTheDocument();
    expect(screen.getByText(/1 has not been screened yet\./)).toBeInTheDocument();
    expect(screen.getByText(SENTENCE, { exact: false })).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    const held = rows.map((r) => within(r).getByRole("link", { name: /^(TCS|INFY|ITC)$/ }).textContent);
    expect(held).toEqual(["TCS", "INFY", "ITC"]);
    expect(within(rows[0]!).getByText("Compliant")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("Not compliant")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("Not screened")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show them/ })).toBeNull();
  });

  it("says nothing extra when every holding is compliant", async () => {
    engine(true, ["INFY", "TCS"], statuses({ TCS: COMPLIANT_ROW, INFY: COMPLIANT_ROW }));
    renderPage(<PaperPositionsCard positions={POSITIONS.slice(0, 2)} bookName="XS Monthly" />);
    await waitFor(() => expect(screen.getAllByText("Compliant")).toHaveLength(2));
    expect(screen.queryByTestId("paper-book-shariah-note")).toBeNull();
  });

  it("still lists every holding, as not screened, when the results cannot be had", async () => {
    engine(true, ["INFY", "ITC", "TCS"], () => {
      throw new ApiError("HTTP_404", "Not Found", 404);
    });
    renderPage(<PaperPositionsCard positions={POSITIONS} bookName="XS Monthly" />);
    const note = await screen.findByTestId("paper-book-shariah-note");
    expect(note).toHaveTextContent("Shariah status is not available right now.");
    expect(screen.getAllByRole("row")).toHaveLength(4);
    expect(screen.getAllByText("Not screened")).toHaveLength(3);
  });
});

describe("a paper book's queued orders in Shariah mode", () => {
  it("keeps every order, labels each stock, and puts the sentence above the table", async () => {
    engine(true, ["INFY", "TCS"], statuses({ TCS: COMPLIANT_ROW, INFY: NON_COMPLIANT_ROW }));
    renderPage(<OrderTicket {...TICKET} />);
    const note = await screen.findByTestId("paper-book-shariah-note");
    const table = screen.getByRole("table");
    expect(note).toHaveTextContent("1 of these stocks is not Shariah-compliant.");
    expect(note.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(table).getAllByRole("button", { name: /^Record / })).toHaveLength(2);
    expect(within(table).getByText("Not compliant")).toBeInTheDocument();
    expect(within(table).getByText("Compliant")).toBeInTheDocument();
  });

  it("can still note a placement for a stock that is not compliant", async () => {
    engine(true, ["INFY", "TCS"], statuses({ TCS: COMPLIANT_ROW, INFY: NON_COMPLIANT_ROW }));
    renderPage(<OrderTicket {...TICKET} />);
    await screen.findByTestId("paper-book-shariah-note");
    fireEvent.click(screen.getByRole("button", { name: "Record sell INFY" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});

describe("a paper book in Institutional mode", () => {
  it("shows no label and no sentence, and asks nothing", async () => {
    engine(false, [], {});
    renderPage(<PaperPositionsCard positions={POSITIONS} bookName="XS Monthly" />);
    await screen.findByRole("link", { name: "TCS" });
    await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalled());
    expect(screen.queryByText("Compliant")).toBeNull();
    expect(screen.queryByTestId("paper-book-shariah-note")).toBeNull();
    expect(vi.mocked(api).mock.calls.filter(([p]) => String(p).includes("/shariah/status"))).toHaveLength(0);
  });
});
