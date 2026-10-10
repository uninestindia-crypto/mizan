import { useCallback, useSyncExternalStore } from "react";

// "Show the hidden stocks" lasts for the session. It is kept in memory and, when the browser allows it, in session
// storage so a reload keeps it. The page works the same if storage is blocked.

const PREFIX = "quantos.mode.showHidden.";
const chosen = new Set<string>();
const listeners = new Set<() => void>();

function stored(scope: string): boolean {
  try {
    return sessionStorage.getItem(PREFIX + scope) === "1";
  } catch {
    return false;
  }
}

function remember(scope: string, value: boolean): void {
  try {
    if (value) sessionStorage.setItem(PREFIX + scope, "1");
    else sessionStorage.removeItem(PREFIX + scope);
  } catch {
    /* kept in memory only */
  }
}

function read(scope: string): boolean {
  return chosen.has(scope) || stored(scope);
}

function write(scope: string, value: boolean): void {
  if (value) chosen.add(scope);
  else chosen.delete(scope);
  remember(scope, value);
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Whether this list shows the stocks that are hidden by default, and how to change that. */
export function useShowHidden(scope: string): [boolean, (value: boolean) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => read(scope),
    () => false,
  );
  const set = useCallback((next: boolean) => write(scope, next), [scope]);
  return [value, set];
}

/** For tests: forget every choice. */
export function forgetHiddenChoices(): void {
  for (const scope of [...chosen]) remember(scope, false);
  chosen.clear();
  try {
    sessionStorage.clear();
  } catch {
    /* nothing stored */
  }
  listeners.forEach((listener) => listener());
}
