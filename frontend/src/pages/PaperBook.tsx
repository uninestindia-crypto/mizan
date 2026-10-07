import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { EquityChart, type EquitySeries } from "../components/charts";
import { DataGate } from "../components/common";
import { PaperBookNote } from "../components/mode/PaperBookNote";
import { ShariahBadge } from "../components/mode/ShariahBadge";
import { useModeLabels } from "../components/mode/useModeLabels";
import { OrderTicket } from "../components/OrderTicket";
import { PaperPositionsCard } from "../components/PaperPositions";
import { PlacementTrackingCard } from "../components/PlacementTrackingCard";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  EmptyState,
  PageHeader,
  Skeleton,
  Stat,
} from "../components/ui";
import { errorMessage } from "../lib/api";
import { date, inr, inrCompact, int, pct, tone } from "../lib/format";
import { usePaperBook, useStopPaperBook } from "../lib/queries";
import type { PaperBookDetail, PaperStatus } from "../lib/types";

const STATUS_LABEL: Record<PaperStatus, string> = {
  WAITING: "waiting for the next session",
  RUNNING: "running",
  STOPPED: "stopped",
  ATTENTION: "needs attention",
};

function statusTone(status: PaperStatus): "up" | "warn" | "neutral" {
  if (status === "RUNNING") return "up";
  if (status === "WAITING" || status === "ATTENTION") return "warn";
  return "neutral";
}

export default function PaperBook() {
  return (
    <DataGate>
      <PaperBookPage />
    </DataGate>
  );
}

function PaperBookPage() {
  const { id = "" } = useParams();
  const bookQuery = usePaperBook(id);
  const stopMutation = useStopPaperBook();
  const [confirmStop, setConfirmStop] = useState(false);

  if (bookQuery.isPending) return <Skeleton className="h-[600px]" />;
  if (bookQuery.isError || !bookQuery.data) {
    return (
      <EmptyState
        title="This paper book does not exist"
        action={
          <Link to="/paper">
            <Button variant="secondary">Back to paper trading</Button>
          </Link>
        }
      />
    );
  }

  const book: PaperBookDetail = bookQuery.data;

  const header = (
    <PageHeader
      title={
        <div className="flex flex-wrap items-center gap-2.5">
          <span>{book.name}</span>
          <Badge tone={statusTone(book.status)}>{STATUS_LABEL[book.status]}</Badge>
        </div>
      }
      subtitle={
        <>
          {book.template.name} · started {date(book.start_session)}
          {book.last_session ? ` · valued ${date(book.last_session)}` : ""}
        </>
      }
      actions={
        book.status !== "STOPPED" && !confirmStop ? (
          <Button variant="secondary" onClick={() => setConfirmStop(true)}>
            Stop this book
          </Button>
        ) : undefined
      }
    />
  );

  if (book.error) {
    return (
      <div className="space-y-5">
        <Link to="/paper" className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> Paper trading
        </Link>
        {header}
        <Callout tone="danger">{book.error}</Callout>
      </div>
    );
  }

  return (
    <PaperBookDetailView
      book={book}
      confirmStop={confirmStop}
      setConfirmStop={setConfirmStop}
      stopMutation={stopMutation}
      header={header}
    />
  );
}

