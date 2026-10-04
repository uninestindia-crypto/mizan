import { ArrowLeft, ChevronDown, FileText, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { DrawdownChart, EquityChart, type EquitySeries } from "../components/charts";
import { VerdictBanner } from "../components/common";
import { Badge, Button, Callout, Card, CardHeader, cx, Delta, EmptyState, PageHeader, Segmented, Skeleton, Switch } from "../components/ui";
import { date, dateTime, inr, inrCompact, int, num, pct } from "../lib/format";
import { useLabRun } from "../lib/queries";
import type { LabResult, Performance } from "../lib/types";

export default function LabRun() {
  const { runId = "" } = useParams();
  const run = useLabRun(runId);
  if (run.isPending) return <Skeleton className="h-[600px]" />;
  if (run.isError || !run.data) {
    return (
      <EmptyState
        title="Test not found"
        action={
          <Link to="/lab">
            <Button variant="secondary">Back to the lab</Button>
          </Link>
        }
      />
    );
  }
  return <Result result={run.data} />;
}

function Result({ result }: { result: LabResult }) {
  const [log, setLog] = useState(false);
  const scopeLabel = result.scope.kind === "universe" ? result.scope.universe_label ?? result.scope.universe : (result.scope.requested ?? []).join(", ");
  const series = useMemo<EquitySeries[]>(() => {
    const out: EquitySeries[] = [
      { label: "Strategy", color: "brand", points: result.equity.map((r) => ({ time: r[0], value: r[1] })) },
      { label: "NIFTY", color: "muted", dashed: true, points: result.equity.map((r) => ({ time: r[0], value: r[2] })) },
    ];
    if (result.comparison) out.push({ label: "Whole list", color: "violet", points: result.equity.map((r) => ({ time: r[0], value: r[3] ?? 0 })) });
    return out;
  }, [result]);
  const again = new URLSearchParams({
    params: JSON.stringify(result.params),
    capital: String(result.capital),
    start: result.period.start,
  });
  if (result.scope.kind === "stocks") again.set("symbols", (result.scope.requested ?? []).join(","));
  const rerun = `/lab/new/${result.template.id}?${again.toString()}`;

  return (
    <div className="space-y-5">
      <Link to="/lab" className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Strategy Lab
      </Link>
      <PageHeader
        eyebrow={`Test #${result.verdict.trials} · ${dateTime(result.created_at)}`}
        title={result.template.name}
        subtitle={
          <>
            On {scopeLabel} · {date(result.period.start)} to {date(result.period.end)} · {int(result.period.sessions)} sessions · starting with{" "}
            {inrCompact(result.capital)}
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/paper/new?from=${result.id}`}>
              <Button icon={<FileText className="size-4" aria-hidden />}>Paper trade this</Button>
            </Link>
            <Link to={rerun}>
              <Button variant="secondary" icon={<RotateCcw className="size-4" aria-hidden />}>
                Test again with changes
              </Button>
            </Link>
          </div>
        }
      />
      <VerdictBanner {...result.verdict} />
      {result.scope.kind === "universe" && (
        <Callout tone="warn" title="Read this before trusting the return">
          This stock list holds only companies that are listed and large <em>today</em>. Businesses that failed or shrank are missing, which makes buying rising
          stocks look easier than it really was. That is why the result is judged against owning the whole list, and why QuantOS will not call it proof.
        </Callout>
      )}

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[15px] font-semibold text-ink">Growth of {inrCompact(result.capital)}</h2>
              <Legend comparison={Boolean(result.comparison)} />
            </div>
            <Switch checked={log} onChange={setLog} label="Log scale" />
          </div>
          <EquityChart series={series} log={log} />
          <h3 className="mb-1 mt-5 text-[13px] font-semibold text-ink-2">Drawdown (% below the previous peak)</h3>
          <DrawdownChart series={series} />
        </Card>
        <Card>
          <CardHeader title="Head to head" subtitle="After every charge and slippage" />
          <Comparison result={result} />
        </Card>
      </div>

      {(result.scope.excluded.length > 0 || result.notes.length > 0) && (
        <Card>
          <CardHeader title="Things you should know about this test" />
          <div className="space-y-3">
            {result.notes.map((note) => (
              <Callout key={note} tone="warn">
                {note}
              </Callout>
            ))}
            {result.scope.excluded.length > 0 && (
              <Callout tone="info" title={`${result.scope.excluded.length} stocks left out`}>
                Their price history breaks inside the test period (a demerger or a rights issue whose effect cannot be measured):{" "}
                {result.scope.excluded
                  .slice(0, 12)
                  .map((e) => e.symbol)
                  .join(", ")}
                {result.scope.excluded.length > 12 ? "…" : ""}.
              </Callout>
            )}
          </div>
        </Card>
      )}

      <Trades result={result} />
      <Assumptions items={result.assumptions} />
    </div>
  );
}

function Legend({ comparison }: { comparison: boolean }) {
  return (
    <div className="mt-1 flex flex-wrap gap-4 text-[12.5px] text-ink-3">
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded bg-brand" /> Strategy
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded border-t-2 border-dashed border-ink-3" /> NIFTY (NIFTYBEES)
      </span>
      {comparison && (
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded bg-violet" /> Whole list, equal weight
        </span>
      )}
    </div>
  );
}

const ROWS: { label: string; get: (p: Performance) => number | null; format: (v: number | null) => string; better: "high" | "low" | null }[] = [
  { label: "Total return", get: (p) => p.total_return, format: (v) => pct(v), better: "high" },
  { label: "Per year (CAGR)", get: (p) => p.cagr, format: (v) => pct(v), better: "high" },
  { label: "Worst fall", get: (p) => p.max_drawdown, format: (v) => pct(v), better: "high" },
  { label: "Volatility", get: (p) => p.volatility, format: (v) => pct(v, 0, false), better: "low" },
  { label: "Sharpe ratio", get: (p) => p.sharpe, format: (v) => num(v, 2), better: "high" },
  { label: "Time invested", get: (p) => p.time_invested, format: (v) => pct(v, 0, false), better: null },
  { label: "Trades", get: (p) => p.fills, format: (v) => int(v), better: null },
  { label: "Charges paid", get: (p) => p.charges, format: (v) => inr(v, 0), better: "low" },
  { label: "Final value", get: (p) => p.final_equity, format: (v) => inrCompact(v), better: "high" },
];

function Comparison({ result }: { result: LabResult }) {
  const columns = [
    { key: "strategy", label: "Strategy", perf: result.strategy },
    { key: "nifty", label: "NIFTY", perf: result.benchmark },
    ...(result.comparison ? [{ key: "list", label: "List", perf: result.comparison.performance }] : []),
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[12px] font-semibold uppercase tracking-wide text-ink-3">
            <th className="pb-2 text-left font-semibold">&nbsp;</th>
            {columns.map((c) => (
              <th key={c.key} className="pb-2 pl-4 text-right font-semibold">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {ROWS.map((row) => {
            const values = columns.map((c) => row.get(c.perf));
            const valid = values.filter((v): v is number => v !== null);
            const best = row.better === null || valid.length < 2 ? null : row.better === "high" ? Math.max(...valid) : Math.min(...valid);
            return (
              <tr key={row.label}>
                <td className="py-2.5 pr-3 text-ink-2">{row.label}</td>
                {values.map((v, i) => (
                  <td key={columns[i]!.key} className={cx("num py-2.5 pl-4 text-right", v !== null && v === best ? "font-semibold text-ink" : "text-ink-2")}>
                    {row.format(v)}
                  </td>
                ))}
              </tr>
            );
          })}
          {result.strategy.win_rate !== null && (
            <tr>
              <td className="py-2.5 pr-3 text-ink-2">Winning trades</td>
              <td className="num py-2.5 text-right text-ink-2">{pct(result.strategy.win_rate, 0, false)}</td>
              <td colSpan={columns.length - 1} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Trades({ result }: { result: LabResult }) {
  const [view, setView] = useState<"closed" | "open">("closed");
  const [limit, setLimit] = useState(25);
  const trades = [...result.trades].reverse();
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Trades</h2>
          <p className="mt-0.5 text-[13px] text-ink-3">
            {int(result.trades.length)} completed · {int(result.open_positions.length)} still open at the end
          </p>
        </div>
        <Segmented
          label="Trades"
          size="sm"
          value={view}
          onChange={setView}
          options={[
            { value: "closed", label: "Completed" },
            { value: "open", label: "Open" },
          ]}
        />
      </div>
      <div className="mt-3 overflow-x-auto">
        {view === "closed" ? (
          trades.length === 0 ? (
            <EmptyState title="No completed trades" body="Every position was still open when the test ended." />
          ) : (
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                  <th className="px-5 py-2.5 text-left">Stock</th>
                  <th className="px-3 py-2.5 text-left">Bought</th>
                  <th className="px-3 py-2.5 text-left">Sold</th>
                  <th className="px-3 py-2.5 text-right">Days</th>
                  <th className="px-3 py-2.5 text-right">Buy price</th>
                  <th className="px-3 py-2.5 text-right">Sell price</th>
                  <th className="px-5 py-2.5 text-right">Profit after charges</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {trades.slice(0, limit).map((t, i) => (
                  <tr key={`${t.symbol}-${t.exit_date}-${i}`}>
                    <td className="px-5 py-2.5 font-medium text-ink">
                      <Link to={`/stock/${t.symbol}`} className="hover:underline">
                        {t.symbol}
                      </Link>
                    </td>
                    <td className="num px-3 py-2.5 text-ink-2">{date(t.entry_date)}</td>
                    <td className="num px-3 py-2.5 text-ink-2">{date(t.exit_date)}</td>
                    <td className="num px-3 py-2.5 text-right text-ink-2">{t.sessions}</td>
                    <td className="num px-3 py-2.5 text-right text-ink-2">{num(t.entry_price)}</td>
                    <td className="num px-3 py-2.5 text-right text-ink-2">{num(t.exit_price)}</td>
                    <td className="px-5 py-2.5 text-right">
                      <Delta value={t.pnl} strong>
                        {inr(t.pnl, 0)}
                      </Delta>{" "}
                      <span className="num text-[12px] text-ink-3">{pct(t.return_pct)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : result.open_positions.length === 0 ? (
          <EmptyState title="No open positions" body="Everything had been sold when the test ended." />
        ) : (
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                <th className="px-5 py-2.5 text-left">Stock</th>
                <th className="px-3 py-2.5 text-right">Shares</th>
                <th className="px-3 py-2.5 text-right">Average price</th>
                <th className="px-3 py-2.5 text-right">Last close</th>
                <th className="px-5 py-2.5 text-right">Unrealised</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {result.open_positions.map((p) => (
                <tr key={p.symbol}>
                  <td className="px-5 py-2.5 font-medium text-ink">{p.symbol}</td>
                  <td className="num px-3 py-2.5 text-right text-ink-2">{int(p.quantity)}</td>
                  <td className="num px-3 py-2.5 text-right text-ink-2">{num(p.average_price)}</td>
                  <td className="num px-3 py-2.5 text-right text-ink-2">{num(p.last_close)}</td>
                  <td className="px-5 py-2.5 text-right">
                    <Delta value={p.unrealized_pnl} strong>
                      {inr(p.unrealized_pnl, 0)}
                    </Delta>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {view === "closed" && trades.length > limit && (
          <div className="border-t border-line px-5 py-3">
            <button type="button" onClick={() => setLimit(limit + 50)} className="text-[13px] font-medium text-brand hover:underline">
              Show more ({int(trades.length - limit)} left)
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}

function Assumptions({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center justify-between text-left">
        <span>
          <span className="block text-[15px] font-semibold text-ink">How this was tested</span>
          <span className="block text-[13px] text-ink-3">The exact rules behind every number on this page</span>
        </span>
        <ChevronDown className={cx("size-5 text-ink-3 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <ul className="mt-4 space-y-2.5">
          {items.map((item) => (
            <li key={item} className="flex gap-2.5 text-[13.5px] text-ink-2">
              <Badge tone="neutral" className="mt-0.5 shrink-0">
                ✓
              </Badge>
              {item}
            </li>
          ))}
          <li className="text-[12.5px] text-ink-3">
            Past results do not guarantee future returns. QuantOS is not investment advice and is not registered with SEBI.
          </li>
        </ul>
      )}
    </Card>
  );
}
