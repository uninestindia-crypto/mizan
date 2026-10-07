import { Link } from "react-router";
import { inr, pct } from "../lib/format";
import { type LiveQuotes, useLiveQuotes } from "../lib/live";
import { useWatchlist } from "../lib/queries";
import type { ShariahStatus } from "../lib/shariahStatus";
import type { WatchRow } from "../lib/types";
import { Sparkline } from "./charts";
import { LiveChip, LiveConnectNote } from "./live/LivePrice";
import { ModeFilterNote, SymbolLine, useModeFilter } from "./mode";
import type { ModeFilter } from "./mode/useModeFilter";
import { Button, Card, Delta, EmptyState, Skeleton } from "./ui";

const ROW_LINK = "flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-surface-2";

interface RowProps {
  w: WatchRow;
  quotes: LiveQuotes | undefined;
  /** The stock's Shariah result, or null while it is not known or the app is in Institutional mode. */
  status: ShariahStatus | null;
}

function WatchlistRow({ w, quotes, status }: RowProps) {
  return (
    <li>
      <Link to={`/stock/${w.symbol}`} className={ROW_LINK}>
        <div className="min-w-0">
          <SymbolLine symbol={w.symbol} status={status} />
          <div className="truncate text-[12.5px] text-ink-3">{w.name ?? "Not in data"}</div>
          <LiveChip symbol={w.symbol} quotes={quotes} />
        </div>
        <Sparkline values={w.spark ?? []} width={84} height={28} />
        <div className="w-24 shrink-0 text-right">
          <div className="num text-sm font-medium text-ink">{inr(w.close)}</div>
          <Delta value={w.chg_1d} className="text-[12.5px]">
            {pct(w.chg_1d, 2)}
          </Delta>
          <div className="text-[11.5px] text-ink-3">End of day</div>
        </div>
      </Link>
    </li>
  );
}

function Empty() {
  const browse = (
    <Link to="/markets">
      <Button variant="secondary" size="sm">
        Browse markets
      </Button>
    </Link>
  );
  return (
    <EmptyState
      title="Nothing on your watchlist"
      body="Open any stock and choose Watch to follow it here."
      action={browse}
    />
  );
}

function Rows({ filter, quotes }: { filter: ModeFilter<WatchRow>; quotes: LiveQuotes | undefined }) {
  return (
    <ul className="mt-3 divide-y divide-line">
      {filter.visible.map((w) => (
        <WatchlistRow key={w.symbol} w={w} quotes={quotes} status={filter.statusOf(w.symbol)} />
      ))}
    </ul>
  );
}

/** The stocks you follow. In Shariah mode only the compliant ones, each labelled, with one control for the rest. */
export function Watchlist() {
  const watch = useWatchlist();
  const rows = watch.data ?? [];
  const filter = useModeFilter(rows, "home-watchlist");
  const live = useLiveQuotes(rows.map((w) => w.symbol));
  return (
    <Card padded={false} className="h-full">
      <div className="px-5 pt-5">
        <h2 className="text-[15px] font-semibold text-ink">Watchlist</h2>
        <p className="mt-0.5 text-[13px] text-ink-3">Three-month trend</p>
        <LiveConnectNote quotes={live.data} className="mt-2" />
        <ModeFilterNote filter={filter} coverage className="mt-2" />
      </div>
      {watch.isPending ? (
        <div className="p-5">
          <Skeleton className="h-32" />
        </div>
      ) : rows.length === 0 ? (
        <Empty />
      ) : (
        <Rows filter={filter} quotes={live.data} />
      )}
    </Card>
  );
}
