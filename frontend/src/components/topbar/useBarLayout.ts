import { type RefObject, useLayoutEffect, useState } from "react";

export type BarLayout = "inline" | "popover";

/** The bar needs about this much room to show every chip in words beside the search field and the mode switch. */
export const INLINE_FROM = 1620;

/** Wide enough for the chips, or not. A width of 0 means it has not been measured, which counts as wide. */
export function barLayout(width: number): BarLayout {
  return width === 0 || width >= INLINE_FROM ? "inline" : "popover";
}

/**
 * The width of the bar, measured before the first paint and again whenever the window changes. Where measuring is
 * not possible the width stays 0 and the bar shows the chips.
 */
export function useBarLayout(bar: RefObject<HTMLElement | null>): BarLayout {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = bar.current;
    if (!element) return;
    setWidth(element.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver((entries) => setWidth(entries[0]?.contentRect.width ?? 0));
    watch.observe(element);
    return () => watch.disconnect();
  }, [bar]);
  return barLayout(width);
}
