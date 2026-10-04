import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bookmark, BookmarkCheck, FlaskConical, Plus, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { PriceChart, type PriceRange } from "../components/charts";
import { AsOf, DataGate } from "../components/common";
import { HoldingDialog } from "../components/HoldingDialog";
import { Badge, Button, Callout, Card, CardHeader, Delta, EmptyState, Input, Segmented, Skeleton, Stat, Switch } from "../components/ui";
import { ApiError } from "../lib/api";
import { date, inr, int, num, pct, tone } from "../lib/format";
import { tools, useBars, useStock, useWatchlistToggle } from "../lib/queries";

export default function Stock() {
  const { symbol = "" } = useParams();
  return (
    <DataGate>
      <StockPage symbol={symbol.toUpperCase()} />
    </DataGate>
  );
}

function StockPage({ symbol }: { symbol: string }) {
  const stock = useStock(symbol);
  const bars = useBars(symbol);
  const watch = useWatchlistToggle();
  const [range, setRange] = useState<PriceRange>("1Y");
  const [kind, setKind] = useState<"candles" | "line">("candles");
  const [averages, setAverages] = useState(true);
  const [adding, setAdding] = useState(false);

  const info = stock.data?.info;
  const snap = info?.snapshot;
  const stats = stock.data?.stats;
  const breaks = useMemo(
    () => (stock.data?.actions ?? []).filter((a) => a.breaks_history && a.ex_date > (info?.first_date ?? "")),
    [stock.data?.actions, info?.first_date],
  );
  const events = useMemo(
    () => [
      ...breaks.map((a) => ({ date: a.ex_date, label: a.kinds.includes("rights") ? "Rights issue" : "Demerger" })),
      ...(stock.data?.flags ?? []).map((f) => ({ date: f.d, label: "Data break" })),
    ],
    [breaks, stock.data?.flags],
  );

  // After every hook: returning earlier changed the hook count between renders and blanked the page.
  if (stock.isError) {
    const missing = stock.error instanceof ApiError && stock.error.status === 404;
    return (
      <EmptyState
        title={missing ? `${symbol} is not in the market data` : "Could not load this stock"}
        body={missing ? "Check the symbol, or search for the company name." : String(stock.error)}
        action={
          <Link to="/markets">
            <Button variant="secondary">Back to markets</Button>
          </Link>
        }
      />
    );
  }
  return (
    <div className="space-y-5">
      <Link to="/markets" className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Markets
      </Link>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">{symbol}</h1>
            {info?.is_etf ? <Badge tone="violet">ETF</Badge> : null}
            {info?.security_type === "PCA" && <Badge tone="warn">Under surveillance</Badge>}
            {info?.series === "BE" && <Badge tone="warn">Trade-to-trade</Badge>}
          </div>
          <p className="mt-0.5 text-sm text-ink-2">{info?.name ?? " "}</p>
          {snap ? (
            <div className="mt-3 flex flex-wrap items-baseline gap-3">
              <span className="num text-3xl font-semibold tracking-tight text-ink">{inr(snap.close)}</span>
              <Delta value={snap.chg_1d} strong className="text-base">
                {pct(snap.chg_1d, 2)}
              </Delta>
              <AsOf iso={snap.asof} />
            </div>
          ) : (
            <Skeleton className="mt-3 h-9 w-64" />
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            icon={stock.data?.in_watchlist ? <BookmarkCheck className="size-4 text-brand" aria-hidden /> : <Bookmark className="size-4" aria-hidden />}
            loading={watch.isPending}
            onClick={() => watch.mutate({ symbol, add: !stock.data?.in_watchlist })}
          >
            {stock.data?.in_watchlist ? "Watching" : "Watch"}
          </Button>
          <Button variant="secondary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>
            Add to portfolio
          </Button>
          <Link to={`/lab/new/trend?symbols=${symbol}`}>
            <Button icon={<FlaskConical className="size-4" aria-hidden />}>Test a strategy</Button>
          </Link>
        </div>
      </header>

      {breaks.map((a) => (
        <Callout key={`${a.ex_date}-${a.subject}`} tone="warn" title={`${a.subject} on ${date(a.ex_date)}: the price drop here is not lost money`}>
          A {a.kinds.includes("rights") ? "rights issue" : "demerger"} changes what one share represents, and its size is not published, so QuantOS cannot adjust the history.
          Prices and returns that span {date(a.ex_date)} are not comparable, and the Strategy Lab will not test across it.
        </Callout>
      ))}
      <div className="grid gap-5 xl:grid-cols-3">
        <div className="space-y-5 xl:col-span-2">
          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <Segmented<PriceRange>
                label="Chart range"
                size="sm"
                value={range}
                onChange={setRange}
                options={(["1M", "6M", "1Y", "5Y", "MAX"] as const).map((r) => ({ value: r, label: r }))}
              />
              <div className="flex items-center gap-4">
                <Switch checked={averages} onChange={setAverages} label="50/200-day averages" />
                <Segmented
                  label="Chart type"
                  size="sm"
                  value={kind}
                  onChange={setKind}
                  options={[
                    { value: "candles", label: "Candles" },
                    { value: "line", label: "Line" },
                  ]}
                />
              </div>
            </div>
            {bars.data ? <PriceChart bars={bars.data} range={range} kind={kind} showAverages={averages} events={events} /> : <Skeleton className="h-[380px]" />}
            {averages && (
              <div className="mt-2 flex gap-4 text-[12px] text-ink-3">
                <span className="flex items-center gap-1.5">
                  <span className="h-0.5 w-4 rounded bg-violet" /> 50-day
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-0.5 w-4 rounded bg-ink-3" /> 200-day
                </span>
              </div>
            )}
          </Card>
          <Card>
            <CardHeader title="Statistics" subtitle="Price returns, excluding dividends" />
            {stats && snap ? (
              <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
                <Stat label="1 month" value={pct(stats.ret_1m)} tone={tone(stats.ret_1m)} />
                <Stat label="6 months" value={pct(stats.ret_6m)} tone={tone(stats.ret_6m)} />
                <Stat label="1 year" value={pct(stats.ret_1y)} tone={tone(stats.ret_1y)} />
                <Stat label="5 years" value={pct(stats.ret_5y)} tone={tone(stats.ret_5y)} />
                <Stat label="Volatility (1y)" value={pct(stats.vol_1y, 0, false)} hint="How much the price typically swings in a year. NIFTY is usually 12–18%." />
                <Stat label="Worst fall (1y)" value={pct(stats.max_drawdown_1y)} tone="down" hint="Largest peak-to-trough drop in the last year." />
                <Stat label="Beta vs NIFTY" value={num(stats.beta_1y, 2)} hint="1.0 moves with the market; above 1 swings more than it." />
                <Stat label="Turnover" value={snap.turnover_cr === null ? "—" : `₹${num(snap.turnover_cr, 0)} cr/day`} hint="Median daily traded value, last 60 sessions." />
              </div>
            ) : (
              <Skeleton className="h-32" />
            )}
            {snap && snap.high_52w !== null && snap.low_52w !== null && <Range52 low={snap.low_52w} high={snap.high_52w} close={snap.close} />}
          </Card>
        </div>
        <div className="space-y-5">
          {snap && <CostToTrade price={snap.close} />}
          {info && (info.stitch_note || (stock.data?.flags.length ?? 0) > 0) && (
            <Card>
              <CardHeader title="About this data" />
              <div className="space-y-3 text-[13.5px] text-ink-2">
                {info.stitch_note && <Callout tone="warn">{info.stitch_note}</Callout>}
                <p>
                  {int(info.sessions)} sessions from {date(info.first_date)} to {date(info.last_date)}.
                </p>
              </div>
            </Card>
          )}
          <Card>
            <CardHeader title="Corporate actions" subtitle="From NSE filings" />
            <Actions actions={stock.data?.actions ?? []} loading={stock.isPending} />
          </Card>
        </div>
      </div>
      <HoldingDialog open={adding} onOpenChange={setAdding} initial={{ symbol, avg_price: snap ? String(snap.close) : "" }} lockSymbol />
    </div>
  );
}

function Range52({ low, high, close }: { low: number; high: number; close: number }) {
  const position = high > low ? ((close - low) / (high - low)) * 100 : 50;
  return (
    <div className="mt-6">
      <div className="flex justify-between text-[12.5px] text-ink-3">
        <span>52-week low {num(low)}</span>
        <span>52-week high {num(high)}</span>
      </div>
      <div className="relative mt-2 h-1.5 rounded-full bg-gradient-to-r from-down/60 via-surface-3 to-up/60">
        <div role="img" className="absolute -top-1 size-3.5 -translate-x-1/2 rounded-full border-2 border-surface bg-ink shadow" style={{ left: `${position}%` }} aria-label={`Last close at ${num(position, 0)}% of the 52-week range`} />
      </div>
    </div>
  );
}

function CostToTrade({ price }: { price: number }) {
  const [quantity, setQuantity] = useState("100");
  const qty = Math.max(1, Number(quantity) || 1);
  const costs = useQuery({
    queryKey: ["stock-costs", price, qty],
    queryFn: () => tools.costs({ segment: "delivery", buy_price: price, sell_price: price, quantity: qty }),
  });
  return (
    <Card>
      <CardHeader title="Cost to trade" subtitle="Buy today, sell later at the same price" />
      <div className="flex items-center gap-3">
        <label htmlFor="ctt-qty" className="text-[13px] text-ink-2">
          Shares
        </label>
        <Input id="ctt-qty" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value.replace(/\D/g, ""))} className="w-28" />
        <span className="num text-[13px] text-ink-3">= {inr(qty * price, 0)}</span>
      </div>
      {costs.data ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-ink-2">Round-trip charges</span>
            <span className="num text-lg font-semibold text-ink">{inr(costs.data.charges)}</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-ink-2">Price must rise to break even</span>
            <span className="num font-semibold text-warn">{pct(costs.data.breakeven_move_pct, 2)}</span>
          </div>
          <p className="text-[12.5px] text-ink-3">
            Delivery trade with your broker charges from Settings, at NSE rates in force today.{" "}
            <Link to="/tools/costs" className="font-medium text-brand hover:underline">
              Full breakdown
            </Link>
          </p>
        </div>
      ) : (
        <Skeleton className="mt-4 h-16" />
      )}
    </Card>
  );
}

