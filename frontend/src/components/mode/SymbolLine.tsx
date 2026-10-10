import type { ShariahStatus } from "../../lib/shariahStatus";
import { ShariahBadge } from "./ShariahBadge";

/** A stock's symbol with its Shariah label beside it. The label is plain text, for rows that are already a link. */
export function SymbolLine({ symbol, status }: { symbol: string; status: ShariahStatus | null }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
      <span className="text-sm font-semibold text-ink">{symbol}</span>
      <ShariahBadge compact status={status} />
    </div>
  );
}
