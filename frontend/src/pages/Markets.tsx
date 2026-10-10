import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, Clock3, Search } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { AsOf, DataGate } from "../components/common";
import { ModeFilterNote } from "../components/mode/ModeFilterNote";
import { ShariahBadge } from "../components/mode/ShariahBadge";
import { type ModeFilter, useModeFilter } from "../components/mode/useModeFilter";
import { Badge, Card, cx, Delta, PageHeader, Segmented, Skeleton, Tooltip } from "../components/ui";
import { date, int, num, pct } from "../lib/format";
import { useScreener } from "../lib/queries";
import type { ScreenerRow } from "../lib/types";

type Universe = "liquid" | "nifty500" | "all";
type SortKey = "symbol" | "close" | "chg_1d" | "ret_1m" | "ret_6m" | "ret_1y" | "vol_1y" | "from_52w_high" | "turnover_cr";
type Preset = "active" | "near_high" | "momentum" | "low_vol" | "fallers" | "above_200";

const PRESETS: { id: Preset; label: string; description: string; filter: (r: ScreenerRow) => boolean; sort: SortKey; desc: boolean }[] = [
  { id: "active", label: "Most traded", description: "Highest median daily turnover", filter: () => true, sort: "turnover_cr", desc: true },
  { id: "near_high", label: "Near 52-week high", description: "Within 5% of the one-year high", filter: (r) => (r.from_52w_high ?? -1) >= -0.05, sort: "from_52w_high", desc: true },
  { id: "momentum", label: "Strong 6-month trend", description: "Best six-month return", filter: (r) => r.ret_6m !== null, sort: "ret_6m", desc: true },
  { id: "low_vol", label: "Low volatility", description: "Calmest one-year price swings", filter: (r) => r.vol_1y !== null, sort: "vol_1y", desc: false },
  { id: "fallers", label: "Biggest 1-month fallers", description: "Worst one-month return", filter: (r) => r.ret_1m !== null, sort: "ret_1m", desc: false },
  { id: "above_200", label: "Above 200-day average", description: "Price above its 200-day moving average", filter: (r) => r.sma_200 !== null && r.close > r.sma_200, sort: "turnover_cr", desc: true },
];

const COLUMNS: { key: SortKey; label: string; align: "left" | "right"; width: string; hint?: string }[] = [
  { key: "symbol", label: "Stock", align: "left", width: "minmax(220px,2.2fr)" },
  { key: "close", label: "Price", align: "right", width: "minmax(96px,1fr)" },
  { key: "chg_1d", label: "1D", align: "right", width: "minmax(72px,0.8fr)" },
  { key: "ret_1m", label: "1M", align: "right", width: "minmax(72px,0.8fr)" },
  { key: "ret_6m", label: "6M", align: "right", width: "minmax(72px,0.8fr)" },
  { key: "ret_1y", label: "1Y", align: "right", width: "minmax(72px,0.8fr)" },
  { key: "vol_1y", label: "Volatility", align: "right", width: "minmax(88px,0.9fr)", hint: "Annualised volatility of daily returns over the last year." },
  { key: "from_52w_high", label: "From high", align: "right", width: "minmax(88px,0.9fr)", hint: "Distance of the last close from the 52-week high." },
  { key: "turnover_cr", label: "Turnover", align: "right", width: "minmax(96px,1fr)", hint: "Median daily traded value over the last 60 sessions, in ₹ crore." },
];

const gridTemplate = COLUMNS.map((c) => c.width).join(" ");

export default function Markets() {
  return (
    <>
      <PageHeader title="Markets" subtitle="Screen NSE stocks and ETFs on real, cleaned daily data. Click any row for charts, statistics and costs." />
      <DataGate>
        <Screener />
      </DataGate>
    </>
  );
}

function Screener() {
  const [universe, setUniverse] = useState<Universe>("liquid");
  const [preset, setPreset] = useState<Preset>("active");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "turnover_cr", desc: true });
  const [query, setQuery] = useState("");
  const screener = useScreener(universe);
  const latest = screener.data?.latest ?? null;

  const rows = useMemo(() => {
    const base = screener.data?.rows ?? [];
    const presetDef = PRESETS.find((p) => p.id === preset)!;
    const text = query.trim().toUpperCase();
    const filtered = base.filter((r) => presetDef.filter(r) && (!text || r.symbol.includes(text) || r.name.toUpperCase().includes(text)));
    const dir = sort.desc ? -1 : 1;
    return filtered.sort((a, b) => {
      if (sort.key === "symbol") return a.symbol.localeCompare(b.symbol) * dir;
      const av = a[sort.key] as number | null;
      const bv = b[sort.key] as number | null;
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av - bv) * dir;
    });
  }, [screener.data, preset, sort, query]);

  const filter = useModeFilter(rows, "markets", { statusFrom: screener.data?.rows.map((r) => r.symbol) });

  const choosePreset = (id: Preset) => {
    const def = PRESETS.find((p) => p.id === id)!;
    setPreset(id);
    setSort({ key: def.sort, desc: def.desc });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Universe"
          value={universe}
          onChange={setUniverse}
          options={[
            { value: "liquid", label: "Liquid stocks" },
            { value: "nifty500", label: "NIFTY 500" },
            { value: "all", label: "All listed" },
          ]}
        />
        <div className="flex items-center gap-3">
          <AsOf iso={latest} />
          <div className="relative w-64">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by symbol or name"
              aria-label="Filter by symbol or name"
              className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15"
            />
          </div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Screens">
        {PRESETS.map((p) => (
          <Tooltip key={p.id} content={p.description}>
            <button
              type="button"
              role="radio"
              aria-checked={preset === p.id}
              onClick={() => choosePreset(p.id)}
              className={cx(
                "h-8 rounded-full border px-3.5 text-[13px] font-medium transition-colors",
                preset === p.id ? "border-brand bg-brand-soft text-brand" : "border-line bg-surface text-ink-2 hover:border-line-strong hover:text-ink",
              )}
            >
              {p.label}
            </button>
          </Tooltip>
        ))}
      </div>
      <ModeFilterNote filter={filter} coverage />
      <Card padded={false} className="overflow-hidden">
        {screener.isPending ? (
          <div className="space-y-2 p-5">
            {Array.from({ length: 8 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <VirtualTable rows={filter.visible} filter={filter} latest={latest} sort={sort} onSort={(key) => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== "symbol" && key !== "vol_1y" }))} />
        )}
      </Card>
      <p className="text-[12.5px] text-ink-3">
        {int(filter.visible.length)} shown. Returns are price-only (dividends excluded) and computed on each stock's own sessions. Stocks with older data are marked
        with a clock.
      </p>
    </div>
  );
}

