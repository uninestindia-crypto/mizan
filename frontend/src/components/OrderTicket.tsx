import { Check, ClipboardCopy, Download } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Link } from "react-router";
import { buildTicket, ticketToCsv, ticketToText } from "../lib/orderTicket";
import { paperBookPickNote } from "../lib/picks";
import { DASH, date, inr, int } from "../lib/format";
import type { OrdersFreshness, PaperQueuedOrder, Placement } from "../lib/types";
import { PickSecondOpinion } from "./copilot/PickSecondOpinion";
import { PaperBookNote } from "./mode/PaperBookNote";
import { ShariahBadge } from "./mode/ShariahBadge";
import { useModeLabels } from "./mode/useModeLabels";
import { PlacementDialog, type PlacementTarget } from "./PlacementDialog";
import { Badge, Button, Callout, Card, CardHeader, Field, Input } from "./ui";

/** Digits and one dot only: the money the person types is never trusted as a number until cleaned. */
const cleanMoney = (raw: string) => raw.replace(/[^\d.]/g, "").replace(/(\..*)\./g, "$1");

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/**
 * Tomorrow's orders, made safe to copy by hand into your own broker.
 *
 * Two rules drive the layout. First, an out-of-date order list must never look like a current one,
 * so when the engine says STALE the quantities are hidden behind an explicit "show anyway" and no
 * copy or export is offered. Second, QuantOS never connects to a broker: it hands over numbers and
 * the person places the orders themselves.
 */
function pickNoteFor(bookName: string, row: { symbol: string; side: "BUY" | "SELL" }): string {
  return paperBookPickNote(bookName, row.symbol, row.side === "BUY" ? "queued_buy" : "queued_sell");
}

