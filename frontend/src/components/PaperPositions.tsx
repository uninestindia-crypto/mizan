import { Link } from "react-router";
import { inr, inrSigned, int, pct } from "../lib/format";
import { paperBookPickNote } from "../lib/picks";
import type { PaperPosition } from "../lib/types";
import { PickSecondOpinion } from "./copilot/PickSecondOpinion";
import { Card, CardHeader, Delta } from "./ui";

const HEAD = "px-3 py-2";

const HEAD_ROW = "border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3";
const COLUMNS: Array<[string, boolean]> = [
  ["Stock", false],
  ["Shares", true],
  ["Average price", true],
  ["Last close", true],
  ["Value", true],
  ["Share of book", true],
  ["Unrealised", true],
  ["Check", true],
];

/** What a paper book holds today, each stock with a button to get an independent second opinion on it. */
export function PaperPositionsCard({ positions, bookName }: { positions: PaperPosition[]; bookName: string }) {
  return (
    <Card>
      <CardHeader title="What it holds" />
      {positions.length === 0 ? (
        <p className="text-sm text-ink-3">It holds no shares yet.</p>
      ) : (
        <PositionsTable positions={positions} bookName={bookName} />
      )}
    </Card>
  );
}

function PositionsTable({ positions, bookName }: { positions: PaperPosition[]; bookName: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className={HEAD_ROW}>
            {COLUMNS.map(([label, right]) => (
              <th key={label} className={`${HEAD} ${right ? "text-right" : "text-left"}`}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {positions.map((p) => (
            <PositionRow key={p.symbol} position={p} bookName={bookName} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PositionRow({ position: p, bookName }: { position: PaperPosition; bookName: string }) {
  return (
    <tr>
      <td className="px-3 py-2 font-medium text-ink">
        <Link to={`/stock/${p.symbol}`} className="hover:underline">
          {p.symbol}
        </Link>
      </td>
      <td className="num px-3 py-2 text-right text-ink-2">{int(p.quantity)}</td>
      <td className="num px-3 py-2 text-right text-ink-2">{inr(p.average_price)}</td>
      <td className="num px-3 py-2 text-right text-ink-2">{inr(p.last_close)}</td>
      <td className="num px-3 py-2 text-right text-ink-2">{inr(p.market_value, 0)}</td>
      <td className="num px-3 py-2 text-right text-ink-2">{pct(p.weight, 1, false)}</td>
      <td className="px-3 py-2 text-right">
        <Delta value={p.unrealized_pnl} strong>
          {inrSigned(p.unrealized_pnl)}
        </Delta>
      </td>
      <td className="px-3 py-2 text-right">
        <PickSecondOpinion symbol={p.symbol} note={paperBookPickNote(bookName, p.symbol, "holding")} />
      </td>
    </tr>
  );
}
