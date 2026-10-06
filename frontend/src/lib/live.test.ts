import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, type MockInstance, vi } from "vitest";
import { api } from "./api";
import {
  asOfLine,
  batchSymbols,
  describeChange,
  fetchLiveQuotes,
  formatIndiaTime,
  hasPrice,
  knownLabel,
  labelWords,
  type LiveQuote,
  type LiveQuotes,
  mergeQuotes,
  normalizeSymbols,
  pollInterval,
  quoteFor,
  shouldPoll,
  useLiveQuotes,
} from "./live";

vi.mock("./api", async (importOriginal) => {
  const real = await importOriginal<typeof import("./api")>();
  return { ...real, api: vi.fn() };
});

const quote = (over: Partial<LiveQuote> = {}): LiveQuote => ({
  last_price: 3500.5,
  change_pct: 0.42,
  label: "LIVE",
  as_of: "2026-10-06T10:15:00+05:30",
  source: "Upstox",
  message: null,
  ...over,
});

const answer = (quotes: Record<string, LiveQuote>, over: Partial<LiveQuotes> = {}): LiveQuotes => ({
  connected: true,
  message: null,
  quotes,
  ...over,
});

describe("the plain word beside every price", () => {
  it("names each label in words a person reads", () => {
    expect(labelWords("LIVE")).toBe("Live");
    expect(labelWords("DELAYED")).toBe("Delayed");
    expect(labelWords("LAST_CLOSE")).toBe("Last close");
    expect(labelWords("UNAVAILABLE")).toBe("Not available");
  });

  it("reads anything it does not know as not available, never as a price", () => {
    for (const odd of ["", "live", "STALE", null, undefined, "toString", "constructor", "__proto__"]) {
      expect(labelWords(odd)).toBe("Not available");
      expect(knownLabel(odd)).toBe("UNAVAILABLE");
    }
  });
});

describe("choosing which symbols to ask about", () => {
  it("upper-cases, trims, drops blanks and repeats, and keeps the first-seen order", () => {
    expect(normalizeSymbols([" tcs ", "INFY", "tcs", "", "  ", "Infy", "M&M"])).toEqual(["TCS", "INFY", "M&M"]);
  });

  it("leaves out anything the engine would refuse, so one odd entry cannot blank the rest", () => {
    const odd = ["TCS", "BAD SYMBOL", "A".repeat(16), "BAJAJ-AUTO", "x/y", "é"];
    expect(normalizeSymbols(odd)).toEqual(["TCS", "BAJAJ-AUTO"]);
  });

  it("splits a long list into requests of at most 20", () => {
    const many = Array.from({ length: 45 }, (_, i) => `S${i}`);
    expect(batchSymbols(many).map((group) => group.length)).toEqual([20, 20, 5]);
    expect(batchSymbols(many.slice(0, 20))).toHaveLength(1);
    expect(batchSymbols([])).toEqual([]);
  });
});

describe("when to keep asking", () => {
  it("polls only with something to ask about and a visible tab", () => {
    expect(shouldPoll(3, true)).toBe(true);
    expect(shouldPoll(0, true)).toBe(false);
    expect(shouldPoll(3, false)).toBe(false);
    expect(shouldPoll(0, false)).toBe(false);
  });

  it("asks every 20 seconds, or not at all", () => {
    expect(pollInterval(2, true)).toBe(20_000);
    expect(pollInterval(2, false)).toBe(false);
    expect(pollInterval(0, true)).toBe(false);
  });
});

describe("showing the time in India", () => {
  it("writes the time the same way whatever zone the computer is set to", () => {
    expect(formatIndiaTime("2026-10-06T10:15:00+05:30")).toBe("6 Oct, 10:15 am India time");
    expect(formatIndiaTime("2026-10-06T04:45:00Z")).toBe("6 Oct, 10:15 am India time");
    expect(formatIndiaTime("2026-10-06T15:45:00+05:30")).toBe("6 Oct, 3:45 pm India time");
  });

  it("handles midnight, noon and a date that differs from the one in London", () => {
    expect(formatIndiaTime("2026-10-05T18:30:00Z")).toBe("6 Oct, 12:00 am India time");
    expect(formatIndiaTime("2026-10-06T12:00:00+05:30")).toBe("6 Oct, 12:00 pm India time");
    expect(formatIndiaTime("2026-12-31T20:00:00Z")).toBe("1 Jan, 1:30 am India time");
  });

  it("returns nothing for a time it cannot read", () => {
    expect(formatIndiaTime("not a time")).toBeNull();
    expect(formatIndiaTime("")).toBeNull();
    expect(formatIndiaTime(null)).toBeNull();
  });

  it("says where the price came from", () => {
    expect(asOfLine(quote())).toBe("As of 6 Oct, 10:15 am India time, from Upstox");
    expect(asOfLine(quote({ source: null }))).toContain("from Upstox");
    expect(asOfLine(quote({ as_of: null }))).toBeNull();
  });
});

