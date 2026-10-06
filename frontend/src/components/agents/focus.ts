import { useEffect } from "react";

// Moving focus on purpose, so a person using the keyboard or a screen reader is never dropped at the top of the page.

/** The element marked with this key (`data-focus-key`), or null. Compared as plain text, so no key needs escaping. */
export function findByFocusKey(key: string): HTMLElement | null {
  const marked = document.querySelectorAll<HTMLElement>("[data-focus-key]");
  return [...marked].find((element) => element.dataset.focusKey === key) ?? null;
}

/** The "My agents" heading: where focus goes when the agent a person just deleted was the one they were on. */
export const MY_AGENTS = "my-agents";

/** The page's own heading, which is where focus goes when the control a person came from is gone. */
export const PAGE_HEADING = "page-heading";

/**
 * Once `ready`, puts focus on the control marked `key` (or the page heading when it is gone) and says so by calling
 * `done`. A `key` of null does nothing.
 */
export function useFocusReturn(key: string | null, ready: boolean, done: () => void): void {
  useEffect(() => {
    if (key === null || !ready) return;
    (findByFocusKey(key) ?? findByFocusKey(PAGE_HEADING))?.focus();
    done();
  }, [key, ready, done]);
}
