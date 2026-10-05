// "Tomorrow's orders" turned into something a person can place by hand in their own broker app.
// QuantOS never connects to a broker: this only does arithmetic and formatting.

import type { PaperQueuedOrder } from "./types";

export interface TicketRow extends PaperQueuedOrder {
  /** Shares to trade for the person's own account size, whole shares only. */
  yourQuantity: number;
  /** yourQuantity × reference price, or null when there is no price. */
  value: number | null;
}

export interface Ticket {
  rows: TicketRow[];
  /** Orders that round down to zero shares at this account size, so are left out. */
  tooSmall: PaperQueuedOrder[];
  buyValue: number;
  sellValue: number;
  /** Account size ÷ the book's starting money. */
  factor: number;
}

/**
 * Scale the book's orders to the person's own account size.
 *
 * The book trades with `bookCapital`; someone copying it with a different amount takes the same
 * proportions. Shares are rounded **down** so a copy never spends more than the person chose, and an
 * order that rounds to nothing is reported rather than silently dropped.
 */
export function buildTicket(
  orders: readonly PaperQueuedOrder[],
  bookCapital: number,
  yourCapital: number,
): Ticket {
  const factor =
    Number.isFinite(bookCapital) && bookCapital > 0 && Number.isFinite(yourCapital) && yourCapital > 0
      ? yourCapital / bookCapital
      : 0;
  const rows: TicketRow[] = [];
  const tooSmall: PaperQueuedOrder[] = [];
  let buyValue = 0;
  let sellValue = 0;
  for (const order of orders) {
    // Equal capital must reproduce the book's quantity exactly, whatever floating point does.
    const scaled = factor === 1 ? order.quantity : Math.floor(order.quantity * factor + 1e-9);
    if (scaled < 1) {
      tooSmall.push(order);
      continue;
    }
    const value = order.reference_price === null ? null : scaled * order.reference_price;
    if (value !== null) {
      if (order.side === "BUY") buyValue += value;
      else sellValue += value;
    }
    rows.push({ ...order, yourQuantity: scaled, value });
  }
  return { rows, tooSmall, buyValue, sellValue, factor };
}

// A cell that begins with one of these is read by a spreadsheet as a formula.
const FORMULA_START = /^[=+\-@\t\r]/;

function csvCell(value: string | number): string {
  let text = String(value);
  if (FORMULA_START.test(text)) text = `'${text}`;
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** One order per line, in the order the book decided them; opens cleanly in Excel or Sheets. */
export function ticketToCsv(rows: readonly TicketRow[], asOf: string | null): string {
  const header = ["Side", "Exchange", "Symbol", "Quantity", "Reference price (INR)", "Approx value (INR)", "Decided at close of"];
  const lines = rows.map((row) =>
    [
      row.side,
      "NSE",
      row.symbol,
      row.yourQuantity,
      row.reference_price === null ? "" : row.reference_price.toFixed(2),
      row.value === null ? "" : row.value.toFixed(2),
      asOf ?? "",
    ]
      .map(csvCell)
      .join(","),
  );
  return [header.map(csvCell).join(","), ...lines].join("\r\n") + "\r\n";
}

/** The same orders as plain lines for a message or a note: `BUY 64 ADANIENSOL @ ~1541.90`. */
export function ticketToText(rows: readonly TicketRow[], asOf: string | null): string {
  const lines = rows.map(
    (row) =>
      `${row.side} ${row.yourQuantity} ${row.symbol} NSE` +
      (row.reference_price === null ? "" : ` @ ~${row.reference_price.toFixed(2)}`),
  );
  return [`Orders decided at the close of ${asOf ?? "unknown"}`, ...lines].join("\n");
}

export type PlacementFields =
  | { ok: true; quantity: number | null; price: string | null }
  | { ok: false; error: string };

/**
 * Turn what was typed in the "I placed this" form into what is sent.
 *
 * Shares must be a whole number of at least one; a price is optional, but a price that is typed must
 * be a positive amount. A skipped order carries neither, so a stale number cannot ride along.
 */
export function parsePlacementFields(status: "PLACED" | "SKIPPED", shares: string, price: string): PlacementFields {
  if (status === "SKIPPED") return { ok: true, quantity: null, price: null };
  const sharesText = shares.trim();
  if (!/^\d+$/.test(sharesText) || Number(sharesText) < 1) {
    return { ok: false, error: "Enter how many shares you placed, as a whole number." };
  }
  const quantity = Number(sharesText);
  if (!Number.isSafeInteger(quantity) || quantity > 100_000_000) return { ok: false, error: "That is too many shares." };
  const priceText = price.trim().replace(/,/g, "");
  if (priceText === "") return { ok: true, quantity, price: null };
  if (!/^\d+(\.\d{1,4})?$/.test(priceText) || Number(priceText) <= 0) {
    return { ok: false, error: "Enter your price as a positive amount, such as 1541.90, or leave it empty." };
  }
  return { ok: true, quantity, price: priceText };
}
