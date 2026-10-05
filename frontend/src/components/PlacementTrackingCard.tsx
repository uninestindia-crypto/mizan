import { DASH, date, inr, inrSigned, int, num } from "../lib/format";
import type { PlacementTracking, TrackingRow } from "../lib/types";
import { Badge, Card, CardHeader, Stat } from "./ui";

function stateLabel(row: TrackingRow): string {
  if (row.status === "SKIPPED") return "Skipped";
  if (row.state === "WAITING") return "Waiting for the paper fill";
  if (row.state === "NO_FILL") return "No paper fill to compare";
  return row.worse_bps === null ? "No price noted" : row.worse_bps > 0 ? "Worse than paper" : "Better than paper";
}

const bps = (value: number | null) => (value === null ? DASH : `${value > 0 ? "+" : value < 0 ? "−" : ""}${num(Math.abs(value), 1)} bps`);

/**
 * How your hand-copied orders compared with what the paper book did with the same orders.
 *
 * Only prices you typed are compared, and the sign convention is the one a person reads: positive
 * means you paid more, or sold for less, than the paper book.
 */
export function PlacementTrackingCard({ tracking }: { tracking: PlacementTracking }) {
  if (tracking.rows.length === 0) return null;
  return (
    <Card>
      <CardHeader
        title="How your copy compares"
        subtitle="Only the orders and prices you noted. Positive means you paid more, or sold for less, than the paper book."
      />
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Stat label="Placed" value={int(tracking.placed)} sub={`${int(tracking.skipped)} skipped`} />
        <Stat label="With a price noted" value={int(tracking.compared)} sub={tracking.waiting > 0 ? `${int(tracking.waiting)} waiting for the paper fill` : undefined} />
        <Stat
          label="Average difference"
          value={bps(tracking.mean_worse_bps)}
          tone={tracking.mean_worse_bps === null || tracking.mean_worse_bps === 0 ? "flat" : tracking.mean_worse_bps > 0 ? "down" : "up"}
        />
        <Stat
          label="What it cost you"
          value={tracking.total_cost === null ? DASH : inrSigned(-tracking.total_cost)}
          tone={tracking.total_cost === null || tracking.total_cost === 0 ? "flat" : tracking.total_cost > 0 ? "down" : "up"}
          sub="against the paper fills"
        />
      </div>
      {tracking.unrecorded > 0 && (
        <p className="mt-3 text-[12.5px] text-ink-3">
          {int(tracking.unrecorded)} order{tracking.unrecorded === 1 ? "" : "s"} the book traded on days you recorded {tracking.unrecorded === 1 ? "has" : "have"} no note, so
          {tracking.unrecorded === 1 ? " it is" : " they are"} not in these figures.
        </p>
      )}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <caption className="sr-only">Your recorded orders against the paper fills</caption>
          <thead>
            <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
              <th scope="col" className="px-3 py-2 text-left">Decided</th>
              <th scope="col" className="px-3 py-2 text-left">Order</th>
              <th scope="col" className="px-3 py-2 text-right">Your shares</th>
              <th scope="col" className="px-3 py-2 text-right">Your price</th>
              <th scope="col" className="px-3 py-2 text-right">Paper price</th>
              <th scope="col" className="px-3 py-2 text-right">Difference</th>
              <th scope="col" className="px-3 py-2 text-left">Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {tracking.rows.map((row) => (
              <tr key={`${row.as_of}-${row.symbol}-${row.side}`}>
                <td className="px-3 py-2 text-ink-2">{date(row.as_of)}</td>
                <td className="px-3 py-2 font-medium text-ink">
                  <Badge tone={row.side === "BUY" ? "up" : "down"}>{row.side}</Badge> {row.symbol}
                </td>
                <td className="num px-3 py-2 text-right text-ink-2">{row.status === "PLACED" ? int(row.quantity) : DASH}</td>
                <td className="num px-3 py-2 text-right text-ink-2">{row.price !== null ? inr(row.price) : DASH}</td>
                <td className="num px-3 py-2 text-right text-ink-2">{row.paper_price !== null ? inr(row.paper_price) : DASH}</td>
                <td className="num px-3 py-2 text-right text-ink-2">{bps(row.worse_bps)}</td>
                <td className="px-3 py-2 text-[12.5px] text-ink-3">{stateLabel(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
