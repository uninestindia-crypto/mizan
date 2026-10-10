import { pct } from "../../lib/format";
import { basketPickNote } from "../../lib/picks";
import { overallStatus } from "../../lib/shariah";
import type { ShariahBasketConstituent } from "../../lib/types";
import { PickSecondOpinion } from "../copilot/PickSecondOpinion";
import { Badge } from "../ui";
import { priceText } from "./basketModel";
import { DataStatusBadge } from "./dataStatus";
import { STATUS_LABEL, STATUS_TONE } from "./labels";

const ROW =
  "flex flex-wrap items-center justify-between gap-x-3 gap-y-2 rounded-[var(--radius-control)] " +
  "border border-line bg-surface px-3 py-2";

/** The stock's own screening result with its data status beside it; a stock outside the sample has none. */
function Screening({ stock }: { stock: ShariahBasketConstituent }) {
  const { aaoifi_status: aaoifi, tasis_status: tasis } = stock;
  const verdict = aaoifi && tasis ? overallStatus(aaoifi, tasis) : null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      {verdict ? (
        <Badge tone={STATUS_TONE[verdict]}>{STATUS_LABEL[verdict]}</Badge>
      ) : (
        <Badge>No screening result</Badge>
      )}
      <DataStatusBadge status={stock.data_status} />
    </div>
  );
}

function Stock({ stock, basketName }: { stock: ShariahBasketConstituent; basketName: string }) {
  return (
    <li className={ROW}>
      <div className="min-w-0">
        <div className="text-[13px]">
          <span className="font-semibold text-ink">{stock.symbol}</span>{" "}
          <span className="num text-ink-3">({pct(stock.weight, 0, false)})</span>
        </div>
        {stock.company_name && <div className="truncate text-xs text-ink-3">{stock.company_name}</div>}
        <div className="num text-xs text-ink-2">{priceText(stock)}</div>
        <Screening stock={stock} />
      </div>
      <PickSecondOpinion symbol={stock.symbol} note={basketPickNote(basketName, stock.symbol)} />
    </li>
  );
}

export function BasketStocks({ stocks, basketName }: { stocks: ShariahBasketConstituent[]; basketName: string }) {
  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">Stocks in this basket</h3>
      <ul className="mt-2 space-y-2">
        {stocks.map((stock) => (
          <Stock key={stock.symbol} stock={stock} basketName={basketName} />
        ))}
      </ul>
    </div>
  );
}
