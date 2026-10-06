// Second opinions that finished while their window was closed, so the app can say so and offer to reopen them.
// A second opinion takes a minute or two and people go on with something else while it runs.

import { useSyncExternalStore } from "react";

export interface ReadyRun {
  symbol: string;
  outcome: "done" | "failed";
}

const EMPTY: readonly ReadyRun[] = [];
const listeners = new Set<() => void>();
let ready: readonly ReadyRun[] = EMPTY;

function publish(next: readonly ReadyRun[]): void {
  ready = next;
  listeners.forEach((listener) => listener());
}

/** Remember that a run finished while nobody was looking. A newer outcome for the same stock replaces the older. */
export function markReady(symbol: string, outcome: ReadyRun["outcome"]): void {
  publish([...ready.filter((run) => run.symbol !== symbol), { symbol, outcome }]);
}

/** The person has seen it, or has started the stock again. */
export function clearReady(symbol?: string): void {
  const next = symbol === undefined ? EMPTY : ready.filter((run) => run.symbol !== symbol);
  if (next.length !== ready.length) publish(next);
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => void listeners.delete(listener);
};

/** The runs that finished while their window was closed, oldest first. */
export function useReadyRuns(): readonly ReadyRun[] {
  return useSyncExternalStore(subscribe, () => ready, () => EMPTY);
}

/** What to say about a finished run, in plain words. */
export function readyWords(run: ReadyRun): string {
  return run.outcome === "done"
    ? `Second opinion on ${run.symbol} is ready. Open it.`
    : `Second opinion on ${run.symbol} did not finish. Open it to see why.`;
}