function PaperBookDetailView({
  book,
  confirmStop,
  setConfirmStop,
  stopMutation,
  header,
}: {
  book: PaperBookDetail;
  confirmStop: boolean;
  setConfirmStop: (v: boolean) => void;
  stopMutation: ReturnType<typeof useStopPaperBook>;
  header: ReactNode;
}) {
  const series = useMemo<EquitySeries[]>(() => {
    return [
      {
        label: "This book",
        color: "brand",
        points: book.curve.map((c) => ({ time: c[0], value: c[1] })),
      },
      {
        label: "NIFTY (NIFTYBEES)",
        color: "muted",
        dashed: true,
        points: book.curve.map((c) => ({ time: c[0], value: c[2] })),
      },
    ];
  }, [book.curve]);

  const labels = useModeLabels(book.trades.map((t) => t.symbol));
  const targetWhat =
    book.scope.kind === "stocks"
      ? (book.scope.symbols ?? []).join(", ") || "None"
      : book.scope.universe_label ?? book.scope.universe ?? "A whole list";

  return (
    <div className="space-y-5">
      <Link to="/paper" className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Paper trading
      </Link>
      {header}

      {confirmStop && (
        <Callout
          tone="warn"
          action={
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="danger"
                loading={stopMutation.isPending}
                onClick={() => {
                  stopMutation.mutate(book.id, {
                    onSuccess: () => setConfirmStop(false),
                  });
                }}
              >
                Stop book
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={stopMutation.isPending}
                onClick={() => setConfirmStop(false)}
              >
                Keep running
              </Button>
            </div>
          }
        >
          Stopping freezes this book at its latest value. It cannot be restarted or deleted.
        </Callout>
      )}

      {stopMutation.isError && (
        <Callout tone="danger">
          {errorMessage(stopMutation.error)}
        </Callout>
      )}

      {book.attention.map((item, i) => (
        <Callout key={i} tone="warn" title="Read this first">
          {item}
        </Callout>
      ))}

      {book.reading && (
        <Callout tone="info" title={book.reading.title}>
          {book.reading.body}
        </Callout>
      )}

      {/* Stats row */}
      <Card>
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
          <Stat
            label="Value"
            value={inrCompact(book.equity)}
            sub={`Started with ${inrCompact(book.capital)}`}
          />
          <Stat
            label="Return"
            value={pct(book.return, 2)}
            tone={tone(book.return)}
          />
          <Stat
            label="Versus NIFTY"
            value={pct(book.excess, 2)}
            tone={tone(book.excess)}
            sub={`NIFTY ${pct(book.benchmark_return, 2)}`}
          />
          <Stat
            label="Cash"
            value={inrCompact(book.cash)}
          />
          <Stat
            label="Charges paid"
            value={inr(book.charges)}
            sub={`plus ${inr(book.slippage)} slippage`}
          />
        </div>
      </Card>

      {/* Card: Growth of your money */}
      <Card>
        <CardHeader title="Growth of your money" />
        {book.curve.length < 2 ? (
          <p className="text-sm text-ink-3">The chart appears after the first full session.</p>
        ) : (
          <EquityChart series={series} />
        )}
      </Card>

      {/* Card: Tomorrow's orders, made safe to copy by hand */}
      <OrderTicket
        orders={book.orders}
        queued={book.queued}
        bookName={book.name}
        bookCapital={book.capital}
        slippageBps={book.slippage_bps}
        reading={book.reading}
        bookId={book.id}
        placements={book.placements}
      />

      <PlacementTrackingCard tracking={book.tracking} />

      <PaperPositionsCard positions={book.positions} bookName={book.name} />

      {/* Card: Trades so far */}
      <Card>
        <CardHeader title="Trades so far" />
        {book.trades.length > 0 && <PaperBookNote labels={labels} className="mb-3" />}
        {book.trades.length === 0 ? (
          <p className="text-sm text-ink-3">No trades yet. The first orders fill at the next session's open.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Side</th>
                  <th className="px-3 py-2 text-left">Stock</th>
                  <th className="px-3 py-2 text-right">Shares</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">Charges</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {book.trades.map((t, i) => (
                  <tr key={`${t.symbol}-${t.date}-${t.side}-${i}`}>
                    <td className="num px-3 py-2 text-ink-2">{date(t.date)}</td>
                    <td className="px-3 py-2">
                      <Badge tone={t.side === "BUY" ? "up" : "down"}>{t.side}</Badge>
                    </td>
                    <td className="px-3 py-2 font-medium text-ink">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <Link to={`/stock/${t.symbol}`} className="hover:underline">
                          {t.symbol}
                        </Link>
                        <ShariahBadge compact symbol={t.symbol} status={labels.statusOf(t.symbol)} />
                      </div>
                    </td>
                    <td className="num px-3 py-2 text-right text-ink-2">{int(t.quantity)}</td>
                    <td className="num px-3 py-2 text-right text-ink-2">{inr(t.price)}</td>
                    <td className="num px-3 py-2 text-right text-ink-2">{inr(t.fee)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Card: How this book works */}
      <Card>
        <CardHeader title="How this book works" />
        <ul className="space-y-2.5 text-[13.5px] text-ink-2">
          <li className="flex gap-2">
            <span className="text-ink-3">•</span>
            <span>Decisions at each close.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-ink-3">•</span>
            <span>Fills at the next open.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-ink-3">•</span>
            <span>Exact NSE charges plus {book.slippage_bps} basis points of slippage.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-ink-3">•</span>
            <span>
              Prices move forward as new market data arrives. QuantOS updates it after each close, or you can{" "}
              <Link to="/settings/data" className="font-medium text-brand hover:underline">
                update it now
              </Link>
              .
            </span>
          </li>
          <li className="flex gap-2">
            <span className="text-ink-3">•</span>
            <span>Never places a real order.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-ink-3">•</span>
            <span>
              What it trades:{" "}
              <span className="font-medium text-ink">{targetWhat}</span>
            </span>
          </li>
          {Object.keys(book.params).length > 0 && (
            <li className="flex gap-2">
              <span className="text-ink-3">•</span>
              <span>
                Settings:{" "}
                <span className="font-medium text-ink">
                  {Object.entries(book.params)
                    .map(([k, v]) => `${k}: ${typeof v === "boolean" ? (v ? "Yes" : "No") : v}`)
                    .join(" · ")}
                </span>
              </span>
            </li>
          )}
        </ul>
      </Card>
    </div>
  );
}
