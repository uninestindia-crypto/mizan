import { Pencil, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../ui";
import { date, inr, int, num, plural } from "../../lib/format";
import type { PortfolioRow } from "../../lib/types";
import { useModeFilter } from "../mode/useModeFilter";
import { GainCell, HEAD_ROW, HoldingsFrame, StockName, ValueAndGain } from "./holdingCells";
import { useNarrow } from "./useNarrow";

// The last close is the same for every purchase of a stock and is on the by-stock view, so a narrower table drops it.
const CLOSE = "hidden px-2 xl:table-cell";
const ACTIONS = "flex justify-end gap-1 opacity-60 transition-opacity focus-within:opacity-100 group-hover:opacity-100";

export interface LotActions {
  onEdit: (row: PortfolioRow) => void;
  onRemove: (row: PortfolioRow) => void;
}

/** Every purchase on its own line: the account it sits in, the day it was bought, and what it is worth now. */
export function LotTable(props: { rows: PortfolioRow[]; showAccounts: boolean; toggle: ReactNode } & LotActions) {
  const filter = useModeFilter(props.rows, "portfolio");
  const narrow = useNarrow();
  const subtitle = `${plural(props.rows.length, "lot")}, one for each purchase`;
  return (
    <HoldingsFrame wide subtitle={subtitle} toggle={props.toggle} filter={filter}>
      <table className="w-full text-sm" aria-label="Holdings by lot">
        <LotHead narrow={narrow} showAccounts={props.showAccounts} />
        <tbody className="divide-y divide-line">
          {filter.visible.map((row) => (
            <LotRow
              key={row.id}
              row={row}
              filter={filter}
              narrow={narrow}
              showAccounts={props.showAccounts}
              actions={props}
            />
          ))}
        </tbody>
      </table>
    </HoldingsFrame>
  );
}

function LotHead({ narrow, showAccounts }: { narrow: boolean; showAccounts: boolean }) {
  return (
    <thead>
      <tr className={HEAD_ROW}>
        <th className="px-4 py-2.5 text-left">Stock</th>
        {!narrow && showAccounts && <th className="px-2 py-2.5 text-left">Account</th>}
        {!narrow && <th className="px-2 py-2.5 text-left">Bought</th>}
        {!narrow && <th className="px-2 py-2.5 text-right">Qty</th>}
        {!narrow && <th className="px-2 py-2.5 text-right">Avg price</th>}
        {!narrow && <th className={cx(CLOSE, "py-2.5 text-right")}>Last close</th>}
        <th className="px-2 py-2.5 text-right">{narrow ? "Value and gain" : "Value"}</th>
        {!narrow && <th className="px-2 py-2.5 text-right">Gain</th>}
        {!narrow && (
          <th className="px-3 py-2.5 text-right">
            <span className="sr-only">Actions</span>
          </th>
        )}
      </tr>
    </thead>
  );
}

interface RowProps {
  row: PortfolioRow;
  filter: ReturnType<typeof useModeFilter<PortfolioRow>>;
  narrow: boolean;
  showAccounts: boolean;
  actions: LotActions;
}

/** The small line under a stock's symbol. On a phone it also carries what the other columns would have shown. */
function subLine(props: RowProps): ReactNode {
  const h = props.row;
  if (h.error) return h.error;
  if (!props.narrow) return h.note || undefined;
  const where = props.showAccounts && h.account_name ? ` · ${h.account_name}` : "";
  return (
    <>
      <span className="num block">
        {int(h.quantity)} shares at {num(h.avg_price)}
      </span>
      <span className="block">
        Bought {date(h.buy_date)}
        {where}
      </span>
      {h.note ? <span className="block">{h.note}</span> : null}
    </>
  );
}

function LotRow(props: RowProps) {
  const h = props.row;
  const stock = <StockName symbol={h.symbol} filter={props.filter} sub={subLine(props)} />;
  if (props.narrow) {
    return (
      <tr className="group">
        <td className="px-4 py-3">
          {stock}
          <div className="mt-1.5 -ml-2.5">
            <RowActions row={h} {...props.actions} roomy />
          </div>
        </td>
        <td className="px-4 py-3 text-right align-top">
          <ValueAndGain value={h.value} pnl={h.pnl} pnlPct={h.pnl_pct} />
        </td>
      </tr>
    );
  }
  return (
    <tr className="group">
      <td className="px-4 py-3">{stock}</td>
      {props.showAccounts && <td className="px-2 py-3 text-ink-2">{h.account_name ?? "—"}</td>}
      <td className="whitespace-nowrap px-2 py-3 text-ink-2">{date(h.buy_date)}</td>
      <td className="num px-2 py-3 text-right text-ink-2">{int(h.quantity)}</td>
      <td className="num px-2 py-3 text-right text-ink-2">{num(h.avg_price)}</td>
      <td className={cx(CLOSE, "num py-3 text-right text-ink-2")}>{num(h.close)}</td>
      <td className="num px-2 py-3 text-right font-medium text-ink">{inr(h.value, 0)}</td>
      <td className="px-2 py-3 text-right">
        <GainCell pnl={h.pnl} pnlPct={h.pnl_pct} />
      </td>
      <td className="px-3 py-3 text-right">
        <RowActions row={h} {...props.actions} />
      </td>
    </tr>
  );
}

function RowActions(props: { row: PortfolioRow; roomy?: boolean } & LotActions) {
  const { row, onEdit, onRemove } = props;
  const where = row.account_name ? ` in ${row.account_name}` : "";
  const size = props.roomy ? "p-2.5" : "p-1.5";
  return (
    <div className={props.roomy ? "flex gap-1" : ACTIONS}>
      <button
        type="button"
        aria-label={`Edit ${row.symbol} bought ${date(row.buy_date)}${where}`}
        className={`rounded-lg ${size} text-ink-3 hover:bg-surface-2 hover:text-ink`}
        onClick={() => onEdit(row)}
      >
        <Pencil className="size-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label={`Remove ${row.symbol} bought ${date(row.buy_date)}${where}`}
        className={`rounded-lg ${size} text-ink-3 hover:bg-down-soft hover:text-down`}
        onClick={() => onRemove(row)}
      >
        <Trash2 className="size-4" aria-hidden />
      </button>
    </div>
  );
}