describe("describing a change in words as well as a sign", () => {
  it("gives the sign and a word", () => {
    expect(describeChange(0.42)).toEqual({ text: "+0.42%", word: "up" });
    expect(describeChange(-1.5)).toEqual({ text: "−1.50%", word: "down" });
    expect(describeChange(1234.5)).toEqual({ text: "+1,234.50%", word: "up" });
  });

  it("calls a change too small to show unchanged", () => {
    expect(describeChange(0)).toEqual({ text: "0.00%", word: "unchanged" });
    expect(describeChange(0.004)).toEqual({ text: "0.00%", word: "unchanged" });
    expect(describeChange(-0.004)).toEqual({ text: "0.00%", word: "unchanged" });
  });

  it("shows nothing when there is no number", () => {
    expect(describeChange(null)).toBeNull();
    expect(describeChange(undefined)).toBeNull();
    expect(describeChange(Number.NaN)).toBeNull();
  });
});

describe("reading the answer for one stock", () => {
  it("has a price only when it is not marked unavailable and a number came with it", () => {
    expect(hasPrice(quote())).toBe(true);
    expect(hasPrice(quote({ label: "UNAVAILABLE" }))).toBe(false);
    expect(hasPrice(quote({ last_price: null }))).toBe(false);
    expect(hasPrice(quote({ last_price: Number.NaN }))).toBe(false);
  });

  it("answers nothing when live prices are not connected", () => {
    const off = answer({ TCS: quote() }, { connected: false, message: "Connect it." });
    expect(quoteFor(off, "TCS")).toBeNull();
    expect(quoteFor(undefined, "TCS")).toBeNull();
  });

  it("treats a stock the engine did not answer for as not available", () => {
    expect(quoteFor(answer({}), "TCS")?.label).toBe("UNAVAILABLE");
    expect(quoteFor(answer({ TCS: quote() }), " tcs ")?.label).toBe("LIVE");
    expect(quoteFor(answer({ TCS: quote({ label: "WEIRD" as never }) }), "TCS")?.label).toBe("UNAVAILABLE");
  });

  it("joins the answers of several requests, naming the first reason when one is not connected", () => {
    const joined = mergeQuotes([answer({ A: quote() }), answer({ B: quote() }, { connected: false, message: "Why." })]);
    expect(joined.connected).toBe(false);
    expect(joined.message).toBe("Why.");
    expect(Object.keys(joined.quotes).sort()).toEqual(["A", "B"]);
  });
});

describe("fetching live prices", () => {
  beforeEach(() => {
  vi.mocked(api).mockReset();
});

  it("asks for a whole watchlist in one request", async () => {
    vi.mocked(api).mockResolvedValue(answer({ TCS: quote() }));
    await fetchLiveQuotes(["TCS", "INFY", "M&M"]);
    expect(api).toHaveBeenCalledTimes(1);
    expect(api).toHaveBeenCalledWith("/api/v2/live/quotes?symbols=TCS,INFY,M%26M");
  });

  it("uses a second request only past 20 symbols, and merges the two", async () => {
    vi.mocked(api).mockImplementation(async (url: string) => {
      const names = new URL(url, "http://x").searchParams.get("symbols")?.split(",") ?? [];
      return answer(Object.fromEntries(names.map((name) => [name, quote()])));
    });
    const many = Array.from({ length: 21 }, (_, i) => `S${i}`);
    const result = await fetchLiveQuotes(many);
    expect(api).toHaveBeenCalledTimes(2);
    expect(Object.keys(result.quotes)).toHaveLength(21);
  });
});

describe("the live price hook", () => {
  let visibility: MockInstance<() => DocumentVisibilityState>;
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: new QueryClient() }, children);

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api).mockReset();
    vi.mocked(api).mockResolvedValue(answer({ TCS: quote() }));
    visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  });
  afterEach(() => {
    cleanup();
    visibility.mockRestore();
    vi.useRealTimers();
  });

  it("asks nothing when there are no symbols", async () => {
    renderHook(() => useLiveQuotes([]), { wrapper });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(api).not.toHaveBeenCalled();
  });

  it("asks again every 20 seconds while the tab is visible", async () => {
    renderHook(() => useLiveQuotes(["TCS", "tcs"]), { wrapper });
    await vi.advanceTimersByTimeAsync(100);
    expect(api).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(20_100);
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("stops asking while the tab is hidden and stops for good when the screen is left", async () => {
    const { unmount } = renderHook(() => useLiveQuotes(["TCS"]), { wrapper });
    await vi.advanceTimersByTimeAsync(100);
    visibility.mockReturnValue("hidden");
    act(() => void document.dispatchEvent(new Event("visibilitychange")));
    const before = vi.mocked(api).mock.calls.length;
    await vi.advanceTimersByTimeAsync(65_000);
    expect(api).toHaveBeenCalledTimes(before);
    unmount();
    visibility.mockReturnValue("visible");
    await vi.advanceTimersByTimeAsync(65_000);
    expect(api).toHaveBeenCalledTimes(before);
  });
});
