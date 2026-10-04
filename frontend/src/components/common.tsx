import { CircleSlash, FlaskConical, Scale, ShieldAlert, ShieldCheck, Sparkles, X } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";
import { Link } from "react-router";
import { ageLabel, date, daysSince, pct } from "../lib/format";
import { useSearch, useStatus } from "../lib/queries";
import type { VerdictLevel } from "../lib/types";
import { Badge, Button, Card, cx, EmptyState, ProgressBar, Spinner } from "./ui";

const images = import.meta.glob<string>("../assets/illustrations/*.png", { eager: true, import: "default" });

export function Illustration({ name, className, alt = "" }: { name: string; className?: string; alt?: string }) {
  const src = images[`../assets/illustrations/${name}.png`];
  if (!src) return null;
  return <img src={src} alt={alt} className={cx("pointer-events-none select-none object-contain", className)} draggable={false} />;
}

/** Renders children only when the market index is ready; otherwise explains how to connect data. */
export function DataGate({ children }: { children: ReactNode }) {
  const status = useStatus();
  if (status.isPending) return <Spinner />;
  if (status.data?.index.ready) return <>{children}</>;
  const building = status.data?.index.job.state === "RUNNING";
  const download = status.data?.download;
  const downloading = download?.state === "RUNNING";
  return (
    <Card className="mt-2">
      <EmptyState
        art={<Illustration name="empty-data" className="h-40 w-40" />}
        title={downloading ? "Downloading market data…" : building ? "Preparing market data…" : "Get your market data"}
        body={
          downloading ? (
            <div className="mx-auto mt-1 max-w-sm space-y-2 text-left">
              <ProgressBar value={download.progress} label="Downloading market data" />
              <p className="text-center">
                {download.done} of {download.total} stocks so far. It keeps going in the background, so you can leave this page.
              </p>
            </div>
          ) : building ? (
            "QuantOS is indexing ten years of NSE prices. This takes a minute or two."
          ) : (
            "QuantOS needs real NSE daily prices on this computer. It can download them for you in about five minutes, free and with no account, or you can use data you already have."
          )
        }
        action={
          <Link to="/settings/data">
            <Button>{downloading || building ? "View progress" : "Get market data"}</Button>
          </Link>
        }
      />
    </Card>
  );
}

export function AsOf({ iso, className }: { iso: string | null | undefined; className?: string }) {
  const age = daysSince(iso);
  const stale = age !== null && age > 5;
  return (
    <span className={cx("num inline-flex items-center gap-1.5 text-[12.5px]", stale ? "text-warn" : "text-ink-3", className)}>
      <span className={cx("size-1.5 rounded-full", stale ? "bg-warn" : "bg-up")} aria-hidden />
      Data to {date(iso)}
      {stale && age !== null ? ` · ${ageLabel(age)}` : ""}
    </span>
  );
}

// ---------------------------------------------------------------------- symbol picking

