import { useMemo } from "react";
import { useAppMode } from "../../lib/mode";
import { type ShariahStatus, type StatusState, useShariahStatuses } from "../../lib/shariahStatus";

export interface ModeLabels {
  active: boolean;
  state: StatusState;
  /** How many of the stocks are not compliant or questionable. */
  notCompliant: number;
  /** How many have not been screened yet. */
  notScreened: number;
  note: string | null;
  statusOf: (symbol: string) => ShariahStatus | null;
}

/**
 * For paper books: the Shariah result of each stock, to label it with. This never hides, removes or changes anything,
 * because a paper book keeps what its own rule holds and orders.
 */
export function useModeLabels(symbols: readonly string[]): ModeLabels {
  const { isShariah } = useAppMode();
  const { state, statusOf, note } = useShariahStatuses(symbols);
  const counts = useMemo(() => {
    let notCompliant = 0;
    let notScreened = 0;
    for (const symbol of new Set(symbols.map((s) => s.toUpperCase()))) {
      const verdict = statusOf(symbol)?.verdict;
      if (verdict === "NOT_SCREENED") notScreened += 1;
      else if (verdict === "NON_COMPLIANT" || verdict === "QUESTIONABLE") notCompliant += 1;
    }
    return { notCompliant, notScreened };
  }, [symbols, statusOf]);
  return { active: isShariah, state: isShariah ? state : "off", ...counts, note, statusOf };
}
