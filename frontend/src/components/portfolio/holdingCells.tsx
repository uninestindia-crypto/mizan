import { Link } from "react-router";
import { inr, inrSigned, pct } from "../../lib/format";
import type { ModeFilter } from "../mode/useModeFilter";
import { ModeFilterNote } from "../mode/ModeFilterNote";
import { ShariahBadge } from "../mode/ShariahBadge";
import { Card, cx, Delta } from "../ui";
import type { ReactNode } from "react";

// The pieces the two holdings tables share: the card they sit in, a stock's name with its Shariah label, a gain.

export const HEAD_ROW =
  "border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3";

/** The card around a holdings table: its heading, the way to switch views, and the note about hidden stocks. */
export function HoldingsFrame(props: {
  /** Use the whole row, with nothing beside it. */
  wide?: boolean;
  subtitle: string;
  toggle: ReactNode;
  filter: ModeFilter<unknown>;
  children: ReactNode;
}) {
  return (
    <Card padded={false} className={cx("min-w-0", props.wide ? "xl:col-span-3" : "xl:col-span-2")}>
      <div className="px-5 pt-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
          <div className="min-w-[12rem] flex-1">
            <h2 className="text-[15px] font-semibold text-ink">Holdings</h2>
            <p className="mt-0.5 text-[13px] text-ink-3">{props.subtitle}</p>
          </div>
          <div className="shrink-0">{props.toggle}</div>
        </div>
        <ModeFilterNote filter={props.filter} extra="The totals above still include them." className="-mt-2 mb-3" />
      </div>
      <div className="overflow-x-auto">{props.children}</div>
    </Card>
  );
}

/** A stock's symbol (a link to its page), its Shariah label in Shariah mode, and a small line under it. */
export function StockName(props: { symbol: string; filter: ModeFilter<unknown>; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Link to={`/stock/${props.symbol}`} className="font-semibold text-ink hover:underline">
          {props.symbol}
        </Link>
        <ShariahBadge compact symbol={props.symbol} status={props.filter.statusOf(props.symbol)} />
      </div>
      {props.sub ? <div className="text-[12px] text-ink-3">{props.sub}</div> : null}
    </div>
  );
}

export function GainCell({ pnl, pnlPct }: { pnl: number | undefined; pnlPct: number | null | undefined }) {
  return (
    <>
      <Delta value={pnl} strong>
        {inrSigned(pnl)}
      </Delta>
      <div className="num text-[12px] text-ink-3">{pct(pnlPct)}</div>
    </>
  );
}

/** On a phone, a holding's value and its gain share one column. */
export function ValueAndGain(props: { value?: number; pnl?: number; pnlPct?: number | null }) {
  return (
    <>
      <div className="num font-medium text-ink">{inr(props.value, 0)}</div>
      <div className="num flex flex-wrap justify-end gap-x-1.5 text-[12.5px]">
        <Delta value={props.pnl} strong className="whitespace-nowrap">
          {inrSigned(props.pnl)}
        </Delta>
        <span className="whitespace-nowrap text-ink-3">{pct(props.pnlPct)}</span>
      </div>
    </>
  );
}
