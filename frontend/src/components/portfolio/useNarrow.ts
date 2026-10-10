import { useSyncExternalStore } from "react";

// A screen too narrow for the full holdings tables (a phone, or a tablet with the side menu open), where the tables
// show fewer columns so nothing has to be scrolled sideways.

const QUERY = "(max-width: 1023px)";

const media = (): MediaQueryList | null => (typeof window.matchMedia === "function" ? window.matchMedia(QUERY) : null);

function subscribe(listener: () => void): () => void {
  const list = media();
  list?.addEventListener("change", listener);
  return () => list?.removeEventListener("change", listener);
}

export function useNarrow(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => media()?.matches ?? false,
    () => false,
  );
}
