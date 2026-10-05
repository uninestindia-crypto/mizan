import { Info, Plus } from "lucide-react";
import { Link } from "react-router";
import { Sparkline } from "../components/charts";
import { Illustration } from "../components/common";
import { DownloadData } from "../components/DataFolderPicker";
import { Badge, Button, Callout, Card, CardHeader, Delta, EmptyState, PageHeader, Skeleton, Stat } from "../components/ui";
import { date, dateTime, inr, inrCompact, inrSigned, int, pct, tone } from "../lib/format";
import { usePaperBooks, usePaperMine, usePaperUpdates, useStatus } from "../lib/queries";
import type { PaperBook, PaperBookSummary, PaperStatus } from "../lib/types";

const STATUS_LABEL: Record<PaperStatus, string> = {
  WAITING: "Waiting for the next session",
  RUNNING: "Running",
  STOPPED: "Stopped",
  ATTENTION: "Needs attention",
};

function statusTone(status: PaperStatus): "up" | "warn" | "neutral" {
  if (status === "RUNNING") return "up";
  if (status === "WAITING" || status === "ATTENTION") return "warn";
  return "neutral";
}

export default function Paper() {
  const status = useStatus();
  const ready = status.data?.index.ready ?? false;
  const mine = usePaperMine(ready);
  const books = usePaperBooks();
  const myBooks = mine.data ?? [];
  const latest = status.data?.index.latest_session;
  return (
    <>
      <PageHeader
        title="Paper trading"
        subtitle="Follow a strategy rule forward in time with virtual money on real prices. It is the safest way to find out if an idea survives the real market. Nothing here ever places a real order."
        actions={
          ready ? (
            <Link to="/paper/new">
              <Button icon={<Plus className="size-4" aria-hidden />}>Start a paper book</Button>
            </Link>
          ) : undefined
        }
      />
      <Callout tone="info" className="mb-5" title="How to read these numbers">
        A paper book's profit or loss is mostly what the market did, minus charges. A few weeks of results cannot show that a rule has skill. Books use
        prices up to {latest ? date(latest) : "the latest session"}.
      </Callout>
      {ready && <AutoUpdateLine />}
      {ready && <DownloadData prominent={false} />}

      <h2 className="mb-3 mt-6 text-[15px] font-semibold text-ink">Your paper books</h2>
      {!ready ? (
        <Card>
          <EmptyState
            art={<Illustration name="paper-trading" className="size-44" />}
            title="Get market data first"
            body="A paper book needs real prices to follow. Download them in Settings, then start your first book here."
            action={
              <Link to="/settings/data">
                <Button>Get market data</Button>
              </Link>
            }
          />
        </Card>
      ) : mine.isPending ? (
        <Skeleton className="h-40" />
      ) : myBooks.length === 0 ? (
        <Card>
          <EmptyState
            art={<Illustration name="paper-trading" className="size-44" />}
            title="Start your first paper book"
            body="Pick a rule from the Strategy Lab (for example buy and hold, or momentum), choose the stocks and the virtual money, and QuantOS follows it day by day: the orders it would place, what they cost, and how it compares with simply holding NIFTY."
            action={
              <Link to="/paper/new">
                <Button icon={<Plus className="size-4" aria-hidden />}>Start a paper book</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {myBooks.map((book) => (
            <MyBookRow key={book.id} book={book} />
          ))}
        </div>
      )}

      {(books.data ?? []).length > 0 && (
        <>
          <h2 className="mb-1 mt-10 text-[15px] font-semibold text-ink">From your research workspace</h2>
          <p className="mb-3 text-[13px] text-ink-3">Paper books started outside this app, shown read-only.</p>
          <div className="space-y-5">
            {(books.data ?? []).map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

function AutoUpdateLine() {
  const updates = usePaperUpdates();
  const info = updates.data;
  if (!info || info.state === "IDLE") return null;
  const tone = info.state === "CURRENT" ? "up" : info.state === "UPDATING" ? "brand" : "warn";
  const label = { OFF: "Automatic updates off", CANNOT: "Update by hand", UPDATING: "Updating", CURRENT: "Up to date", BEHIND: "Behind", IDLE: "" }[info.state];
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 text-[13px] text-ink-2" role="status">
      <Badge tone={tone}>{label}</Badge>
      <span>{info.message}</span>
    </div>
  );
}

function MyBookRow({ book }: { book: PaperBookSummary }) {
  const what = book.scope.kind === "stocks" ? (book.scope.symbols ?? []).join(", ") : (book.scope.universe_label ?? book.scope.universe ?? "a list");
  return (
    <Link to={`/paper/${book.id}`} className="block rounded-2xl border border-line bg-surface p-4 shadow-[var(--shadow-card)] transition-colors hover:border-line-strong">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-[15px] font-semibold text-ink">{book.name}</span>
            <Badge tone={statusTone(book.status)}>{STATUS_LABEL[book.status]}</Badge>
            {book.attention > 0 && !book.error && <Badge tone="warn">{book.attention} to read</Badge>}
          </div>
          <div className="mt-0.5 truncate text-[12.5px] text-ink-3">
            {book.template} · {what} · started {date(book.start_session)}
            {book.sessions > 0 ? ` · ${int(book.sessions)} sessions` : ""}
          </div>
          {book.error && <div className="mt-1 text-[12.5px] text-down">{book.error}</div>}
        </div>
        {!book.error && (
          <div className="flex items-center gap-6">
            <Sparkline values={book.spark} width={96} height={32} />
            <div className="text-right">
              <div className="num text-[15px] font-semibold text-ink">{inrCompact(book.equity)}</div>
              <div className="text-[12.5px]">
                <Delta value={book.return}>{pct(book.return, 2)}</Delta>
                <span className="text-ink-3"> · NIFTY {pct(book.benchmark_return, 2)}</span>
              </div>
            </div>
            {book.queued > 0 &&
              (book.orders_state === "CURRENT" ? (
                <Badge tone="brand">{book.queued} orders tomorrow</Badge>
              ) : book.orders_state === "STALE" ? (
                <Badge tone="down">Orders out of date</Badge>
              ) : null)}
          </div>
        )}
      </div>
    </Link>
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
