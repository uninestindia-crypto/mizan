import { useMemo } from "react";
import { useAppMode } from "../../lib/mode";
import { type ShariahStatus, type StatusState, useShariahStatuses } from "../../lib/shariahStatus";
import { useShowHidden } from "./hiddenChoice";

/** A list item the filter understands: a symbol, or anything with one. */
export type Filterable = string | { symbol: string };

export const symbolOf = (item: Filterable): string => (typeof item === "string" ? item : item.symbol);

export interface ModeFilter<T> {
  /** True in Shariah mode. In Institutional mode nothing is filtered and nothing is shown. */
  active: boolean;
  state: StatusState;
  /** What to show now: only the compliant stocks by default, everything once the person asks. */
  visible: T[];
  hiddenCount: number;
  /** How many were given, before any were hidden. */
  total: number;
  showHidden: boolean;
  setShowHidden: (value: boolean) => void;
  /** Every stock would be hidden and the person has not asked to see them. */
  nothingLeft: boolean;
  /** A plain sentence when the Shariah results could not be had. */
  note: string | null;
  statusOf: (item: Filterable) => ShariahStatus | null;
}

export interface FilterOptions {
  /** Ask for these stocks' results instead of the listed ones (a steadier list, so a re-sort does not re-ask). */
  statusFrom?: readonly string[];
}

/**
 * In Shariah mode keeps only the compliant stocks, unless the person chose to see the rest. While the results are on
 * their way the whole list is shown, so a list is never empty just because it is being checked. A stock that cannot be
 * confirmed as compliant is hidden, never shown as if it were.
 */
export function useModeFilter<T extends Filterable>(
  items: readonly T[],
  scope: string,
  options: FilterOptions = {},
): ModeFilter<T> {
  const { isShariah } = useAppMode();
  const lookup = useShariahStatuses(options.statusFrom ?? items.map(symbolOf));
  const [showHidden, setShowHidden] = useShowHidden(scope);
  const { statusOf, state, note } = lookup;
  const decided = isShariah && (state === "ready" || state === "unavailable");
  const hidden = useMemo(
    () => (decided ? items.filter((item) => statusOf(symbolOf(item))?.verdict !== "COMPLIANT") : []),
    [decided, items, statusOf],
  );
  const visible = useMemo(() => {
    if (hidden.length === 0 || showHidden) return [...items];
    const out = new Set<T>(hidden);
    return items.filter((item) => !out.has(item));
  }, [hidden, items, showHidden]);
  return {
    active: isShariah,
    state: isShariah ? state : "off",
    visible,
    hiddenCount: hidden.length,
    total: items.length,
    showHidden,
    setShowHidden,
    nothingLeft: decided && items.length > 0 && visible.length === 0,
    note,
    statusOf: (item) => statusOf(symbolOf(item)),
  };
}