function Actions({ actions, loading }: { actions: { ex_date: string; subject: string; kinds: string[]; breaks_history: boolean }[]; loading: boolean }) {
  const [all, setAll] = useState(false);
  if (loading) return <Skeleton className="h-24" />;
  if (actions.length === 0) return <p className="text-sm text-ink-3">No corporate actions on record.</p>;
  const shown = all ? [...actions].reverse() : [...actions].reverse().slice(0, 6);
  return (
    <div>
      <ol className="space-y-3">
        {shown.map((a) => (
          <li key={`${a.ex_date}-${a.subject}`} className="flex gap-3">
            <div className="num w-24 shrink-0 text-[12.5px] text-ink-3">{date(a.ex_date)}</div>
            <div className="min-w-0 text-[13.5px]">
              <div className="text-ink">{a.subject}</div>
              {a.breaks_history && (
                <div className="mt-1 flex items-start gap-1.5 text-[12.5px] text-warn">
                  <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  Prices before and after this date are not comparable; the lab will not test across it.
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      {actions.length > 6 && (
        <button type="button" onClick={() => setAll(!all)} className="mt-3 text-[13px] font-medium text-brand hover:underline">
          {all ? "Show fewer" : `Show all ${actions.length}`}
        </button>
      )}
    </div>
  );
}
