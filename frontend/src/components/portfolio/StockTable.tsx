import { ChevronRight } from "lucide-react";
import { type ReactNode, useState } from "react";
import { inr, int, num, pct, plural } from "../../lib/format";
import type { PortfolioPosition, PositionPlace } from "../../lib/types";
import { useModeFilter } from "../mode/useModeFilter";
import { cx } from "../ui";
import { GainCell, HEAD_ROW, HoldingsFrame, StockName, ValueAndGain } from "./holdingCells";
import { useNarrow } from "./useNarrow";

function addPlace(byAccount: Map<number, PositionPlace>, place: PositionPlace): void {
  const before = byAccount.get(place.account_id);
  if (!before) {
    byAccount.set(place.account_id, Object.assign({}, place));
    return;
  }
  before.quantity += place.quantity;
  before.value = before.value == null || place.value == null ? null : before.value + place.value;
}

/** The accounts that hold a stock, once each: two purchases in one account are one line with their shares added. */
export function placesOf(position: PortfolioPosition): PositionPlace[] {
  const byAccount = new Map<number, PositionPlace>();
  position.accounts.forEach((place) => addPlace(byAccount, place));
  return [...byAccount.values()];
}

function whereText(places: readonly PositionPlace[]): string {
  const first = places[0];
  if (places.length === 1 && first) return `In ${first.account_name ?? "one account"}`;
  return `In ${plural(places.length, "account")}`;
}

/** Which stocks are opened, and a way to open or close one. */
function useOpened(): [ReadonlySet<string>, (symbol: string) => void] {
  const [opened, setOpened] = useState<ReadonlySet<string>>(new Set());
  const flip = (symbol: string) => {
    const after = new Set(opened);
    if (!after.delete(symbol)) after.add(symbol);
    setOpened(after);
  };
  return [opened, flip];
}

type Filter = ReturnType<typeof useModeFilter<PortfolioPosition>>;

/** One line per stock across the accounts in view. With several accounts, a line opens to show who holds how many. */
export function StockTable(props: { positions: PortfolioPosition[]; showAccounts: boolean; toggle: ReactNode }) {
  const filter = useModeFilter(props.positions, "portfolio");
  const [opened, flip] = useOpened();
  const narrow = useNarrow();
  return (
    <HoldingsFrame subtitle={plural(props.positions.length, "stock")} toggle={props.toggle} filter={filter}>
      <table className="w-full text-sm" aria-label="Holdings by stock">
        <StockHead narrow={narrow} />
        {filter.visible.map((position) => (
          <PositionGroup
            key={position.symbol}
            position={position}
            filter={filter}
            narrow={narrow}
            expandable={props.showAccounts}
            expanded={opened.has(position.symbol)}
            onFlip={() => flip(position.symbol)}
          />
        ))}
      </table>
    </HoldingsFrame>
  );
}

function StockHead({ narrow }: { narrow: boolean }) {
  return (
    <thead>
      <tr className={HEAD_ROW}>
        <th className="px-4 py-2.5 text-left">Stock</th>
        {!narrow && <th className="px-2 py-2.5 text-right">Qty</th>}
        {!narrow && <th className="px-2 py-2.5 text-right">Avg price</th>}
        {!narrow && <th className="px-2 py-2.5 text-right">Last close</th>}
        <th className="px-2 py-2.5 text-right">{narrow ? "Value and gain" : "Value"}</th>
        {!narrow && <th className="px-2 py-2.5 text-right">Gain</th>}
        {!narrow && <th className="px-4 py-2.5 text-right">Share</th>}
      </tr>
    </thead>
  );
}

interface GroupProps {
  position: PortfolioPosition;
  filter: Filter;
  narrow: boolean;
  expandable: boolean;
  expanded: boolean;
  onFlip: () => void;
}

function PositionGroup(props: GroupProps) {
  return (
    <tbody className="border-b border-line last:border-b-0">
      <PositionRow {...props} />
      {props.expandable && props.expanded && <PlacesRow position={props.position} narrow={props.narrow} />}
    </tbody>
  );
}

/** The small line under a stock's symbol. On a phone it also carries the shares and the average price. */
function subLine(p: PortfolioPosition, props: GroupProps): ReactNode {
  if (p.error) return p.error;
  const where = props.expandable ? whereText(placesOf(p)) : p.name;
  if (!props.narrow) return where;
  return (
    <>
      <span className="num block">
        {int(p.quantity)} shares at {num(p.avg_price)}
      </span>
      {where}
    </>
  );
}

function PositionRow(props: GroupProps) {
  const p = props.position;
  return (
    <tr>
      <td className="px-4 py-3">
        <div className="flex items-start gap-1.5">
          {props.expandable && <Opener position={p} expanded={props.expanded} onFlip={props.onFlip} />}
          <StockName symbol={p.symbol} filter={props.filter} sub={subLine(p, props)} />
        </div>
      </td>
      {!props.narrow && <td className="num px-2 py-3 text-right text-ink-2">{int(p.quantity)}</td>}
      {!props.narrow && <td className="num px-2 py-3 text-right text-ink-2">{num(p.avg_price)}</td>}
      {!props.narrow && <td className="num px-2 py-3 text-right text-ink-2">{num(p.close)}</td>}
      <ValueCells position={p} narrow={props.narrow} />
      {!props.narrow && <td className="num px-4 py-3 text-right text-ink-2">{pct(p.weight, 1, false)}</td>}
    </tr>
  );
}

function ValueCells({ position: p, narrow }: { position: PortfolioPosition; narrow: boolean }) {
  if (narrow) {
    return (
      <td className="px-4 py-3 text-right">
        <ValueAndGain value={p.value} pnl={p.pnl} pnlPct={p.pnl_pct} />
      </td>
    );
  }
  return (
    <>
      <td className="num px-2 py-3 text-right font-medium text-ink">{inr(p.value, 0)}</td>
      <td className="px-2 py-3 text-right">
        <GainCell pnl={p.pnl} pnlPct={p.pnl_pct} />
      </td>
    </>
  );
}

function Opener(props: { position: PortfolioPosition; expanded: boolean; onFlip: () => void }) {
  const symbol = props.position.symbol;
  return (
    <button
      type="button"
      aria-expanded={props.expanded}
      aria-controls={`places-${symbol}`}
      aria-label={`${props.expanded ? "Hide" : "Show"} which accounts hold ${symbol}`}
      onClick={props.onFlip}
      className="-ml-1.5 mt-[-2px] rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink"
    >
      <ChevronRight className={cx("size-4 transition-transform", props.expanded && "rotate-90")} aria-hidden />
    </button>
  );
}

function PlacesRow({ position, narrow }: { position: PortfolioPosition; narrow: boolean }) {
  return (
    <tr id={`places-${position.symbol}`} className="bg-surface-2/50">
      <td colSpan={narrow ? 2 : 7} className="px-4 py-3 pl-11">
        <ul aria-label={`Accounts holding ${position.symbol}`} className="grid gap-1.5 text-[13px] sm:grid-cols-2">
          {placesOf(position).map((place) => (
            <li key={place.account_id} className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-ink">{place.account_name ?? "An account"}</span>
              <span className="num shrink-0 text-ink-2">
                {plural(place.quantity, "share")}
                {place.value == null ? "" : ` · ${inr(place.value, 0)}`}
              </span>
            </li>
          ))}
        </ul>
      </td>
    </tr>
  );
}
