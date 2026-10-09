import type { ShariahBasket } from "../../lib/types";
import { NOT_COMPUTED_LEAD, historyMessage, notComputedMessage } from "./basketModel";

/** QuantOS has never back-tested a basket, so there is no return or risk figure here. It says so in words. */
export function BasketPerformance({ basket }: { basket: ShariahBasket }) {
  const history = historyMessage(basket);
  return (
    <div className="mt-4 space-y-1.5 rounded-[var(--radius-control)] border border-line bg-surface-2 p-3 text-[13px]">
      <p className="text-ink-2">
        <span className="font-semibold text-ink">{NOT_COMPUTED_LEAD}</span> {notComputedMessage(basket)}
      </p>
      {history && <p className="text-ink-2">{history}</p>}
    </div>
  );
}
