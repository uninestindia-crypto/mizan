import { date, plural } from "../../lib/format";
import type { PositionLot } from "../../lib/fundamentalsTypes";

/** What a lot's holding period says, as facts: days held, and whether it counts as more than 12 months yet. */
function lotWords(lot: PositionLot): string {
  const held = `Held for ${plural(lot.days_held, "day")}`;
  const from = `counts as more than 12 months from ${date(lot.long_term_on)}`;
  const term = lot.is_long_term ? "held more than 12 months" : from;
  return `${held} · ${term}`;
}

function Lot({ lot, showAccount }: { lot: PositionLot; showAccount: boolean }) {
  const where = showAccount && lot.account_name ? ` in ${lot.account_name}` : "";
  return (
    <li className="space-y-0.5">
      <p className="text-ink">
        {plural(lot.quantity, "share")} bought {date(lot.buy_date)}
        {where}
      </p>
      <p className="text-ink-3">{lotWords(lot)}</p>
    </li>
  );
}

/**
 * Each purchase of a stock, oldest first, with how long it has been held. The sentence under the list is the engine's
 * own, shown exactly as sent. No tax amounts or rates appear here.
 */
export function LotsList(props: { symbol: string; lots: PositionLot[]; note?: string; showAccount: boolean }) {
  return (
    <div className="space-y-2 text-[13px]">
      <p className="font-medium text-ink">Purchases and how long each has been held</p>
      <ul aria-label={`Purchases of ${props.symbol}`} className="space-y-2">
        {props.lots.map((lot, at) => (
          <Lot key={`${lot.holding_id ?? "lot"}-${at}`} lot={lot} showAccount={props.showAccount} />
        ))}
      </ul>
      {props.note && <p className="text-ink-3">{props.note}</p>}
    </div>
  );
}
