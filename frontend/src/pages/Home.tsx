import { ArrowRight, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { Sparkline } from "../components/charts";
import { AsOf, DataGate, Illustration } from "../components/common";
import { Badge, Button, Card, CardHeader, Delta, EmptyState, PageHeader, Segmented, Skeleton, Stat } from "../components/ui";
import { ageLabel, date, daysSince, inr, inrCompact, inrSigned, num, pct, tone } from "../lib/format";
import { useOverview, usePaperBooks, usePortfolio, useStatus, useWatchlist } from "../lib/queries";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function Home() {
  const status = useStatus();
  return (
    <>
      <PageHeader
        title={greeting()}
        subtitle="Real NSE prices, exact costs, honest numbers. Here is where the market and your money stand."
        actions={status.data?.index.ready ? <AsOf iso={status.data.index.latest_session} /> : null}
      />
      <DataGate>
        <HomeContent />
      </DataGate>
    </>
  );
}

function HomeContent() {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-3">
        <MarketPulse />
        <Breadth />
        <PortfolioCard />
      </div>
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Movers />
        </div>
        <div className="lg:col-span-2">
          <Watchlist />
        </div>
      </div>
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <LabInvite />
        </div>
        <div className="lg:col-span-2">
          <PaperMini />
        </div>
      </div>
    </div>
  );
}

function MarketPulse() {
  const overview = useOverview();
  const bench = overview.data?.benchmark;
  const lag = bench && overview.data ? (daysSince(bench.asof) ?? 0) - (daysSince(overview.data.latest_session) ?? 0) : 0;
  return (
    <Card>
      <CardHeader title="NIFTY 50" subtitle={bench ? `Tracked by ${bench.symbol} · to ${date(bench.asof)}` : "Benchmark"} />
      {lag > 3 && (
        <p className="-mt-2 mb-3 text-[12.5px] text-warn">NIFTY data is {ageLabel(lag).replace(" old", "")} behind the stock data, so comparisons with it end earlier.</p>
      )}
      {overview.isPending ? (
        <Skeleton className="h-24" />
      ) : bench ? (
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="num text-3xl font-semibold tracking-tight text-ink">{inr(bench.close)}</div>
            <div className="mt-1 flex items-center gap-3 text-[13px]">
              <Delta value={bench.chg_1d} strong>
                {pct(bench.chg_1d, 2)} today
              </Delta>
              <span className="text-ink-3">1M</span>
              <Delta value={bench.ret_1m}>{pct(bench.ret_1m)}</Delta>
              <span className="text-ink-3">1Y</span>
              <Delta value={bench.ret_1y}>{pct(bench.ret_1y)}</Delta>
            </div>
          </div>
          <Sparkline values={bench.spark} width={120} height={48} />
        </div>
      ) : (
        <p className="text-sm text-ink-3">NIFTYBEES is not in the market data.</p>
      )}
    </Card>
  );
}

function Breadth() {
  const overview = useOverview();
  const b = overview.data?.breadth;
  const total = b ? b.advancers + b.decliners + b.unchanged : 0;
  return (
    <Card>
      <CardHeader title="Market breadth" subtitle={b ? `Liquid ${b.count} · session of ${date(b.asof)}` : "Liquid stocks"} />
      {overview.isPending || !b ? (
        <Skeleton className="h-24" />
      ) : (
        <div className="space-y-4">
          <div className="flex items-baseline gap-2">
            <span className="num text-3xl font-semibold tracking-tight text-ink">{pct(b.above_200dma_pct, 0, false)}</span>
            <span className="text-[13px] text-ink-2">above their 200-day average</span>
          </div>
          <div>
            <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-3" aria-hidden>
              <div className="bg-up" style={{ width: `${(b.advancers / Math.max(1, total)) * 100}%` }} />
              <div className="bg-ink-3/40" style={{ width: `${(b.unchanged / Math.max(1, total)) * 100}%` }} />
              <div className="bg-down" style={{ width: `${(b.decliners / Math.max(1, total)) * 100}%` }} />
            </div>
            <div className="num mt-2 flex justify-between text-[12.5px]">
              <span className="text-up">{b.advancers} rose</span>
              <span className="text-down">{b.decliners} fell</span>
            </div>
          </div>
          {b.stale > 0 && <p className="text-[12px] text-ink-3">{b.stale} stocks have older data and are not counted.</p>}
        </div>
      )}
    </Card>
  );
}

function PortfolioCard() {
  const portfolio = usePortfolio();
  const totals = portfolio.data?.totals;
  return (
    <Card>
      <CardHeader
        title="Your portfolio"
        action={
          <Link to="/portfolio" className="text-[13px] font-medium text-brand hover:underline">
            Open
          </Link>
        }
      />
      {portfolio.isPending ? (
        <Skeleton className="h-24" />
      ) : totals ? (
        <div className="grid grid-cols-2 gap-4">
          <Stat label="Value" value={inrCompact(totals.value)} />
          <Stat label="Today" value={inrSigned(totals.day_change)} tone={tone(totals.day_change)} />
          <Stat label="Total gain" value={inrSigned(totals.pnl)} tone={tone(totals.pnl)} sub={pct(totals.pnl_pct)} />
          <Stat label="Cost to exit today" value={inr(totals.exit_charges, 0)} hint="Statutory charges plus your broker's, if you sold everything at the last close." />
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <Illustration name="empty-portfolio" className="size-20" />
          <div>
            <p className="text-sm text-ink-2">Add what you own to see your real gain after costs, and how it compares with NIFTY.</p>
            <Link to="/portfolio" className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-brand hover:underline">
              Add holdings <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </div>
        </div>
      )}
    </Card>
  );
}