export function OrderTicket({
  orders,
  queued,
  bookName,
  bookCapital,
  slippageBps,
  reading,
  bookId,
  placements,
}: {
  bookId: string;
  /** What you have already noted for this book's orders. */
  placements: Placement[];
  orders: OrdersFreshness;
  queued: PaperQueuedOrder[];
  bookName: string;
  bookCapital: number;
  slippageBps: number;
  /** The book's own verdict on whether its record shows anything yet. */
  reading?: { level: "TOO_EARLY" | "SOME_HISTORY"; title: string; body: string } | null;
}) {
  const moneyId = useId();
  const [mine, setMine] = useState(() => String(Math.round(bookCapital)));
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [recording, setRecording] = useState<PlacementTarget | null>(null);
  const yourCapital = Number(mine);
  const ticket = useMemo(() => buildTicket(queued, bookCapital, yourCapital), [queued, bookCapital, yourCapital]);
  const labels = useModeLabels(queued.map((o) => o.symbol));
  const asOf = orders.as_of;
  const noteFor = (symbol: string, side: "BUY" | "SELL") =>
    placements.find((p) => p.as_of === asOf && p.symbol === symbol && p.side === side) ?? null;

  const subtitle =
    orders.state === "CURRENT" && asOf
      ? `Decided at the close of ${date(asOf)} using only prices up to it. They fill at the next session's open.`
      : "Decided at a close using only prices up to it; they fill at the next session's open.";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(ticketToText(ticket.rows, asOf));
      setCopied(true);
      setCopyFailed(false);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopyFailed(true);
    }
  };

  const fileName = `${bookName.replace(/[^\w-]+/g, "-").replace(/^-+|-+$/g, "") || "orders"}-${asOf ?? "orders"}.csv`;

  return (
    <Card>
      <CardHeader
        title="Tomorrow's orders"
        subtitle={subtitle}
        action={
          orders.state === "CURRENT" ? (
            <Badge tone="up">Current</Badge>
          ) : orders.state === "STALE" ? (
            <Badge tone="down">Out of date</Badge>
          ) : undefined
        }
      />

      {orders.state === "STALE" && (
        <Callout
          tone="danger"
          title="Do not place these orders"
          action={
            <Link to="/settings/data" className="text-[13px] font-medium text-brand hover:underline">
              Update market data
            </Link>
          }
        >
          {orders.message}
        </Callout>
      )}
      {(orders.state === "STOPPED" || orders.state === "UNKNOWN") && (
        <p className="text-sm text-ink-3">{orders.message}</p>
      )}

      {orders.state === "CURRENT" && queued.length === 0 && (
        <p className="text-sm text-ink-3">No orders are waiting. At the last close the rule had nothing to change.</p>
      )}

      {orders.state === "CURRENT" && queued.length > 0 && (
        <div className="space-y-4">
          {reading?.level === "TOO_EARLY" && (
            <Callout tone="warn" title="Too early to copy with real money">
              {reading.body} Copying this book now with real money is a bet, not a test.
            </Callout>
          )}
          <div className="grid gap-4 sm:grid-cols-[minmax(0,16rem)_1fr] sm:items-end">
            <Field
              label="Your account size"
              htmlFor={moneyId}
              hint={
                ticket.factor === 1
                  ? "Same as the book, so the quantities are the book's own."
                  : ticket.factor > 0
                    ? `${ticket.factor.toFixed(3)}× the book. Shares are rounded down.`
                    : "Enter the amount you would copy this with."
              }
            >
              <Input
                id={moneyId}
                prefix="₹"
                inputMode="decimal"
                value={mine}
                onChange={(e) => setMine(cleanMoney(e.target.value))}
              />
            </Field>
            <div className="flex flex-wrap gap-2 sm:justify-end">
              <Button
                variant="secondary"
                icon={copied ? <Check className="size-4" aria-hidden /> : <ClipboardCopy className="size-4" aria-hidden />}
                onClick={() => void copy()}
                disabled={ticket.rows.length === 0}
              >
                {copied ? "Copied" : "Copy orders"}
              </Button>
              <Button
                variant="secondary"
                icon={<Download className="size-4" aria-hidden />}
                onClick={() => download(fileName, ticketToCsv(ticket.rows, asOf))}
                disabled={ticket.rows.length === 0}
              >
                Download CSV
              </Button>
            </div>
          </div>
          {copyFailed && (
            <p role="status" className="text-[12.5px] text-down">
              Your browser would not allow copying. Use Download CSV instead.
            </p>
          )}

          <PaperBookNote labels={labels} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <caption className="sr-only">Orders to place, scaled to your account size</caption>
              <thead>
                <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                  <th scope="col" className="px-3 py-2 text-left">Side</th>
                  <th scope="col" className="px-3 py-2 text-left">Stock</th>
                  <th scope="col" className="px-3 py-2 text-right">Your shares</th>
                  <th scope="col" className="px-3 py-2 text-right">Book shares</th>
                  <th scope="col" className="px-3 py-2 text-right">About price</th>
                  <th scope="col" className="px-3 py-2 text-right">About value</th>
                  <th scope="col" className="px-3 py-2 text-right">Your record</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {ticket.rows.map((row, i) => (
                  <tr key={`${row.symbol}-${row.side}-${i}`}>
                    <td className="px-3 py-2">
                      <Badge tone={row.side === "BUY" ? "up" : "down"}>{row.side}</Badge>
                    </td>
                    <td className="px-3 py-2 font-medium text-ink">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link to={`/stock/${row.symbol}`} className="hover:underline">
                          {row.symbol}
                        </Link>
                        <ShariahBadge compact symbol={row.symbol} status={labels.statusOf(row.symbol)} />
                        <PickSecondOpinion symbol={row.symbol} note={pickNoteFor(bookName, row)} />
                      </div>
                    </td>
                    <td className="num px-3 py-2 text-right font-semibold text-ink">{int(row.yourQuantity)}</td>
                    <td className="num px-3 py-2 text-right text-ink-3">{int(row.quantity)}</td>
                    <td className="num px-3 py-2 text-right text-ink-2">
                      {row.reference_price !== null ? inr(row.reference_price) : DASH}
                    </td>
                    <td className="num px-3 py-2 text-right text-ink-2">{row.value !== null ? inr(row.value, 0) : DASH}</td>
                    <td className="px-3 py-2 text-right">
                      {(() => {
                        const note = noteFor(row.symbol, row.side);
                        return (
                          <Button
                            size="sm"
                            variant={note ? "ghost" : "secondary"}
                            aria-label={`${note ? "Edit" : "Record"} ${row.side.toLowerCase()} ${row.symbol}`}
                            onClick={() =>
                              asOf &&
                              setRecording({
                                bookId,
                                asOf,
                                symbol: row.symbol,
                                side: row.side,
                                suggestedShares: row.yourQuantity,
                                existing: note,
                              })
                            }
                          >
                            {note
                              ? note.status === "SKIPPED"
                                ? "Skipped"
                                : `Placed ${int(note.quantity)}${note.price != null ? ` @ ${inr(note.price)}` : ""}`
                              : "Record"}
                          </Button>
                        );
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-line text-[12.5px] text-ink-3">
                  <td colSpan={5} className="px-3 py-2 text-right">
                    Buys {ticket.sellValue > 0 ? "and sells " : ""}total
                  </td>
                  <td className="num px-3 py-2 text-right text-ink-2">
                    {inr(ticket.buyValue, 0)}
                    {ticket.sellValue > 0 ? ` / ${inr(ticket.sellValue, 0)}` : ""}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>

          {ticket.tooSmall.length > 0 && (
            <p className="text-[12.5px] text-ink-3">
              Too small to buy a whole share at this account size, so left out:{" "}
              {ticket.tooSmall.map((o) => `${o.side} ${o.symbol}`).join(", ")}.
            </p>
          )}
        </div>
      )}

      {orders.state === "STALE" && queued.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-[13px] font-medium text-ink-3 hover:text-ink">
            Show the {queued.length} out-of-date orders for the record
          </summary>
          <ul className="mt-2 space-y-1 text-ink-3">
            {queued.map((o, i) => (
              <li key={`${o.symbol}-${i}`} className="num">
                {o.side} {int(o.quantity)} {o.symbol} (decided {asOf ? date(asOf) : DASH})
              </li>
            ))}
          </ul>
        </details>
      )}

      <PlacementDialog target={recording} onClose={() => setRecording(null)} />

      <p className="mt-4 border-t border-line pt-3 text-[12.5px] leading-relaxed text-ink-3">
        QuantOS never connects to your broker and places nothing for you. The paper book fills at the next open
        plus {slippageBps} basis points of slippage and exact NSE charges; your own fills will differ. These are the
        orders a paper rule would place. They are not advice.
      </p>
    </Card>
  );
}