function VirtualTable({
  rows,
  filter,
  latest,
  sort,
  onSort,
}: {
  rows: ScreenerRow[];
  filter: ModeFilter<ScreenerRow>;
  latest: string | null;
  sort: { key: SortKey; desc: boolean };
  onSort: (key: SortKey) => void;
}) {
  const parent = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => parent.current, estimateSize: () => 56, overscan: 12 });
  return (
    <div role="table" aria-label="Screener results" aria-rowcount={rows.length + 1} className="overflow-x-auto">
      <div className="min-w-[980px]">
        <div role="row" className="sticky top-0 z-10 grid border-b border-line bg-surface-2/80 px-4 backdrop-blur" style={{ gridTemplateColumns: gridTemplate }}>
          {COLUMNS.map((c) => {
            const active = sort.key === c.key;
            return (
              <div key={c.key} role="columnheader" aria-sort={active ? (sort.desc ? "descending" : "ascending") : "none"} className={cx("py-2.5", c.align === "right" && "text-right")}>
                <button
                  type="button"
                  onClick={() => onSort(c.key)}
                  title={c.hint}
                  className={cx("inline-flex items-center gap-1 text-[12px] font-semibold uppercase tracking-wide", active ? "text-ink" : "text-ink-3 hover:text-ink")}
                >
                  {c.label}
                  {active && (sort.desc ? <ArrowDown className="size-3" aria-hidden /> : <ArrowUp className="size-3" aria-hidden />)}
                </button>
              </div>
            );
          })}
        </div>
        <div ref={parent} className="h-[calc(100vh-340px)] min-h-[360px] overflow-y-auto">
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map((item) => {
              const r = rows[item.index]!;
              const stale = latest !== null && r.asof < latest;
              return (
                <div
                  key={r.symbol}
                  role="row"
                  tabIndex={0}
                  onClick={() => void navigate(`/stock/${r.symbol}`)}
                  onKeyDown={(e) => e.key === "Enter" && void navigate(`/stock/${r.symbol}`)}
                  className="absolute left-0 right-0 grid cursor-pointer items-center border-b border-line px-4 transition-colors hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
                  style={{ gridTemplateColumns: gridTemplate, height: item.size, transform: `translateY(${item.start}px)` }}
                >
                  <div role="cell" className="flex min-w-0 items-center gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-semibold text-ink">{r.symbol}</span>
                        {r.is_etf ? <Badge tone="violet">ETF</Badge> : null}
                        {r.security_type === "PCA" && <Badge tone="warn">Surveillance</Badge>}
                        {r.series === "BE" && <Badge tone="warn">T2T</Badge>}
                        <ShariahBadge compact status={filter.statusOf(r.symbol)} />
                        {stale && (
                          <Tooltip content={`Data to ${date(r.asof)}`}>
                            <Clock3 className="size-3.5 text-warn" aria-label={`Data to ${date(r.asof)}`} />
                          </Tooltip>
                        )}
                      </div>
                      <div className="truncate text-[12.5px] text-ink-3">{r.name}</div>
                    </div>
                  </div>
                  <div role="cell" className="num text-right text-sm font-medium text-ink">
                    {num(r.close)}
                  </div>
                  {(["chg_1d", "ret_1m", "ret_6m", "ret_1y"] as const).map((k) => (
                    <div role="cell" key={k} className="text-right text-sm">
                      <Delta value={r[k]}>{pct(r[k], 1)}</Delta>
                    </div>
                  ))}
                  <div role="cell" className="num text-right text-sm text-ink-2">
                    {pct(r.vol_1y, 0, false)}
                  </div>
                  <div role="cell" className="num text-right text-sm text-ink-2">
                    {pct(r.from_52w_high, 1)}
                  </div>
                  <div role="cell" className="num text-right text-sm text-ink-2">
                    {r.turnover_cr === null ? "—" : `₹${num(r.turnover_cr, r.turnover_cr < 10 ? 1 : 0)} cr`}
                  </div>
                </div>
              );
            })}
          </div>
          {rows.length === 0 && <div className="py-16 text-center text-sm text-ink-3">No stocks match this screen.</div>}
        </div>
      </div>
    </div>
  );
}