function Movers() {
  const overview = useOverview();
  const [side, setSide] = useState<"gainers" | "losers">("gainers");
  const rows = overview.data?.[side] ?? [];
  return (
    <Card padded={false}>
      <div className="flex items-center justify-between gap-3 px-5 pt-5">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Biggest moves</h2>
          <p className="mt-0.5 text-[13px] text-ink-3">Liquid stocks, last session</p>
        </div>
        <Segmented
          label="Movers"
          size="sm"
          value={side}
          onChange={setSide}
          options={[
            { value: "gainers", label: "Gainers" },
            { value: "losers", label: "Losers" },
          ]}
        />
      </div>
      <ul className="mt-3 divide-y divide-line">
        {overview.isPending &&
          Array.from({ length: 5 }, (_, i) => (
            <li key={i} className="px-5 py-3">
              <Skeleton className="h-5" />
            </li>
          ))}
        {rows.map((m) => (
          <li key={m.symbol}>
            <Link to={`/stock/${m.symbol}`} className="flex items-center justify-between gap-4 px-5 py-3 transition-colors hover:bg-surface-2">
              <div className="flex min-w-0 items-center gap-3">
                <span className={`flex size-8 items-center justify-center rounded-full ${side === "gainers" ? "bg-up-soft text-up" : "bg-down-soft text-down"}`}>
                  {side === "gainers" ? <TrendingUp className="size-4" aria-hidden /> : <TrendingDown className="size-4" aria-hidden />}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-ink">{m.symbol}</div>
                  <div className="truncate text-[12.5px] text-ink-3">{m.name}</div>
                </div>
              </div>
              <div className="text-right">
                <div className="num text-sm font-medium text-ink">{inr(m.close)}</div>
                <Delta value={m.chg_1d} className="text-[13px]" strong>
                  {pct(m.chg_1d, 2)}
                </Delta>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Watchlist() {
  const watch = useWatchlist();
  const rows = watch.data ?? [];
  return (
    <Card padded={false} className="h-full">
      <div className="px-5 pt-5">
        <h2 className="text-[15px] font-semibold text-ink">Watchlist</h2>
        <p className="mt-0.5 text-[13px] text-ink-3">Three-month trend</p>
      </div>
      {watch.isPending ? (
        <div className="p-5">
          <Skeleton className="h-32" />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title="Nothing on your watchlist"
          body="Open any stock and choose Watch to follow it here."
          action={
            <Link to="/markets">
              <Button variant="secondary" size="sm">
                Browse markets
              </Button>
            </Link>
          }
        />
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {rows.map((w) => (
            <li key={w.symbol}>
              <Link to={`/stock/${w.symbol}`} className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-surface-2">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-ink">{w.symbol}</div>
                  <div className="truncate text-[12.5px] text-ink-3">{w.name ?? "Not in data"}</div>
                </div>
                <Sparkline values={w.spark ?? []} width={84} height={28} />
                <div className="w-24 text-right">
                  <div className="num text-sm font-medium text-ink">{inr(w.close)}</div>
                  <Delta value={w.chg_1d} className="text-[12.5px]">
                    {pct(w.chg_1d, 2)}
                  </Delta>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function LabInvite() {
  const status = useStatus();
  return (
    <Card className="relative overflow-hidden">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          <Badge tone="brand">Strategy Lab</Badge>
          <h2 className="mt-3 text-xl font-semibold tracking-tight text-ink">Test an idea before you risk real money</h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-2">
            SEBI found that about 9 in 10 individual F&amp;O traders lose money. Try your rule on six years of real NSE prices with every charge
            included, and QuantOS will tell you plainly whether it beat simply holding NIFTY.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link to="/lab">
              <Button icon={<ArrowRight className="size-4" aria-hidden />}>Open the lab</Button>
            </Link>
            {status.data && status.data.lab_runs > 0 && <span className="text-[13px] text-ink-3">{num(status.data.lab_runs, 0)} tests so far</span>}
          </div>
        </div>
        <Illustration name="lab-hero" className="hidden size-40 shrink-0 sm:block" />
      </div>
    </Card>
  );
}

function PaperMini() {
  const books = usePaperBooks();
  return (
    <Card className="h-full">
      <CardHeader
        title="Paper books"
        subtitle="Virtual money, real prices"
        action={
          <Link to="/paper" className="text-[13px] font-medium text-brand hover:underline">
            Open
          </Link>
        }
      />
      {books.isPending ? (
        <Skeleton className="h-20" />
      ) : (books.data ?? []).length === 0 ? (
        <p className="text-sm text-ink-3">No paper books are running on this computer.</p>
      ) : (
        <ul className="space-y-3">
          {(books.data ?? []).map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink">{b.name}</div>
                <div className="text-[12.5px] text-ink-3">{b.status === "WAITING" ? "Waiting for first session" : b.asof ? `to ${date(b.asof.slice(0, 10))}` : b.status}</div>
              </div>
              {b.return !== undefined && b.return !== null ? (
                <Delta value={b.return} strong>
                  {pct(b.return, 2)}
                </Delta>
              ) : (
                <Badge>{b.status.toLowerCase()}</Badge>
              )}
            </li>
          ))}
          <li className="text-[12px] text-ink-3">Market plus costs, not proof of skill.</li>
        </ul>
      )}
    </Card>
  );
}
