import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  createSeriesMarkers,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  type SeriesType,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { inr, inrCompact, num } from "../lib/format";
import { token } from "../lib/theme";
import type { Bars } from "../lib/types";
import { cx } from "./ui";

function palette() {
  return {
    text: token("--q-ink-3"),
    line: token("--q-line"),
    ink: token("--q-ink"),
    brand: token("--q-brand"),
    up: token("--q-up"),
    down: token("--q-down"),
    muted: token("--q-ink-3"),
    violet: token("--q-violet"),
    surface: token("--q-surface"),
  };
}

function baseOptions(height: number) {
  const p = palette();
  return {
    height,
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor: p.text,
      fontFamily: "Inter Variable, system-ui, sans-serif",
      fontSize: 12,
    },
    grid: { vertLines: { visible: false }, horzLines: { color: p.line } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
    crosshair: { mode: CrosshairMode.Magnet },
    localization: { locale: "en-IN" },
  };
}

/** Re-render charts when the theme attribute flips so canvas colours follow the tokens. */
function useThemeVersion(): number {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const observer = new MutationObserver(() => setVersion((v) => v + 1));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return version;
}

function sma(values: number[], window: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i] ?? 0;
    if (i >= window) sum -= values[i - window] ?? 0;
    if (i >= window - 1) out[i] = sum / window;
  }
  return out;
}

export type PriceRange = "1M" | "6M" | "1Y" | "5Y" | "MAX";
const RANGE_SESSIONS: Record<PriceRange, number> = { "1M": 22, "6M": 126, "1Y": 252, "5Y": 1260, MAX: Infinity };

