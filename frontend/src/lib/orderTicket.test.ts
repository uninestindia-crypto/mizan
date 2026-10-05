import { describe, expect, it } from "vitest";
import { buildTicket, ticketToCsv, ticketToText } from "./orderTicket";
import type { PaperQueuedOrder } from "./types";

const orders: PaperQueuedOrder[] = [
  { side: "BUY", symbol: "ADANIENSOL", quantity: 64, reference_price: 1541.9 },
  { side: "BUY", symbol: "HFCL", quantity: 436, reference_price: 228.01 },
  { side: "SELL", symbol: "WELCORP", quantity: 43, reference_price: 2311.9 },
];

describe("scaling a book's orders to your own account", () => {
  it("reproduces the book exactly at the same account size", () => {
    const ticket = buildTicket(orders, 1_000_000, 1_000_000);
    expect(ticket.rows.map((r) => r.yourQuantity)).toEqual([64, 436, 43]);
    expect(ticket.tooSmall).toEqual([]);
    expect(ticket.factor).toBe(1);
  });

  it("rounds down so a copy never spends more than it was given", () => {
    const ticket = buildTicket(orders, 1_000_000, 250_000);
    expect(ticket.rows.map((r) => [r.symbol, r.yourQuantity])).toEqual([
      ["ADANIENSOL", 16],
      ["HFCL", 109],
      ["WELCORP", 10],
    ]);
    expect(ticket.buyValue).toBeLessThanOrEqual(250_000);
  });

  it("reports an order that rounds to nothing instead of dropping it silently", () => {
    const ticket = buildTicket(orders, 1_000_000, 20_000);
    expect(ticket.tooSmall.map((o) => o.symbol)).toContain("WELCORP");
    expect(ticket.rows.every((r) => r.yourQuantity >= 1)).toBe(true);
  });

  it("totals buys and sells separately and skips orders with no price", () => {
    const ticket = buildTicket(
      [...orders, { side: "BUY", symbol: "NOPRICE", quantity: 10, reference_price: null }],
      1_000_000,
      1_000_000,
    );
    expect(ticket.buyValue).toBeCloseTo(64 * 1541.9 + 436 * 228.01, 2);
    expect(ticket.sellValue).toBeCloseTo(43 * 2311.9, 2);
    expect(ticket.rows.find((r) => r.symbol === "NOPRICE")?.value).toBeNull();
  });

  it("produces no orders for a zero, negative or non-finite account size", () => {
    for (const bad of [0, -5, Number.NaN, Number.POSITIVE_INFINITY]) {
      const ticket = buildTicket(orders, 1_000_000, bad);
      expect(ticket.rows).toEqual([]);
      expect(ticket.tooSmall).toHaveLength(3);
    }
    expect(buildTicket(orders, 0, 1_000_000).rows).toEqual([]);
  });
});

describe("exporting the orders", () => {
  const rows = buildTicket(orders, 1_000_000, 1_000_000).rows;

  it("writes a header and one CRLF line per order", () => {
    const csv = ticketToCsv(rows, "2026-10-05");
    const lines = csv.trimEnd().split("\r\n");
    expect(lines[0]).toBe("Side,Exchange,Symbol,Quantity,Reference price (INR),Approx value (INR),Decided at close of");
    expect(lines[1]).toBe("BUY,NSE,ADANIENSOL,64,1541.90,98681.60,2026-10-05");
    expect(lines).toHaveLength(4);
  });

  it("leaves the price empty rather than writing a made-up one", () => {
    const csv = ticketToCsv(
      buildTicket([{ side: "BUY", symbol: "X", quantity: 1, reference_price: null }], 1, 1).rows,
      null,
    );
    expect(csv.split("\r\n")[1]).toBe("BUY,NSE,X,1,,,");
  });

  it("stops a spreadsheet reading a cell as a formula and quotes awkward cells", () => {
    const csv = ticketToCsv(
      buildTicket([{ side: "BUY", symbol: '=HYPERLINK("x")', quantity: 1, reference_price: 1 }], 1, 1).rows,
      null,
    );
    expect(csv.split("\r\n")[1]).toBe(`BUY,NSE,"'=HYPERLINK(""x"")",1,1.00,1.00,`);
  });

  it("writes plain text a person can paste into a message", () => {
    const text = ticketToText(rows, "2026-10-05");
    expect(text.split("\n")).toEqual([
      "Orders decided at the close of 2026-10-05",
      "BUY 64 ADANIENSOL NSE @ ~1541.90",
      "BUY 436 HFCL NSE @ ~228.01",
      "SELL 43 WELCORP NSE @ ~2311.90",
    ]);
  });
});