export function SymbolSearch({
  onPick,
  placeholder = "Search NSE stocks and ETFs",
  exclude = [],
  autoFocus = false,
}: {
  onPick: (symbol: string) => void;
  placeholder?: string;
  exclude?: string[];
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const results = useSearch(query);
  const listId = useId();
  // While the answer for the latest keystroke is still on its way, the list on screen belongs to an
  // earlier query ("reli" for "relia"); never offer or pick from it.
  const fresh = results.isPlaceholderData ? [] : (results.data ?? []);
  const options = fresh.filter((r) => !exclude.includes(r.symbol)).slice(0, 8);
  const [enterPending, setEnterPending] = useState(false);
  const pick = (symbol: string) => {
    onPick(symbol);
    setQuery("");
    setOpen(false);
    setActive(0);
    setEnterPending(false);
  };
  useEffect(() => {
    // Enter pressed before the answer arrived: take the best match as soon as it does.
    if (enterPending && !results.isFetching) {
      const first = options[0];
      if (first) pick(first.symbol);
      else setEnterPending(false);
    }
  }); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="relative">
      <input
        value={query}
        autoFocus={autoFocus}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(options.length - 1, a + 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(0, a - 1));
          } else if (e.key === "Enter" && options[active]) {
            e.preventDefault();
            pick(options[active].symbol);
          } else if (e.key === "Enter" && query.trim()) {
            e.preventDefault();
            setEnterPending(true);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        placeholder={placeholder}
        className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-3 hover:border-line-strong focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15"
      />
      {open && query.trim() && (
        <ul id={listId} role="listbox" className="absolute left-0 right-0 top-11 z-30 max-h-72 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-[var(--shadow-pop)]">
          {options.length === 0 && <li className="px-3 py-2.5 text-sm text-ink-3">{results.isFetching ? "Searching…" : "No matches"}</li>}
          {options.map((r, i) => (
            <li
              key={r.symbol}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(r.symbol);
              }}
              onMouseEnter={() => setActive(i)}
              className={cx("flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm", i === active && "bg-surface-2")}
            >
              <span className="min-w-0">
                <span className="font-semibold text-ink">{r.symbol}</span>
                <span className="ml-2 truncate text-ink-3">{r.name}</span>
              </span>
              {r.is_etf ? <Badge tone="violet">ETF</Badge> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function SymbolChips({ symbols, onRemove }: { symbols: string[]; onRemove: (s: string) => void }) {
  if (symbols.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {symbols.map((s) => (
        <span key={s} className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 py-1 pl-3 pr-1.5 text-[13px] font-medium text-ink">
          {s}
          <button type="button" onClick={() => onRemove(s)} aria-label={`Remove ${s}`} className="rounded-full p-0.5 text-ink-3 hover:bg-surface-3 hover:text-ink">
            <X className="size-3.5" aria-hidden />
          </button>
        </span>
      ))}
    </div>
  );
}

// -------------------------------------------------------------------------- verdicts

export const VERDICT_STYLE: Record<VerdictLevel, { tone: "up" | "down" | "warn" | "neutral" | "brand"; icon: typeof ShieldCheck; label: string }> = {
  EDGE: { tone: "up", icon: ShieldCheck, label: "Evidence of an edge" },
  PROMISING: { tone: "brand", icon: Sparkles, label: "Promising, not proven" },
  NO_EVIDENCE: { tone: "neutral", icon: Scale, label: "No real evidence" },
  TOO_SHORT: { tone: "warn", icon: FlaskConical, label: "Too little history" },
  LOST: { tone: "down", icon: CircleSlash, label: "Lost to the comparison" },
};

export function VerdictBadge({ level }: { level: VerdictLevel }) {
  const style = VERDICT_STYLE[level];
  const Icon = style.icon;
  return (
    <Badge tone={style.tone === "neutral" ? "neutral" : style.tone}>
      <Icon className="size-3.5" aria-hidden />
      {style.label}
    </Badge>
  );
}

const bannerTone: Record<string, string> = {
  up: "border-up/30 bg-up-soft",
  down: "border-down/30 bg-down-soft",
  warn: "border-warn/30 bg-warn-soft",
  brand: "border-brand/25 bg-brand-soft",
  neutral: "border-line bg-surface-2",
};

const iconTone: Record<string, string> = { up: "text-up", down: "text-down", warn: "text-warn", brand: "text-brand", neutral: "text-ink-2" };

export function VerdictBanner({
  level,
  title,
  body,
  probability,
  threshold,
  trials,
}: {
  level: VerdictLevel;
  title: string;
  body: string;
  probability: number | null;
  threshold: number;
  trials: number;
}) {
  const style = VERDICT_STYLE[level];
  const Icon = level === "LOST" ? ShieldAlert : style.icon;
  return (
    <section aria-label="Verdict" className={cx("rounded-[var(--radius-card)] border p-5 sm:p-6", bannerTone[style.tone])}>
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <div className={cx("flex size-12 shrink-0 items-center justify-center rounded-2xl bg-surface shadow-sm", iconTone[style.tone])}>
          <Icon className="size-6" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-ink-3">Verdict</div>
          <h2 className="mt-0.5 text-xl font-semibold tracking-tight text-ink">{title}</h2>
          <p className="mt-1.5 max-w-3xl text-[14.5px] leading-relaxed text-ink-2">{body}</p>
        </div>
        <div className="w-full shrink-0 sm:w-56">
          {level === "TOO_SHORT" || level === "LOST" ? (
            <p className="text-[12.5px] leading-relaxed text-ink-2">
              <span className="font-semibold text-ink">No probability shown.</span>{" "}
              {level === "LOST"
                ? "It finished behind, so there is no edge to measure."
                : "With this little history any number would look more certain than it is."}
            </p>
          ) : (
            <>
              <ProbabilityMeter probability={probability} threshold={threshold} />
              <p className="mt-2 text-[12px] text-ink-3">
                Adjusted for {trials === 1 ? "this test" : `all ${trials} tests you have run`}. More tests make luck look like skill, so each one raises the bar.
              </p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

export function ProbabilityMeter({ probability, threshold }: { probability: number | null; threshold: number }) {
  const value = probability ?? 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12.5px]">
        <span className="text-ink-2">Chance it is more than luck</span>
        <span className="num text-base font-semibold text-ink">{probability === null ? "—" : pct(value, 0, false)}</span>
      </div>
      <div className="relative mt-2 h-2 rounded-full bg-surface-3">
        <div className={cx("h-full rounded-full", value >= threshold ? "bg-up" : "bg-brand")} style={{ width: `${Math.round(value * 100)}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 rounded bg-ink" style={{ left: `${threshold * 100}%` }} aria-hidden />
      </div>
      <div className="mt-1 text-right text-[11.5px] text-ink-3">QuantOS bar: {pct(threshold, 0, false)}</div>
    </div>
  );
}
