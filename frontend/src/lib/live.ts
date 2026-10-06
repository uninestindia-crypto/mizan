import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { api } from "./api";
import { num } from "./format";

// Live prices are read-only and optional: every screen keeps working with the end-of-day price when they are off.

export type LiveLabel = "LIVE" | "DELAYED" | "LAST_CLOSE" | "UNAVAILABLE";

export interface LiveQuote {
  last_price: number | null;
  /** Percent points, as the engine sends it: 0.42 means 0.42%. */
  change_pct: number | null;
  label: LiveLabel;
  as_of: string | null;
  source: string | null;
  message: string | null;
}

export interface LiveQuotes {
  connected: boolean;
  message: string | null;
  quotes: Record<string, LiveQuote>;
}

export const POLL_MS = 20_000;
export const MAX_SYMBOLS = 20;
const FRESH_MS = 15_000;

export const NOT_CONNECTED_MESSAGE =
  "Live prices are not connected yet. Open Settings, then Accounts and keys, to add your Upstox key.";

// ----------------------------------------------------------------------------------- pure helpers

const WORDS: Record<LiveLabel, string> = {
  LIVE: "Live",
  DELAYED: "Delayed",
  LAST_CLOSE: "Last close",
  UNAVAILABLE: "Not available",
};

export function knownLabel(label: string | null | undefined): LiveLabel {
  return label && Object.hasOwn(WORDS, label) ? (label as LiveLabel) : "UNAVAILABLE";
}

/** The plain word shown next to every price. A label the app does not know reads as "Not available". */
export function labelWords(label: string | null | undefined): string {
  return WORDS[knownLabel(label)];
}

/** What the engine accepts as a share symbol. One odd entry in a list would otherwise refuse the whole request. */
const VALID_SYMBOL = /^[A-Z0-9&-]{1,15}$/;

/** Upper-case, trim, drop blanks, repeats and anything that is not a share symbol, keep the first-seen order. */
export function normalizeSymbols(symbols: readonly string[]): string[] {
  const seen = new Set<string>();
  for (const raw of symbols) {
    const symbol = raw.trim().toUpperCase();
    if (VALID_SYMBOL.test(symbol)) seen.add(symbol);
  }
  return [...seen];
}

/** The engine takes at most 20 symbols per request. */
export function batchSymbols(symbols: readonly string[], size = MAX_SYMBOLS): string[][] {
  const groups: string[][] = [];
  for (let start = 0; start < symbols.length; start += size) groups.push(symbols.slice(start, start + size));
  return groups;
}

/** Poll only when there is something to ask about and the person can see the tab. */
export function shouldPoll(symbolCount: number, tabVisible: boolean): boolean {
  return symbolCount > 0 && tabVisible;
}

export function pollInterval(symbolCount: number, tabVisible: boolean): number | false {
  return shouldPoll(symbolCount, tabVisible) ? POLL_MS : false;
}

export function mergeQuotes(parts: readonly LiveQuotes[]): LiveQuotes {
  const connected = parts.every((part) => part.connected);
  const message = parts.find((part) => part.message)?.message ?? null;
  const quotes: Record<string, LiveQuote> = Object.assign({}, ...parts.map((part) => part.quotes));
  return { connected, message: connected ? null : message, quotes };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const INDIA_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Kolkata",
  month: "numeric",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  hourCycle: "h23",
});

/** "6 Oct, 10:15 am India time", whatever time zone this computer is set to. */
export function formatIndiaTime(iso: string | null | undefined): string | null {
  const when = iso ? new Date(iso) : null;
  if (!when || Number.isNaN(when.getTime())) return null;
  const parts = INDIA_PARTS.formatToParts(when);
  const part: Record<string, string> = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  const hour = Number(part.hour);
  const clock = `${hour % 12 || 12}:${part.minute} ${hour >= 12 ? "pm" : "am"}`;
  return `${Number(part.day)} ${MONTHS[Number(part.month) - 1] ?? ""}, ${clock} India time`;
}

export function asOfLine(quote: Pick<LiveQuote, "as_of" | "source">): string | null {
  const when = formatIndiaTime(quote.as_of);
  return when ? `As of ${when}, from ${quote.source || "Upstox"}` : null;
}

export interface Change {
  text: string;
  word: "up" | "down" | "unchanged";
}

/** The sign and a word, so colour is never the only signal. `changePct` is in percent points. */
export function describeChange(changePct: number | null | undefined): Change | null {
  if (typeof changePct !== "number" || !Number.isFinite(changePct)) return null;
  const size = num(Math.abs(changePct), 2);
  if (Number(size.replace(/,/g, "")) === 0) return { text: "0.00%", word: "unchanged" };
  return changePct > 0 ? { text: `+${size}%`, word: "up" } : { text: `−${size}%`, word: "down" };
}

/** A quote shows a price only when it has one and is not marked unavailable. */
export function hasPrice(quote: LiveQuote): boolean {
  return quote.label !== "UNAVAILABLE" && typeof quote.last_price === "number" && Number.isFinite(quote.last_price);
}

const UNAVAILABLE: LiveQuote = {
  last_price: null,
  change_pct: null,
  label: "UNAVAILABLE",
  as_of: null,
  source: null,
  message: null,
};

/** The entry for one symbol; a symbol the engine did not answer for is "Not available". */
export function quoteFor(quotes: LiveQuotes | undefined, symbol: string): LiveQuote | null {
  if (!quotes || !quotes.connected) return null;
  const quote = quotes.quotes[symbol.trim().toUpperCase()];
  return quote ? { ...quote, label: knownLabel(quote.label) } : UNAVAILABLE;
}

// ---------------------------------------------------------------------------------------- loading

export async function fetchLiveQuotes(symbols: readonly string[]): Promise<LiveQuotes> {
  const query = (group: string[]) => group.map(encodeURIComponent).join(",");
  const urls = batchSymbols(symbols).map((group) => `/api/v2/live/quotes?symbols=${query(group)}`);
  return mergeQuotes(await Promise.all(urls.map((url) => api<LiveQuotes>(url))));
}

function subscribeVisibility(notify: () => void): () => void {
  document.addEventListener("visibilitychange", notify);
  return () => document.removeEventListener("visibilitychange", notify);
}

/** Is the person looking at this tab? Prices are not fetched in a hidden one. */
export function usePageVisible(): boolean {
  return useSyncExternalStore(
    subscribeVisibility,
    () => document.visibilityState !== "hidden",
    () => true,
  );
}

/**
 * Live prices for a list of stocks in one request (more only past 20). Refreshes every 20 seconds while the tab is
 * visible, and not at all with no symbols. A failure is quiet: the screen simply keeps its end-of-day price.
 */
export function useLiveQuotes(symbols: readonly string[]) {
  const list = normalizeSymbols(symbols);
  const visible = usePageVisible();
  return useQuery({
    queryKey: ["live-quotes", [...list].sort().join(",")],
    queryFn: () => fetchLiveQuotes(list),
    enabled: list.length > 0,
    staleTime: FRESH_MS,
    refetchInterval: pollInterval(list.length, visible),
    refetchOnWindowFocus: true,
    retry: false,
  });
}
