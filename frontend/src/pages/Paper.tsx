import { Info } from "lucide-react";
import { Link } from "react-router";
import { Illustration } from "../components/common";
import { Badge, Button, Callout, Card, CardHeader, Delta, EmptyState, PageHeader, Skeleton, Stat } from "../components/ui";
import { date, dateTime, inr, inrCompact, inrSigned, int, pct, tone } from "../lib/format";
import { usePaperBooks } from "../lib/queries";
import type { PaperBook } from "../lib/types";

export default function Paper() {
  const books = usePaperBooks();
  return (
    <>
      <PageHeader
        title="Paper trading"
        subtitle="Strategies following real prices with virtual money, shown read-only. It is the safest way to find out if an idea survives the real market."
      />
      <Callout tone="info" className="mb-5" title="How to read these numbers">
        A paper book's profit or loss is mostly what the market did, minus charges. A few weeks of results cannot show that a model has skill. QuantOS shows
        these books read-only; it never changes what they trade.
      </Callout>
      {books.isPending ? (
        <Skeleton className="h-64" />
      ) : (books.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            art={<Illustration name="paper-trading" className="size-44" />}
            title="No paper books yet"
            body="A paper book follows a strategy day by day on real prices with virtual money. QuantOS cannot start one from this app yet: they are started in the research workspace and appear here once they exist. Until then, the Strategy Lab is where you can try an idea on past prices without risking anything."
            action={
              <Link to="/lab">
                <Button variant="secondary">Open the Strategy Lab</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="space-y-5">
          {(books.data ?? []).map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      )}
    </>
  );
}

function BookCard({ book }: { book: PaperBook }) {
  const waiting = book.status === "WAITING";
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-ink">{book.name}</h2>
            <Badge tone={book.status === "RUNNING" || book.status === "COMPLETED" ? "up" : waiting ? "warn" : "neutral"}>{book.status.toLowerCase()}</Badge>
          </div>
          <p className="mt-0.5 text-[13px] text-ink-3">
            {book.started ? `Started ${date(book.started)}` : ""}
            {book.asof ? ` · valued ${book.asof.length > 10 ? dateTime(book.asof) : date(book.asof)}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">
          <Info className="size-3.5" aria-hidden />
          {book.label}
        </div>
      </div>
      {waiting || book.message ? (
        <p className="mt-4 text-sm text-ink-2">{book.message}</p>
      ) : (
        <>
          <div className="mt-5 grid grid-cols-2 gap-6 md:grid-cols-4">
            <Stat label="Value" value={inrCompact(book.equity)} sub={`Started with ${inrCompact(book.capital)}`} />
            <Stat label="Return" value={pct(book.return, 2)} tone={tone(book.return)} />
            <Stat label="Cash" value={inrCompact(book.cash)} />
            <Stat label="Positions" value={int(book.position_count ?? 0)} sub={book.closed_count !== undefined ? `${int(book.closed_count)} closed` : undefined} />
          </div>
          {book.halt_reason && (
            <Callout tone="warn" className="mt-4" title="Stopped">
              {book.halt_reason}
            </Callout>
          )}
          {(book.positions ?? []).length > 0 && (
            <div className="mt-5 overflow-x-auto">
              <CardHeader title="Largest positions" subtitle="Marked at the latest close in the market data" className="mb-2" />
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                    <th className="px-3 py-2 text-left">Stock</th>
                    <th className="px-3 py-2 text-left">Entered</th>
                    <th className="px-3 py-2 text-right">Shares</th>
                    <th className="px-3 py-2 text-right">Cost</th>
                    <th className="px-3 py-2 text-right">Value</th>
                    <th className="px-3 py-2 text-right">Unrealised</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {(book.positions ?? []).map((p) => (
                    <tr key={p.symbol}>
                      <td className="px-3 py-2 font-medium text-ink">
                        <Link to={`/stock/${p.symbol}`} className="hover:underline">
                          {p.symbol}
                        </Link>
                      </td>
                      <td className="num px-3 py-2 text-ink-2">{date(p.entry_date)}</td>
                      <td className="num px-3 py-2 text-right text-ink-2">{int(p.shares)}</td>
                      <td className="num px-3 py-2 text-right text-ink-2">{inr(p.entry_value, 0)}</td>
                      <td className="num px-3 py-2 text-right text-ink-2">{inr(p.market_value, 0)}</td>
                      <td className="px-3 py-2 text-right">
                        <Delta value={p.unrealized}>{inrSigned(p.unrealized)}</Delta>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
