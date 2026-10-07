import { type ReactNode, useState } from "react";
import { useAppMode } from "../../lib/mode";
import { useShariahStatuses } from "../../lib/shariahStatus";
import { AddAnywayDialog } from "./AddAnywayDialog";

export interface WatchGuard {
  /** Run `proceed` now, or after the person agrees. Removing from a watchlist and Institutional mode never ask. */
  ask: (add: boolean, proceed: () => void) => void;
  /** The question window. Render it once on the page. */
  dialog: ReactNode;
}

/** In Shariah mode, adding a stock that is not confirmed compliant asks first. */
export function useWatchGuard(symbol: string): WatchGuard {
  const { isShariah } = useAppMode();
  const lookup = useShariahStatuses([symbol]);
  const [waiting, setWaiting] = useState<(() => void) | null>(null);
  const status = lookup.statusOf(symbol);
  const ask = (add: boolean, proceed: () => void) => {
    if (!add || !isShariah || status?.verdict === "COMPLIANT") proceed();
    else setWaiting(() => proceed);
  };
  const answer = (add: boolean) => {
    const proceed = waiting;
    setWaiting(null);
    if (add) proceed?.();
  };
  const dialog = (
    <AddAnywayDialog
      symbol={symbol}
      status={status}
      open={waiting !== null}
      onAdd={() => answer(true)}
      onCancel={() => answer(false)}
    />
  );
  return { ask, dialog };
}