export function PriceChart({
  bars,
  range,
  kind,
  showAverages,
  events = [],
  height = 380,
}: {
  bars: Bars;
  range: PriceRange;
  kind: "candles" | "line";
  showAverages: boolean;
  events?: { date: string; label: string }[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const themeVersion = useThemeVersion();

  useEffect(() => {
    const el = ref.current;
    if (!el || bars.dates.length === 0) return;
    const p = palette();
    const chart: IChartApi = createChart(el, baseOptions(height));
    const n = bars.dates.length;
    const from = Math.max(0, n - RANGE_SESSIONS[range]);
    const time = (i: number) => bars.dates[i] as Time;
    chart.priceScale("right").applyOptions({ scaleMargins: { top: 0.06, bottom: 0.24 } });

    let main: ISeriesApi<SeriesType>;
    if (kind === "candles") {
      const series = chart.addSeries(CandlestickSeries, {
        upColor: p.up,
        downColor: p.down,
        wickUpColor: p.up,
        wickDownColor: p.down,
        borderVisible: false,
        priceFormat: { type: "price", precision: 2, minMove: 0.05 },
      });
      series.setData(
        bars.dates.map((_, i) => ({ time: time(i), open: bars.open[i]!, high: bars.high[i]!, low: bars.low[i]!, close: bars.close[i]! })),
      );
      main = series;
    } else {
      const series = chart.addSeries(LineSeries, { color: p.brand, lineWidth: 2, priceLineVisible: false });
      series.setData(bars.dates.map((_, i) => ({ time: time(i), value: bars.close[i]! })));
      main = series;
    }
    const markers = events.flatMap((event) => {
      const at = bars.dates.findIndex((d) => d >= event.date);
      return at < 0 ? [] : [{ time: time(at), position: "aboveBar" as const, color: p.down, shape: "arrowDown" as const, text: event.label }];
    });
    if (markers.length > 0) createSeriesMarkers(main, markers);

    const volume = chart.addSeries(HistogramSeries, { priceScaleId: "", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(
      bars.dates.map((_, i) => ({
        time: time(i),
        value: bars.volume[i]!,
        color: (bars.close[i] ?? 0) >= (bars.open[i] ?? 0) ? `${p.up}55` : `${p.down}55`,
      })),
    );

    if (showAverages) {
      for (const [window, color] of [
        [50, p.violet],
        [200, p.muted],
      ] as const) {
        const values = sma(bars.close, window);
        const line = chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        line.setData(values.flatMap((v, i) => (v === null ? [] : [{ time: time(i), value: v }])));
      }
    }
    chart.timeScale().setVisibleRange({ from: time(from), to: time(n - 1) });
    return () => chart.remove();
  }, [bars, range, kind, showAverages, events, height, themeVersion]);

  return <div ref={ref} className="w-full" style={{ height }} />;
}

export interface EquitySeries {
  label: string;
  color: "brand" | "muted" | "violet";
  dashed?: boolean;
  points: { time: string; value: number }[];
}

export function EquityChart({ series, log = false, height = 340 }: { series: EquitySeries[]; log?: boolean; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const themeVersion = useThemeVersion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const p = palette();
    const colors = { brand: p.brand, muted: p.muted, violet: p.violet };
    const chart = createChart(el, {
      ...baseOptions(height),
      rightPriceScale: { borderVisible: false, mode: log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal },
      localization: { locale: "en-IN", priceFormatter: (v: number) => inrCompact(v) },
    });
    for (const s of series) {
      const line = chart.addSeries(LineSeries, {
        color: colors[s.color],
        lineWidth: s.color === "brand" ? 2 : 2,
        lineStyle: s.dashed ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: true,
        title: s.label,
      });
      line.setData(s.points.map((pt) => ({ time: pt.time as Time, value: pt.value })));
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, log, height, themeVersion]);

  return <div ref={ref} className="w-full" style={{ height }} />;
}

export function DrawdownChart({ series, height = 180 }: { series: EquitySeries[]; height?: number }) {
  const drawdowns = useMemo(
    () =>
      series.map((s) => {
        let peak = -Infinity;
        return {
          ...s,
          points: s.points.map((pt) => {
            peak = Math.max(peak, pt.value);
            return { time: pt.time, value: (pt.value / peak - 1) * 100 };
          }),
        };
      }),
    [series],
  );
  const ref = useRef<HTMLDivElement>(null);
  const themeVersion = useThemeVersion();
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const p = palette();
    const colors = { brand: p.brand, muted: p.muted, violet: p.violet };
    const chart = createChart(el, { ...baseOptions(height), localization: { locale: "en-IN", priceFormatter: (v: number) => `${num(v, 0)}%` } });
    for (const s of drawdowns) {
      const line = chart.addSeries(LineSeries, { color: colors[s.color], lineWidth: 1, lineStyle: s.dashed ? LineStyle.Dashed : LineStyle.Solid, priceLineVisible: false, lastValueVisible: false });
      line.setData(s.points.map((pt) => ({ time: pt.time as Time, value: pt.value })));
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [drawdowns, height, themeVersion]);
  return <div ref={ref} className="w-full" style={{ height }} />;
}

// ------------------------------------------------------------------------ SVG components

export function Sparkline({ values, className, height = 32, width = 112 }: { values: number[]; className?: string; height?: number; width?: number }) {
  if (values.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`);
  const rising = (values[values.length - 1] ?? 0) >= (values[0] ?? 0);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={cx(rising ? "text-up" : "text-down", className)} aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function PayoffChart({
  grid,
  breakevens,
  spot,
  height = 300,
}: {
  grid: [number, number, number][];
  breakevens: number[];
  spot: number;
  height?: number;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => setWidth(Math.max(280, entries[0]?.contentRect.width ?? 640)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  if (grid.length < 2) return null;
  const pad = { l: 64, r: 16, t: 16, b: 28 };
  const xs = grid.map((g) => g[0]);
  const ys = grid.flatMap((g) => [g[1], g[2]]);
  const xMin = xs[0]!;
  const xMax = xs[xs.length - 1]!;
  const yMin = Math.min(0, ...ys);
  const yMax = Math.max(0, ...ys);
  const ySpan = yMax - yMin || 1;
  const sx = (x: number) => pad.l + ((x - xMin) / (xMax - xMin)) * (width - pad.l - pad.r);
  const sy = (y: number) => pad.t + (1 - (y - yMin) / ySpan) * (height - pad.t - pad.b);
  const path = (col: 1 | 2) => grid.map((g, i) => `${i ? "L" : "M"}${sx(g[0]).toFixed(1)},${sy(g[col]).toFixed(1)}`).join("");
  const zeroY = sy(0);
  const ticks = [yMin, yMin + ySpan / 2, yMax];
  const hovered = hover === null ? null : grid[hover];
  return (
    <div ref={wrap} className="relative w-full">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Profit and loss by underlying price at expiry and today"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = xMin + ((e.clientX - rect.left - pad.l) / (width - pad.l - pad.r)) * (xMax - xMin);
          let best = 0;
          for (let i = 1; i < grid.length; i++) if (Math.abs(grid[i]![0] - x) < Math.abs(grid[best]![0] - x)) best = i;
          setHover(best);
        }}
      >
        <defs>
          <clipPath id="payoff-above">
            <rect x={0} y={0} width={width} height={Math.max(0, zeroY)} />
          </clipPath>
          <clipPath id="payoff-below">
            <rect x={0} y={zeroY} width={width} height={Math.max(0, height - zeroY)} />
          </clipPath>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={width - pad.r} y1={sy(t)} y2={sy(t)} stroke="var(--q-line)" />
            <text x={pad.l - 8} y={sy(t) + 4} textAnchor="end" fontSize={11} fill="var(--q-ink-3)">
              {inrCompact(t)}
            </text>
          </g>
        ))}
        <path d={`${path(1)}L${sx(xMax)},${zeroY}L${sx(xMin)},${zeroY}Z`} fill="var(--q-up)" opacity={0.12} clipPath="url(#payoff-above)" />
        <path d={`${path(1)}L${sx(xMax)},${zeroY}L${sx(xMin)},${zeroY}Z`} fill="var(--q-down)" opacity={0.12} clipPath="url(#payoff-below)" />
        <line x1={pad.l} x2={width - pad.r} y1={zeroY} y2={zeroY} stroke="var(--q-line-strong)" />
        <path d={path(2)} fill="none" stroke="var(--q-violet)" strokeWidth={1.5} strokeDasharray="5 4" />
        <path d={path(1)} fill="none" stroke="var(--q-brand)" strokeWidth={2} />
        <line x1={sx(spot)} x2={sx(spot)} y1={pad.t} y2={height - pad.b} stroke="var(--q-ink-3)" strokeDasharray="2 3" />
        <text x={sx(spot)} y={height - 8} textAnchor="middle" fontSize={11} fill="var(--q-ink-2)">
          Spot {num(spot, 0)}
        </text>
        {breakevens.map((b) => (
          <g key={b}>
            <circle cx={sx(b)} cy={zeroY} r={3.5} fill="var(--q-surface)" stroke="var(--q-ink)" strokeWidth={1.5} />
          </g>
        ))}
        {hovered && (
          <line x1={sx(hovered[0])} x2={sx(hovered[0])} y1={pad.t} y2={height - pad.b} stroke="var(--q-ink-2)" strokeWidth={1} />
        )}
      </svg>
      {hovered && (
        <div
          className="pointer-events-none absolute top-2 rounded-lg border border-line bg-surface px-3 py-2 text-[12.5px] shadow-[var(--shadow-pop)]"
          style={{ left: Math.min(width - 190, Math.max(0, sx(hovered[0]) + 10)) }}
        >
          <div className="font-medium text-ink">At {num(hovered[0], 0)}</div>
          <div className="num text-ink-2">Expiry: {inr(hovered[1], 0)}</div>
          <div className="num text-ink-2">Today: {inr(hovered[2], 0)}</div>
        </div>
      )}
    </div>
  );
}

const DONUT_COLORS = ["var(--q-brand)", "var(--q-violet)", "var(--q-up)", "var(--q-warn)", "var(--q-down)", "var(--q-ink-3)"];

export function Donut({ slices, size = 160 }: { slices: { label: string; value: number }[]; size?: number }) {
  const total = slices.reduce((s, x) => s + Math.max(0, x.value), 0);
  if (total <= 0) return null;
  const r = size / 2 - 10;
  const c = 2 * Math.PI * r;
  let offset = 0;
  const top = slices.slice(0, 5);
  const rest = slices.slice(5).reduce((s, x) => s + x.value, 0);
  const shown = rest > 0 ? [...top, { label: "Others", value: rest }] : top;
  return (
    <div className="flex items-center gap-5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Allocation">
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {shown.map((s, i) => {
            const len = (s.value / total) * c;
            const el = (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={DONUT_COLORS[i % DONUT_COLORS.length]}
                strokeWidth={16}
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
              />
            );
            offset += len;
            return el;
          })}
        </g>
      </svg>
      <ul className="space-y-1.5 text-[13px]">
        {shown.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
            <span className="w-24 truncate text-ink-2">{s.label}</span>
            <span className="num font-medium text-ink">{num((s.value / total) * 100, 1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
